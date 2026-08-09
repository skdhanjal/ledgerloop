"""Assistant config tests. These values now come from outside the codebase."""
import pytest
from pydantic import ValidationError

from deploy.assistants import AssistantContext, load


def cfg(**over):
    base = dict(tenant_id="acme-corp", variance_tolerance=0.05,
                max_auto_approve=50_000, investigator_tier="strong")
    return {**base, **over}


# ---- validation is the point ------------------------------------------
def test_valid_config_loads():
    assert AssistantContext(**cfg()).variance_tolerance == 0.05


def test_percentage_typo_is_rejected():
    """0.8 meant as 8% would approve almost everything. Fail loudly."""
    with pytest.raises(ValidationError, match="implausibly high"):
        AssistantContext(**cfg(variance_tolerance=0.8))


def test_negative_tolerance_rejected():
    with pytest.raises(ValidationError):
        AssistantContext(**cfg(variance_tolerance=-0.05))


def test_unknown_model_tier_rejected():
    with pytest.raises(ValidationError, match="unknown tier"):
        AssistantContext(**cfg(investigator_tier="gpt-9-ultra"))


def test_zero_tolerance_is_allowed():
    """Globex genuinely has no tolerance - do not over-validate."""
    assert AssistantContext(**cfg(variance_tolerance=0.0)).variance_tolerance == 0.0


# ---- the shipped definitions --------------------------------------------
def test_all_shipped_assistants_are_valid():
    """A malformed assistants.json must fail in CI, not at deploy."""
    assistants = load()
    assert assistants
    for name, ctx in assistants.items():
        assert ctx.tenant_id, f"{name} has no tenant"


def test_each_tenant_has_at_least_one_assistant():
    tenants = {c.tenant_id for c in load().values()}
    assert {"acme-corp", "globex-ltd"} <= tenants


def test_monthend_variant_is_stricter_than_standard():
    """A named variant that is not actually stricter is a config bug."""
    a = load()
    assert (a["acme-ap-monthend"].variance_tolerance
            < a["acme-ap"].variance_tolerance)
    assert (a["acme-ap-monthend"].max_auto_approve
            < a["acme-ap"].max_auto_approve)
