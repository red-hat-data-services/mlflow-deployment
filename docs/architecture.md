# Architecture

## Authorization flow

![MLflow Authorization Flow](architecture.drawio.png)

### Two auth layers

1. **OAuth Proxy** (sidecar, port 4180) — handles browser login via OpenShift OAuth and forwards the user's Bearer token to MLflow. Single delegate-urls gate:
   - `/` → SAR check: `mlflow.kubeflow.org/experiments get` (any authenticated user via `mlflow-reader-authenticated`)

2. **MLflow kubernetes-auth** (plugin) — validates the Bearer token via Kubernetes SelfSubjectAccessReview, mapping HTTP methods to K8s verbs (`GET→get`, `POST→create`, `DELETE→delete`) against resources in the `mlflow.kubeflow.org` API group. The OTLP `/v1/traces` endpoint is covered by the plugin and maps to `experiments update` (name-scoped by the payload's `experiment_id`).

### Request paths

| Path | Auth layer | Description |
|------|-----------|-------------|
| Browser → UI | OAuth proxy (login) + kubernetes-auth | Full RBAC per resource |
| Any → `/v1/traces` | OAuth proxy (`experiments get`, catch-all) + kubernetes-auth (`experiments update`, name-scoped) | Trace ingestion |
| Any → `/api/2.0/mlflow/*` | OAuth proxy + kubernetes-auth | Full RBAC per resource |

### RBAC resources

**Managed by ArgoCD** (`rbac.yaml`):
- Shared roles: `mlflow-reader`, `mlflow-editor`, `mlflow-admin`, `mlflow-trace-pusher`
- CI service account (`mlflow-ci-traces`) bindings

**Managed by ArgoCD** (`experiments/*.yaml`):
- Per-experiment scoped roles (via `resourceNames`)
- Maintainer RoleBindings

**Applied by cluster-admin** (`bootstrap/it-grant.yaml`):
- `mlflow-rbac-manager` Role + RoleBinding (grants ArgoCD + namespace admins the permissions needed to manage the MLflow RBAC roles)
- `system:auth-delegator` ClusterRoleBinding (OAuth proxy TokenReview)

### Pod namespace fallback

The kubernetes-auth plugin normally requires workspaces to determine the namespace for SAR checks. The patched image includes a fallback that reads the pod's own namespace from `/var/run/secrets/kubernetes.io/serviceaccount/namespace` when workspaces are disabled, allowing single-tenant deployments to work without `--enable-workspaces`.
