# Shared Portainer

Servers subscribe to Portainer by adding it to `shared_services`:

```yaml
shared_services:
  - name: portainer
    environments:
      prod:
        domain: portainer.example.com
      stage: {}
```

Application compose files normally do not need to reference Portainer. If an
admin helper container must call it, attach that container to the matching
external network and use host `portainer` on port `9000`.

```yaml
networks:
  shared:
    name: shared-prod # use shared-stage for stage deployments
    external: true
```

Production HTTP is published on `127.0.0.1:9000`; stage HTTP is published on
`127.0.0.1:9001`.
