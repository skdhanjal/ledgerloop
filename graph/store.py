"""Store construction, with local embeddings so semantic search costs nothing."""
import os
from functools import lru_cache

from langgraph.store.memory import InMemoryStore
import psycopg

EMBED_DIMS = 384          # all-MiniLM-L6-v2 class models

@lru_cache(maxsize=1)
def _embedder():
    """Local CPU embeddings - no API, no quota, works offline.

    fastembed downloads a small ONNX model on first use (~90 MB) and runs on
    CPU. If you would rather not, get_store(semantic=False) below gives you a
    working store with exact-key lookups only.
    """
    from fastembed import TextEmbedding
    return TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [list(v) for v in _embedder().embed(texts)]


def get_store(kind: str | None = None, semantic: bool = True):
    kind = kind or os.getenv("LEDGERLOOP_STORE", "memory")

    index = ({"embed": embed_texts, "dims": EMBED_DIMS, "fields": ["text"]}
             if semantic else None)

    if kind == "memory":
        return InMemoryStore(index=index)

    if kind == "postgres":
        from langgraph.store.postgres import PostgresStore
        uri = os.environ["LEDGERLOOP_PG_URI"]
        conn = psycopg.connect(uri, autocommit=True)
        store = PostgresStore(conn, index=index)
        store.setup()
        return store

    raise ValueError(f"unknown store: {kind}")
