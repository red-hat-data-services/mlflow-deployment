"""Patch kubernetes-auth middleware to fall back to pod namespace.

When workspaces are disabled and no X-MLFLOW-WORKSPACE header is sent,
the plugin uses the pod's own namespace for SAR checks instead of
requiring a workspace context. This catches the FEATURE_DISABLED
exception from resolve_workspace_from_header and falls back gracefully.
"""

import sys

TARGET = "/usr/local/lib/python3.12/site-packages/mlflow_kubernetes_plugins/auth/middleware.py"

HELPER = '''
_POD_NAMESPACE: str | None = None
_POD_NAMESPACE_RESOLVED = False


def _get_pod_namespace() -> str | None:
    """Return the Kubernetes namespace this pod is running in.

    Cached after first call (including negative results to avoid
    repeated syscalls). Returns None outside a Kubernetes pod.
    """
    global _POD_NAMESPACE, _POD_NAMESPACE_RESOLVED
    if _POD_NAMESPACE_RESOLVED:
        return _POD_NAMESPACE
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
            value = f.read().strip()
            _POD_NAMESPACE = value or None
    except OSError:
        _POD_NAMESPACE = None
    _POD_NAMESPACE_RESOLVED = True
    return _POD_NAMESPACE

'''

ANCHOR = 'def _replace_scope_headers'

OLD_RESOLVE = '''            if workspace_name is None:
                # FastAPI executes middlewares in reverse order, so this auth middleware can run
                # before the MLflow workspace middleware. Resolve here using the same helper, which
                # also falls back to the configured default workspace when the header is missing
                # or empty.
                try:
                    workspace = resolve_workspace_from_header(
                        request.headers.get(WORKSPACE_HEADER_NAME)
                    )
                except MlflowException as exc:
                    return JSONResponse(
                        status_code=exc.get_http_status_code(),
                        content=json.loads(exc.serialize_as_json()),
                    )

                if workspace is not None:
                    workspace_name = workspace.name
                    workspace_context.set_server_request_workspace(workspace_name)
                    workspace_set = True'''

NEW_RESOLVE = '''            if workspace_name is None:
                try:
                    workspace = resolve_workspace_from_header(
                        request.headers.get(WORKSPACE_HEADER_NAME)
                    )
                except MlflowException as exc:
                    if exc.error_code == databricks_pb2.FEATURE_DISABLED:
                        workspace_name = _get_pod_namespace()
                    else:
                        return JSONResponse(
                            status_code=exc.get_http_status_code(),
                            content=json.loads(exc.serialize_as_json()),
                        )
                else:
                    if workspace is not None:
                        workspace_name = workspace.name
                        workspace_context.set_server_request_workspace(workspace_name)
                        workspace_set = True

            if workspace_name is None:
                workspace_name = _get_pod_namespace()'''

with open(TARGET) as f:
    content = f.read()

if '_POD_NAMESPACE_RESOLVED' in content:
    print('Already patched')
    sys.exit(0)

if ANCHOR not in content:
    print(f'ERROR: anchor not found: {ANCHOR}', file=sys.stderr)
    sys.exit(1)

if OLD_RESOLVE not in content:
    print(f'ERROR: resolve block not found', file=sys.stderr)
    sys.exit(1)

content = content.replace(ANCHOR, HELPER + ANCHOR, 1)
content = content.replace(OLD_RESOLVE, NEW_RESOLVE, 1)

with open(TARGET, 'w') as f:
    f.write(content)

print('Patched middleware with pod namespace fallback')
