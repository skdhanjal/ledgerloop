"""Stub purchase-order / goods-receipt store, backed by the generated JSON.

This is a stand-in for an ERP read API. It is deliberately a class with state
(an open dataset) rather than a module of functions, because that is what makes
it a *dependency* - the thing Day 4 is teaching you to inject rather than import.
"""
import json
from pathlib import Path

DATA = Path("data/generated")


class PurchaseOrderDB:
    def __init__(self, data_dir: Path = DATA):
        self._pos = {p["po_number"]: p
                     for p in json.loads((data_dir / "purchase_orders.json").read_text())}
        self._receipts = {r["po_number"]: r
                          for r in json.loads((data_dir / "goods_receipts.json").read_text())}

    def get_po(self, po_number: str) -> dict | None:
        return self._pos.get(po_number)

    def get_receipt(self, po_number: str) -> dict | None:
        return self._receipts.get(po_number)

    def __repr__(self) -> str:          # keeps tracebacks readable
        return f"<PurchaseOrderDB pos={len(self._pos)}>"
