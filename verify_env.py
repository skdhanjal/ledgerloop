"""Day 1 environment verification. Run this before writing any graph code."""
import sys
from importlib.metadata import version, PackageNotFoundError
from rich.console import Console

console = Console()
results: list[tuple[str, bool, str]] = []


def check(label, fn):
    try:
        results.append((label, True, fn() or "ok"))
    except Exception as e:
        results.append((label, False, f"{type(e).__name__}: {e}"))


def v(pkg):
    """Read the INSTALLED version from package metadata.

    Do not use pkg.__version__ - several of these packages do not define it,
    and you would be reporting an AttributeError instead of a version.
    """
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "MISSING"


def check_langgraph():
    from langgraph.graph import StateGraph, START, END           # noqa: F401
    from langgraph.checkpoint.sqlite import SqliteSaver          # noqa: F401
    return (f"langgraph {v('langgraph')} · "
            f"checkpoint-sqlite {v('langgraph-checkpoint-sqlite')}")


def check_langchain():
    # v1 canonical import paths - see the LangChain v1 release notes
    from langchain.agents import create_agent                    # noqa: F401
    from langchain.chat_models import init_chat_model            # noqa: F401
    from langchain.tools import tool                             # noqa: F401
    return f"langchain {v('langchain')} · core {v('langchain-core')}"


def check_model_basic():
    from config import get_model, PRIMARY_MODEL
    resp = get_model().invoke("Reply with exactly: READY")
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return f"{PRIMARY_MODEL} -> {text.strip()[:32]}"


def check_tool_calling():
    """THE IMPORTANT ONE. A model that responds is not a model that calls tools."""
    from langchain.tools import tool
    from config import get_model

    @tool
    def lookup_po(po_number: str) -> str:
        """Look up a purchase order by its number."""
        return f"PO {po_number}: 100 units of WIDGET-A at 25.00 each"

    resp = get_model().bind_tools([lookup_po]).invoke(
        "Look up purchase order PO-4471 using your tools."
    )
    if not getattr(resp, "tool_calls", None):
        preview = str(resp.content)[:120]
        raise RuntimeError(
            "No tool_calls returned - the model DESCRIBED the tool instead of "
            f"calling it. It said: {preview!r} ... This model or provider does "
            "not support tool calling properly. Pick a different model. "
            "Do NOT continue to Day 2."
        )
    call = resp.tool_calls[0]
    return f"called {call['name']}({call['args']})"


check("LangGraph imports",  check_langgraph)
check("LangChain imports",  check_langchain)
check("Model responds",     check_model_basic)
check("Model TOOL CALLING", check_tool_calling)

console.print()
for label, ok, detail in results:
    mark = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
    console.print(f"  {mark}  {label:<22} {detail}")
console.print()

if all(ok for _, ok, _ in results):
    console.print("[bold green]Environment verified. Proceed to Day 2.[/bold green]")
else:
    console.print("[bold red]Fix the failures above before writing graph code.[/bold red]")
    sys.exit(1)
