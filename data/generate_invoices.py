"""Generate synthetic invoices with matching POs/receipts and seeded exceptions.

Ground truth is emitted alongside each invoice - it becomes the golden dataset on
Day 22, so it must be CONSTRUCTED, never inferred.
"""
import json, random
from dataclasses import dataclass, asdict
from pathlib import Path
from faker import Faker

fake = Faker()
OUT = Path(__file__).parent / "generated"

EXCEPTION_TYPES = [
    "clean",            # matches perfectly        -> auto_approve
    "price_variance",   # unit price above PO      -> hold
    "short_shipment",   # received < invoiced      -> hold
    "missing_po",       # PO reference not found   -> hold
    "duplicate",        # same vendor + invoice no -> reject
    "tax_error",        # total != subtotal + tax  -> hold
]


@dataclass
class LineItem:
    sku: str
    description: str
    quantity: int
    unit_price: float

    @property
    def amount(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass
class Invoice:
    invoice_no: str
    vendor: str
    po_number: str | None
    currency: str
    date: str
    lines: list[LineItem]
    subtotal: float
    tax: float
    total: float
    tenant_id: str
    # --- ground truth: never shown to the agent ---
    seeded_exception: str = "clean"
    expected_decision: str = "auto_approve"
    expected_reason: str | None = None


def make_lines(n):
    return [
        LineItem(
            sku=f"SKU-{random.randint(1000, 9999)}",
            description=f"{fake.word().capitalize()} {fake.word()}",
            quantity=random.randint(1, 50),
            unit_price=round(random.uniform(5, 500), 2),
        )
        for _ in range(n)
    ]


def build(idx, exception, tenant, prior):
    lines = make_lines(random.choice([1, 2, 3, 5, 8]))
    po_number = f"PO-{4000 + idx}"
    vendor = fake.company()

    po = {"po_number": po_number, "vendor": vendor,
          "lines": [{"sku": l.sku, "quantity": l.quantity,
                     "unit_price": l.unit_price} for l in lines]}
    receipt = {"po_number": po_number,
               "lines": [{"sku": l.sku, "quantity_received": l.quantity} for l in lines]}

    subtotal = round(sum(l.amount for l in lines), 2)
    tax = round(subtotal * 0.18, 2)

    inv = Invoice(
        invoice_no=f"INV-{10000 + idx}", vendor=vendor, po_number=po_number,
        currency="INR", date=fake.date_this_year().isoformat(), lines=lines,
        subtotal=subtotal, tax=tax, total=round(subtotal + tax, 2),
        tenant_id=tenant, seeded_exception=exception,
    )

    # --- inject the exception AND record the ground-truth decision ---
    if exception == "price_variance":
        inv.lines[0].unit_price = round(inv.lines[0].unit_price * 1.35, 2)
        inv.subtotal = round(sum(l.amount for l in inv.lines), 2)
        inv.tax = round(inv.subtotal * 0.18, 2)
        inv.total = round(inv.subtotal + inv.tax, 2)
        inv.expected_decision, inv.expected_reason = "hold", "price_variance"

    elif exception == "short_shipment":
        receipt["lines"][0]["quantity_received"] = max(0, inv.lines[0].quantity - 5)
        inv.expected_decision, inv.expected_reason = "hold", "short_shipment"

    elif exception == "missing_po":
        inv.po_number = f"PO-{99000 + idx}"          # references nothing
        inv.expected_decision, inv.expected_reason = "hold", "missing_po"

    elif exception == "duplicate" and prior:
        src = random.choice(prior)
        inv.invoice_no, inv.vendor = src.invoice_no, src.vendor
        inv.expected_decision, inv.expected_reason = "reject", "duplicate"

    elif exception == "tax_error":
        inv.total = round(inv.total + random.uniform(50, 500), 2)
        inv.expected_decision, inv.expected_reason = "hold", "tax_error"

    return inv, {"po": po, "receipt": receipt}


def as_text(inv):
    """The 'raw' invoice as the agent first sees it - untrusted text."""
    body = "\n".join(
        f"  {l.sku:<10} {l.description:<28} {l.quantity:>4} x "
        f"{l.unit_price:>10.2f} = {l.amount:>12.2f}" for l in inv.lines
    )
    return (f"INVOICE\nVendor: {inv.vendor}\nInvoice No: {inv.invoice_no}\n"
            f"Date: {inv.date}\nPO Reference: {inv.po_number}\n"
            f"Currency: {inv.currency}\n\nLine Items:\n{body}\n\n"
            f"Subtotal: {inv.subtotal:.2f}\nTax (18%): {inv.tax:.2f}\n"
            f"Total Due: {inv.total:.2f}\n")


def main(n: int = 20, seed: int = 42):
    random.seed(seed); Faker.seed(seed)
    OUT.mkdir(parents=True, exist_ok=True)

    invoices, pos, receipts = [], [], []
    tenants = ["acme-corp", "globex-ltd"]

    for i in range(n):
        # 60% clean / 40% exceptions - mirrors real AP exception rates
        exc = "clean" if random.random() <= 0.65 else random.choice(EXCEPTION_TYPES[1:])
        inv, refs = build(i, exc, random.choice(tenants), invoices)
        invoices.append(inv); pos.append(refs["po"]); receipts.append(refs["receipt"])
        (OUT / f"{inv.tenant_id}_{i:03d}.txt").write_text(as_text(inv), encoding="utf-8")

    (OUT / "invoices.json").write_text(
        json.dumps([asdict(i) for i in invoices], indent=2, default=str), encoding="utf-8")
    (OUT / "purchase_orders.json").write_text(json.dumps(pos, indent=2), encoding="utf-8")
    (OUT / "goods_receipts.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")

    counts = {}
    for inv in invoices:
        counts[inv.seeded_exception] = counts.get(inv.seeded_exception, 0) + 1
    print(f"Generated {n} invoices in {OUT}")
    for k, v in sorted(counts.items()):
        print(f"  {k:<18} {v}")


if __name__ == "__main__":
    main()
