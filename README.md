# MLflow Deployment

MLflow instance deployed on OpenShift via ArgoCD, with Kubernetes-native RBAC for per-experiment access control.

## Instance

| Resource | URL |
|----------|-----|
| Web UI | https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com/ |
| ArgoCD app | `mlflow` in `ambient-code--argocd` |
| Namespace | `ambient-code--mlflow` |

## Architecture

- **MLflow** — OpenDataHub MLflow image with kubernetes-auth plugin
- **PostgreSQL** — metadata store (experiments, runs, traces, metrics)
- **S3** — artifact store (`s3://ambient-code-mlflow-artifacts/mlflow`)
- **OAuth Proxy** — browser authentication via OpenShift OAuth, forwards Bearer tokens to MLflow
- **kubernetes-auth** — per-resource RBAC via Kubernetes SubjectAccessReview

## Repository structure

```
kustomization.yaml          # Root kustomization (ArgoCD source)
rbac.yaml                   # Shared roles, CI SA, admin bindings
experiments/                # Per-experiment RBAC (self-contained kustomization)
  _template.yaml            # Onboarding template
  kustomization.yaml        # Add new experiment files here
  rfe-assessor.yaml         # Example: rfe-assessor experiment
bootstrap/                  # One-time cluster-admin resources
  it-grant.yaml             # RBAC escalation grant + auth-delegator
Containerfile               # Patched MLflow image build
patches/                    # Python patches applied by Containerfile
```

## Documentation

- [docs/architecture.md](docs/architecture.md) — authorization flow, RBAC model, pod namespace fallback
- [docs/onboarding.md](docs/onboarding.md) — adding a new agent to MLflow trace collection
