# Bootstrap (one-time, cluster-admin)

`it-grant.yaml` contains resources the ambient-code tenant cannot create itself
and must be applied **once** by a cluster-admin:

```bash
oc apply -f bootstrap/it-grant.yaml
```

## What it does

| Resource | Why it can't be tenant-managed |
|----------|-------------------------------|
| `Role/mlflow-rbac-manager` + binding | Grants the ArgoCD tenant account the exact MLflow permissions the managed roles delegate, so it can create them via GitOps (`rbac.yaml`) without hitting privilege-escalation prevention. Uses scoped permissions rather than the broad `escalate` verb. |
| `ClusterRoleBinding/mlflow-oauth-proxy-auth-delegator` | The OAuth proxy needs `system:auth-delegator` for TokenReview. TokenReview is cluster-scoped (no namespaced equivalent), so this can't be tenant-managed. |

### Why scoped permissions instead of `escalate`

`escalate` on roles is a blank check — it would let the ArgoCD account create a
Role granting *any* permission (secrets, etc.) and bind it. Instead, we grant the
account exactly the permissions the MLflow roles delegate, so it can only ever
delegate those. Since `mlflow.kubeflow.org` has no CRDs, these permissions are
virtual (used only by MLflow's SAR checks) and grant nothing actionable.

## After applying

ArgoCD reconciles `rbac.yaml` (ServiceAccount + reader/editor/admin/trace-pusher
roles + CI bindings) automatically on the next sync — no further manual steps.

## Verify

```bash
# ArgoCD can now create the roles
oc get roles -n ambient-code--mlflow | grep mlflow
# OAuth proxy can do token review
oc get clusterrolebinding mlflow-oauth-proxy-auth-delegator
```
