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

App deployments do not create or mutate Postgres databases or RabbitMQ vhosts on
every run. The deploy pipeline injects connection settings from the infra
catalog, and shared service containers are managed by base/shared-service
playbooks. Create application databases and RabbitMQ vhosts explicitly when
introducing a new app or changing credentials.

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
