"""Fault-tolerance wiring. Policies differ per node because failures differ."""
from httpx import post
from langgraph.types import RetryPolicy, TimeoutPolicy

from graph.nodes import extract
from graph.posting import posting_failed

TRANSIENT = RetryPolicy(max_attempts=3, initial_interval=0.5,
                        backoff_factor=2.0, max_interval=8.0, jitter=True)


def only_transient(error: Exception) -> bool:
    """Explicit is better than default here - this node moves money.

    The default retry_on is already conservative (connection errors, 5xx from
    httpx/requests; NOT ValueError/TypeError/RuntimeError). We narrow further:
    a business rejection from the ERP must never be retried, because retrying
    a rejected payment is how you turn one failure into three.
    """
    from httpx import ConnectError, ReadTimeout
    from langgraph.errors import NodeTimeoutError
    return isinstance(error, (ConnectError, ReadTimeout, NodeTimeoutError))


def wire_fault_tolerance(b):
    # defaults for every node - retries on genuinely transient errors only
    b.set_node_defaults(
        retry_policy=TRANSIENT,
        timeout=TimeoutPolicy(run_timeout=120),
    )

    # the money node: tighter timeout, explicit retry filter, error handler
    b.add_node("post_to_erp", post,
               timeout=TimeoutPolicy(run_timeout=45),
               retry_policy=RetryPolicy(max_attempts=3, retry_on=only_transient, jitter=True),
               error_handler=posting_failed)

    # model nodes: idle timeout suits streaming; run_timeout would kill a
    # slow-but-progressing generation
    b.add_node("extract", extract,
               timeout=TimeoutPolicy(idle_timeout=30),
               retry_policy=TRANSIENT)

    return b
