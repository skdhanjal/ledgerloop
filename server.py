"""FastAPI + SSE approval queue. No Node toolchain - htmx does the DOM work.

Two endpoints and one rule: the browser only ever sees ProgressEvent,
DecisionEvent and ApprovalEvent. Graph state never crosses this boundary.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from langgraph.types import Command

from graph.app import build_app, context_for
from graph.checkpointing import get_checkpointer
from graph.erp import get_erp_client
from graph.events import ApprovalEvent, DecisionEvent

# The graph is built in a LIFESPAN handler, not at import time.
#
# This endpoint streams, so it needs an ASYNC checkpointer. SqliteSaver raises
# NotImplementedError on aget_tuple/aput - astream() calls those. And the async
# saver needs an await to construct, which you cannot do at module level.
#
# Your tests will not catch this: InMemorySaver implements both interfaces, so
# everything passes until the server runs for real.
graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    checkpointer = await get_checkpointer("sqlite")   # AsyncSqliteSaver
    graph = build_app(checkpointer=checkpointer, store_kind="memory")
    yield
    conn = getattr(checkpointer, "conn", None)

    if conn is not None:
        await conn.close()

    get_erp_client().close() 

app = FastAPI(title="LedgerLoop", lifespan=lifespan)


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def config_for(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}


@app.post("/invoices/{thread_id}/start")
async def start(thread_id: str, body: dict):
    """Reject double-texting: one run per invoice thread at a time.

    Concurrent runs on a payment thread is exactly the shape that produces a
    double payment (Day 19), so this is a rejection rather than a queue.
    """
    snapshot = await graph.aget_state(config_for(thread_id))
    pending_interrupt = any(t.interrupts for t in snapshot.tasks)

    if snapshot.next and not pending_interrupt:
        raise HTTPException(409, "already running - poll the existing stream")

    return {"thread_id": thread_id, "stream": f"/invoices/{thread_id}/stream"}


@app.get("/invoices/{thread_id}/stream")
async def stream_invoice(thread_id: str, invoice: str):
    """`invoice` is a STEM, resolved against the data directory here.

    Accepting a filesystem path from the browser would let a caller read any
    file the process can reach. Resolve and verify instead of trusting.
    """
    candidate = (Path("data/generated") / f"{invoice}.txt").resolve()
    if not candidate.is_file() or Path("data/generated").resolve() not in candidate.parents:
        raise HTTPException(404, "no such invoice")
    path = str(candidate)

    cfg = config_for(thread_id)
    ctx = context_for(thread_id.split(":")[0])

    async def events():
        try:
            async for ns, mode, chunk in graph.astream(
                    {"invoice_path": path}, context=ctx, config=cfg,
                    stream_mode=["custom", "updates"], subgraphs=True):
                # print("mode", mode, chunk)    

                if mode == "custom":
                    yield sse(chunk)                    # our typed events only

                elif mode == "updates" and "__interrupt__" in chunk:
                    # The graph paused. Emit the payload and CLOSE - do not
                    # hold the connection open for a human who may take days.
                    yield sse(ApprovalEvent(
                        thread_id=thread_id,
                        payload=chunk["__interrupt__"][0].value).model_dump())
                    return

            final = (await graph.aget_state(cfg)).values
            yield sse(DecisionEvent(decision=final.get("decision", "hold"), reason=final.get("reason", "")).model_dump())

        except asyncio.CancelledError:
            # client disconnected - the graph keeps running, state is durable
            raise

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/invoices/{thread_id}/resume")
async def resume(thread_id: str, decision: dict):
    """Minutes or days later, from any process with the same checkpointer."""
    cfg = config_for(thread_id)
    snapshot = await graph.aget_state(cfg)

    if not any(t.interrupts for t in snapshot.tasks):
        raise HTTPException(409, "thread is not awaiting approval")

    # ainvoke, not invoke: same checkpointer, same rule. Mixing a sync call
    # into an async saver raises the mirror-image NotImplementedError.
    result = await graph.ainvoke(Command(resume=decision),
                                 context=context_for(thread_id.split(":")[0]),
                                 config=cfg)
    return {"decision": result.get("decision"),
            "payment_id": result.get("payment_id")}


@app.get("/invoices")
def list_invoices():
    """What the picker is populated from. Stems only - the browser never
    receives a filesystem path it could tamper with."""
    return {"invoices": sorted(p.stem for p in Path("data/generated").glob("*.txt"))}


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the page from disk. No template engine, no build step.

    static/index.html is a real file, not a Python string - so an editor can
    lint it, a browser can hard-refresh it, and it does not get re-quoted
    every time someone edits the CSS.
    """
    return FileResponse("static/index.html")
