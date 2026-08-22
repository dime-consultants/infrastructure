#!/usr/bin/env python3
import os
import json
import yaml

BASE_DIR = os.path.dirname(__file__)
servers_dir = os.path.abspath(os.path.join(BASE_DIR, "../config/environments"))

inventory = {"_meta": {"hostvars": {}}, "all": {"hosts": [], "children": []}}

for filename in os.listdir(servers_dir):
    if filename.endswith(".yml"):
        path = os.path.join(servers_dir, filename)
        with open(path) as f:
            data = yaml.safe_load(f)

        if data.get("enabled") is False:
            continue

        name = data["server_name"]
        aliases = data.get("server_aliases") or []
        target_server = os.environ.get("TARGET_SERVER")
        public_ip = data.get("public_ip")
        ssh_user = data.get("ssh_user")

        if target_server in [name, *aliases]:
            public_ip = os.environ.get("TARGET_PUBLIC_IP", public_ip)
            ssh_user = os.environ.get("TARGET_SSH_USER", ssh_user)

        if not public_ip:
            public_ip_secret = data.get("public_ip_secret_name")
            public_ip = (
                os.environ.get(public_ip_secret)
                if public_ip_secret
                else None
            )

        if not ssh_user:
            ssh_user_secret = data.get("ssh_user_secret_name")
            ssh_user = (
                os.environ.get(ssh_user_secret)
                if ssh_user_secret
                else None
            )

        if not public_ip:
            public_ip = name

        if not ssh_user:
            ssh_user = "ubuntu"

        inventory["all"]["hosts"].append(name)
        inventory["_meta"]["hostvars"][name] = {
            "ansible_host": public_ip,
            "ansible_user": ssh_user,
            **{
                k: v
                for k, v in data.items()
                if k not in (
                    "environment_name",
                    "server_name",
                    "server_aliases",
                    "ssh_user",
                    "ssh_user_secret_name",
                    "public_ip",
                    "public_ip_secret_name",
                )
            }
        }

print(json.dumps(inventory))
