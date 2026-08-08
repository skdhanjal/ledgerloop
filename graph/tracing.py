"""Tracing setup and the metadata that makes regressions attributable.

Four fields do the work: model actually served, prompt version, graph version,
tenant. Everything else in a trace is diagnosis; these are attribution, and
you cannot backfill them onto last week's runs.
"""
import os
import subprocess
from functools import lru_cache

PROMPT_VERSION = "2026-08-08.a"        # bump on ANY prompt edit
GRAPH_VERSION = "v2"                   # bump on topology change

@lru_cache(maxsize=1)
def code_version() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def run_config(*, 
        thread_id: str, 
        invoice_id: str = None, 
        tenant_id: str = None,
        topology: str = "pipeline", 
        extra: dict | None = None
    ) -> dict:
    """One place that builds config. If it is built here, it is tagged."""
    tenant_id = tenant_id or thread_id.split(':')[0]
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": f"invoice:{invoice_id}",
        "tags": [f"tenant:{tenant_id}", f"topology:{topology}", f"prompt:{PROMPT_VERSION}"],
        "metadata": {
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "prompt_version": PROMPT_VERSION,
            "graph_version": GRAPH_VERSION,
            "code_version": code_version(),
            **(extra or {}),
        },
        "recursion_limit": 40,
    }
    return config
