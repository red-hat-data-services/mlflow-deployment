# Bootstrap (one-time, cluster-admin)

`it-grant.yaml` contains resources the ambient-code tenant cannot create itself
and must be applied **once** by a cluster-admin:

```bash
oc apply -f bootstrap/it-grant.yaml
```

## What it does

| Resource | Why it can't be tenant-managed |
|----------|-------------------------------|
| `Role/mlflow-rbac-manager` + binding | Grants the ArgoCD tenant account `escalate`/`bind` on roles so it can manage the MLflow RBAC roles (`rbac.yaml`) via GitOps. Without it, ArgoCD hits privilege-escalation prevention. |
| `ClusterRoleBinding/mlflow-oauth-proxy-auth-delegator` | The OAuth proxy needs `system:auth-delegator` for TokenReview. ClusterRoleBindings are cluster-scoped and not permitted for the tenant. |

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
