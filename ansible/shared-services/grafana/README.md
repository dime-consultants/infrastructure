# Shared Grafana

Servers subscribe to Grafana by adding it to `shared_services`:

```yaml
shared_services:
  - name: grafana
    environments:
      prod:
        domain: grafana.example.com
      stage: {}
```

Application compose files usually do not need to reference Grafana. Exporters or
sidecars that should be reachable from Grafana can attach to the matching shared
network.

```yaml
services:
  exporter:
    networks:
      - app
      - shared

networks:
  app:
  shared:
    name: shared-prod # use shared-stage for stage deployments
    external: true
```

Production Grafana is published on `127.0.0.1:3000`; stage is published on
`127.0.0.1:3100`.
