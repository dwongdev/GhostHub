"""Specter-owned runtime store for the shared rate limiter owner."""

from specter import create_store


rate_limit_runtime_store = create_store('rate_limit_runtime', {
    'rate_limiter': None,
})
