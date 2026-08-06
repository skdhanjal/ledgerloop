# LedgerLoop

LedgerLoop is a capstone project from the LangGraph 30‑Day Sprint, built to demonstrate how to design durable, multi‑agent workflows for financial operations.

## Architecture

    uv run python -c "from graph.app import build_app; \
      print(build_app(checkpointer_kind='memory', store_kind='memory') \
            .get_graph().draw_mermaid())" > docs/graph.mmd

Regenerate at every milestone. The diff between v0 and v1 is the clearest
record of how the system grew.