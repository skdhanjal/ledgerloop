# Updating the baseline

The baseline is a claim about how good the system is. Changing it is a
decision, not a chore.

## Rules
1. The baseline is updated in the SAME PR as the change that moves it.
   A separate "update baseline" PR is how a regression gets laundered.
2. The PR description must say WHICH metric moved, by how much, and why.
3. A baseline that goes DOWN needs an explicit reason. "The eval got harder"
   is valid. "It was failing CI" is not.
4. Never add `continue-on-error: true`. If the gate is wrong, fix the gate
   (in a PR that says so) or fix the threshold - both are reviewable.

## Ritual
    uv run python -m evals.run_eval --split dev --model local --json out.json
    uv run python -m evals.gate --current out.json --update-baseline
    git add evals/baseline.json
    # then paste the printed delta into the PR body

The first pin was made in Build 22.4 from a clean tree. Every pin after
that goes through --update-baseline, which prints the delta it is about
to write. If that command prints nothing, you are re-pinning an identical
run and the commit is noise - drop it.

## Quarantine
A check that fails intermittently for reasons unrelated to the change goes
to `evals/quarantine.txt` with a date and an owner. Quarantined checks still
RUN and still report - they just do not block. Anything quarantined for more
than 14 days gets fixed or deleted; a permanent quarantine list is the same
as no gate.
