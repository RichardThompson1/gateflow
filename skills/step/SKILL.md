---
name: step
description: Run one build step through the five gates at a chosen supervision level. Usage: /gateflow:step <step-id> [--full | --auto] (default = plan-then-go). Use when starting or resuming a defined build step.
---

# /gateflow:step — one build step, five gates, chosen supervision

Runs ONE build step through the five-gate process. The gates always RUN. The supervision level only
decides **where you stop and show the user.**

## Args

`/gateflow:step <step-id> [--full | --auto]`

| Level | Flag | Stops at |
|---|---|---|
| Full | `--full` | after gate 1 (rows + defaults), **and** after gate 4 (findings) |
| **Plan-then-go** | *(default)* | after gate 1 only — user approves the plan, then run to completion |
| Auto | `--auto` | nothing. Show the gate-1 rows for the record, keep going. |

**Every level aborts to the user** on: a gate failure, a third failed implementation attempt, a
default the brief did not anticipate, a suite regression, or anything destructive/irreversible.
"Unattended" means *don't narrate* — never *don't stop when something is wrong*. State the level in
your first message so the user knows whether to walk away.

## The sequence

### Gate 1 — contract
Invoke `/gateflow:gate1` for `<step-id>`: the contract rows (each citing its design-doc section) and
the **"DEFAULT: X, because Y"** list.
- `--full` / default: **present both and STOP.** This is the cheap intervention point.
- `--auto`: present them, note you are proceeding, continue.

### Gate 2 — implement, phase by phase
For each phase, dispatch **subagent_type `gateflow:implementer`** (always this one — do not pick by
judgment). The brief is *only* the phase's contract rows, the read-first list, locked schemas, and
the venue. The agent carries the norms, conformance rule, reporting format, and reads THIS REPO's
`## Run & ops` section for launch discipline — **do not re-type those.**

**Review every phase diff yourself before dispatching the next phase — at every supervision level.**
Read the actual diff, not the agent's summary. Heavy/integration runs go through the repo's run
discipline (its `## Run & ops` section or run skill); verify the implementer used it.

### Gate 3 — reconciliation
Invoke `/gateflow:gate3`: every row walked against the code with `file:line`, marked
done/partial/deferred/stub, then the three-view report + the real/stub/deferred buckets. No row
unreconciled.

### Gate 4 — adversarial review (fresh eyes, no build context)
- **`--full` and default:** dispatch ONE `gateflow:gate4` subagent with the doc section, the contract
  rows, and the diff. Present findings.
  - `--full`: **STOP** for the user to triage before applying.
  - default: triage yourself, apply the real ones, re-run affected suites, report what you
    applied/rejected and why in gate 5.
- **`--auto`: strengthen it.** With no human between gate 4 and gate 5, one reviewer is not enough,
  and a mode that cries wolf gets abandoned. Call the **Workflow** tool with a review workflow that
  (1) fans out several `gateflow:gate4`-style reviewers on distinct lenses (claimed-not-built,
  stubbed-as-real, doc-behavior-unhandled, shortcut-survivable tests, + a domain lens if the diff
  touches concurrency/resource-lifetime), (2) adversarially verifies each finding with independent
  skeptics prompted to REFUTE (default refuted when uncertain; survive only on majority
  non-refutation), (3) returns surviving findings ranked by severity. Apply survivors, re-run
  affected suites, report. **Interrupt the user only if** a survivor is severe enough to change the
  step's contract, or a fix fails.

### Gate 5 — report + checkpoint
Three-view report (components / behavior / agreed deliverables), each row done/partial/deferred/stub
with `file:line`, then the real/stub/deferred buckets. Then invoke `/gateflow:checkpoint`. **Do not
commit** — tell the user the tree is ready; they commit.

## Standing rules
Both suites green before gate 5. Numbers carry lifecycle classes; per-unit deltas cite a baseline.
No scaffolding ahead, no third-party-source edits, no commits.
