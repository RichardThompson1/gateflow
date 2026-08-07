# /gateflow:report — literal-language reporting filter

Applies to EVERY channel: chat replies, agent briefs, memory files, code comments, docstrings,
commit-message drafts, JSON/artifact field names. Origin: three strikes on the metaphor ban
(memory `no-metaphorical-language`, 2026-08-06/07).

## Rule

Every claim names the literal mechanism, and every claim of magnitude carries the number and its
lifecycle class (once-per-run / per-startup / per-unit-of-work) with its baseline. If a sentence
would survive with the technical content removed, delete the sentence.

## Banned terms and their replacements

| Banned | Write instead |
|---|---|
| load-bearing | "X depends on it: <which component, which behavior>" |
| seam | the named boundary: "the point in <function> where <what changes>" |
| quiet / quietly / silent(ly) as color | state what is NOT emitted: "produces no log line / no error" |
| spike | "transient increase to <value> for <duration>" |
| knee / sweet spot / inflection | "the point where <quantity> changes slope, at <value>" |
| X-shaped / "-shaped" anything | describe the actual relation between the variables |
| high-water mark | "maximum RAM occupancy during the run" (user wording, 2026-08-07) |
| weak / strong (of a model or checkpoint) | name the checkpoint and its measured success rate |
| flowery intensifiers (dramatically, massively, blazing) | the ratio or delta, with baseline |

The table is not exhaustive: the test is "is this word a figure of speech standing in for a
mechanism or a number?" If yes, replace it with the mechanism or the number.

## Reserved prefixes (identifier rule, same origin)

- `P*` names PACER schedules only. `S*` names the S1/S2 model stages only.
- Contract-row and gate IDs use other letters (KV*, R*, Z*, G*, ...).

## Procedure

1. **Outbound scan** — before sending any report or writing any memory/doc: scan for the table's
   terms and for any figurative noun/adjective; replace each per the table.
2. **Agent briefs** — every subagent brief includes the one-line ban: "Use only literal technical
   language; banned examples: seam, quiet, load-bearing, high-water mark, spike; magnitude claims
   carry numbers." (The table above is the reference; the one-liner is the inoculation.)
3. **Inbound filter** — when relaying an agent's report to the user, apply the same scan to the
   relayed text; an agent's violation does not get forwarded.
