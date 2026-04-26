"""Shared tunnel runtime-state helpers."""

from app.services.system.tunnel.runtime_store import (
    DEFAULT_ACTIVE_TUNNEL_INFO,
    tunnel_runtime_store,
)


def tunnel_runtime_access(reader):
    """Read tunnel runtime state under the Specter store lock."""
    return tunnel_runtime_store.access(reader)


def update_tunnel_runtime(mutator):
    """Mutate tunnel runtime state through the Specter-owned store."""
    return tunnel_runtime_store.update(mutator)


def get_active_tunnel_info():
    """Return a snapshot of the current active tunnel state."""
    return tunnel_runtime_access(
        lambda state: dict(state.get('active_tunnel_info', {})),
    )


def set_active_tunnel_info(partial):
    """Shallow-merge into the current active tunnel info."""
    def _merge(draft):
        active = draft.setdefault('active_tunnel_info', dict(DEFAULT_ACTIVE_TUNNEL_INFO))
        active.update(partial)

    update_tunnel_runtime(_merge)


def replace_active_tunnel_info(info=None):
    """Replace active tunnel info with a normalized default-backed mapping."""
    payload = dict(DEFAULT_ACTIVE_TUNNEL_INFO)
    if info:
        payload.update(info)
    update_tunnel_runtime(
        lambda draft: draft.__setitem__('active_tunnel_info', payload),
    )
