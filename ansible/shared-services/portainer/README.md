# Shared Portainer

Servers subscribe to Portainer by adding it to `shared_services`:

```yaml
shared_services:
  - name: portainer
    environments:
      prod:
        domain: portainer.example.com
```

Portainer is usually only needed once per server, so subscribe the production
environment only. It runs on the production shared network, `shared-prod`.

Application compose files normally do not need to reference Portainer. If an
admin helper container must call it, attach that container to the matching
external network and use host `portainer` on port `9000`.

```yaml
networks:
  default:
    name: ${SHARED_NETWORK} # prod=shared-prod, stage=shared-stage
    external: true

services:
  admin-helper:
    image: ${IMAGE_TAG}
```

Production HTTP is published on `127.0.0.1:9000`. Stage support exists in the
shared-service catalog, but servers should only subscribe to it if they
intentionally need a separate stage Portainer instance.
