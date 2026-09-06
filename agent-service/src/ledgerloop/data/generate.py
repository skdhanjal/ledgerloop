"""Multi-tenant synthetic invoice/PO/goods-receipt generator (C1, Day 2).

Ground truth is constructed alongside every document, never inferred from it
(invariant I2): before an invoice is built, this module decides which
exception type (if any) it will demonstrate, then builds the invoice/PO/GR
to realize exactly that condition. The expected decision comes from a fixed
type -> decision table (DECISION_FOR_TYPE), not from re-running any matching
or policy logic.

Determinism: a single `random.Random(seed)` drives every choice, in a fixed
generation order (tenants, then invoices within a tenant, in index order),
and no wall-clock value is ever written to output -- so two runs with the
same --seed produce byte-identical files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from pydantic import BaseModel

from ledgerloop.data.models import (
    DECISION_FOR_TYPE,
    EXCEPTION_TYPES,
    CatalogItem,
    GoodsReceipt,
    GoodsReceiptLine,
    GroundTruth,
    Invoice,
    LineItem,
    PurchaseOrder,
    Tenant,
    Vendor,
)

BASE_DATE = date(2026, 1, 1)

# Fixed base config for the first 3 tenants -- deliberately different vendor
# pools, variance tolerances and auto-approve ceilings (doc's Done-when).
TENANT_BASE = [
    {"tenant_id": "acme", "name": "Acme Corp", "tolerance": 0.02, "ceiling": 2500.0},
    {"tenant_id": "contoso", "name": "Contoso Ltd", "tolerance": 0.05, "ceiling": 5000.0},
    {"tenant_id": "globex", "name": "Globex Inc", "tolerance": 0.08, "ceiling": 10000.0},
]


def content_hash(doc: BaseModel) -> str:
    payload = doc.model_dump(mode="json")
    payload.pop("content_hash", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def finalize(doc: BaseModel) -> BaseModel:
    return doc.model_copy(update={"content_hash": content_hash(doc)})


def write_json(path: Path, doc: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump(mode="json")
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def build_tenants(n_tenants: int, rng: random.Random, fake: Faker) -> list[Tenant]:
    tenants = []
    for i in range(n_tenants):
        if i < len(TENANT_BASE):
            base = TENANT_BASE[i]
        else:
            base = {
                "tenant_id": f"tenant-{i:02d}",
                "name": fake.company(),
                "tolerance": [0.02, 0.05, 0.08][i % 3],
                "ceiling": [2500.0, 5000.0, 10000.0][i % 3],
            }
        vendors = []
        for v in range(8):
            catalog = [
                CatalogItem(
                    description=fake.bs().capitalize(),
                    uom=rng.choice(["EA", "BOX", "HR", "KG"]),
                    unit_price=round(rng.uniform(10, 500), 2),
                )
                for _ in range(rng.randint(3, 5))
            ]
            vendors.append(
                Vendor(
                    vendor_id=f"{base['tenant_id']}-vendor-{v:02d}",
                    name=fake.company(),
                    catalog=catalog,
                )
            )
        tenants.append(
            Tenant(
                tenant_id=base["tenant_id"],
                name=base["name"],
                variance_tolerance=base["tolerance"],
                auto_approve_ceiling=base["ceiling"],
                vendors=vendors,
            )
        )
    return tenants


def assign_exception_types(count: int, rng: random.Random) -> list[str]:
    """Decide each invoice's exception type up front (construction, not
    inference). ~60% clean, remainder spread across EXCEPTION_TYPES."""
    exception_total = round(count * 0.4)
    clean_total = count - exception_total
    types = ["clean"] * clean_total
    for i in range(exception_total):
        types.append(EXCEPTION_TYPES[i % len(EXCEPTION_TYPES)])
    rng.shuffle(types)
    # Guarantee index 0 is never 'duplicate' -- it needs a prior invoice to
    # duplicate, and generation is sequential.
    if types and types[0] == "duplicate":
        swap_at = next((i for i, t in enumerate(types) if t != "duplicate"), 0)
        types[0], types[swap_at] = types[swap_at], types[0]
    return types


def pick_lines(vendor: Vendor, rng: random.Random) -> list[LineItem]:
    items = rng.sample(vendor.catalog, k=min(len(vendor.catalog), rng.randint(1, 4)))
    lines = []
    for item in items:
        qty = rng.randint(1, 20)
        lines.append(
            LineItem(
                description=item.description,
                quantity=qty,
                uom=item.uom,
                unit_price=item.unit_price,
                line_total=round(qty * item.unit_price, 2),
            )
        )
    return lines


def totals(lines: list[LineItem]) -> tuple[float, float, float]:
    subtotal = round(sum(line.line_total for line in lines), 2)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)
    return subtotal, tax, total


def cap_to_budget(lines: list[LineItem], budget: float) -> list[LineItem]:
    """Scale quantities (never price) down so subtotal fits under `budget`,
    keeping line_total == quantity * unit_price for every line."""
    subtotal = sum(line.line_total for line in lines)
    if subtotal <= budget or subtotal <= 0:
        return lines
    factor = budget / subtotal
    return [
        line.model_copy(
            update={
                "quantity": (qty := max(1, round(line.quantity * factor))),
                "line_total": round(qty * line.unit_price, 2),
            }
        )
        for line in lines
    ]


class InvoiceBundle:
    def __init__(
        self, invoice: Invoice, po: PurchaseOrder | None, gr: GoodsReceipt | None, gt: GroundTruth
    ):
        self.invoice = invoice
        self.po = po
        self.gr = gr
        self.gt = gt


def build_bundle(
    tenant: Tenant,
    index: int,
    exception_type: str,
    rng: random.Random,
    history: list[InvoiceBundle],
) -> InvoiceBundle:
    tid = tenant.tenant_id
    invoice_id = f"{tid}-INV-{index:04d}"
    inv_date = (BASE_DATE + timedelta(days=index)).isoformat()

    if exception_type == "duplicate":
        source = rng.choice(history)
        invoice = source.invoice.model_copy(update={"invoice_id": invoice_id, "date": inv_date})
        po, gr = source.po, source.gr
        gt = GroundTruth(
            invoice_id=invoice_id,
            tenant_id=tid,
            exception_type="duplicate",
            expected_decision=DECISION_FOR_TYPE["duplicate"],
            expected_exceptions=["duplicate"],
        )
        return InvoiceBundle(invoice, po, gr, gt)

    vendor = rng.choice(tenant.vendors)
    po_lines = pick_lines(vendor, rng)
    po_lines = cap_to_budget(po_lines, tenant.auto_approve_ceiling * 0.5)
    po_number = f"{tid}-PO-{index:04d}"
    po = PurchaseOrder(po_number=po_number, tenant_id=tid, vendor=vendor.name, lines=po_lines)

    invoice_lines = [line.model_copy() for line in po_lines]
    gr_lines = [
        GoodsReceiptLine(description=line.description, quantity_received=line.quantity)
        for line in po_lines
    ]

    if exception_type == "price_variance":
        i = rng.randrange(len(invoice_lines))
        bump = 1 + tenant.variance_tolerance + 0.05
        bumped_price = round(invoice_lines[i].unit_price * bump, 2)
        bumped_total = round(bumped_price * invoice_lines[i].quantity, 2)
        invoice_lines[i] = invoice_lines[i].model_copy(
            update={"unit_price": bumped_price, "line_total": bumped_total}
        )

    if exception_type == "short_shipment":
        i = rng.randrange(len(gr_lines))
        shortfall = max(1, gr_lines[i].quantity_received // 3)
        gr_lines[i] = gr_lines[i].model_copy(
            update={"quantity_received": gr_lines[i].quantity_received - shortfall}
        )

    subtotal, tax, total = totals(invoice_lines)

    if exception_type == "arithmetic_error":
        subtotal = round(subtotal + rng.uniform(5, 25), 2)
        total = round(subtotal + tax, 2)

    if exception_type == "over_ceiling":
        scale = (tenant.auto_approve_ceiling * 1.5) / max(total, 1.0)
        invoice_lines = [
            line.model_copy(update={"line_total": round(line.line_total * scale, 2)})
            for line in invoice_lines
        ]
        subtotal, tax, total = totals(invoice_lines)

    invoice_po_number: str | None = po_number
    written_po: PurchaseOrder | None = po
    written_gr: GoodsReceipt | None = GoodsReceipt(
        gr_number=f"{tid}-GR-{index:04d}", tenant_id=tid, po_number=po_number, lines=gr_lines
    )

    if exception_type == "missing_po":
        invoice_po_number = f"{tid}-PO-9999-MISSING"
        written_po = None
        written_gr = None

    invoice = Invoice(
        invoice_id=invoice_id,
        tenant_id=tid,
        vendor=vendor.name,
        invoice_no=f"{vendor.vendor_id}-{index:05d}",
        po_number=invoice_po_number,
        date=inv_date,
        lines=invoice_lines,
        subtotal=subtotal,
        tax=tax,
        total=total,
    )

    expected_exceptions = [] if exception_type == "clean" else [exception_type]
    gt = GroundTruth(
        invoice_id=invoice_id,
        tenant_id=tid,
        exception_type=exception_type,
        expected_decision=DECISION_FOR_TYPE[exception_type],
        expected_exceptions=expected_exceptions,
    )

    return InvoiceBundle(invoice, written_po, written_gr, gt)


def split_counts(total: int, n: int) -> list[int]:
    base, rem = divmod(total, n)
    return [base + 1 if i < rem else base for i in range(n)]


def generate(n_tenants: int, n_invoices: int, seed: int, out_dir: Path) -> None:
    rng = random.Random(seed)
    fake = Faker()
    fake.seed_instance(seed)

    tenants = build_tenants(n_tenants, rng, fake)
    counts = split_counts(n_invoices, n_tenants)

    manifest_docs: list[str] = []

    for tenant, count in zip(tenants, counts, strict=True):
        write_json(out_dir / tenant.tenant_id / "tenant.json", finalize(tenant))
        manifest_docs.append(f"{tenant.tenant_id}/tenant:{content_hash(tenant)}")

        types = assign_exception_types(count, rng)
        history: list[InvoiceBundle] = []
        for idx, exc_type in enumerate(types, start=1):
            bundle = build_bundle(tenant, idx, exc_type, rng, history)

            tenant_dir = out_dir / tenant.tenant_id

            invoice = finalize(bundle.invoice)
            write_json(tenant_dir / "invoices" / f"{invoice.invoice_id}.json", invoice)
            manifest_docs.append(f"{tenant.tenant_id}/invoices/{invoice.invoice_id}:{invoice.content_hash}")

            if bundle.po is not None:
                po = finalize(bundle.po)
                write_json(tenant_dir / "purchase_orders" / f"{po.po_number}.json", po)
                manifest_docs.append(
                    f"{tenant.tenant_id}/purchase_orders/{po.po_number}:{po.content_hash}"
                )

            if bundle.gr is not None:
                gr = finalize(bundle.gr)
                write_json(tenant_dir / "goods_receipts" / f"{gr.gr_number}.json", gr)
                manifest_docs.append(
                    f"{tenant.tenant_id}/goods_receipts/{gr.gr_number}:{gr.content_hash}"
                )

            gt = finalize(bundle.gt)
            write_json(tenant_dir / "ground_truth" / f"{invoice.invoice_id}.json", gt)
            manifest_docs.append(f"{tenant.tenant_id}/ground_truth/{invoice.invoice_id}:{gt.content_hash}")

            if exc_type != "duplicate":
                history.append(InvoiceBundle(bundle.invoice, bundle.po, bundle.gr, bundle.gt))

    manifest_docs.sort()
    dataset_hash = hashlib.sha256("\n".join(manifest_docs).encode()).hexdigest()
    manifest = {
        "seed": seed,
        "tenants": [t.tenant_id for t in tenants],
        "invoice_count": n_invoices,
        "invoice_counts_by_tenant": {t.tenant_id: c for t, c in zip(tenants, counts, strict=True)},
        "dataset_hash": dataset_hash,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate multi-tenant synthetic AP fixture data")
    parser.add_argument("--tenants", type=int, default=3)
    parser.add_argument(
        "--invoices", type=int, default=150, help="Total invoices, split across tenants"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    generate(args.tenants, args.invoices, args.seed, args.out)


if __name__ == "__main__":
    main()
