# Day 1 — Environment, Monorepo, Graph Runtime vs Agent Harness & Terraform Bootstrap

**Phase:** P0 Foundations · **Components:** C18 (Infrastructure as code) · **Commit:** `f22d4f3`

## What we built

Nothing that *runs* yet — Day 1 is entirely scaffolding, and that's intentional. Concretely:

1. A git repository at `~/projects/ledgerloop` with a **monorepo layout**: separate top-level folders for the agent backend (`agent-service/`), the web frontend (`frontend/`), the LLM gateway (`litellm-proxy/`), infrastructure code (`infra/`), evaluation code (`evals/`), and generated data (`data/`) — even though only `agent-service/` and `infra/` have real content so far.
2. A Python project inside `agent-service/`, managed by `uv`, with **every third-party library the whole 30-day build will ever need** already declared and version-locked — not just the ones Day 1 happens to use.
3. A lint rule that will **fail the build** the moment any code tries to import an LLM provider's SDK directly (`openai`, `google.generativeai`, etc.) — put in place before there's any code that could violate it.
4. A brand-new, dedicated Google Cloud project (`ledgerloop-880ac9`), with billing attached and a spend alert configured, plus the two pieces of cloud infrastructure Terraform will ever create by a human typing commands directly (a state bucket and a container registry) — everything else Terraform creates from here on.
5. A reusable Terraform "recipe" for deploying a container to Cloud Run — written now, used by nobody yet.

## Concepts introduced

### 1. LangGraph vs. `create_agent` — a runtime and a harness built on it

**The problem this solves.** Most "build an AI agent" tutorials give you a single loop: ask the model what to do, run whatever tool it picked, feed the result back, repeat until it says it's done. That works for a chatbot. It does not work for an accounts-payable system, because AP needs things a simple loop structurally cannot express:

- **Wait for a human for days**, then continue exactly where it left off — even across a server restart.
- **Split into N parallel branches** (one per invoice line item) where N isn't known until the invoice is read, then wait for *all* of them before continuing.
- **Guarantee a payment decision never depends on anything a language model produced** — not even indirectly.

**LangGraph** is a low-level runtime built to make these possible. You describe your system as a graph: a set of named *nodes* (plain Python functions) connected by *edges*, operating over a shared *state* object. LangGraph executes this in **super-steps** (this comes from a Google research paper on large-scale graph processing called Pregel, hence "Pregel-style"): in each super-step, every node that's currently "active" runs, and whatever changes they produce are combined and committed together before the next super-step begins. Because every super-step's state gets **checkpointed** (saved to a database), the whole execution is durable — you can kill the process mid-run and resume from the last completed super-step, which is exactly the property "wait for a human for three days" needs.

**`langchain.agents.create_agent`** is a different, higher-level thing: a *pre-built* graph, already wired up as the classic "reason → call a tool → look at the result → repeat" loop (this pattern is called **ReAct**, short for Reason+Act). Under the hood it's *built using* LangGraph — it's not a competing technology, it's a harness sitting on top of the runtime. You reach for it exactly when a plain tool-calling loop is genuinely all you need, because then you get retries, structured output, and "middleware" hooks for free instead of re-implementing them.

**Why this matters for LedgerLoop specifically:** most of the *pipeline* (intake → extract → match → decide → post) needs the raw graph, because it has the parallel-fan-out and durable-pause requirements above. But the "investigate this exception" step, later in the build, is genuinely just a tool-calling loop — and that's where `create_agent` will get used instead of hand-rolling the same loop ourselves. Day 1 doesn't build either yet; it just makes sure the dependency (`langgraph` *and* `langchain`, not one or the other) is available for both.

### 2. Why the *whole* dependency graph gets locked today, not incrementally

The instinct when starting a new project is "just install what I need right now, add more later." That's the wrong call here, for a specific, learnable reason: **Python dependency resolution is a constraint-satisfaction problem across your *entire* installed set, not per-package.** If you install package A today and package B in week three, and it turns out some deep transitive dependency of B conflicts with a version of a library A already pinned, you don't find out until week three — often as a mysterious runtime error that has nothing to do with the code you just wrote.

So instead, Day 1 declares every library the doc says the whole 30-day build will need — `langgraph`, `langchain`, `fastapi`, `psycopg` (Postgres driver), `fastembed` (embeddings), `faker` (fake data), and so on — all in one `uv add` command, and lets `uv` resolve them **together**. That resolution either succeeds cleanly (as it did: **89 packages, zero conflicts**) or fails loudly *today*, when a conflict costs ten minutes to fix instead of a lost afternoon in week four.

**The lockfile (`uv.lock`)** is the output of that resolution: it pins the exact version of every package, direct and transitive (a dependency of a dependency). Committing it means anyone who clones this repo and runs `uv sync` gets the *identical* environment — not "whatever the latest compatible version happens to be today."

**Upper-bounded ranges** (e.g. `"langgraph>=1.2.11,<1.3"`) are the other half of this discipline. A bare `>=1.2.11` would let a routine `uv sync` months from now silently jump to `langgraph 1.4.0` if that's released — and a major runtime like LangGraph can change how checkpoints or interrupts behave between versions. The `<1.3` ceiling means any such upgrade has to be a *deliberate*, single-package action (`uv lock --upgrade-package langgraph`), never an accident of routine syncing.

### 3. The gateway-guard lint rule — enforcing an architecture decision in code, not in a code-review checklist

LedgerLoop's design (not yet built, but already decided) requires that **no service ever talks to OpenAI or Google directly** — every model call has to go through a self-hosted gateway (coming Day 4), so that spend, rate limits, and provider fallback are controlled in exactly one place instead of scattered across every service's config.

The naive way to enforce that is "remember not to do it" or "catch it in code review." Both fail eventually — someone under deadline pressure imports `openai` directly to unblock themselves, and it ships. Instead, Day 1 adds a `ruff` rule (`flake8-tidy-imports` banned-api, rule code `TID251`) that makes `import openai` anywhere in the codebase **a build failure**, with a message explaining why. I proved this actually works rather than just writing it and hoping — I wrote a throwaway file with `import openai` in it, ran the linter, and watched it fail with exit code 1 and the exact message: *"Call the LiteLLM gateway, never a provider SDK directly."*

This is a small example of a bigger pattern that recurs throughout this build: **turn an architectural rule into an automated, unbypassable check**, rather than trusting anyone (including future-me) to remember it. The policy engine's "never see model output" rule (Day 5) and the tool-allowlist-matches-registry rule (Day 16) both work the same way.

### 4. Terraform, state, and why a bucket exists before any real resource does

**Terraform** lets you describe cloud infrastructure as code — instead of clicking through the GCP console to create a database, you write a `.tf` file describing the database you want, and Terraform computes what needs to change and applies it. The payoff: the *entire* infrastructure of the system can be recreated from scratch, by anyone, by running one command against an empty project — nothing depends on someone remembering which console buttons they clicked eighteen months ago.

To do that diffing (what exists vs. what should exist), Terraform needs to remember what it created last time — that record is called **state**. If state lived only on a laptop's disk, two people (or one person from two machines) could clobber each other's changes, and losing the laptop means losing the ability to safely manage the infrastructure at all. So state gets stored in a **backend** — here, a Google Cloud Storage bucket (`gs://ledgerloop-880ac9-tfstate`), created with versioning turned on so even a bad state write can be rolled back.

That bucket, plus a place to store built container images (**Artifact Registry**), are the **only two things ever created by a human typing a command directly** in this entire project. Everything else — the database, the Cloud Run services, the networking — gets created *by Terraform*, described in `.tf` files, from Day 4 onward. Day 1 proves the wiring works by running `terraform init` (which connects Terraform to that backend) and `terraform plan` (which computes a diff) against the real bucket, and confirming the diff is empty — **zero resources exist yet, and that's correct**, not a sign anything is missing, because nothing in the build needs a database or a running service yet.

### 5. Terraform modules — writing the recipe before there's a reason to use it

A **module** is a reusable, parameterized bundle of resource definitions — think of it like a function, but for infrastructure: it takes inputs (image, environment variables, how many instances, a service identity) and produces a resource (here, a Cloud Run service). LedgerLoop needs **three** near-identical Cloud Run services eventually (the agent backend, the frontend, and the LLM gateway) — same shape, different image and config each time.

Day 1 writes that module (`infra/modules/cloud-run/`) but **instantiates it zero times** — nothing calls it yet. This is deliberate, not premature: the doc's whole infrastructure philosophy is "provision each resource on the day that first needs it," and *writing* a reusable pattern early is exactly what prevents three separate, slowly-diverging copies of "how do I deploy a container" from appearing on Days 4, 9, and 27 as each service gets built. The module gets its first real caller on Day 4 (the gateway) and its remaining two on Day 27.

## Design decisions made today

Full raw entries live in [`../DECISIONS.md`](../DECISIONS.md); the reasoning behind each, spelled out:

**A new GCP project, not the one already active on this machine.** The `gcloud` CLI here was already configured against an unrelated project (`sentinel-desk-dev`) from other work. Reusing it would have mixed LedgerLoop's billing, IAM, and eventual audit trail with something unrelated — and one of this system's own design principles (tenant isolation, Day 26) is exactly "don't let unrelated things share a blast radius." So a fresh project (`ledgerloop-880ac9`) was created, billing was linked explicitly, and a **$20/month budget alert** (firing at 50/90/100% spend) was set up on Day 1 itself — three days earlier than the doc's own "watch the bill from Day 9" reminder, because the risk of an unexpected charge starts the moment a project can spend money, not the moment the first expensive resource exists.

**The Python package is called `ledgerloop`, the directory is called `agent-service`.** These are deliberately different things. The *directory* name matches the monorepo layout the whole doc uses (`agent-service/`, `frontend/`, `litellm-proxy/`) because that's what Terraform and deployment tooling key off of. The *importable package* inside it is named `ledgerloop` because every command in the master doc invokes it that way (`python -m ledgerloop.cli`, `ledgerloop.data.generate`, etc.) — matching the doc's own naming saves translating every future command by hand.

**`langchain-openai` is a real dependency; `langchain-google-genai` isn't.** This one's worth understanding because it looks contradictory at first glance. Once the gateway (Day 4) exists, it will expose one unified endpoint that *speaks the OpenAI wire protocol* regardless of which real provider (OpenAI or Google) is actually answering behind it. The standard way to call an OpenAI-protocol endpoint from LangChain is the `ChatOpenAI` class from the `langchain-openai` package, pointed at a custom `base_url` — that's calling *our own gateway*, not OpenAI, so it doesn't violate the "never call a provider directly" rule from concept #3 above. Since *every* tier talks through that same OpenAI-shaped door, there's never a call site anywhere in `agent-service` that needs Google's own client library — that concern is entirely the gateway's, invisible to everything calling it.

## Code walkthrough

**`agent-service/pyproject.toml`** — the project manifest. The key section:

```toml
[project]
name = "ledgerloop"
...
dependencies = [
    "faker>=40.38.0,<41",
    "fastapi>=0.141.1,<0.142",
    "langgraph>=1.2.11,<1.3",
    "langchain>=1.4.0,<2",
    ...
]
```
Every entry is a floor-and-ceiling range (concept #2 above), not a bare minimum. The `[tool.ruff.lint.flake8-tidy-imports.banned-api]` section at the bottom is the gateway guard (concept #3):
```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"openai".msg = "Call the LiteLLM gateway, never a provider SDK directly (C10)."
```

**`agent-service/scripts/check_versions.py`** — a small script that doesn't trust "I asked for version X," it checks "what actually got installed," via Python's `importlib.metadata`. This matters because a *range* like `<1.3` could still resolve to several different patch versions over time; this script is what Day 28's CI will run on every commit to catch drift loudly instead of silently.

**`agent-service/src/ledgerloop/`** — the package skeleton: empty subpackages (`graph/`, `data/`, `policy/`, `tools/`, `stubs/`, `api/`, `guardrails/`, `evals/`, `bench/`) that mirror the pipeline's own architecture (C1–C20). Nothing lives in them yet — Day 2 puts the first real code in `graph/` and `data/`.

**`infra/modules/cloud-run/`** — three files: `variables.tf` (the module's inputs — image, env vars, scaling bounds, service account, an `allow_unauthenticated` flag), `main.tf` (the actual `google_cloud_run_v2_service` resource, built from those inputs), `outputs.tf` (what the module hands back to whoever calls it — the deployed URL, service name, revision). Notice `min_instances` defaults to `0`: every Cloud Run service in this build scales to zero when idle, a deliberate cost trade-off the doc measures the latency cost of on Day 29.

**`infra/backend.tf` / `infra/providers.tf` / `infra/variables.tf`** — the root module's plumbing: which GCS bucket holds state, which GCP project and region to target, and a `project_id` variable defaulted to `ledgerloop-880ac9` so every later `terraform` command in this repo targets the right project without re-typing it.

**`infra/main.tf`** — currently just a comment block. This is the resource inventory table from the master doc (which day adds what), written directly into the file that will eventually hold those resources, so the sequencing decision is visible in the code itself, not just in a doc that could drift from what's actually there.

## Verify it yourself

Every one of these was actually run during the build — this is the same evidence, framed so you can reproduce it, not just take my word for it. Run them from `~/projects/ledgerloop` unless noted.

**1. The monorepo layout exists.**
```bash
ls
# expect: agent-service  data  docs  evals  frontend  infra  litellm-proxy
git log --oneline
# expect: the Day 1 build commit, followed by one or more learning-doc retrofit commits
```

**2. The dependency graph is locked and matches what's installed.**
```bash
cd agent-service
uv run python scripts/check_versions.py
```
Expected tail of the output:
```
version graph OK
```
If you want to see the actual lockfile contents for one package:
```bash
grep -A2 '^name = "langgraph"' uv.lock
```
Expected:
```
name = "langgraph"
version = "1.2.11"
source = { registry = "https://pypi.org/simple" }
```

**3. The gateway-guard lint rule actually fails a build — don't take this on faith, break it yourself.**
```bash
echo 'import openai' > /tmp/guard_test.py
uv run ruff check /tmp/guard_test.py
echo "exit code: $?"
rm /tmp/guard_test.py
```
Expected: a `TID251` error naming `openai` as banned, with the message *"Call the LiteLLM gateway, never a provider SDK directly (C10)."*, and **exit code 1** (a real failure, not a warning).

**4. The GCP project, billing, and budget alert are real.**
```bash
gcloud projects describe ledgerloop-880ac9 --format="value(projectId,lifecycleState)"
# expect: ledgerloop-880ac9  ACTIVE

gcloud billing projects describe ledgerloop-880ac9 --format="value(billingEnabled)"
# expect: True

gcloud billing budgets list --billing-account=01D6C8-3B6B7B-19CD26 --format="value(displayName)" | grep ledgerloop
# expect: ledgerloop-monthly
```

**5. Terraform state is real and there's genuinely nothing deployed yet.**
```bash
cd ../infra
gsutil ls gs://ledgerloop-880ac9-tfstate/
# expect: gs://ledgerloop-880ac9-tfstate/terraform/  (the state prefix `terraform init` created)

terraform plan
# expect: "No changes. Your infrastructure matches the configuration." — zero resources, and that's correct

gcloud run services list --project=ledgerloop-880ac9
# expect: an empty list — no Cloud Run service exists yet, on purpose
```

If any of these don't match, something drifted since this was written — that's worth flagging, not silently working around.

## Claude Code concept(s) used today

**Plan mode.** Full explanation lives in [`CLAUDE_CODE_GUIDE.md`](CLAUDE_CODE_GUIDE.md#plan-mode) (start there for the general concept); the LedgerLoop-specific note: it was used twice on Day 1 alone — once to work out the overall multi-week execution approach (cadence, GCP/spend decisions) before touching a keyboard, and again to redesign the operating rhythm itself after the feedback that a chat summary wasn't a substitute for something study-able. Both times, the value wasn't "get permission to write code" — it was forcing an explicit, editable, written-down plan *before* acting, so a wrong assumption (like "a chat paragraph counts as documentation") gets caught and corrected once instead of repeating across 29 more days.

## New terms

Added to [`GLOSSARY.md`](GLOSSARY.md): `uv`, lockfile, upper-bounded version pin, `src/` layout, `ruff`, banned-API lint rule, LangGraph, Pregel-style execution, `create_agent`, Terraform, Terraform state, Terraform backend, Terraform module, GCP project, Artifact Registry, billing budget alert, Cloud Run, monorepo.

## Check your understanding

1. What specifically can LangGraph's raw `StateGraph` express that `langchain.agents.create_agent` cannot, and why does LedgerLoop's *pipeline* need that while its *investigator* step (coming later) doesn't?
2. Why was the entire dependency graph locked in one `uv add` command today instead of adding libraries incrementally as each day needs them? What failure does this prevent, and when would that failure otherwise surface?
3. What does the upper bound in `"langgraph>=1.2.11,<1.3"` actually prevent, concretely — walk through what would happen without it if LangGraph released version 1.3.0 in week four.
4. The gateway-guard lint rule bans `import openai`. Why doesn't it also break the `langchain-openai` package we *did* install? What's the difference between what that package does and what a banned direct import would do?
5. Terraform state was created today (the GCS bucket), but zero actual cloud resources (databases, Cloud Run services) exist yet. Explain why that's the correct state of things on Day 1, not a gap.
6. What's the difference between the `agent-service` directory name and the `ledgerloop` package name inside it — and why are they allowed to differ?

**Answers**

1. `create_agent` is a fixed reason→act→observe loop; it can't natively express a durable multi-day pause that survives a process restart, a runtime-determined parallel fan-out with a synchronized join, or a hard guarantee that a decision node never receives model output. LangGraph's raw graph can express all three because you control the nodes, edges, and checkpointing directly. The investigator step doesn't need any of that — it's genuinely just "call tools until you have an answer," which is exactly what `create_agent` already does well.
2. It prevents discovering a transitive dependency conflict late — e.g., adding library B in week three that needs a different version of something library A (added week one) already pinned. Resolving everything together on Day 1 surfaces that conflict immediately (in minutes), instead of as a confusing runtime break weeks into the build.
3. Without the `<1.3` ceiling, a routine `uv sync` (or a fresh `uv.lock` regeneration) could pull in LangGraph 1.3.0 automatically the moment it's released, even mid-project. If 1.3.0 changed checkpoint or interrupt semantics, code written against 1.2.x could break silently, with no single commit to blame. The ceiling forces any such upgrade to be a deliberate, single-package action taken on a milestone day, with the full eval suite re-run afterward.
4. `import openai` (the raw SDK) would let code call OpenAI's actual API directly, bypassing the gateway entirely. `langchain_openai.ChatOpenAI` is a client class that speaks the *same wire protocol* but gets pointed at our own gateway's `base_url` — it's calling our infrastructure, not OpenAI's, even though the protocol looks identical. The lint rule bans the raw import specifically because that's the thing that would actually reach OpenAI's servers.
5. Terraform state and a state *backend* are about **how** Terraform remembers what it's managing — they need to exist before Terraform manages anything, the same way a filing cabinet needs to exist before you file anything in it. Day 1's pipeline (extraction, matching, policy) doesn't need a database or a deployed service yet, so creating one now would be infrastructure with nothing depending on it — exactly the anti-pattern the doc calls out ("no day provisions a resource nothing yet depends on").
6. The directory name (`agent-service`) matches the monorepo layout that Terraform and deployment tooling reference. The importable package name (`ledgerloop`) matches every CLI invocation written in the master doc (`python -m ledgerloop.cli`). Python doesn't require a package's import name to match the folder it's checked out into — only the `src/ledgerloop/` path inside that folder has to match what `pyproject.toml` tells the build backend to look for.
