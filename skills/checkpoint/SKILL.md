---
name: checkpoint
description: Persist a completed build step — update the build-state memory, the deferred + stub registers, the step's own memory anchor, and the project status. Run at every milestone, not just at the end of an arc.
---

# /gateflow:checkpoint — make the step survive the session

Work that is not checkpointed into memory is work a future session cannot resume. Run at **every
milestone**, not only at the end of an arc.

## 1. The registers (the load-bearing part)

In the repo's build-state memory:
- **Deferred register** — every intentionally-unbuilt behavior + **the step that owns it**. Add new
  deferrals; remove anything this step actually built.
- **Stub register** — every fake + **the real mechanism it replaces**. Add new stubs; remove every
  stub this step made real.

These are how "done" keeps its meaning across sessions. A deferral that silently vanishes becomes a
phantom feature everyone assumes exists.

## 2. The build-state anchor

Update it with: what this step built, the gate-3 buckets condensed, suite counts, and **what is next**
(the resume anchor — a cold session should start from it).

## 3. The step's own memory

Append the contract rows with final status + `file:line`, the gate-4 register (findings + what was
applied/rejected and why), and the measured numbers **with lifecycle classes**. Keep the existing
anchor structure — add a section, don't rewrite the file.

## 4. Project status

Update the project status summary to what a cold session needs to orient: current step, what's done,
what's next, active gotchas.

## 5. New lessons → their own memory

A durable, transferable lesson (a gotcha that will bite again, a stance the user took, a surprising
mechanism) gets its **own memory file** with `**Why:**` and `**How to apply:**`, plus a one-line
index pointer. Lessons get recalled by name — don't bury them in the build-state blob. Distinguish
METHOD-lessons (portable, belong at the user/global level) from PROJECT-lessons (stay per-repo). Do
not save what the repo already records (code structure, git history, what a file does).

## 6. Report

Tell the user what was checkpointed, which registers changed, and that the tree is green and **ready
to commit — but do not commit.** The user commits.
