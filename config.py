"""Central configuration. Every node gets its model from here (via Runtime context, Day 4)."""
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

# "provider:model" form - init_chat_model splits on the colon.
# Equivalent: init_chat_model("<model>", model_provider="google_genai")
PRIMARY_MODEL = os.getenv("LEDGERLOOP_MODEL")
LOCAL_MODEL   = os.getenv("LEDGERLOOP_LOCAL_MODEL", "groq:gpt-oss-20b")

if not PRIMARY_MODEL or "<paste" in PRIMARY_MODEL:
    raise RuntimeError(
        "LEDGERLOOP_MODEL is unset or still a placeholder. Open your provider "
        "console, copy the current model id, and put it in .env as "
        "'provider:model' - e.g. google_genai:<flash-model-id>"
    )


TIERS = {
    "strong": PRIMARY_MODEL,  # extraction, investigation
    "local":  LOCAL_MODEL,    # routing, judging, summarising
}

def get_model(tier: str = "strong", **kwargs):
    """One place that knows how to build a model.

    init_chat_model accepts 'provider:model' strings, so swapping providers or
    surviving a model deprecation never requires touching a call site.
    """
    name = TIERS.get(tier) or TIERS["strong"]
    return init_chat_model(name or PRIMARY_MODEL, temperature=0, **kwargs)
