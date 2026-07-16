---
name: gate1
description: Author the gate-1 contract for a build step — one row per required behavior citing its design-doc section, plus every default stated as "DEFAULT: X, because Y" — then stop for user review.
---

# /gateflow:gate1 — the contract, before any code

Gate 1 of the five-gate process. **The contract is the definition of done.** It exists because
implementation that is never reconciled against the up-front scope ships gaps that green behavior
tests happily hide.

## 1. The contract rows

One row **per required behavior**, derived from the repo's design docs + the agreed scope. Each row:

| Field | Rule |
|---|---|
| **ID** | short + stable (it will be cited for the life of the project) |
| **Behavior** | what the system must *do*, in mechanism terms, not outcome terms |
| **Cites** | the design-doc section or `file:line` it comes from — **a row with no citation is a row you invented** |
| **Conformance sketch** | the test that fails **if the mechanism is absent** — plus the venue |
| **Status** | starts empty; gate 3 fills it |

For every sketch, apply: *would this still pass if I took a shortcut?* If yes, rewrite it. **Read the
contract doc you are authoring rows from personally — never via a digest.** Background material may go
to a `gateflow:digest` subagent.

## 2. The defaults list — the cheap intervention point

**Every** choice you intend to make, each stated as **"DEFAULT: X, because Y."** Include the plan
doc's open decisions PLUS every new choice discovered during read-in. If you would otherwise have
"just picked" it, it goes on this list. It is far cheaper for the user to veto here than to find it
baked into a mechanism three phases later.

## 3. Scope boundary

State what this step **does not** do, so its absence reads as intent. Point at the step that owns each
excluded item.

## Then stop

Present the rows, the defaults, and the scope boundary **in chat** and **wait**, unless the caller
said `--auto`. Do not write code, create files, or scaffold. Gate 1 produces a contract and nothing else.
