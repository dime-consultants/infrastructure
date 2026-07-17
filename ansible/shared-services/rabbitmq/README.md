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
to the matching external network and connect to host `rabbitmq` on port `5672`.

```yaml
services:
  worker:
    environment:
      RABBITMQ_HOST: rabbitmq
      RABBITMQ_PORT: 5672
    networks:
      - app
      - shared

networks:
  app:
  shared:
    name: shared-prod # use shared-stage for stage deployments
    external: true
```

Production AMQP is published on `127.0.0.1:5672`, stage on `127.0.0.1:5673`.
The management UI uses `15672` for production and `15673` for stage on the host.
