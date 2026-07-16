# gateflow

A portable build-discipline plugin for Claude Code. It carries the **method** — a five-gate build
process, concept-first reporting, diagram-first design, and an orchestrator/worker split — so it
travels to every repo and machine. Each repo supplies only its own **content** (project facts, how to
run it, permissions, memory).

## What's in it

**Always-on norms** (injected each session by a `SessionStart` hook, `NORMS.md`): report
concept-first, diagram a design before building on it, surface choices as "DEFAULT: X because Y", no
scaffolding ahead, numbers carry lifecycle classes, no commits unless asked.

**Skills** (namespaced — plugin skills always are):
- `/gateflow:step <id> [--full | --auto]` — run one build step through all five gates at a chosen
  supervision level. Default is **plan-then-go** (stop after gate 1 for the user to approve the rows +
  defaults, then run to completion). `--full` also stops after gate 4. `--auto` never stops and
  strengthens gate 4 into a multi-reviewer + adversarial-verify workflow.
- `/gateflow:gate1` — author the contract (rows citing docs + the "DEFAULT: X because Y" list), stop.
- `/gateflow:gate3` — reconcile every row against the code, emit the three-view report + buckets.
- `/gateflow:checkpoint` — persist the step into memory + the deferred/stub registers.

**Agents:**
- `gateflow:implementer` (Opus) — implements one phase, test-first; carries the norms + conformance
  rule; reads THIS repo's `## Run & ops` for launch discipline.
- `gateflow:gate4` (Opus, read-only) — adversarial fresh-eyes review, no build context.
- `gateflow:digest` (Sonnet) — bulk reads returned as structured digests.

## What each repo must supply (the binding)

The plugin is domain-neutral. A repo that uses it provides:

1. **A `## Run & ops` section** in its `CLAUDE.md` (or a doc it points at): the durable/background
   runner, absolute-path rules, the resource-peak statement required before a heavy launch, pre-flight
   idle/contention checks, build-freshness rules, and how results are harvested. `gateflow:implementer`
   reads this verbatim; if it's missing, the agent asks rather than improvising a launch.
2. **A run skill** (optional but recommended) — the local equivalent of a `/run` command, e.g. a
   `/<repo>-run` that wraps the durable runner. Referenced from `## Run & ops`.
3. **Design docs** with cite-able section headings (gate 1 authors rows against them).
4. **A build-state memory** with a deferred register + a stub register (`/gateflow:checkpoint` maintains
   them).
5. **A permission allowlist** in `.claude/settings.local.json` for its own tools.

A `CLAUDE.md` pointer — "build steps run through `/gateflow:step`; a plain-English 'do step X' should
route through it" — makes a cold session pick up the workflow without being told.

## Install

**Local test (this machine, no marketplace):**
```bash
claude --plugin-dir /path/to/gateflow
```

**Across machines (the intended path):** push this directory as a git repo (a private GitHub repo is
fine), then on each machine:
```bash
/plugin marketplace add <github-user>/gateflow
/plugin install gateflow@gateflow
```
Update everywhere by pushing a new version and re-running `/plugin install`.

## Verify on first install (recalled-from-docs — smoke-test these)

- **The SessionStart hook fires and injects `NORMS.md`.** Start a session with the plugin enabled and
  confirm the norms appear in context. If `${CLAUDE_PLUGIN_ROOT}` isn't the right variable on your
  version, adjust the `hooks/hooks.json` command (a `printf` of the text inline also works).
- **`/gateflow:step` resolves** and dispatches `gateflow:implementer` / `gateflow:gate4` /
  `gateflow:digest` by their scoped names.
- **The hook path** (`hooks/hooks.json` at plugin root) is where your Claude Code version expects it.

## Provenance

Distilled from the PACER project's five-gate build process and orchestrator-mode working norms
(2026-07). PACER is the reference consumer; see its `CLAUDE.md` `## Run & ops` for a worked example of
the repo-side binding.
