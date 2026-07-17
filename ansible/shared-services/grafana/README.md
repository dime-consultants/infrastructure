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

Application compose files usually do not need to reference Grafana. Exporters or
sidecars that should be reachable from Grafana can attach to the matching shared
network.

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
