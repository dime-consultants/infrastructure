# Infrastructure Operations

## Deployment Resolution

Application deployments are resolved by `ansible/scripts/deployment_resolver.py`.
GitHub Actions uses the same resolver for target selection and environment
metadata, so app matching behavior is not duplicated in workflow YAML.

An app can be matched by:

- `repo`, such as `dime-consultants/ai_invoicing`
- repository URL, such as `https://github.com/dime-consultants/ai_invoicing.git`
- app `name`
- repo slug, such as `ai_invoicing`
- any value listed in `aliases`
- any configured environment `domain`

If a repository dispatch payload includes `target_server` or `server`, the
deployment is restricted to that server. Without a server override, the app is
deployed to every enabled server that declares that app and environment.

## Adding A Server

Create `ansible/data/servers/<server>.yml` with:

- `server_name`
- SSH, user, and public IP secret names
- `shared_services`
- `apps`
- optional `extra_domains`
- optional `backups`

The inventory and GitHub Actions matrix discover enabled server files
automatically.

GitHub Actions runs Ansible from Python 3.12. Remote hosts use Ansible's
interpreter discovery by default. Only set `ansible_python_interpreter`, for
example `/usr/bin/python3.12`, when that interpreter is already installed on the
target host.

## Adding An App

Add the app under the target server's `apps` list:

```yaml
apps:
  - name: billing-api
    repo: dime-consultants/billing-api
    aliases:
      - billing
      - billing-api.dimeconsultants.africa
    port_env: API_PORT
    postgres_database: billing
    environments:
      prod:
        domain: billing-api.dimeconsultants.africa
        port: 6100
      stage:
        domain: stage-billing-api.dimeconsultants.africa
        port: 6101
```

The app compose should publish the host port through the injected variable, for
example:

```yaml
ports:
  - "${API_PORT}:8000"
```

Stale deployment artifacts can be removed before Compose recreates the stack:

```yaml
remove_deploy_artifacts:
  - /root/tools/billing-api/image.tar
```

Server-specific Docker maintenance can also cap journal disk usage during base
setup and app deployments:

```yaml
docker_setup_enabled: false
shared_services_deploy_enabled: false
docker_maintenance:
  cleanup_min_disk_use_percent: 88
  journal_vacuum_size: 300M
```

Use `docker_setup_enabled: false` for hosts where Docker is already installed
and base configuration should skip Docker repository, package, service, and
maintenance tasks. Use `shared_services_deploy_enabled: false` when shared
services are already managed separately and base configuration should skip
shared-service deploy and cleanup tasks.

App deployments run heavy Docker maintenance only when disk usage reaches
`cleanup_min_disk_use_percent`, and post-deploy maintenance is off by default.
Per-app Compose behavior can be tuned when the image tags are immutable:

```yaml
compose_pull: missing
compose_recreate: auto
compose_wait_timeout: 120
```

App deployments do not create or mutate Postgres databases or RabbitMQ vhosts on
every run. The deploy pipeline injects connection settings from the infra
catalog, and shared service containers are managed by base/shared-service
playbooks. Create application databases and RabbitMQ vhosts explicitly when
introducing a new app or changing credentials.

## Load Balancing

Host-level Nginx can load balance a domain across multiple backends. If no
backends are configured, the existing single `127.0.0.1:<port>` proxy is used.

```yaml
apps:
  - name: billing-api
    repo: dime-consultants/billing-api
    load_balancing:
      method: least_conn
    environments:
      prod:
        domain: billing-api.dimeconsultants.africa
        port: 6100
        backends:
          - host: 127.0.0.1
            port: 6100
            weight: 2
          - host: 10.0.0.12
            port: 6100
```

Supported methods are `round_robin`, `least_conn`, and `ip_hash`.

## K3s And Helm

K3s installation is opt-in per server:

```yaml
k3s:
  enabled: true
  channel: stable
  disable: []
```

When `k3s.enabled: true`, K3s/Traefik owns ports 80 and 443 by default and host
Nginx is stopped/disabled by base setup. If a K3s server must keep host Nginx,
set `nginx_enabled: true` and disable Traefik.

Apps can deploy through the reusable Helm chart at
`ansible/helm/dime-app`:

```yaml
apps:
  - name: billing-api
    repo: dime-consultants/billing-api
    deployment_type: helm
    image:
      repository: ghcr.io/dime-consultants/billing-api
    environments:
      prod:
        namespace: prod
        domain: billing-api.dimeconsultants.africa
        replicas: 3
        container_port: 8000
        service:
          type: ClusterIP
          port: 80
          targetPort: 8000
        nginx_managed: false
        ingress:
          enabled: true
          className: traefik
        helm:
          namespace: prod
```

K3s includes Traefik by default when it is not listed under `k3s.disable`.
Traefik handles ingress routing and Kubernetes Services load balance across
healthy pods.
Application secrets should be provided through GitHub Secrets or inventory
secret references and rendered into Kubernetes Secrets by Helm; do not commit
secret values.

## Backups

Backups are opt-in per server:

```yaml
backups:
  enabled: true
  schedule: "*-*-* 02:30:00"
  retention:
    keep_daily: 7
    keep_weekly: 4
    keep_monthly: 6
  paths:
    - /opt
    - /etc/nginx/sites-available
    - /etc/nginx/sites-enabled
    - /etc/letsencrypt
```

Required GitHub Secrets:

- `RESTIC_REPOSITORY`
- `RESTIC_PASSWORD`

The base setup playbook installs Restic, renders `/usr/local/sbin/dime-restic-backup`,
and enables `dime-restic-backup.timer`. The script dumps shared Postgres
databases with `pg_dumpall`, backs up configured paths, runs retention cleanup,
and checks the repository.

Useful server commands:

```bash
systemctl list-timers dime-restic-backup.timer
sudo systemctl start dime-restic-backup.service
sudo journalctl -u dime-restic-backup.service -n 100 --no-pager
```

## Monitoring

The `grafana` shared service includes:

- Grafana for dashboards
- Loki for logs
- Promtail for Docker log collection
- Prometheus for metrics
- Node Exporter for host metrics
- cAdvisor for container metrics

Expose Grafana by adding a `domain` under the server's `grafana` shared service
subscription.

## Security

Base setup installs and enables:

- UFW with deny-by-default ingress
- Fail2Ban for SSH and common Nginx abuse patterns
- unattended security upgrades

The `Security Scan` GitHub workflow runs Trivy against this repo for
vulnerabilities, secrets, and infrastructure misconfiguration.
