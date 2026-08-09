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

## v3 - Phase 4 complete (Day 24)

### Reliability
| property | evidence |
|---|---|
| Crash recovery | 20/20 threads resumed cleanly (`kill_test.py`) |
| Exactly-once posting | money test: kill after ERP write -> `count: 1` |
| Corrected amount re-posts | different idempotency key, verified |
| Transient failure handling | retry on transient only; business rejections never retried |
| Node timeouts | `run_timeout` on posting, `idle_timeout` on streaming nodes |
| Degraded paths | extraction, investigation, posting all degrade to a held invoice |

### Evaluation
| property | value |
|---|---|
| Dataset | 150 stratified, constructed truth, 100 dev / 50 held-out |
| Deterministic evaluators | extraction, decision, exceptions (P/R), grounding, trajectory |
| Judge calibration | kappa <fill> on 50 hand-labelled items |
| Measured noise floor | <fill> pp (5 runs, same commit, local model) |
| CI gate | hard gates every push; full eval nightly; held-out at release |
| Smallest detected regression | <fill> pp |

### Security
| property | evidence |
|---|---|
| **Decision unreachable by model output** | `test_policy_signature_takes_no_model_output` |
| **Injection -> auto_approve rate** | 0 / 12 injection stratum cases |
| Tool surface | 4 read-only tools, allowlist enforced in middleware |
| Argument validation | shape-checked; traversal and oversized args blocked |
| Tenant isolation | store namespaces tenant-first, tested |
| PII in stream events | 0 (walked every key of every event) |
| Secrets in message channel | redacted at the tool boundary |

### Still open at v3
- `thread_id` is trusted input - anyone holding one can read/resume (Day 26)
- No rate limiting or abuse controls on the API surface (Day 26)
- Injection detection is best-effort; containment is the guarantee

