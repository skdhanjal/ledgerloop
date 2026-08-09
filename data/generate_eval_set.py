"""Generate synthetic invoices with matching POs/receipts and seeded exceptions.

Ground truth is emitted alongside each invoice - it becomes the golden dataset on
Day 22, so it must be CONSTRUCTED, never inferred.
"""

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from faker import Faker

fake = Faker()

# Output directories
DATA_DIR = Path(__file__).parent
EVALS_DIR = DATA_DIR.parent / "evals"
OUT = DATA_DIR / "generated"

STRATA = {
    "clean": 30,
    "price_variance": 20,
    "short_shipment": 15,
    "missing_po": 15,
    "duplicate": 12,
    "tax_error": 12,
    "uom_mismatch": 14,       # over-sampled
    "near_tolerance": 12,     # variance within 0.5pp of tolerance threshold
    "multi_exception": 10,    # multiple defects on one invoice
    "extraction_hostile": 10, # layout challenges/noise
}


@dataclass
class LineItem:
    sku: str
    description: str
    quantity: int
    unit_price: float
    uom: str = "EA"  # Unit of Measure

    @property
    def amount(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass
class Invoice:
    invoice_no: str
    invoice_id: str
    vendor: str
    po_number: str | None
    currency: str
    date: str
    lines: list[LineItem]
    subtotal: float
    tax: float
    total: float
    tenant_id: str
    is_hostile: bool = False
    # --- ground truth: never shown to the agent ---
    seeded_exception: str = "clean"
    expected_decision: str = "auto_approve"
    expected_reason: str | None = None
    expected_exceptions: list[str] = None

    def __post_init__(self):
        if self.expected_exceptions is None:
            if self.seeded_exception == "clean":
                self.expected_exceptions = []
            else:
                self.expected_exceptions = [self.seeded_exception]


def make_lines(n):
    return [
        LineItem(
            sku=f"SKU-{random.randint(1000, 9999)}",
            description=f"{fake.word().capitalize()} {fake.word()}",
            quantity=random.randint(1, 50),
            unit_price=round(random.uniform(5, 500), 2),
            uom="EA",
        )
        for _ in range(n)
    ]


def build(idx, exception, tenant, prior):
    lines = make_lines(random.choice([2, 3, 5, 8]))
    po_number = f"PO-{4000 + idx}"
    vendor = fake.company()

    po = {
        "po_number": po_number,
        "vendor": vendor,
        "lines": [
            {
                "sku": l.sku,
                "quantity": l.quantity,
                "unit_price": l.unit_price,
                "uom": l.uom,
            }
            for l in lines
        ],
    }
    receipt = {
        "po_number": po_number,
        "lines": [
            {"sku": l.sku, "quantity_received": l.quantity} for l in lines
        ],
    }

    subtotal = round(sum(l.amount for l in lines), 2)
    tax = round(subtotal * 0.18, 2)
    inv = Invoice(
        invoice_id=f"{tenant}_{idx:03d}",
        invoice_no=f"INV-{10000 + idx}",
        vendor=vendor,
        po_number=po_number,
        currency="INR",
        date=fake.date_this_year().isoformat(),
        lines=lines,
        subtotal=subtotal,
        tax=tax,
        total=round(subtotal + tax, 2),
        tenant_id=tenant,
        seeded_exception=exception,
    )

    # --- Inject exceptions and set expected values ---
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
        inv.po_number = f"PO-{99000 + idx}"
        inv.expected_decision, inv.expected_reason = "hold", "missing_po"

    elif exception == "duplicate" and prior:
        src = random.choice(prior)
        inv.invoice_no, inv.vendor = src.invoice_no, src.vendor
        inv.expected_decision, inv.expected_reason = "reject", "duplicate"

    elif exception == "tax_error":
        inv.total = round(inv.total + random.uniform(50, 500), 2)
        inv.expected_decision, inv.expected_reason = "hold", "tax_error"

    elif exception == "uom_mismatch":
        # PO has EA (Each), Invoice bills in BOX (Box of 10) with altered unit price
        inv.lines[0].uom = "BOX"
        inv.lines[0].unit_price = round(inv.lines[0].unit_price * 10, 2)
        inv.subtotal = round(sum(l.amount for l in inv.lines), 2)
        inv.tax = round(inv.subtotal * 0.18, 2)
        inv.total = round(inv.subtotal + inv.tax, 2)
        inv.expected_decision, inv.expected_reason = "hold", "uom_mismatch"

    elif exception == "near_tolerance":
        # Variance sitting right within 0.5 percentage points of typical 5% threshold
        inv.lines[0].unit_price = round(inv.lines[0].unit_price * 1.054, 2)
        inv.subtotal = round(sum(l.amount for l in inv.lines), 2)
        inv.tax = round(inv.subtotal * 0.18, 2)
        inv.total = round(inv.subtotal + inv.tax, 2)
        inv.expected_decision, inv.expected_reason = "hold", "near_tolerance"

    elif exception == "multi_exception":
        # Combines price variance + short shipment + tax error
        inv.lines[0].unit_price = round(inv.lines[0].unit_price * 1.20, 2)
        receipt["lines"][0]["quantity_received"] = max(0, inv.lines[0].quantity - 2)
        inv.subtotal = round(sum(l.amount for l in inv.lines), 2)
        inv.tax = round(inv.subtotal * 0.18, 2)
        inv.total = round(inv.subtotal + inv.tax + 15.00, 2)
        inv.expected_decision = "hold"
        inv.expected_reason = "multi_exception"
        inv.expected_exceptions = ["price_variance", "short_shipment", "tax_error"]

    elif exception == "extraction_hostile":
        inv.is_hostile = True
        inv.expected_decision = "auto_approve"

    return inv, {"po": po, "receipt": receipt}


def as_text(inv: Invoice) -> str:
    """The 'raw' invoice text seen by the agent."""
    if inv.is_hostile:
        # Generates awkward/noisy visual layout
        header = f"*** INVOICE DETAILS ***\nVendor: {inv.vendor.upper()} | Date: {inv.date}\nRef PO: {inv.po_number}\n"
        body = "\n".join(
            f"ITEM> {l.sku} | QTY: {l.quantity} {l.uom} @ {l.unit_price} USD -> TOTAL: {l.amount}"
            for l in inv.lines
        )
        footer = f"\n[SUMMARY]\nSUB-TTL: {inv.subtotal}\nTAX: {inv.tax}\nAMOUNT DUE: {inv.total}"
        return f"{header}\n{body}\n{footer}\n--- PAGE 1 OF 1 ---"

    body = "\n".join(
        f"  {l.sku:<10} {l.description:<28} {l.quantity:>4} {l.uom:<3} x "
        f"{l.unit_price:>10.2f} = {l.amount:>12.2f}"
        for l in inv.lines
    )
    return (
        f"INVOICE\nVendor: {inv.vendor}\nInvoice No: {inv.invoice_no}\n"
        f"Date: {inv.date}\nPO Reference: {inv.po_number}\n"
        f"Currency: {inv.currency}\n\nLine Items:\n{body}\n\n"
        f"Subtotal: {inv.subtotal:.2f}\nTax (18%): {inv.tax:.2f}\n"
        f"Total Due: {inv.total:.2f}\n"
    )


def main(n: int = 150, seed: int = 4242):
    random.seed(seed)
    Faker.seed(seed)

    OUT.mkdir(parents=True, exist_ok=True)
    EVALS_DIR.mkdir(parents=True, exist_ok=True)

    # Build exact quota list according to STRATA definitions
    target_strata = STRATA.copy()
    if sum(target_strata.values()) != n:
        print(f"Warning: STRATA total ({sum(target_strata.values())}) != n ({n}). Adjusting proportionally.")

    all_exceptions = []
    for stratum_name, count in target_strata.items():
        all_exceptions.extend([stratum_name] * count)
    
    random.shuffle(all_exceptions)

    invoices, pos, receipts = [], [], []
    tenants = ["acme-corp", "globex-ltd"]

    for i, exc in enumerate(all_exceptions):
        inv, refs = build(i, exc, random.choice(tenants), invoices)
        invoices.append(inv)
        pos.append(refs["po"])
        receipts.append(refs["receipt"])

        txt_file = OUT / f"{inv.invoice_id}.txt"
        txt_file.write_text(as_text(inv), encoding="utf-8")

    # Write source raw JSON files
    (OUT / "invoices.json").write_text(
        json.dumps([asdict(i) for i in invoices], indent=2, default=str),
        encoding="utf-8",
    )
    (OUT / "purchase_orders.json").write_text(
        json.dumps(pos, indent=2), encoding="utf-8"
    )
    (OUT / "goods_receipts.json").write_text(
        json.dumps(receipts, indent=2), encoding="utf-8"
    )

    # --- Perform Stratified-Proportional Split (2:1 dev/held_out) ---
    by_stratum = {}
    for inv in invoices:
        by_stratum.setdefault(inv.seeded_exception, []).append(inv)

    dev_set, held_out_set = [], []

    for stratum_name, items in by_stratum.items():
        random.shuffle(items)
        dev_count = round(len(items) * (2 / 3))  # 66.6% to dev, 33.3% to held-out
        
        dev_set.extend(items[:dev_count])
        held_out_set.extend(items[dev_count:])

    def format_eval_item(inv: Invoice) -> dict:
        return {
            "invoice_id": inv.invoice_id,
            "tenant_id": inv.tenant_id,
            "path": str(OUT / f"{inv.invoice_id}.txt"),
            "seeded_exception": inv.seeded_exception,
            "expected_decision": inv.expected_decision,
            "expected_exceptions": inv.expected_exceptions,
            "expected_tools": ["lookup_po", "lookup_receipt"],
            "truth_fields": {
                "vendor": inv.vendor,
                "invoice_no": inv.invoice_no,
                "po_number": inv.po_number,
                "total": inv.total,
                "subtotal": inv.subtotal,
                "tax": inv.tax,
            },
        }

    dev_eval_data = [format_eval_item(i) for i in dev_set]
    held_out_eval_data = [format_eval_item(i) for i in held_out_set]

    (EVALS_DIR / "dev.json").write_text(
        json.dumps(dev_eval_data, indent=2), encoding="utf-8"
    )
    (EVALS_DIR / "held_out.json").write_text(
        json.dumps(held_out_eval_data, indent=2), encoding="utf-8"
    )

    print(f"Successfully generated {len(invoices)} invoices!")
    print(f"  Dev split: {len(dev_eval_data)} items -> {EVALS_DIR / 'dev.json'}")
    print(f"  Held-out split: {len(held_out_eval_data)} items -> {EVALS_DIR / 'held_out.json'}\n")
    
    print("Stratum distribution across splits:")
    for stratum_name in STRATA:
        dev_c = sum(1 for i in dev_set if i.seeded_exception == stratum_name)
        ho_c = sum(1 for i in held_out_set if i.seeded_exception == stratum_name)
        print(f"  {stratum_name:<20} total: {dev_c + ho_c:<3} | dev: {dev_c:<2} | held_out: {ho_c:<2}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate stratified eval dataset.")
    parser.add_argument("--n", type=int, default=150, help="Total dataset size")
    parser.add_argument("--seed", type=int, default=4242, help="Random seed")
    args = parser.parse_args()

    main(n=args.n, seed=args.seed)