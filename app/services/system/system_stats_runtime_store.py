"""Specter-owned runtime store for rolling system-stats polling state."""

from specter import create_store


system_stats_runtime_store = create_store('system_stats_runtime', {
    'last_cpu_times': None,
    'last_cpu_percent': 0.0,
    'last_poll_time': 0.0,
})
