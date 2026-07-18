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
      stage: {}
```

If the default proxy port from `ansible/data/shared-services.yml` is not right
for a domain, set `proxy_port` beside `domain`.

RabbitMQ management domains should use RabbitMQ's own login only. Do not add
Nginx `basic_auth` to RabbitMQ, because both layers need the same HTTP
`Authorization` header.

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
    labels:
      observability.app: payments
      observability.component: api
      observability.environment: ${SHARED_ENV}
    environment:
      DATABASE_DB: ${DATABASE_DB}
      DATABASE_USER: ${DATABASE_USER}
      DATABASE_PASSWORD: ${DATABASE_PASSWORD}
      DATABASE_HOST: ${DATABASE_HOST}
      DATABASE_PORT: ${DATABASE_PORT}
      CELERY_BROKER_URL: ${CELERY_BROKER_URL}
```

The `observability.*` labels are optional, but they make logs easier to filter
in Grafana. The deploy workflow provides `SHARED_ENV` as `prod` or `stage`.

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
    labels:
      observability.app: payments
      observability.component: api
      observability.environment: ${SHARED_ENV}
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
    labels:
      observability.app: payments
      observability.component: worker
      observability.environment: ${SHARED_ENV}
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
    port_env: API_PORT
    postgres_database: payments
    rabbitmq_namespace: payments
    environments:
      prod:
        domain: payments.example.com
        port: 8014
      stage:
        domain: stage-payments.example.com
        port: 8015
        port_env:
          API_PORT: 8015
          METRICS_PORT: 9015
```

`postgres_database`, `rabbitmq_namespace`, and `port_env` can be declared once
on the app when they are the same for every environment. Environment values
override app-level values when they differ. `port` is environment-specific
because production and stage usually listen on different host ports.

By default, app deploy exports `port` as `API_PORT`. Use `port_env` to choose a
different env var name, or use a mapping when the compose file needs multiple
named ports.

For example, this app compose needs both `API_PORT` and `METRICS_PORT`:

```yaml
services:
  api:
    image: ${IMAGE_TAG}
    ports:
      - "${API_PORT}:8000"
      - "${METRICS_PORT}:9100"
```

Declare those names in the matching environment:

```yaml
apps:
  - name: payments
    repo: stevendegwa/payments
    port_env: API_PORT
    environments:
      prod:
        domain: payments.example.com
        port: 8014
        port_env:
          API_PORT: 8014
          METRICS_PORT: 9014
```

For `prod`, app deploy writes:

```env
API_PORT=8014
METRICS_PORT=9014
```

Base setup and the shared-services playbook create every declared
`postgres_database` and RabbitMQ vhost after the shared containers are running.
The app deploy playbook repeats the same provisioning idempotently before
starting app containers, so migrations do not race a missing database.

The deploy workflow appends `DATABASE_DB` when `postgres_database` is present
and RabbitMQ credentials / `CELERY_BROKER_URL` when `rabbitmq_namespace` is
present. RabbitMQ namespaces are provisioned as vhosts on the shared RabbitMQ
instance. Queue names remain owned by the app compose/settings.
