FROM ghcr.io/mlflow/mlflow:v3.12.0 AS vanilla-ui

FROM quay.io/opendatahub/mlflow@sha256:395ed436128283efd31293ed6bb0fffe5f00b5967c19559d25b1d9d9756d559f

# Replace ODH federated UI with vanilla MLflow UI.
# The ODH UI requires the kubeflow central dashboard for workspace
# navigation, which is not available in standalone deployments.
COPY --from=vanilla-ui \
    /usr/local/lib/python3.10/site-packages/mlflow/server/js/build/ \
    /usr/local/lib/python3.12/site-packages/mlflow/server/js/build/

USER 0

# Fall back to pod namespace when workspaces are disabled.
# This allows kubernetes-auth to work without --enable-workspaces
# in single-tenant deployments — SAR checks use the pod's own
# namespace instead of requiring a workspace-to-namespace mapping.
COPY patches/middleware-pod-namespace.py /tmp/middleware-patch.py
RUN /usr/bin/python3.12 /tmp/middleware-patch.py && rm /tmp/middleware-patch.py

USER 1001
