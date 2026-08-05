"""Investigator with a typed verdict instead of free text."""
from langchain.agents import create_agent

from .extraction import ExceptionVerdict
from .investigator import SYSTEM, opening_message
from .middleware import ledgerloop_middleware

def investigate_node_factory_v3(model, tools):
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM,
        response_format=ExceptionVerdict,     # auto-wrapped by capability
        middleware=ledgerloop_middleware(),
    )

    def investigate(state) -> dict:
        result = agent.invoke({"messages": [opening_message(state)]})
        verdict: ExceptionVerdict | None = result.get("structured_response")

        if verdict is None:
            # The agent stopped without producing a verdict. Degrade, do not crash.
            return {
                "investigation": "investigator produced no structured verdict",
                "exceptions": [{"code": "investigation_failed", "severity": "medium", "detail": "no verdict"}],
                "audit": [{"node": "investigate", "event": "no_verdict"}],
            }

        return {
            "investigation": verdict.root_cause,
            "verdict": verdict.model_dump(),
            "notes": [f"confidence {verdict.confidence:.2f}"],
            "audit": [{"node": "investigate", "event": "verdict",
                       "recommendation": verdict.recommendation,
                       "confidence": verdict.confidence,
                       "evidence_count": len(verdict.evidence)}],
        }

    return investigate
