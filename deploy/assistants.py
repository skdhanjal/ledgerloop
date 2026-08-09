"""Assistant definitions as data. One file, reviewable, diffable.

These used to be a dict inside context_for() in Python (Day 12). Moving them
here means a tolerance change is a config change, not a deploy - and every run
records which assistant version produced it.
"""
import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

DEFINITIONS = Path("deploy/assistants.json")

class AssistantContext(BaseModel):
    """The configurable surface. Mirrors LedgerContext's serialisable fields.

    Validated because these values now come from outside the codebase - a
    finance lead editing a tolerance should get a clear error, not a graph
    that silently approves everything.
    """
    tenant_id: str
    variance_tolerance: float = Field(ge=0.0, le=0.5)
    max_auto_approve: float = Field(ge=0.0)
    investigator_tier: str = Field(default="strong")
    require_human_above: float = Field(ge=0.0, default=0.0)

    @field_validator("investigator_tier")
    @classmethod
    def known_tier(cls, v: str) -> str:
        if v not in {"strong", "local"}:
            raise ValueError(f"unknown tier '{v}'")
        return v

    @field_validator("variance_tolerance")
    @classmethod
    def flag_unusual_tolerance(cls, v: float) -> float:
        # 50% is the hard ceiling above; anything over 20% is almost certainly
        # a typo (0.8 meant as 8%). Fail loudly rather than approve everything.
        if v > 0.20:
            raise ValueError(
                f"tolerance {v:.0%} is implausibly high - did you mean "
                f"{v / 10:.0%}? Override deliberately if not.")
        return v


def load() -> dict[str, AssistantContext]:
    raw = json.loads(DEFINITIONS.read_text())
    return {name: AssistantContext(**cfg) for name, cfg in raw.items()}


async def sync(client, dry_run: bool = True) -> list[str]:
    """Reconcile the file with the deployment. New values create NEW VERSIONS;
    nothing is overwritten in place, so rollback stays available."""
    changes = []
    existing = {a["name"]: a for a in await client.assistants.search()}

    for name, ctx in load().items():
        payload = ctx.model_dump()
        current = existing.get(name)

        if current is None:
            changes.append(f"CREATE {name}")
            if not dry_run:
                await client.assistants.create(graph_id="ledgerloop", name=name,
                                               context=payload)
        elif current["context"] != payload:
            diff = {k: (current["context"].get(k), v)
                    for k, v in payload.items() if current["context"].get(k) != v}
            changes.append(f"NEW VERSION {name}: {diff}")
            if not dry_run:
                await client.assistants.update(current["assistant_id"],
                                               context=payload)
    return changes
