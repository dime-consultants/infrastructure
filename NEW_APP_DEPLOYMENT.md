# New App Deployment Guide

This guide explains how to add a new application to this infra repository and
deploy it through the existing GitHub Actions and Ansible flow.

The current Dime server is configured for K3s with Traefik owning ports 80 and
443. New web apps should normally use `deployment_type: k3s`, `nginx_managed:
false`, and a Traefik ingress.

## Deployment Flow

There are two separate workflows:

1. `Base Server Configuration`
   - Installs and configures server-level infrastructure.
   - Installs K3s and configures Traefik.
   - Deploys Portainer, Grafana, Argo CD, shared routes, and other base
     resources.
   - Runs from this infra repository.

2. `Deploy Application`
   - Deploys one app version.
   - Creates or verifies app dependencies such as Postgres databases and RabbitMQ
     namespaces when the app config asks for them.
   - Applies the app manifest to K3s or deploys a Compose app.
   - Usually runs after an app repository sends a `repository_dispatch` event to
     this infra repository.

Run base configuration after changing server inventory, K3s, dashboard, shared
service, ingress, firewall, or template settings. Run app deployment after a new
image is built and the app repository sends a deployment payload.

## Files You Usually Edit

| File | Purpose |
| --- | --- |
| `ansible/config/environments/dime.yml` | Main Dime server inventory, apps, domains, ports, K3s settings |
| `ansible/config/shared-services/catalog.yml` | Shared Postgres/RabbitMQ/Grafana/Portainer defaults and secret names |
| `.github/workflows/deploy-app.yml` | Receives app deployment dispatches |
| `.github/workflows/base-configure.yml` | Applies base server setup |
| `ansible/templates/k3s-app-manifest.yaml.j2` | Direct K3s app manifest template |

Most new apps only require an entry under `apps:` in
`ansible/config/environments/dime.yml`.

## Required Inputs

Before adding an app, decide these values:

| Value | Example | Notes |
| --- | --- | --- |
| App name | `billing` | Short infra name, used for resource naming |
| GitHub repo | `dime-consultants/billing-api` | Used to match deployment dispatches |
| Environment | `prod`, `stage`, or both | Must match inventory environment keys |
| Domain | `billing.dimeconsultants.africa` | DNS must point to the server public IP |
| Container port | `8000` | The port the container listens on |
| K3s namespace | `prod` or `stage` | Existing namespaces are declared in inventory |
| Image tag | `ghcr.io/dime-consultants/billing-api:<sha>` | Usually sent by the app repo |
| Postgres database | `billing` | Optional |
| RabbitMQ namespace | `billing` | Optional |
| App secrets | `SECRET_KEY`, API keys, etc. | Sent by app repo in `env_secrets` |

## Add A K3s Web App

Add a new item under `apps:` in `ansible/config/environments/dime.yml`.

Example API app with production and stage environments:

```yaml
apps:
  - name: billing
    repo: dime-consultants/billing-api
    deployment_type: k3s
    aliases:
      - billing-api
      - billing.dimeconsultants.africa
      - stage-billing.dimeconsultants.africa
    port_env: API_PORT
    postgres_database: billing
    rabbitmq_namespace: billing
    secret_names:
      SECRET_KEY: BILLING_SECRET_KEY
    remove_deploy_artifacts:
      - /root/tools/billing/image.tar
    compose_pull: missing
    compose_recreate: auto
    compose_wait_timeout: 120
    environments:
      prod:
        domain: billing.dimeconsultants.africa
        replicas: 2
        nginx_managed: false
        port: 8000
        container_port: 8000
        env:
          DEBUG: "False"
          DJANGO_SETTINGS_MODULE: config.settings
          SYSTEM_BASE_URL: billing.dimeconsultants.africa
        service:
          type: ClusterIP
          port: 80
          targetPort: 8000
        probes:
          path: /api/health
        ingress:
          enabled: true
          className: traefik
          annotations:
            traefik.ingress.kubernetes.io/router.entrypoints: websecure
            traefik.ingress.kubernetes.io/router.tls: "true"
            traefik.ingress.kubernetes.io/router.tls.certresolver: letsencrypt
          tls:
            enabled: true
        k3s:
          namespace: prod

      stage:
        domain: stage-billing.dimeconsultants.africa
        replicas: 1
        nginx_managed: false
        port: 8001
        container_port: 8001
        env:
          DEBUG: "False"
          DJANGO_SETTINGS_MODULE: config.settings
          SYSTEM_BASE_URL: stage-billing.dimeconsultants.africa
        service:
          type: ClusterIP
          port: 80
          targetPort: 8001
        probes:
          path: /api/health
        ingress:
          enabled: true
          className: traefik
          annotations:
            traefik.ingress.kubernetes.io/router.entrypoints: websecure
            traefik.ingress.kubernetes.io/router.tls: "true"
            traefik.ingress.kubernetes.io/router.tls.certresolver: letsencrypt
          tls:
            enabled: true
        k3s:
          namespace: stage
```

Important details:

- `repo` must match the app repository's `GITHUB_REPOSITORY`.
- `aliases` allow deployments to match by app slug or domain.
- `container_port` and `service.targetPort` must match the port inside the
  container.
- `port` is still useful because infra exports it through `port_env`, but K3s
  routing uses the Kubernetes service and ingress.
- `nginx_managed: false` is required for K3s/Traefik routes.
- `ingress.annotations.traefik.ingress.kubernetes.io/router.tls.certresolver`
  tells Traefik to request a Let's Encrypt certificate.
- `postgres_database` and `rabbitmq_namespace` are optional. Add them only when
  the app needs those shared dependencies.

## Add A Frontend App

Example Next.js or Node frontend:

```yaml
apps:
  - name: customer-ui
    repo: dime-consultants/customer-ui
    deployment_type: k3s
    aliases:
      - customer-ui
      - customer.dimeconsultants.africa
      - stage-customer.dimeconsultants.africa
    port_env: PORT
    environments:
      prod:
        domain: customer.dimeconsultants.africa
        replicas: 2
        nginx_managed: false
        port: 3000
        container_port: 3000
        service:
          type: ClusterIP
          port: 80
          targetPort: 3000
        probes:
          path: /
        env:
          HOME: /home/node
          COREPACK_HOME: /home/node/.cache/node/corepack
          NODE_ENV: production
          NEXT_TELEMETRY_DISABLED: "1"
          PORT: "3000"
        tmpVolume:
          enabled: false
        volumeMounts:
          - mountPath: /tmp
            name: tmp
          - mountPath: /var/tmp
            name: var-tmp
          - mountPath: /home/node/.cache
            name: node-cache
          - mountPath: /app/.next/cache
            name: next-cache
        volumes:
          - name: tmp
            emptyDir: {}
          - name: var-tmp
            emptyDir: {}
          - name: node-cache
            emptyDir: {}
          - name: next-cache
            emptyDir: {}
        ingress:
          enabled: true
          className: traefik
          annotations:
            traefik.ingress.kubernetes.io/router.entrypoints: websecure
            traefik.ingress.kubernetes.io/router.tls: "true"
            traefik.ingress.kubernetes.io/router.tls.certresolver: letsencrypt
          tls:
            enabled: true
        k3s:
          namespace: prod
          normalize_deployment_ports: true
```

Use explicit writable `emptyDir` mounts for paths the app writes to at runtime.
Do not make the whole container filesystem writable unless the image truly
requires it.

## Add A Worker App

Worker apps do not need a public service or ingress.

```yaml
apps:
  - name: billing-worker
    repo: dime-consultants/billing-worker
    deployment_type: k3s
    rabbitmq_namespace: billing
    postgres_database: billing
    environments:
      prod:
        replicas: 1
        nginx_managed: false
        container_port: 8000
        command:
          - celery
        args:
          - -A
          - config
          - worker
          - --loglevel=info
        service:
          enabled: false
        probes:
          enabled: false
        k3s:
          namespace: prod
```

## Shared Dependencies

Use these fields when an app needs shared infrastructure:

```yaml
postgres_database: billing
rabbitmq_namespace: billing
```

When these are set, infra injects connection values into the app deployment:

| Dependency | Injected values |
| --- | --- |
| Postgres | `DATABASE_DB`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, `DATABASE_PORT` |
| RabbitMQ | `RABBITMQ_NAMESPACE`, `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`, `CELERY_BROKER_URL` |

The database name comes from `postgres_database`. The username/password come
from GitHub Secrets configured in `ansible/config/shared-services/catalog.yml`.

## GitHub Secrets

Server-level secrets are configured in the infra repository:

```text
INVOICING_SSH_KEY
INVOICING_SSH_USER
INVOICING_PUBLIC_IP
POSTGRES_PROD_USER
POSTGRES_PROD_PASSWORD
POSTGRES_STAGE_USER
POSTGRES_STAGE_PASSWORD
RABBITMQ_PROD_USER
RABBITMQ_PROD_PASSWORD
RABBITMQ_STAGE_USER
RABBITMQ_STAGE_PASSWORD
GRAFANA_PROD_USER
GRAFANA_PROD_PASSWORD
```

App-specific runtime secrets should normally live in the app repository and be
sent in the deployment payload as `env_secrets`.

Example app secrets:

```text
APP_SECRET_KEY
SENTRY_DSN
THIRD_PARTY_API_KEY
```

Do not commit passwords, API keys, private keys, or generated Django secrets to
inventory files.

## App Repository Deployment Payload

The app repository should build/push its image, then dispatch to this infra
repository.

Example app workflow fragment:

```yaml
- name: Build deploy payload
  id: payload
  shell: bash
  env:
    DEPLOY_ENV: stage
    IMAGE_TAG: ghcr.io/dime-consultants/billing-api:${{ github.sha }}
    APP_SECRET_KEY: ${{ secrets.APP_SECRET_KEY }}
    SENTRY_DSN: ${{ secrets.SENTRY_DSN }}
  run: |
    payload="$(python3 << 'PY'
    import json
    import os

    payload = {
        "app_repo": os.environ["GITHUB_REPOSITORY"],
        "env": os.environ["DEPLOY_ENV"],
        "image_tag": os.environ["IMAGE_TAG"],
        "env_vars": {
            "LOG_LEVEL": "info",
            "FEATURE_FLAGS": "default",
        },
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

The infra workflow matches the app using `app_repo`, `env`, and the inventory
entry under `apps:`.

## DNS And TLS

For every public app domain:

1. Create or update the DNS `A` record to point to the server public IP.
2. Add the domain to the app environment config.
3. Enable Traefik ingress with TLS.
4. Run `Base Server Configuration` if Traefik/base config changed.
5. Deploy the app.

Example DNS records:

```text
billing.dimeconsultants.africa        A    <server-public-ip>
stage-billing.dimeconsultants.africa  A    <server-public-ip>
```

A valid K3s ingress should eventually serve a Let's Encrypt certificate. If the
browser shows `TRAEFIK DEFAULT CERT`, check whether the ingress exists and
whether Traefik ACME is configured.

Useful server checks:

```bash
sudo /usr/local/bin/k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get ingress -A
sudo /usr/local/bin/k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get pods -A
sudo /usr/local/bin/k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml -n kube-system logs deploy/traefik
```

Useful external checks:

```bash
dig +short billing.dimeconsultants.africa
curl -I http://billing.dimeconsultants.africa/
openssl s_client -connect billing.dimeconsultants.africa:443 -servername billing.dimeconsultants.africa </dev/null
```

## First Deployment Checklist

1. Add the app entry to `ansible/config/environments/dime.yml`.
2. Confirm the app domain DNS points to the server public IP.
3. Add or verify any app runtime secrets in the app repository.
4. Add or verify infra shared-service secrets if the app uses Postgres or
   RabbitMQ.
5. Push the infra change.
6. Run `Base Server Configuration` if base/K3s/ingress/shared-service config
   changed.
7. Trigger the app repository deployment workflow.
8. Confirm Kubernetes resources:

```bash
sudo /usr/local/bin/k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get deploy,svc,ingress -n stage
sudo /usr/local/bin/k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get pods -n stage
```

9. Confirm the app is reachable:

```bash
curl -I https://stage-billing.dimeconsultants.africa/
```

## Troubleshooting

### No deployment target found

Check that:

- `repo` matches the app repository's `GITHUB_REPOSITORY`.
- The requested `env` exists under the app's `environments:`.
- `aliases` include any alternate app names used by dispatch payloads.

### Browser shows Traefik default certificate

Check that:

- DNS points to the server public IP.
- The ingress exists for the hostname.
- The ingress has the Traefik cert resolver annotation.
- Port 80 reaches Traefik.
- Traefik logs do not show ACME challenge failures.

### App pod is running but domain returns 404

Check that:

- The ingress hostname matches the DNS name exactly.
- `service.targetPort` matches the container port.
- The service selector matches the deployment labels.
- The app namespace in `k3s.namespace` is correct.

### App pod restarts

Check:

```bash
sudo /usr/local/bin/k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml describe pod -n stage -l app.kubernetes.io/name=billing
sudo /usr/local/bin/k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml logs -n stage -l app.kubernetes.io/name=billing --tail=200
```

Common causes:

- Missing app secret.
- Wrong `container_port`.
- Health probe path does not exist.
- App writes to a path that is not mounted writable.
- Image tag does not exist or image pull credentials are missing.

### Postgres or RabbitMQ provisioning fails

Check that:

- `postgres_database` and `rabbitmq_namespace` are correct.
- Shared-service secrets exist in GitHub Secrets.
- The shared Postgres/RabbitMQ services are running.
- The app deployment targets the intended environment only.

