# Shared Flower

Servers subscribe to Flower by adding it to `shared_services`:

```yaml
shared_services:
  - name: flower
    environments:
      prod:
        domain: flower.example.com
        basic_auth: true
      stage: {}
```

Flower connects to RabbitMQ through `CELERY_BROKER_URL`. Set it with
`shared_service_secrets.flower.<env>.broker_url` or add `broker_url` directly
under the environment.

Production Flower is published on `127.0.0.1:5555`; stage is published on
`127.0.0.1:5556`.
