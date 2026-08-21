# Dime Infrastructure

This repo deploys applications from many repositories to many servers using one
inventory-driven contract.

It supports two deployment runtimes:

- Docker Compose for apps that ship a rendered `docker-compose.yml`.
- K3s plus Helm for apps that should run on Kubernetes.

The infra repo does not need to know every environment variable in every app
ahead of time. Each app repository sends its runtime variables in the deployment
dispatch payload, and this repo adds shared infrastructure values such as
Postgres and RabbitMQ credentials.

## How Deployment Is Resolved

Servers are defined in `ansible/data/servers/*.yml`. A repository dispatch with
`app_repo` and `env` is matched against each server's `apps` list by:

- `repo`
- app `name`
- repo slug
- values in `aliases`
- configured environment `domain`

If the same app exists on several enabled servers, it deploys to all matching
servers unless the dispatch payload includes `server` or `target_server`.

## Server Configuration

Create one file per server under `ansible/data/servers/`.

```yaml
enabled: true

server_name: app-server-1
ssh_secret_name: APP_SERVER_1_SSH_KEY
ssh_user_secret_name: APP_SERVER_1_SSH_USER
public_ip_secret_name: APP_SERVER_1_PUBLIC_IP

k3s:
  enabled: true

shared_services:
  - name: postgres
    environments:
      prod: {}
      stage: {}

  - name: rabbitmq
    environments:
      prod: {}
      stage: {}

apps:
  - name: billing-api
    repo: dime-consultants/billing-api
    aliases:
      - billing
      - billing-api.dimeconsultants.africa
    environments:
      prod:
        domain: billing-api.dimeconsultants.africa
```

K3s is opt-in. By default, Traefik is disabled so host Nginx can keep managing
ports 80 and 443. If Kubernetes ingress should own 80/443, set:

```yaml
k3s:
  enabled: true
  disable: []
```

## Compose App

Use Compose when the app repository sends `docker_compose_b64`.

```yaml
apps:
  - name: billing-api
    repo: dime-consultants/billing-api
    deployment_type: compose
    port_env: API_PORT
    postgres_database: billing
    rabbitmq_namespace: billing
    environments:
      prod:
        domain: billing-api.dimeconsultants.africa
        port: 6100
```

The app compose file should publish the injected port:

```yaml
services:
  api:
    image: "${IMAGE_TAG}"
    env_file:
      - .env
    ports:
      - "${API_PORT}:8000"
```

## Helm App

Use Helm when the app should run on K3s.

```yaml
apps:
  - name: billing-api
    repo: dime-consultants/billing-api
    deployment_type: helm
    image:
      repository: ghcr.io/dime-consultants/billing-api
    postgres_database: billing
    rabbitmq_namespace: billing
    environments:
      prod:
        domain: billing-api.dimeconsultants.africa
        replicas: 3
        container_port: 8000
        service:
          type: NodePort
          port: 80
          targetPort: 8000
          nodePort: 31080
        nginx_managed: true
        port: 31080
        backends:
          - host: 127.0.0.1
            port: 31080
        helm:
          namespace: prod
```

If an image genuinely requires a different user or writable root filesystem,
override the chart security context for that app. Keep the override as narrow
as possible:

```yaml
environments:
  prod:
    podSecurityContext:
      runAsNonRoot: true
      runAsUser: 1001
      runAsGroup: 1001
      fsGroup: 1001
      seccompProfile:
        type: RuntimeDefault
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL
      privileged: false
      readOnlyRootFilesystem: false
      runAsNonRoot: true
```

For a worker with no public HTTP service:

```yaml
apps:
  - name: billing-worker
    repo: dime-consultants/billing-worker
    deployment_type: helm
    image:
      repository: ghcr.io/dime-consultants/billing-worker
    rabbitmq_namespace: billing
    environments:
      prod:
        replicas: 2
        command: ["celery"]
        args: ["-A", "app.worker", "worker", "--loglevel=info"]
        service:
          enabled: false
        probes:
          enabled: false
        nginx_managed: false
        helm:
          namespace: prod
```

## Dynamic Environment Variables

The app repository is responsible for deciding which environment variables it
needs. It sends two maps in the repository dispatch payload:

- `env_vars`: non-sensitive runtime values.
- `env_secrets`: sensitive runtime values.

Infra writes both into the generated `.env` file for Compose deployments. For
Helm deployments, the generated `.env` is converted into Kubernetes Secret data
and loaded by the pod with `envFrom`.

Infra also appends shared values automatically when the app config asks for
them:

- `postgres_database` adds `DATABASE_DB`, `DATABASE_USER`,
  `DATABASE_PASSWORD`, `DATABASE_HOST`, and `DATABASE_PORT`.
- `rabbitmq_namespace` adds `RABBITMQ_NAMESPACE`, `RABBITMQ_DEFAULT_USER`,
  `RABBITMQ_DEFAULT_PASS`, and `CELERY_BROKER_URL`.
- `port` and `port_env` add the published port variable for Compose.

Reserved keys cannot be overridden by app payloads:

- `IMAGE_TAG`
- `SHARED_ENV`
- `SHARED_NETWORK`
- `DATABASE_DB`
- `DATABASE_USER`
- `DATABASE_PASSWORD`
- `DATABASE_HOST`
- `DATABASE_PORT`
- `RABBITMQ_NAMESPACE`
- `RABBITMQ_DEFAULT_USER`
- `RABBITMQ_DEFAULT_PASS`
- `CELERY_BROKER_URL`

## App Repository Dispatch Example

Each app repo can keep environment files in its own repository, parse them in
its CI workflow, and send the final maps to infra.

Example app repo files:

```text
.deploy/prod.env
.deploy/stage.env
```

Example `.deploy/prod.env`:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.production
LOG_LEVEL=info
FEATURE_BILLING=true
```

Example app repository GitHub Actions step:

```yaml
- name: Build deploy payload
  id: payload
  shell: bash
  run: |
    payload="$(python3 << 'PY'
    import json
    import os
    from pathlib import Path

    env_name = os.environ["DEPLOY_ENV"]
    env_vars = {}
    env_file = Path(f".deploy/{env_name}.env")

    if env_file.exists():
        for raw_line in env_file.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip().strip("'").strip('"')

    payload = {
        "app_repo": os.environ["GITHUB_REPOSITORY"],
        "env": env_name,
        "image_tag": os.environ["IMAGE_TAG"],
        "env_vars": env_vars,
        "env_secrets": {
            "SECRET_KEY": os.environ["APP_SECRET_KEY"],
            "SENTRY_DSN": os.environ.get("SENTRY_DSN", ""),
        },
    }

    print(json.dumps(payload))
    PY
    )"
    echo "payload=$payload" >> "$GITHUB_OUTPUT"

- name: Dispatch deploy
  uses: peter-evans/repository-dispatch@v3
  with:
    token: ${{ secrets.INFRA_DISPATCH_TOKEN }}
    repository: dime-consultants/infra
    event-type: deploy-app
    client-payload: ${{ steps.payload.outputs.payload }}
```

If using Compose, include `docker_compose_b64` in the payload:

```bash
docker_compose_b64="$(base64 -w0 docker-compose.yml)"
```

and add:

```json
"docker_compose_b64": "...base64..."
```

## Load Balancing

Host Nginx renders an upstream for each managed app domain. Without explicit
backends it proxies to `127.0.0.1:<port>`.

```yaml
apps:
  - name: billing-api
    repo: dime-consultants/billing-api
    load_balancing:
      method: least_conn
    environments:
      prod:
        domain: billing-api.dimeconsultants.africa
        port: 6100
        backends:
          - host: 127.0.0.1
            port: 6100
            weight: 2
          - host: 10.0.0.12
            port: 6100
```

Supported methods:

- `round_robin`
- `least_conn`
- `ip_hash`

For Helm apps with host Nginx, expose a stable `NodePort` and point the backend
to that node port. For Kubernetes-native ingress, set `nginx_managed: false`
and enable `ingress.enabled`.

## What This Can Accommodate

This setup can deploy many repositories to many servers as long as each app
uses one of the supported runtime contracts:

- Compose app: app repo sends `docker_compose_b64`, `image_tag`, `env_vars`,
  and `env_secrets`.
- Helm app: server inventory sets `deployment_type: helm`, app repo sends
  `image_tag`, `env_vars`, and `env_secrets`.

For deployments that need custom Kubernetes objects beyond Deployment,
Service, Ingress, ConfigMap, Secret, and HPA, add a dedicated Helm chart and set
`helm.chart` to that chart path in the app environment.
