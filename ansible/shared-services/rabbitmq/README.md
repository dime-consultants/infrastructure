# Shared RabbitMQ

Servers subscribe to RabbitMQ by adding it to `shared_services`:

```yaml
shared_services:
  - name: rabbitmq
    environments:
      prod:
        domain: rabbitmq.example.com
        basic_auth: true
      stage: {}
```

App compose files should not define their own RabbitMQ container. Attach the app
to the matching external network and read the broker URL from the deploy-provided
environment variables.

```yaml
version: "3.9"

networks:
  default:
    name: ${SHARED_NETWORK} # prod=shared-prod, stage=shared-stage
    external: true

services:
  worker:
    image: ${IMAGE_TAG}
    command: celery -A app worker -l INFO
    labels:
      observability.app: payments
      observability.component: worker
      observability.environment: ${SHARED_ENV}
    environment:
      CELERY_BROKER_URL: ${CELERY_BROKER_URL}
    restart: always
```

The `observability.*` labels are optional, but they make logs easier to filter
in Grafana. The deploy workflow provides `SHARED_ENV` as `prod` or `stage`.

If an app needs multiple networks, keep the shared network explicit and attach
every service that connects to RabbitMQ:

```yaml
networks:
  app:
  shared:
    name: ${SHARED_NETWORK} # prod=shared-prod, stage=shared-stage
    external: true

services:
  worker:
    image: ${IMAGE_TAG}
    command: celery -A app worker -l INFO
    labels:
      observability.app: payments
      observability.component: worker
      observability.environment: ${SHARED_ENV}
    environment:
      CELERY_BROKER_URL: ${CELERY_BROKER_URL}
    networks:
      - app
      - shared
    restart: always
```

The deploy workflow sets `SHARED_NETWORK` to `shared-prod` or `shared-stage`
and builds `CELERY_BROKER_URL` with host `rabbitmq`, internal port `5672`, and
the app's configured RabbitMQ namespace.

Production AMQP is published on `127.0.0.1:5672`, stage on `127.0.0.1:5673`.
The management UI uses `15672` for production and `15673` for stage on the host.
