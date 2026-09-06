# The Claude Code Guide

This is the second study track for this project — not about LedgerLoop's tech stack (that's `GLOSSARY.md` and the day files), but about **Claude Code and coding agents in general**, so the skill transfers to whatever you build next. It starts with the fundamentals that were already in use before this file existed, then grows one entry per feature, added the day it's first deliberately used.

Each entry answers four questions: what is it, what problem does it solve, how was it used *here*, and — the part that matters for future projects — **when should you reach for it again**.

---

## Fundamentals

Before any named "feature," some basic things have been true since the very first message of this project. They're worth naming explicitly, because they were used, not explained.

### The agent loop: a model that can call tools

At its core, Claude Code is a language model wired up to a fixed set of **tools** — functions it can call: read a file, edit a file, run a shell command, search the web, spawn another instance of itself, and so on. The model doesn't just generate text; on each turn it can choose to call one or more tools, see their real results, and decide what to do next. This repeats — model reasons, calls a tool, reads the result, reasons again — until it decides the task is done and produces a final response. This is the same fundamental shape as LangGraph's ReAct loop (see the LangGraph entry in `GLOSSARY.md`) — which is itself worth noticing: **the thing being built (LedgerLoop's investigator) and the thing doing the building (Claude Code) are the same pattern at different layers.**

### The core tools used so far

- **`Bash`** — runs real shell commands (`git`, `uv`, `gcloud`, `terraform`, `docker`) and returns real output. Every "done when" check in this project has been verified by actually running it here, not by reasoning about what it would probably show.
- **`Read` / `Edit` / `Write`** — file operations, kept deliberately separate from raw shell commands (`cat`, `sed`, `echo >`) because they give a structured diff and a safety check: `Edit` refuses to touch a file that hasn't been `Read` first in the same session, which prevents a class of "I edited a file I never actually looked at" mistakes.
- **git, through the agent** — commits, diffs, and log inspection all happen through the same tool loop, not a separate mechanism. That means every commit made in this project has a real diff you can inspect after the fact.

### The permission/approval model

Not every tool call happens silently. Actions that are hard to reverse or that touch the outside world (creating a GCP project, running a destructive command, pushing to a remote) are things the harness can be configured to pause on for human approval — the exact boundary depends on the permission mode in use for a given session. The principle underneath it, regardless of mode, is: match the blast radius of an action to how much scrutiny it gets. Reading a file is cheap to get wrong; creating a billing-linked cloud project is not, which is why Day 1 confirmed each GCP step's result before moving to the next rather than firing off a long unattended sequence.

### Plan Mode

**What it is.** A distinct operating mode where the agent is restricted to read-only actions plus edits to a single scratch file (a "plan" document), and must get explicit human approval before doing anything else. Entering plan mode, doing research, writing a plan, and calling `ExitPlanMode` for approval is a full, separate cycle from actually executing that plan.

**What problem it solves.** Left unconstrained, an agent asked to "build X" will often start editing files immediately, discovering requirements as it goes — which means by the time you notice a wrong assumption, there's already code (and maybe cloud resources) built on top of it. Plan mode forces the *thinking* to happen and be reviewed *before* the *acting* does, when a correction costs a sentence instead of a rewrite.

**How it was used here.** Twice on Day 1 alone. First, to work out the whole multi-week execution approach — cadence, which GCP project to use, how to handle model spend — as a single reviewable document, before any file existed. Second, immediately after your feedback that a chat summary wasn't good enough: rather than just apologizing and writing a better summary, the fix itself went through plan mode again, so the *new* process (this file, the per-day template) was something you approved in writing before it started shaping every subsequent day.

**Reach for this when (future projects):** the task has real ambiguity in *how* to approach it (not just *what* the end state should be), or when getting it wrong would be expensive to unwind — a new project's architecture, a migration strategy, anything touching money or infrastructure. Skip it for small, obviously-reversible changes, where the ceremony costs more than the mistake would.

---

*(New entries append below as each feature gets used for the first time — see the Claude Code feature map in the execution plan for the anticipated order.)*
