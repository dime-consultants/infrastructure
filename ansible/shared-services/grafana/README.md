# Shared Grafana

Servers subscribe to Grafana by adding it to `shared_services`:

```yaml
shared_services:
  - name: grafana
    environments:
      prod:
        domain: grafana.example.com
```

Grafana is usually only needed once per server, so subscribe the production
environment only. It runs on the production shared network, `shared-prod`.

Grafana includes a shared Loki log store and one Promtail collector per server
environment. Promtail discovers Docker containers through the Docker socket and
pushes stdout/stderr logs to Loki, so application compose files should not run
their own Loki or Promtail containers. Loki retains logs for seven days by
default.

Application compose files usually do not need to reference Grafana. Add stable
labels if you want cleaner log selectors in Grafana Explore:

```yaml
labels:
  observability.app: payments
  observability.component: api
  observability.environment: ${SHARED_ENV}
```

Exporters or sidecars that should be reachable from Grafana can attach to the
matching shared network.

```yaml
networks:
  default:
    name: ${SHARED_NETWORK} # prod=shared-prod, stage=shared-stage
    external: true

services:
  exporter:
    image: ${IMAGE_TAG}
```

Production Grafana is published on `127.0.0.1:3000`. Stage support exists in
the shared-service catalog, but servers should only subscribe to it if they
intentionally need a separate stage Grafana instance.

Logs are available from the provisioned `Loki` datasource. Useful selectors:

```logql
{app="payments"}
{compose_project="payments_prod", compose_service="payments"}
{component="celery-worker-high"}
```
