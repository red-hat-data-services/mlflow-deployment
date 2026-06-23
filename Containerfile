# MLflow 3.13 with kubernetes-auth plugin and vanilla UI.
#
# Built from UBI9 + Python 3.12 since the kubernetes-auth plugin
# requires Python >= 3.12 and the upstream MLflow images use 3.10.

# Stage 1: Get the vanilla UI from the upstream MLflow image
FROM ghcr.io/mlflow/mlflow:v3.13.0 AS vanilla-ui

# Stage 2: Build the kubernetes-auth plugin wheel
FROM registry.access.redhat.com/ubi9/python-312:latest AS plugin-builder
RUN pip install --no-cache-dir build
RUN pip install --no-cache-dir \
    'mlflow-kubernetes-plugins @ git+https://github.com/kubeflow/mlflow-integration.git@v1.3.0'
RUN pip wheel --no-deps --wheel-dir /tmp/wheels mlflow-kubernetes-plugins

# Stage 3: Final image
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

RUN microdnf install -y --setopt=tsflags=nodocs \
        python3.12 python3.12-pip \
        postgresql-libs sqlite \
    && microdnf clean all

# Install MLflow and dependencies
RUN pip3.12 install --no-cache-dir \
    'mlflow[genai]==3.13.0' \
    'psycopg2-binary>=2.9' \
    'boto3>=1.34' \
    'kubernetes>=29.0.0' \
    'graphql-core>=3.2.0'

# Install kubernetes-auth plugin from pre-built wheel
COPY --from=plugin-builder /tmp/wheels/ /tmp/wheels/
RUN pip3.12 install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy vanilla UI (upstream MLflow JS build)
COPY --from=vanilla-ui \
    /usr/local/lib/python3.10/site-packages/mlflow/server/js/build/ \
    /usr/local/lib/python3.12/site-packages/mlflow/server/js/build/

# Patch: fall back to pod namespace when workspaces are disabled
COPY patches/middleware-pod-namespace.py /tmp/middleware-patch.py
RUN python3.12 /tmp/middleware-patch.py && rm /tmp/middleware-patch.py


EXPOSE 5000
USER 1001
ENTRYPOINT ["mlflow"]
CMD ["server", "--host", "0.0.0.0"]
