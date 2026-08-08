"""FastAPI + SSE approval queue.

Three endpoints that mutate a thread, and they are NOT interchangeable:

    /start    begin a run                     -> streams
    /resume   approve or reject               -> Command(resume=...), streams
    /edit     correct a field                 -> update_state(as_node="extract"),
                                                 re-runs matching AND policy,
                                                 streams

The third one is the reason this file is longer than it looks. A correction
must re-enter the graph UPSTREAM so the policy function runs again against the
human's numbers. Resuming with corrected values in the payload would write them
and then post - skipping the check entirely.

Everything the browser receives is a typed event from graph/events.py. Graph
state never crosses this boundary.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from langgraph.types import Command

from graph.app import build_app, context_for
from graph.checkpointing import get_checkpointer
from graph.erp import get_erp_client
from graph.events import ApprovalEvent, DecisionEvent

DATA = Path("data/generated")

# Server-side allowlist. The payload advertises `editable_fields` to the UI,
# but the UI is not the authority - a caller can POST whatever it likes, so the
# allowlist and the coercions live here.
EDITABLE: dict[str, type] = {
    "total": float,
    "subtotal": float,
    "po_number": str,
    "vendor": str,
}

# The graph is built in a lifespan handler, not at import time.
#
# These endpoints stream, so they need an ASYNC checkpointer: SqliteSaver raises
# NotImplementedError on aget_tuple/aput, which astream() calls. And the async
# saver needs an await to construct, which you cannot do at module level.
#
# Your tests will not catch this - InMemorySaver implements BOTH interfaces, so
# everything passes until the server runs for real.
graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    checkpointer = await get_checkpointer("sqlite")
    graph = build_app(checkpointer=checkpointer, store_kind="memory")
    yield

    # --- shutdown: close everything owning a socket or a thread ---
    conn = getattr(checkpointer, "conn", None)
    if conn is not None:
        await conn.close()          # aiosqlite holds a connection AND a thread
    get_erp_client().close()        # httpx pool; a process-lifetime singleton


app = FastAPI(title="LedgerLoop", lifespan=lifespan)


# ------------------------------------------------------------------ helpers
def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def config_for(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}


def tenant_of(thread_id: str) -> str:
    return thread_id.split(":", 1)[-1].split("_")[0]


def resolve_invoice(stem: str) -> str:
    """A STEM, resolved here. Never accept a filesystem path from a browser."""
    candidate = (DATA / f"{stem}.txt").resolve()
    if not candidate.is_file() or DATA.resolve() not in candidate.parents:
        raise HTTPException(404, "no such invoice")
    return str(candidate)

def unpack(item):
    """astream yields (mode, chunk), or (ns, mode, chunk) when subgraphs=True.

    Tolerating both means drive() does not care which the caller asked for -
    and a future endpoint that turns subgraphs off does not break.
    """
    if len(item) == 3:
        return item
    mode, chunk = item
    return (), mode, chunk    


async def pending_interrupt(cfg: dict):
    """The interrupt this thread is parked on, or None."""
    snapshot = await graph.aget_state(cfg)
    for task in snapshot.tasks:
        for intr in (task.interrupts or []):
            return intr
    return None


async def drive(stream, thread_id: str, cfg: dict):
    """Shared SSE body. Now namespace-aware.

    subgraphs=True is what makes the investigation's own progress visible at
    all - without it, every event a subgraph emits is silently dropped and the
    UI shows one long gap where the agent was working.
    """
    emitted_interrupt = False

    try:
        async for item in stream:
            ns, mode, chunk = unpack(item)

            if mode == "custom":
                # Enrich with POSITION, never with the raw namespace: it
                # contains a UUID and it is an internal identifier.
                yield sse({**chunk,
                           "depth": len(ns),
                           "source": ns[-1].split(":")[0] if ns else None})

            elif mode == "updates" and "__interrupt__" in chunk:
                # An interrupt raised inside a subgraph surfaces at BOTH the
                # subgraph and the parent namespace, so this fires twice.
                # Emit once - the payload is identical and the resume is
                # delivered to the parent thread either way.
                if emitted_interrupt:
                    continue
                emitted_interrupt = True
                yield sse(ApprovalEvent(
                    thread_id=thread_id,
                    payload=chunk["__interrupt__"][0].value).model_dump())
                return

        final = (await graph.aget_state(cfg)).values
        yield sse(DecisionEvent(decision=final.get("decision", "hold"),
                                reason=final.get("reason", "")).model_dump())

    except asyncio.CancelledError:
        raise


# ------------------------------------------------------------------- routes
@app.get("/invoices")
def list_invoices():
    """Populates the picker. Stems only - no filesystem paths to the browser."""
    return {"invoices": sorted(p.stem for p in DATA.glob("*.txt"))}


@app.post("/invoices/{thread_id}/start")
async def start(thread_id: str, body: dict):
    """Reject double-texting: one run per invoice thread at a time.

    Concurrent runs on a payment thread is precisely the shape that produces a
    double payment (Day 19), so this is a rejection rather than a queue. The
    client already has a thread_id it can attach a stream to.
    """
    cfg = config_for(thread_id)
    snapshot = await graph.aget_state(cfg)
    parked = await pending_interrupt(cfg)

    if snapshot.next and parked is None:
        raise HTTPException(409, "already running - attach to the existing stream")

    return {"thread_id": thread_id, "stream": f"/invoices/{thread_id}/stream"}


@app.get("/invoices/{thread_id}/stream")
async def stream_invoice(thread_id: str, invoice: str):
    cfg = config_for(thread_id)
    stream = graph.astream(
        {"invoice_path": resolve_invoice(invoice)},
        context=context_for(tenant_of(thread_id)),
        config=cfg, 
        stream_mode=["custom", "updates"],
        subgraphs=True
    )
    return StreamingResponse(drive(stream, thread_id, cfg), media_type="text/event-stream")


@app.post("/invoices/{thread_id}/resume")
async def resume(thread_id: str, decision: dict):
    """Approve or reject. Minutes or days later, from any process.

    Streams, because the resumed portion is not always one node - Day 19's
    posting is a network call with retries, and Day 11's back-edge can
    re-enter the graph at `decide`.
    """
    cfg = config_for(thread_id)

    if await pending_interrupt(cfg) is None:
        raise HTTPException(409, "thread is not awaiting approval")

    action = decision.get("action")
    if action not in {"approve", "reject"}:
        raise HTTPException(422, "use /edit to submit a correction")

    stream = graph.astream(
        Command(resume=decision),
        context=context_for(tenant_of(thread_id)),
        config=cfg, 
        stream_mode=["custom", "updates"],
        subgraphs=True
    )
    return StreamingResponse(drive(stream, thread_id, cfg), media_type="text/event-stream")


@app.post("/invoices/{thread_id}/edit")
async def edit(thread_id: str, body: dict):
    """A correction re-enters the graph UPSTREAM, then it runs again.

    This is deliberately NOT Command(resume={"action": "edit", ...}). The gate
    sits after matching and policy, so resuming with corrected values would
    write them and continue to post - the number would never be re-checked
    against the purchase order.

    as_node="extract" makes LangGraph believe extraction produced these values,
    so matching and the POLICY CHECK run again. The invoice may well hold a
    second time, and that is the correct outcome: the human supplied better
    INPUT, not a better DECISION.
    """
    cfg = config_for(thread_id)
    if await pending_interrupt(cfg) is None:
        raise HTTPException(409, "thread is not awaiting approval")

    raw = body.get("fields") or {}
    if not raw:
        raise HTTPException(422, "no fields submitted")

    # Coerce and allowlist SERVER-SIDE. `editable_fields` in the interrupt
    # payload tells the UI what to render; it does not constrain the caller.
    values: dict = {}
    for name, value in raw.items():
        caster = EDITABLE.get(name)
        if caster is None:
            raise HTTPException(422, f"field '{name}' is not editable")
        try:
            values[name] = caster(value)
        except (TypeError, ValueError):
            raise HTTPException(422, f"'{name}' must be {caster.__name__}")

    # Re-entry point. Everything downstream of extract runs again.
    await graph.aupdate_state(cfg, values, as_node="extract")

    # None means "continue from the checkpoint" - the updated one.
    stream = graph.astream(
        None,
        context=context_for(tenant_of(thread_id)),
        config=cfg, 
        stream_mode=["custom", "updates"],
        subgraphs=True
    )
    return StreamingResponse(drive(stream, thread_id, cfg), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
def index():
    """Served from disk: hard-refresh picks up edits, no restart, no templating."""
    return FileResponse("static/index.html")