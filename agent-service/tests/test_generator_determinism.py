import filecmp
from pathlib import Path

from ledgerloop.data.generate import generate

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_BASE = REPO_ROOT / "data" / "base"


def test_regeneration_is_byte_identical_to_committed_data(tmp_path):
    """The doc's literal Day 2 Done-when check, as a pytest so CI enforces it
    (from Day 28): regenerating with the same seed must reproduce the
    committed dataset byte-for-byte."""
    msg = "run the generator once and commit data/base before pinning to it"
    assert COMMITTED_BASE.exists(), msg

    generate(n_tenants=3, n_invoices=150, seed=42, out_dir=tmp_path)

    committed_files = {
        p.relative_to(COMMITTED_BASE) for p in COMMITTED_BASE.rglob("*") if p.is_file()
    }
    regenerated_files = {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file()}
    assert committed_files == regenerated_files

    mismatches = [
        str(rel)
        for rel in sorted(committed_files)
        if not filecmp.cmp(COMMITTED_BASE / rel, tmp_path / rel, shallow=False)
    ]
    assert mismatches == []


def test_two_independent_runs_match_each_other(tmp_path):
    """Same check without depending on data/base being committed yet --
    two fresh runs with the same seed must agree with each other."""
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    generate(n_tenants=3, n_invoices=30, seed=7, out_dir=out_a)
    generate(n_tenants=3, n_invoices=30, seed=7, out_dir=out_b)

    files_a = {p.relative_to(out_a) for p in out_a.rglob("*") if p.is_file()}
    files_b = {p.relative_to(out_b) for p in out_b.rglob("*") if p.is_file()}
    assert files_a == files_b
    assert all(filecmp.cmp(out_a / rel, out_b / rel, shallow=False) for rel in files_a)
