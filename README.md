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
  mlflow-s3-iam-policy.json # IAM policy for the mlflow-s3 user (artifact store)
Containerfile               # Patched MLflow image build
patches/                    # Python patches applied by Containerfile
```

## Artifact store (S3)

Artifact uploads are **proxied through the tracking server** (`defaultArtifactRoot:
mlflow-artifacts:/` + `serve-artifacts`): clients PUT to the MLflow host and the
server relays to S3. Clients need only the Red Hat CA + tracking token — no AWS
credentials and no Amazon CA. The server holds the AWS creds (`mlflow-s3-credentials`
secret) and is the only party that talks to S3.

The server authenticates to S3 as the IAM user `mlflow-s3`. That user needs
read/write on the bucket — apply
[`bootstrap/mlflow-s3-iam-policy.json`](bootstrap/mlflow-s3-iam-policy.json) once
with an account admin:

```bash
aws iam put-user-policy \
  --user-name mlflow-s3 \
  --policy-name mlflow-artifacts-rw \
  --policy-document file://bootstrap/mlflow-s3-iam-policy.json
```

Verify from inside the pod (should print PUT/GET/DELETE OK):

```bash
oc exec -n ambient-code--mlflow deploy/mlflow -c mlflow -- /usr/bin/python3.12 -c '
import boto3, os
b="ambient-code-mlflow-artifacts"; k="mlflow/_probe/t.txt"
s3=boto3.client("s3", region_name=os.environ["AWS_DEFAULT_REGION"])
s3.put_object(Bucket=b, Key=k, Body=b"ok"); print("PUT OK")
print("GET OK", s3.get_object(Bucket=b, Key=k)["Body"].read())
s3.delete_object(Bucket=b, Key=k); print("DELETE OK")'
```

> Network egress from the pod to S3 (us-east-1) works directly — **no proxy
> needed**. Do not set `HTTPS_PROXY` on the MLflow container: the Python
> kubernetes client ignores `NO_PROXY`, which would route kubernetes-auth's
> in-cluster SAR calls through the proxy and break authorization.

> An experiment's `artifact_location` is fixed at creation. Experiments created
> before this proxied-artifacts change keep their `s3://` root and must be
> recreated to pick up `mlflow-artifacts:/`.

## Documentation

- [docs/architecture.md](docs/architecture.md) — authorization flow, RBAC model, pod namespace fallback
- [docs/onboarding.md](docs/onboarding.md) — adding a new agent to MLflow trace collection
