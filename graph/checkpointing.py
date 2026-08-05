"""Checkpointer construction. One place, so swapping SQLite for Postgres
is a config change rather than an edit in five files.
"""
import os
import sqlite3
from pathlib import Path
import psycopg
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

DB_PATH = Path("ledgerloop.sqlite")


def get_checkpointer(kind: str | None = None):
    """kind: 'memory' | 'sqlite' | 'postgres'."""
    kind = kind or os.getenv("LEDGERLOOP_CHECKPOINTER", "sqlite")

    if kind == "memory":
        return InMemorySaver()

    if kind == "sqlite":
        # NOTE: SqliteSaver.from_conn_string() is a CONTEXT MANAGER. Using it as
        # `saver = SqliteSaver.from_conn_string(path)` gives you a context
        # manager object, not a saver, and fails confusingly at first use.
        # For a long-lived process, own the connection yourself:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()                     # idempotent - creates tables if absent
        return saver

    if kind == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver
        
        uri = os.environ["LEDGERLOOP_PG_URI"]
        conn = psycopg.connect(uri, autocommit=True)
        saver = PostgresSaver(conn)
        saver.setup()                     # run migrations; safe to repeat
        return saver

    raise ValueError(f"unknown checkpointer: {kind}")


def thread_id_for(tenant_id: str, invoice_no: str) -> str:
    """Derived SERVER-SIDE. Never accept a thread_id from a caller unchecked -
    whoever holds it can read and resume that thread's state, which includes
    extracted vendor bank details. Day 26 enforces ownership properly.
    """
    return f"{tenant_id}:{invoice_no}"
