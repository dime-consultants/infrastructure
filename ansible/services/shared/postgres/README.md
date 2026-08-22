# Shared PostgreSQL

Servers subscribe to PostgreSQL by adding it to `shared_services`:

```yaml
shared_services:
  - name: postgres
    environments: [prod, stage]
```

The expanded form is also supported:

```yaml
shared_services:
  - name: postgres
    environments:
      prod: {}
      stage: {}
```

App compose files should not define their own PostgreSQL container. Attach the app
to the matching external network and read the database connection values from
the deploy-provided environment variables.

```yaml
version: "3.9"

x-app-env: &app-env
  DATABASE_DB: ${DATABASE_DB}
  DATABASE_USER: ${DATABASE_USER}
  DATABASE_PASSWORD: ${DATABASE_PASSWORD}
  DATABASE_HOST: ${DATABASE_HOST}
  DATABASE_PORT: ${DATABASE_PORT}

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
      <<: *app-env
    ports:
      - "8000:8000"
    restart: always

  worker:
    image: ${IMAGE_TAG}
    command: celery -A app worker -l INFO
    labels:
      observability.app: payments
      observability.component: worker
      observability.environment: ${SHARED_ENV}
    environment:
      <<: *app-env
    restart: always
```

The `observability.*` labels are optional, but they make logs easier to filter
in Grafana. The deploy workflow provides `SHARED_ENV` as `prod` or `stage`.

For apps with RabbitMQ, also read `CELERY_BROKER_URL` from the deploy-provided
environment. The deploy workflow sets `SHARED_NETWORK` to `shared-prod` or
`shared-stage`, `DATABASE_HOST` to `postgres`, and `DATABASE_PORT` to `5432`.

Production is published on `127.0.0.1:5432`; stage is published on
`127.0.0.1:5433`. Containers should use the internal network port `5432`.
