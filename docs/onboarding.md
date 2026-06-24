# Onboarding a new agent

This guide walks through adding a new agent to MLflow trace collection.

## Overview

Each agent gets:
- An **MLflow experiment** where its traces are stored
- A **scoped RBAC role** granting the agent maintainers access to their experiment
- **CI variables** so the agent's pipeline pushes traces after each run

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
  name: mlflow-<experiment-name>
rules:
  - apiGroups: ["mlflow.kubeflow.org"]
    resources: ["experiments"]
    resourceNames: ["<experiment-name>"]
    verbs: ["get", "list", "update", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: mlflow-<experiment-name>-admin
subjects:
  - kind: User
    name: <user>@redhat.com
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: mlflow-<experiment-name>
  apiGroup: rbac.authorization.k8s.io
```

Add the file to `experiments/kustomization.yaml`:

```yaml
resources:
  - rfe-assessor.yaml
  - <experiment-name>.yaml    # add this line
```

### 2. MLflow admin creates the experiment

After the PR is merged, an MLflow admin creates the experiment in the [MLflow UI](https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com/).

### 3. Set CI variables

Set these variables on your GitLab project (Settings → CI/CD → Variables):

| Variable | Value | Masked |
|----------|-------|--------|
| `MLFLOW_TRACKING_URI` | `https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com` | No |
| `MLFLOW_TRACKING_TOKEN` | *(provided by the MLflow admin)* | Yes |
| `MLFLOW_EXPERIMENT_NAME` | Your experiment name | No |

### 4. Add trace push to your CI pipeline

Add a separate `trace-push` job to your `.gitlab-ci.yml` that runs after the agent job. The job downloads the `claude-otel.jsonl` artifact and pushes traces to MLflow:

```yaml
trace-push:
  stage: observe    # add 'observe' to your stages list
  tags:
    - aipcc-small-x86_64
  image: registry.access.redhat.com/ubi9/python-312:latest
  needs:
    - job: <your-agent-job>
      artifacts: true
  rules:
    - if: $MLFLOW_TRACKING_URI && $MLFLOW_EXPERIMENT_NAME
  allow_failure: true
  retry:
    max: 2
    when: script_failure
  before_script:
    - curl -sL https://certs.corp.redhat.com/certs/2022-IT-Root-CA.pem -o /tmp/RH-IT-Root-CA.pem
    - export REQUESTS_CA_BUNDLE=/tmp/RH-IT-Root-CA.pem
  script:
    - pip install -q agentic-ci
    - agentic-ci mlflow-push claude-otel.jsonl
        --endpoint "$MLFLOW_TRACKING_URI"
        --experiment "$MLFLOW_EXPERIMENT_NAME"
        --token "$MLFLOW_TRACKING_TOKEN"
```

The `before_script` installs the Red Hat IT Root CA so that Python's `requests` library trusts the MLflow Route's TLS certificate. The `ubi9/python-312` image does not include internal CAs by default.

The job:
- Only runs when `MLFLOW_TRACKING_URI` and `MLFLOW_EXPERIMENT_NAME` are set
- Retries automatically up to 2 times on failure
- Never blocks the pipeline (`allow_failure: true`)
- Can be retried manually from the GitLab UI at any time

See `rfe-assessor/.gitlab-ci.yml` for a working example.

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

## Trace export requirements

Traces are captured when the agent CLI exports OTel spans to a local OTLP collector. The `agentic-ci` framework (>= 0.3.8) handles this automatically — see the [agentic-ci MLflow traces documentation](https://github.com/opendatahub-io/agentic-ci/blob/main/docs/mlflow-traces.md) for details.

For Claude Code agents, these environment variables enable full span export with content:

| Variable | Value |
|----------|-------|
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` | `1` |
| `OTEL_LOG_USER_PROMPTS` | `1` |
| `OTEL_LOG_TOOL_DETAILS` | `1` |
| `OTEL_LOG_TOOL_CONTENT` | `1` |

Other agent CLIs (e.g., OpenCode) use their own OTel configuration — refer to the `agentic-ci` harness documentation for specifics.
