### v0 baseline — 1/7 correct

| Invoice | Seeded | Expected | Actual | Time | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `acme-corp_000` | clean | auto_approve | hold | 6.6s | MISS |
| `acme-corp_001` | duplicate | reject | hold | 2.9s | MISS |
| `acme-corp_002` | clean | auto_approve | hold | 6.1s | MISS |
| `acme-corp_003` | clean | auto_approve | hold | 2.9s | MISS |
| `acme-corp_004` | price_variance | hold | hold | 5.7s | OK |
| `acme-corp_005` | clean | auto_approve | hold | 5.4s | MISS |
| `acme-corp_006` | clean | auto_approve | hold | 5.6s | MISS |


## hand-built loop vs create_agent

| implementation | policy acc | investigated | agent agreed | unparsed | wall clock | per invoice |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| handbuilt | 10/20 | 3 | 1/3 | 0 | 8.4s | 0.4s |
| harness | 10/20 | 3 | 2/3 | 0 | 8.7s | 0.4s |


# BENCH.md

## v1 - Phase 2 complete (Day 12)

Same 20 generated invoices, seed=42. Model: <your model id>.
Checkpointer: Postgres, durability="sync". Store: Postgres + fastembed.

| metric                         | v0      | v1      | delta   |
|--------------------------------|---------|---------|---------|
| decision accuracy              |  75%    |  90%    | +15pp   |
| invoices requiring a human     |   0     |   8     | +8      |
| wall clock per invoice         |  4.1s   |  6.8s   | +66%    |
| model calls per invoice        |  2.4    |  3.9    | +63%    |
| cost per APPROVED invoice      |  <fill> |  <fill> |         |
| checkpoint bytes per invoice   |   -     |  <fill> |         |
| crash-resume success (20 kills)|   -     |  20/20  |         |
| extraction failures (degraded) |   -     |  <fill> |         |

### What got better
- Real extraction replaced regex: handles layouts the generator never produced.
- Nothing crashes. Validation failures degrade to a held invoice with a reason.
- Survives a restart at any node. 20/20 kill tests resumed cleanly.
- Vendor memory: second invoice from a known vendor recalls prior resolutions.
- Every decision that moves money is still a Python function, not a model.

### What got WORSE (and why I accepted it)
- **66% slower per invoice.** Real extraction is a model call; sync durability
  adds a write per super-step. Accepted: an unrecoverable double payment costs
  more than 2.7 seconds.
- **63% more model calls.** Extraction + occasional summarization. Accepted for
  now; Day 21 routes cheap work to a local model and Day 28 targets a 40% cut.
- **Time-to-completion is now days, not seconds** for 8 of 20 invoices. That is
  the feature, not a regression - but it creates a new failure mode: a paused
  thread nobody ever returns to. No reminder mechanism exists yet.

### Known gaps at v1
- `post_to_erp` is not idempotent. A crash between the write and the commit
  double-pays. Stub today; Day 19 fixes it properly.
- `thread_id` is trusted input. Anyone holding one can read/resume that thread.
  Day 26 closes it with auth-derived scoping.
- No eval suite beyond decision accuracy. Explanation quality is unmeasured.
  Day 22.

### Decisions carried forward
- D-001 (graph vs harness) resolved on Day 7 - see DECISIONS.md.
- Reading-vs-document validator boundary (Day 8) is the subtlest call so far.
