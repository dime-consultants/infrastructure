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

Base config reconciles these subscriptions. If a shared service environment is
removed from a server file, the next base-config run stops that Compose project
without deleting its Docker volume. Services that remain subscribed are applied
again, so Docker Compose may recreate them if their compose file, image, or env
changed.

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
files. Instead, make the compose default network point at the matching external
shared network:

```yaml
networks:
  default:
    name: ${SHARED_NETWORK} # prod=shared-prod, stage=shared-stage
    external: true

services:
  api:
    image: ${IMAGE_TAG}
    environment:
      DATABASE_DB: ${DATABASE_DB}
      DATABASE_USER: ${DATABASE_USER}
      DATABASE_PASSWORD: ${DATABASE_PASSWORD}
      DATABASE_HOST: ${DATABASE_HOST}
      DATABASE_PORT: ${DATABASE_PORT}
      CELERY_BROKER_URL: ${CELERY_BROKER_URL}
```

If an app needs multiple networks, keep the shared network explicit and attach
every service that connects to PostgreSQL, RabbitMQ, or another shared service:

```yaml
networks:
  app:
  shared:
    name: ${SHARED_NETWORK} # prod=shared-prod, stage=shared-stage
    external: true

services:
  api:
    image: ${IMAGE_TAG}
    environment:
      DATABASE_DB: ${DATABASE_DB}
      DATABASE_USER: ${DATABASE_USER}
      DATABASE_PASSWORD: ${DATABASE_PASSWORD}
      DATABASE_HOST: ${DATABASE_HOST}
      DATABASE_PORT: ${DATABASE_PORT}
      CELERY_BROKER_URL: ${CELERY_BROKER_URL}
    networks:
      - app
      - shared

  worker:
    image: ${IMAGE_TAG}
    environment:
      DATABASE_DB: ${DATABASE_DB}
      DATABASE_USER: ${DATABASE_USER}
      DATABASE_PASSWORD: ${DATABASE_PASSWORD}
      DATABASE_HOST: ${DATABASE_HOST}
      DATABASE_PORT: ${DATABASE_PORT}
      CELERY_BROKER_URL: ${CELERY_BROKER_URL}
    networks:
      - shared
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
        rabbitmq_namespace: payments
      stage:
        domain: stage-payments.example.com
        port: 8015
        postgres_database: payments
        rabbitmq_namespace: payments
```

Base setup and the shared-services playbook create every declared
`postgres_database` and RabbitMQ vhost after the shared containers are running.
The app deploy playbook repeats the same provisioning idempotently before
starting app containers, so migrations do not race a missing database.

The deploy workflow appends `DATABASE_DB` when `postgres_database` is present
and RabbitMQ credentials / `CELERY_BROKER_URL` when `rabbitmq_namespace` is
present. RabbitMQ namespaces are provisioned as vhosts on the shared RabbitMQ
instance. Queue names remain owned by the app compose/settings.
