# Ansible Layout

This directory is organized by responsibility:

- `config/environments/`: one file per deployable environment. `dime.yml` is the canonical environment and contains the `prod` and `stage` Kubernetes namespace definitions.
- `config/shared-services/`: shared service catalog and defaults.
- `config/global/`: global Ansible defaults and operator-facing secret documentation.
- `charts/`: Helm charts used by Kubernetes deployments.
- `services/shared/`: Docker Compose definitions for shared host services such as Postgres and RabbitMQ.
- `playbooks/`: entry points called by CI or operators.
- `tasks/apps/`: application deployment and app dependency preflight tasks.
- `tasks/kubernetes/`: K3s, Traefik, cert-manager, Argo CD, Grafana, Portainer, and ingress tasks.
- `tasks/shared-services/`: shared-service deployment, cleanup, and provisioning tasks.
- `tasks/docker/`: Docker maintenance and migration cleanup tasks.
- `tasks/nginx/`: legacy host Nginx generation tasks.
- `tasks/security/`: OS security baseline tasks.
- `tasks/backups/`: backup service/timer tasks.
- `templates/`: Jinja templates rendered by playbooks and tasks.
- `inventory/`: dynamic inventory implementation.
- `scripts/`: CI/helper scripts such as deployment resolution.
