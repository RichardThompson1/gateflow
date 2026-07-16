---
name: gate3
description: Closing reconciliation for a build step — walk every contract row against the code with file:line, mark done/partial/deferred/stub, then emit the three-view report and the real/stub/deferred buckets.
---

# /gateflow:gate3 — reconciliation + the three-view report

Gates 3 and 5 in one motion: **nothing is "done" until every row is reconciled against the code**,
and the report must never let "done" imply more than was built.

## Part 1 — reconcile

Walk **every** contract row from gate 1. For each, open the code and answer with evidence:

| Status | Means |
|---|---|
| **done** | the mechanism is in the code, and a conformance test fails without it |
| **partial** | some of the row is real; say precisely which part is not |
| **deferred** | intentionally unbuilt; name the step that owns it |
| **stub** | a fake is standing in; name the real mechanism it replaces |

**Every row carries a `file:line`.** A row reconciled from memory is not reconciled — read the code.
If a row's conformance test would pass with the mechanism removed, the row is **not done** —
regardless of what the suite says.

## Part 2 — the three-view report (they catch different omissions)

**(a) Components view** — the structural pieces: what exists now that did not before?
**(b) Behavior view** — what it *does* (the invariant each piece enforces). A complete component list
can still hide a missing behavior.
**(c) Agreed scoped deliverables** — the gate-1 contract rows, verbatim. This is the only view that
describes what you *said you would build*.

Each row in each view: done / partial / deferred / stub, with `file:line`.

## Part 3 — the buckets

- **REAL** — mechanism present, conformance-tested.
- **STUB** — every fake + the real mechanism it stands in for.
- **DEFERRED** — every intentionally-unbuilt behavior + the step that owns it.

## Part 4 — suites + numbers

Both venues, pass/skip counts, and the resource peak of any heavy run. Every measured cost carries
its lifecycle class; every per-unit delta cites its baseline.

## Honesty rule

The point of this gate is that a future session can trust the word "done." If tempted to round a
partial up, don't — write the partial, and write what is missing.
