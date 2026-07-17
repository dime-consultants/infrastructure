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
to the matching external network and connect to host `postgres` on port `5432`.

```yaml
services:
  api:
    environment:
      DATABASE_HOST: postgres
      DATABASE_PORT: 5432
    networks:
      - app
      - shared

networks:
  app:
  shared:
    name: shared-prod # use shared-stage for stage deployments
    external: true
```

Production is published on `127.0.0.1:5432`; stage is published on
`127.0.0.1:5433`. Containers should use the internal network port `5432`.
