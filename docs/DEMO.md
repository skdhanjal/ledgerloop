# Demo script - LedgerLoop v1 (4 minutes)

Three moments. Nothing else. Anyone can show a happy path.

## 1. It works (60s)
    uv run python bench_v1.py
Show the table. Point at the two amber rows in BENCH.md - lead with what got
worse. It buys more credibility than the accuracy number.

## 2. It pauses for a human, and the edit re-runs policy (90s)
    uv run python approve_cli.py "acme-corp:acme-corp_004" --action show
Read the payload aloud: decision, reason, the investigator's evidence,
allowed_actions. Note what is absent - no raw invoice text, because it holds
bank details.

    uv run python approve_cli.py "acme-corp:acme-corp_004" --action edit --set total=4200.00
Show that it HOLDS AGAIN. The human supplied better input, not a better
decision - the policy function still ran. This is the moment auditors care
about.

## 3. It survives being killed (90s)
    uv run python chaos_drill.py --phase crash      # process dies mid-run
    uv run python chaos_drill.py --phase resume     # different process
Point out that intake and extract did not re-run, and that this is a different
process reading state from Postgres.

## Then say the honest part
"Durable execution guarantees the graph makes progress, not that side effects
happen once. post_to_erp is not idempotent yet - a crash between the ERP write
and the checkpoint commit would double-pay. That is Day 19."
