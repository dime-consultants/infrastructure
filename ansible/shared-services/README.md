# Shared Services

Shared services are deployed independently from application stacks. Each server
subscribes to the services it needs in `ansible/data/servers/<server>.yml`.

```yaml
shared_services:
  - name: postgres
    environments:
      prod: {}
      stage: {}
```

The service catalog lives in `ansible/data/shared-services.yml`. Each service has
one reusable Docker Compose file under `ansible/shared-services/<service>/` and
is deployed once per environment into `/opt/shared-services/<service>/<env>`.

Public domains for shared service UIs are declared on the subscribed service, not
in `extra_domains`:

```yaml
shared_services:
  - name: rabbitmq
    environments:
      prod:
        domain: rabbitmq.example.com
        basic_auth: true
      stage: {}
```

If the default proxy port from `ansible/data/shared-services.yml` is not right
for a domain, set `proxy_port` beside `domain`.

Applications should not include shared service containers in their own compose
files. Instead, attach application services to the matching external network:

```yaml
services:
  api:
    networks:
      - app
      - shared

networks:
  app:
  shared:
    name: shared-prod # use shared-stage for stage deployments
    external: true
```

Stable internal hostnames:

| Service | Hostname | Internal port |
| --- | --- | --- |
| PostgreSQL | `postgres` | `5432` |
| RabbitMQ | `rabbitmq` | `5672` |
| Portainer | `portainer` | `9000` |
| Grafana | `grafana` | `3000` |
| Flower | `flower` | `5555` |

Set production credentials through GitHub Secrets. Server files should store
shared service subscriptions only; the shared service catalog stores the GitHub
Secret names once:

```yaml
shared_service_catalog:
  postgres:
    environments:
      prod:
        secret_names:
          username: POSTGRES_PROD_USER
          password: POSTGRES_PROD_PASSWORD
```

The base configuration workflow exposes those GitHub Secrets as environment
variables, and Ansible reads them while rendering each shared service `.env`
file. The full checklist is in `ansible/data/github-secrets.md`.

Postgres database names are declared on the app environment so apps do not share
the same database. They reuse the same Postgres user/password for the
environment:

```yaml
apps:
  - name: payments
    repo: stevendegwa/payments
    environments:
      prod:
        domain: payments.example.com
        port: 8014
        postgres_database: payments
        celery_namespace: payments
      stage:
        domain: stage-payments.example.com
        port: 8015
        postgres_database: payments
        celery_namespace: payments
```

The deploy workflow appends `DATABASE_DB` and `CELERY_NAMESPACE` from this app
environment metadata to the app `.env` before rendering Docker Compose.
