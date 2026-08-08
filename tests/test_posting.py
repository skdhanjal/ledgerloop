
"""The money tests. These are the ones that must never be deleted."""
import pytest

from graph.posting import idempotency_key, post_to_erp, posting_failed


class FakeERP:
    def __init__(self):
        self.payments: dict[str, dict] = {}
        self.post_calls = 0
        self.n = 0

    def get_payment(self, key):
        return self.payments.get(key)

    def post_payment(self, *, idempotency_key, amount, **kw):
        self.post_calls += 1
        if idempotency_key in self.payments:
            return {**self.payments[idempotency_key], "replayed": True}
        self.n += 1
        p = {"payment_id": f"PAY-{self.n:05d}", "amount": amount, "replayed": False}
        self.payments[idempotency_key] = p
        return p


class Ctx:
    def __init__(self, erp, tenant="acme-corp"):
        self.erp, self.tenant_id = erp, tenant


class RT:
    def __init__(self, ctx):
        self.context = ctx


def state(total=3398.40, invoice_no="INV-1001", vendor="Kestrel"):
    return {"total": total, "invoice_no": invoice_no, "vendor": vendor}


# ---- key design -------------------------------------------------------
def test_same_payment_produces_the_same_key():
    assert idempotency_key(state(), "acme") == idempotency_key(state(), "acme")


def test_different_tenants_get_different_keys():
    """Two clients can both receive invoice INV-1001."""
    assert idempotency_key(state(), "acme") != idempotency_key(state(), "globex")


def test_different_vendors_get_different_keys():
    a = idempotency_key(state(vendor="Kestrel"), "acme")
    b = idempotency_key(state(vendor="Halvorsen"), "acme")
    assert a != b


def test_corrected_amount_gets_a_different_key():
    """THE one that matters: a controller fixing 3,398 -> 33,980 must NOT
    replay the original posting."""
    a = idempotency_key(state(total=3398.40), "acme")
    b = idempotency_key(state(total=33980.00), "acme")
    assert a != b


def test_key_is_stable_across_float_representation():
    assert (idempotency_key(state(total=3398.4), "acme")
            == idempotency_key(state(total=3398.40), "acme"))


# ---- the money test ---------------------------------------------------
def test_posting_twice_creates_exactly_one_payment():
    """Simulates a crash-and-resume: the node runs from the top, twice."""
    erp = FakeERP()
    rt = RT(Ctx(erp))

    first = post_to_erp(state(), rt)
    second = post_to_erp(state(), rt)          # the replay

    assert len(erp.payments) == 1
    assert first["payment_id"] == second["payment_id"]


def test_replay_is_detected_by_the_read_not_the_write():
    """The read-before-write should avoid the second POST entirely."""
    erp = FakeERP()
    rt = RT(Ctx(erp))
    post_to_erp(state(), rt)
    post_to_erp(state(), rt)
    assert erp.post_calls == 1                  # second attempt never wrote


def test_replay_is_visible_in_the_audit_trail():
    erp = FakeERP()
    rt = RT(Ctx(erp))
    post_to_erp(state(), rt)
    again = post_to_erp(state(), rt)
    assert again["audit"][0]["event"] == "already_posted"


def test_concurrent_writers_still_produce_one_payment():
    """Both read 'not posted', both write. The KEY covers what the read cannot."""
    erp = FakeERP()
    rt = RT(Ctx(erp))
    key = idempotency_key(state(), "acme-corp")
    erp.post_payment(idempotency_key=key, amount=3398.40)
    erp.post_payment(idempotency_key=key, amount=3398.40)
    assert len(erp.payments) == 1


def test_corrected_invoice_posts_a_second_real_payment():
    """The flip side: a genuinely different amount must NOT be swallowed."""
    erp = FakeERP()
    rt = RT(Ctx(erp))
    post_to_erp(state(total=3398.40), rt)
    post_to_erp(state(total=33980.00), rt)
    assert len(erp.payments) == 2


# ---- the error handler ------------------------------------------------
def test_error_handler_degrades_instead_of_raising():
    out = posting_failed(state(), ConnectionError("ERP unreachable"))
    assert out["decision"] == "hold"
    assert out["posted"] is False
    assert out["exceptions"][0]["code"] == "posting_failed"
