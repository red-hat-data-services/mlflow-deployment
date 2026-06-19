"""Patch kubernetes-auth middleware to fall back to pod namespace.

When workspaces are disabled and no X-MLFLOW-WORKSPACE header is sent,
the plugin uses the pod's own namespace for SAR checks instead of
requiring a workspace context.
"""

import sys

TARGET = "/usr/local/lib/python3.12/site-packages/mlflow_kubernetes_plugins/auth/middleware.py"

HELPER = '''
_POD_NAMESPACE: str | None = None


def _get_pod_namespace() -> str | None:
    """Read the pod namespace from the mounted service account token.

    Cached after first read. Returns None when not running in a pod.
    """
    global _POD_NAMESPACE
    if _POD_NAMESPACE is not None:
        return _POD_NAMESPACE
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
            _POD_NAMESPACE = f.read().strip()
    except FileNotFoundError:
        return None
    return _POD_NAMESPACE

'''

ANCHOR = 'def _replace_scope_headers'
FALLBACK_ANCHOR = '            path_params = _extract_path_params(canonical_path, request.method) or dict('
FALLBACK_INSERT = '            if workspace_name is None:\n                workspace_name = _get_pod_namespace()\n\n'

with open(TARGET) as f:
    content = f.read()

if '_get_pod_namespace' in content:
    print('Already patched')
    sys.exit(0)

if ANCHOR not in content:
    print(f'ERROR: anchor not found: {ANCHOR}', file=sys.stderr)
    sys.exit(1)

if FALLBACK_ANCHOR not in content:
    print(f'ERROR: fallback anchor not found', file=sys.stderr)
    sys.exit(1)

content = content.replace(ANCHOR, HELPER + ANCHOR, 1)
content = content.replace(FALLBACK_ANCHOR, FALLBACK_INSERT + FALLBACK_ANCHOR, 1)

with open(TARGET, 'w') as f:
    f.write(content)

print('Patched middleware with pod namespace fallback')
