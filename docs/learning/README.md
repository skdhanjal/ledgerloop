# LedgerLoop — Study Companion

A day-by-day learning log kept alongside the code. The [master build document](../LedgerLoop_Master_Build_Document.md) is the technical source of truth for *what* to build; this folder is where *why it works* and *what it means* gets explained in depth, so the repo can be understood independently of any chat history.

Two running references sit alongside the day files:

- [`GLOSSARY.md`](GLOSSARY.md) — every LedgerLoop/tech-stack term introduced, indexed by day.
- [`CLAUDE_CODE_GUIDE.md`](CLAUDE_CODE_GUIDE.md) — a separate track for Claude Code and coding-agent concepts themselves, written to transfer to *future* projects, not just this one.

Each day's file also has a **"Verify it yourself"** section — real, copy-pasteable commands with expected output, so you can confirm what got built without taking any report on faith — and ends with a "check your understanding" section. Use both before moving on.

## Index

| Day | Phase | Title | Status | Summary |
|---|---|---|---|---|
| [01](day-01-graph-runtime-monorepo-terraform-bootstrap.md) | P0 | Environment, Monorepo, Graph Runtime vs Agent Harness & Terraform Bootstrap | ✅ done | Repo scaffolded, whole Python dependency graph locked in one shot, GCP project + Terraform state backend created, reusable Cloud Run module written (not yet used) |

*(rows append here as each day completes)*
