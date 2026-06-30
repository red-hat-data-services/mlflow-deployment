# Using the MLflow instance

How to point a client at this MLflow and push traces, once your agent has been
[onboarded](onboarding.md). Three setups are covered:

1. [GitLab CI with agentic-ci](#1-gitlab-ci-with-agentic-ci)
2. [agent-eval-harness (`/eval-mlflow`)](#2-agent-eval-harness-eval-mlflow)
3. [A generic MLflow client](#3-generic-mlflow-client)

They all need the same connection details; only the wiring differs.

## Connection details

| | Value |
|---|---|
| Tracking URI | `https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com` |
| Auth | Bearer token — the `mlflow-ci-traces` service account (CI) or your own account via `oc whoami -t` (interactive); see [Token](#token) |
| TLS | the Route certificate is signed by the Red Hat IT CA; the client must trust it |
| Experiment | your experiment name — created during onboarding; **it must already exist** |

### TLS — trust the Red Hat IT CA

The Route's certificate is signed by the Red Hat IT CA. Most Python clients use
`requests` (via `certifi`), which does not trust it by default — point
`REQUESTS_CA_BUNDLE` at the CA:

```bash
curl -sL https://certs.corp.redhat.com/certs/2022-IT-Root-CA.pem -o /tmp/RH-IT-Root-CA.pem
export REQUESTS_CA_BUNDLE=/tmp/RH-IT-Root-CA.pem
```

(agent-eval-harness is an exception — it uses your system trust store, which
already trusts the Red Hat IT CA, so this is optional there.)

### Token

Authenticate with a **Bearer token**. Which token depends on who is calling:

- **CI / automation** — the shared `mlflow-ci-traces` service-account token your
  MLflow admin provides during onboarding. It can read experiments and push
  traces/usage. With cluster access you can mint one:

  ```bash
  oc create token mlflow-ci-traces -n ambient-code--mlflow --duration=24h
  ```

- **Interactive / personal use** — your own OpenShift token, so you act as
  yourself rather than the shared account (handy when running things from your
  laptop):

  ```bash
  export MLFLOW_TRACKING_TOKEN=$(oc whoami -t)
  ```

  You get whatever your Red Hat account is authorized for: every authenticated
  user can read experiments and traces; pushing to or managing an experiment
  requires your account to maintain it (or be an admin).

> Creating experiments (and datasets) is **admin-only** — for everyone else the
> experiment must already exist (created during onboarding).

## 1. GitLab CI with agentic-ci

Set these CI variables on your GitLab project (Settings → CI/CD → Variables):

| Variable | Value | Masked |
|----------|-------|--------|
| `MLFLOW_TRACKING_URI` | `https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com` | No |
| `MLFLOW_TRACKING_TOKEN` | *(the `mlflow-ci-traces` token)* | Yes |
| `MLFLOW_EXPERIMENT_NAME` | your experiment name | No |

Add a separate `trace-push` job that runs after the agent job and pushes the
`claude-otel.jsonl` artifact to MLflow:

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

The `before_script` installs the Red Hat IT Root CA so `requests` trusts the
Route's certificate (the `ubi9/python-312` image has no internal CAs). The job:

- only runs when `MLFLOW_TRACKING_URI` and `MLFLOW_EXPERIMENT_NAME` are set
- retries automatically up to 2 times on failure
- never blocks the pipeline (`allow_failure: true`)
- can be retried manually from the GitLab UI at any time

See `rfe-assessor/.gitlab-ci.yml` for a working example. The `claude-otel.jsonl`
artifact is produced automatically by agentic-ci (>= 0.3.8) — see its
[MLflow traces docs](https://github.com/opendatahub-io/agentic-ci/blob/main/docs/mlflow-traces.md)
for how capture is configured.

## 2. agent-eval-harness (`/eval-mlflow`)

The eval harness uses the standard MLflow client, so it reads the same env vars.
Running it yourself, authenticate as you (see [Token](#token)):

```bash
export MLFLOW_TRACKING_URI=https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com
export MLFLOW_TRACKING_TOKEN=$(oc whoami -t)
# REQUESTS_CA_BUNDLE is optional here: agent-eval-harness uses your system trust
# store, which already trusts the Red Hat IT CA. Set it only if yours does not:
# export REQUESTS_CA_BUNDLE=/tmp/RH-IT-Root-CA.pem
```

```text
/eval-run --model opus        # run the eval suite
/eval-mlflow --run-id <id>    # log results + push the hierarchical trace
```

The experiment name comes from the project's `eval.yaml` (`mlflow.experiment`)
or `MLFLOW_EXPERIMENT_NAME`; it **must already exist** — the eval push does not
create it. `claude-trace` (standalone skill tracing) uses the same env vars. See
the harness
[TRACING.md](https://github.com/opendatahub-io/agent-eval-harness/blob/main/TRACING.md).

## 3. Generic MLflow client

Any Python using the MLflow client picks up the same environment — the client
sends `MLFLOW_TRACKING_TOKEN` as the `Authorization: Bearer` header and honors
`REQUESTS_CA_BUNDLE` for TLS:

```bash
export MLFLOW_TRACKING_URI=https://mlflow.apps.int.spoke.prod.us-west-2.aws.paas.redhat.com
export MLFLOW_TRACKING_TOKEN=$(oc create token mlflow-ci-traces -n ambient-code--mlflow --duration=24h)
export REQUESTS_CA_BUNDLE=/tmp/RH-IT-Root-CA.pem
```

```python
import mlflow

# URI/token/CA are read from the environment above; set_tracking_uri is optional.
mlflow.set_experiment("your-experiment")   # must already exist

with mlflow.start_run():
    mlflow.log_metric("score", 0.9)
    # log params, artifacts, traces, ...
```

`set_experiment` would otherwise try to *create* the experiment if it is missing
— which the `mlflow-ci-traces` service account is not allowed to do, so always
target an experiment created during onboarding.
