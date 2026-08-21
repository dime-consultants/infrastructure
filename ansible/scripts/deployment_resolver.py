#!/usr/bin/env python3
"""Resolve application deployments from the infra inventory.

The GitHub workflows call this script so app-to-server matching, environment
metadata, and dotenv rendering stay in one place.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

import yaml


RESERVED_APP_ENV_KEYS = {
    "IMAGE_TAG",
    "SHARED_ENV",
    "SHARED_NETWORK",
    "DATABASE_DB",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "RABBITMQ_NAMESPACE",
    "RABBITMQ_DEFAULT_USER",
    "RABBITMQ_DEFAULT_PASS",
    "CELERY_BROKER_URL",
}


def load_yaml(path):
    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_servers(servers_dir):
    servers = []
    for path in sorted(Path(servers_dir).glob("*.yml")):
        data = load_yaml(path)
        if data.get("enabled") is False:
            continue
        data["_source"] = str(path)
        servers.append(data)
    return servers


def normalize_identifier(value):
    if not value:
        return ""
    value = str(value).strip().lower()
    value = value.removeprefix("git@github.com:")
    value = value.removeprefix("https://")
    value = value.removeprefix("http://")
    value = value.removeprefix("www.")
    if value.startswith("github.com/"):
        value = value[len("github.com/") :]
    value = value.removesuffix(".git").strip("/")
    return value


def repo_slug(value):
    normalized = normalize_identifier(value)
    if "/" in normalized:
        return normalized.rsplit("/", 1)[-1]
    return normalized


def app_identifiers(app):
    identifiers = {
        normalize_identifier(app.get("name")),
        normalize_identifier(app.get("repo")),
        repo_slug(app.get("repo")),
    }
    for alias in app.get("aliases", []) or []:
        identifiers.add(normalize_identifier(alias))
    for env_options in (app.get("environments") or {}).values():
        if isinstance(env_options, dict):
            identifiers.add(normalize_identifier(env_options.get("domain")))
    return {item for item in identifiers if item}


def app_matches(app, requested_app):
    requested = normalize_identifier(requested_app)
    requested_slug = repo_slug(requested_app)
    return requested in app_identifiers(app) or requested_slug in app_identifiers(app)


def matching_deployments(servers, requested_app, env_name, target_server=None):
    matches = []
    for server in servers:
        server_name = server.get("server_name")
        if target_server and server_name != target_server:
            continue
        for app in server.get("apps", []) or []:
            if not app_matches(app, requested_app):
                continue
            environments = app.get("environments") or {}
            if env_name not in environments:
                continue
            matches.append({"server": server, "app": app, "env": environments[env_name] or {}})
    return matches


def fail(message):
    raise SystemExit(message)


def secret_value(secret_names, key, label):
    secret_name = secret_names.get(key)
    if not secret_name:
        fail(f"Missing secret_names.{key} for {label}")
    value = os.environ.get(secret_name)
    if not value:
        fail(f"GitHub Secret {secret_name} is required for {label}")
    return value


def subscribed_environment(server, service_name, env_name):
    for service in server.get("shared_services", []) or []:
        if service.get("name") != service_name:
            continue
        environments = service.get("environments") or {}
        if isinstance(environments, dict) and env_name in environments:
            return environments[env_name] or {}
        if isinstance(environments, list) and env_name in environments:
            return {}
    return {}


def service_env_config(shared_service_catalog, service_name, env_name):
    service = shared_service_catalog.get(service_name) or {}
    environments = service.get("environments") or {}
    if env_name not in environments:
        fail(f"Shared service catalog has no {service_name}:{env_name} config")
    return environments[env_name] or {}


def merged_app_env(app, env_options):
    base = {key: value for key, value in app.items() if key != "environments"}
    base.update(env_options)
    return base


def deployment_env_values(server, app, env_options, env_name, shared_service_catalog):
    app_env = merged_app_env(app, env_options)
    deployment_runtime = app_env.get("deployment_type") or app_env.get("runtime") or "compose"
    rabbitmq_namespace = app_env.get("rabbitmq_namespace")
    postgres_database = app_env.get("postgres_database")
    app_port = app_env.get("port")
    port_env = app_env.get("port_env")
    k3s_config = server.get("k3s") or {}
    k3s_backend_host = (
        app_env.get("backend_host")
        or k3s_config.get("external_backend_host")
        or os.environ.get("TARGET_PUBLIC_IP")
    )

    env_values = {}

    if isinstance(port_env, str):
        if not app_port:
            fail(
                f"{server.get('server_name')} {app.get('name')}:{env_name} "
                f"sets port_env={port_env} but has no port"
            )
        env_values[port_env] = str(app_port)
    elif isinstance(port_env, dict):
        for env_key, env_value in port_env.items():
            env_values[str(env_key)] = str(env_value)
    elif port_env is not None:
        fail(
            f"{server.get('server_name')} {app.get('name')}:{env_name} "
            "port_env must be a string or mapping"
        )
    elif app_port:
        env_values["API_PORT"] = str(app_port)

    if postgres_database:
        postgres_subscription = subscribed_environment(server, "postgres", env_name)
        postgres_config = service_env_config(shared_service_catalog, "postgres", env_name)
        postgres_secret_names = (
            postgres_subscription.get("secret_names")
            or postgres_config.get("secret_names")
            or {}
        )
        env_values.update(
            {
                "DATABASE_DB": postgres_database,
                "DATABASE_USER": secret_value(
                    postgres_secret_names, "username", f"postgres:{env_name}"
                ),
                "DATABASE_PASSWORD": secret_value(
                    postgres_secret_names, "password", f"postgres:{env_name}"
                ),
                "DATABASE_HOST": (
                    app_env.get("database_host")
                    or app_env.get("postgres_host")
                    or (
                        k3s_backend_host
                        if deployment_runtime in {"helm", "k3s"} and k3s_backend_host
                        else postgres_config.get("service_host", "postgres")
                    )
                ),
                "DATABASE_PORT": str(
                    app_env.get("database_port")
                    or (
                        postgres_config.get("published_port", 5432)
                        if deployment_runtime in {"helm", "k3s"}
                        else 5432
                    )
                ),
                "SHARED_NETWORK": postgres_config.get("network", f"shared-{env_name}"),
            }
        )

    if rabbitmq_namespace:
        rabbitmq_subscription = subscribed_environment(server, "rabbitmq", env_name)
        rabbitmq_config = service_env_config(shared_service_catalog, "rabbitmq", env_name)
        rabbitmq_secret_names = (
            rabbitmq_subscription.get("secret_names")
            or rabbitmq_config.get("secret_names")
            or {}
        )
        rabbitmq_user = secret_value(
            rabbitmq_secret_names, "username", f"rabbitmq:{env_name}"
        )
        rabbitmq_password = secret_value(
            rabbitmq_secret_names, "password", f"rabbitmq:{env_name}"
        )
        rabbitmq_host = (
            app_env.get("rabbitmq_host")
            or (
                k3s_backend_host
                if deployment_runtime in {"helm", "k3s"} and k3s_backend_host
                else rabbitmq_config.get("service_host", "rabbitmq")
            )
        )
        rabbitmq_port = (
            app_env.get("rabbitmq_port")
            or (
                rabbitmq_config.get("amqp_port", 5672)
                if deployment_runtime in {"helm", "k3s"}
                else 5672
            )
        )
        env_values.update(
            {
                "RABBITMQ_NAMESPACE": rabbitmq_namespace,
                "RABBITMQ_DEFAULT_USER": rabbitmq_user,
                "RABBITMQ_DEFAULT_PASS": rabbitmq_password,
                "CELERY_BROKER_URL": (
                    f"amqp://{quote(rabbitmq_user, safe='')}:"
                    f"{quote(rabbitmq_password, safe='')}@{rabbitmq_host}:{rabbitmq_port}/"
                    f"{quote(rabbitmq_namespace, safe='')}"
                ),
                "SHARED_NETWORK": rabbitmq_config.get(
                    "network", env_values.get("SHARED_NETWORK", f"shared-{env_name}")
                ),
            }
        )

    return env_values


def dotenv_line(key, value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        fail(f"Invalid dotenv key: {key}")
    value = "" if value is None else str(value)
    return f"{key}='{value.replace(chr(39), chr(92) + chr(39))}'\n"


def parse_dotenv_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("\\'", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return bytes(value[1:-1], "utf-8").decode("unicode_escape")
    return value


def parse_dotenv(path):
    values = {}
    with open(path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                fail(f"Invalid dotenv key: {key}")
            values[key] = parse_dotenv_value(value)
    return values


def write_github_output(path, values):
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def cmd_targets(args):
    servers = load_servers(args.servers_dir)
    matches = matching_deployments(servers, args.app, args.env, args.server)
    if args.server and not matches:
        fail(f"No deployment target found for {args.app}:{args.env} on {args.server}")
    if not matches:
        fail(f"No deployment targets found for {args.app}:{args.env}")

    target_servers = []
    for match in matches:
        server_name = match["server"].get("server_name")
        if server_name not in target_servers:
            target_servers.append(server_name)

    servers_csv = ",".join(target_servers)
    print(servers_csv)
    write_github_output(
        args.github_output,
        {
            "servers": servers_csv,
            "servers_json": json.dumps(target_servers),
        },
    )


def cmd_env(args):
    servers = load_servers(args.servers_dir)
    shared_catalog = load_yaml(args.shared_services).get("shared_service_catalog", {})
    matches = matching_deployments(servers, args.app, args.env, args.target_server)
    if len(matches) != 1:
        fail(
            f"Expected one deployment for {args.app}:{args.env} on "
            f"{args.target_server}, found {len(matches)}"
        )

    env_values = deployment_env_values(
        matches[0]["server"], matches[0]["app"], matches[0]["env"], args.env, shared_catalog
    )

    mode = "a" if args.append else "w"
    with open(args.output, mode, encoding="utf-8") as env_file:
        for key, value in env_values.items():
            env_file.write(dotenv_line(key, value))


def cmd_create_env(args):
    env_vars = json.loads(args.env_vars_json or "{}") or {}
    env_secrets = json.loads(args.env_secrets_json or "{}") or {}
    with open(args.output, "w", encoding="utf-8") as env_file:
        env_file.write(dotenv_line("IMAGE_TAG", args.image_tag))
        env_file.write(dotenv_line("SHARED_ENV", args.env))
        for key, value in env_vars.items():
            if key not in RESERVED_APP_ENV_KEYS:
                env_file.write(dotenv_line(key, value))
        for key, value in env_secrets.items():
            if key not in RESERVED_APP_ENV_KEYS:
                env_file.write(dotenv_line(key, value))


def cmd_dotenv_json(args):
    print(json.dumps(parse_dotenv(args.input)))


def build_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    targets = subparsers.add_parser("targets")
    targets.add_argument("--app", required=True)
    targets.add_argument("--env", required=True)
    targets.add_argument("--server")
    targets.add_argument("--servers-dir", default="ansible/data/servers")
    targets.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    targets.set_defaults(func=cmd_targets)

    create_env = subparsers.add_parser("create-env")
    create_env.add_argument("--image-tag", required=True)
    create_env.add_argument("--env", required=True)
    create_env.add_argument("--env-vars-json", default="{}")
    create_env.add_argument("--env-secrets-json", default="{}")
    create_env.add_argument("--output", required=True)
    create_env.set_defaults(func=cmd_create_env)

    dotenv_json = subparsers.add_parser("dotenv-json")
    dotenv_json.add_argument("--input", required=True)
    dotenv_json.set_defaults(func=cmd_dotenv_json)

    env = subparsers.add_parser("env")
    env.add_argument("--app", required=True)
    env.add_argument("--env", required=True)
    env.add_argument("--target-server", required=True)
    env.add_argument("--servers-dir", default="ansible/data/servers")
    env.add_argument("--shared-services", default="ansible/data/shared-services.yml")
    env.add_argument("--output", required=True)
    env.add_argument("--append", action="store_true")
    env.set_defaults(func=cmd_env)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
