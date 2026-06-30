# Onboarding a new agent

This guide covers setting up **access** for a new agent — its experiment and a
scoped RBAC role. Once onboarded, see [usage.md](usage.md) for how to configure a
client and push traces.

## Overview

Onboarding gives an agent:
- An **MLflow experiment** where its traces are stored
- A **scoped RBAC role** granting the agent's maintainers access to that experiment
- Optionally, **scoped access to a dataset** (see [Managing datasets](#managing-datasets))

## Steps

### 1. Open a PR in this repo

Copy `experiments/_template.yaml` to `experiments/<experiment-name>.yaml`:

```yaml
# <experiment-name> experiment
# Agent: <link to agent repo>
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: mlflow-experiment-<experiment-name>
rules:
  - apiGroups: ["mlflow.kubeflow.org"]
    resources: ["experiments"]
    resourceNames: ["<experiment-name>"]
    verbs: ["get", "list", "update", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: mlflow-experiment-<experiment-name>
subjects:
  - kind: User
    name: <user>
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: mlflow-experiment-<experiment-name>
  apiGroup: rbac.authorization.k8s.io
```

> The RoleBinding `name` is each user's **OpenShift username** (what `oc whoami`
> returns), **not** their email. This cluster authenticates users by bare
> username, so an email subject matches no one — reads still work (via the
> shared reader) but trace pushes are denied.

Add the file to `experiments/kustomization.yaml`:

```yaml
resources:
  - rfe-assessor.yaml
  - <experiment-name>.yaml    # add this line
```

### 2. MLflow admin creates the experiment and issues a token

After the PR is merged, an MLflow admin:

- creates the experiment in the [MLflow UI](https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com/)
- provides the agent team with the `mlflow-ci-traces` service-account token used to push traces from CI (for interactive use, people authenticate as themselves — see [usage.md](usage.md))

To grant access to datasets too, see [Managing datasets](#managing-datasets) — they are onboarded with their own role.

Once the experiment exists, see [usage.md](usage.md) to configure a client
(GitLab CI, agent-eval-harness, or a generic MLflow client) and start pushing
traces.

## What maintainers can do

With the per-experiment role, maintainers can:

| Action | Allowed |
|--------|---------|
| View experiment and traces | Yes |
| View scorers and assessments | Yes |
| Create/invoke scorers | Yes |
| Delete traces | Yes |
| Delete the experiment | Yes |
| Create new experiments | No (admin only) |
| View other experiments | No |
| Read datasets | Yes (all — every authenticated user) |
| Maintain a named dataset (records, tags, delete) | Yes, if granted (see below) |
| Create datasets | No (admin only) |

## Managing datasets

Datasets are first-class RBAC resources (`mlflow.kubeflow.org/datasets`), governed like experiments — but **not owned by an experiment** (a dataset can be linked to several). So they get their **own** scoped role and binding, separate from any `mlflow-experiment-<experiment-name>` role, onboarded with [`experiments/_dataset-template.yaml`](../experiments/_dataset-template.yaml).

- **Read** — every authenticated user can already read all datasets via the shared `mlflow-reader` role. No grant needed.
- **Create** — admin-only, like experiments. The `create` verb cannot be name-scoped, so it is never granted to maintainers; an MLflow admin creates the dataset.
- **Maintain** — copy `experiments/_dataset-template.yaml` to `experiments/<dataset-name>-dataset.yaml`, set the name and user(s), and add it to `experiments/kustomization.yaml`. It grants name-scoped management of that one dataset:

  ```yaml
  apiVersion: rbac.authorization.k8s.io/v1
  kind: Role
  metadata:
    name: mlflow-dataset-<dataset-name>
  rules:
    - apiGroups: ["mlflow.kubeflow.org"]
      resources: ["datasets"]
      resourceNames: ["<dataset-name>"]
      verbs: ["get", "list", "update", "delete"]
  ---
  apiVersion: rbac.authorization.k8s.io/v1
  kind: RoleBinding
  metadata:
    name: mlflow-dataset-<dataset-name>
  subjects:
    - kind: User
      name: <user>
      apiGroup: rbac.authorization.k8s.io
  roleRef:
    kind: Role
    name: mlflow-dataset-<dataset-name>
    apiGroup: rbac.authorization.k8s.io
  ```

Because creation is admin-only, dataset tooling must target a **pre-existing** dataset and upsert records into it (an `update`) rather than calling create — the same way trace/eval tooling pushes to a pre-created experiment. (The agent-eval-harness `sync_dataset` does create-then-upsert, so point it at an admin-created dataset and it will only upsert.)
