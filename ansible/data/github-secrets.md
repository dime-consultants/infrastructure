# GitHub Secrets

Create these repository secrets before running the deployment workflows.

## Nginx Proxy Auth

These are only for the Nginx login prompt in front of domains with
`basic_auth: true`. They are not the service's own database, broker, Grafana, or
Flower credentials.

| Secret | Used for |
| --- | --- |
| `BASIC_AUTH_USERNAME` | Nginx basic auth username |
| `BASIC_AUTH_PASSWORD` | Nginx basic auth password |

Base config fails if any server domain has `basic_auth: true` and either secret
is missing. The generated `/etc/nginx/.htpasswd` file is used by Flower and any
other proxied domain with `basic_auth: true`. Do not enable Nginx Basic Auth for
RabbitMQ management domains; RabbitMQ uses the `Authorization` header for its
own login flow.

## `ovhserver`

Connection secrets:

| Secret | Used for |
| --- | --- |
| `OVHSERVER_SSH_KEY` | Private SSH key for Ansible |
| `OVHSERVER_SSH_USER` | SSH username |
| `OVHSERVER_PUBLIC_IP` | Server public IP address |

Shared service runtime secrets:

These are the actual credentials consumed by the shared service containers.
`ansible/data/shared-services.yml` stores the GitHub Secret names once, and
every server uses those same shared service credentials.

Shared service secrets:

| Secret | Used for |
| --- | --- |
| `POSTGRES_PROD_USER` | Shared production Postgres user |
| `POSTGRES_PROD_PASSWORD` | Shared production Postgres password |
| `POSTGRES_STAGE_USER` | Shared stage Postgres user |
| `POSTGRES_STAGE_PASSWORD` | Shared stage Postgres password |
| `RABBITMQ_PROD_USER` | Shared production RabbitMQ user |
| `RABBITMQ_PROD_PASSWORD` | Shared production RabbitMQ password |
| `RABBITMQ_STAGE_USER` | Shared stage RabbitMQ user |
| `RABBITMQ_STAGE_PASSWORD` | Shared stage RabbitMQ password |
| `GRAFANA_PROD_USER` | Shared production Grafana user |
| `GRAFANA_PROD_PASSWORD` | Shared production Grafana password |
| `GRAFANA_STAGE_USER` | Shared stage Grafana user |
| `GRAFANA_STAGE_PASSWORD` | Shared stage Grafana password |
| `RESTIC_REPOSITORY` | Restic backup repository URL/path for servers with backups enabled |
| `RESTIC_PASSWORD` | Restic repository encryption password |

Postgres database names are declared inside each app environment as
`postgres_database`. They are not GitHub Secrets. Apps should use that DB name
in their own compose/env, while reusing the shared Postgres user/password for
that environment.

Flower does not need separate broker URL secrets. Its broker URL is derived from
the RabbitMQ username and password for the same environment.

Derived Flower broker URL format:

```text
amqp://<rabbitmq-user>:<rabbitmq-password>@rabbitmq:5672//
```

Portainer does not currently require a GitHub secret. The initial admin account
is configured through the Portainer UI on first login.

Application runtime secrets are still supplied by each app deployment payload
and are written to that app's `.env` during `Deploy App`. Generated dotenv
values are single-quoted so secrets containing `$` are passed to Docker Compose
literally instead of being interpreted as Compose variable references.
