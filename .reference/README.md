# SUPERSEDED — this directory holds reference material, not the record

`Circle-K-Frontline-Store-Assistant-Demo-Build-Requirements-v1.md` (v2.1, 31 July 2026) — the
**superseded requirements document** — is the material this build started from. It is
**superseded and untracked**. Everything in this directory except this file is `.gitignore`d, so
if you have a copy it came from somewhere other than this repository, and nothing recorded only
there survives a fresh clone.

**Do not treat it as authority.** Ten of its statements are factually wrong, including several
that read as perfectly plausible — the region it names is invalid for this template, the fast
lane it specifies is not implementable, and its A2A justification is out of date.

`BRIEF.md` — the **superseded brief** — is the material that followed it, and it moved here for
the same reason. Eleven ADRs (028, 029, 031, 033, 035, 036, 037, 038, 039, 040 and 041) and
[`CONTEXT.md`](../CONTEXT.md) still cite it by name, and those citations are not broken links to
chase: each one **quotes verbatim the sentence it answers**, so the ask survives in the decision
that resolved it. Read the ADR, not the brief. It is wrong in the same way the requirements
document is — ADR-029 records that it is factually wrong about a Direct Line MCP server, and
`CONTEXT.md` records another of its sentences as an error an ADR documents rather than builds.

## The durable record

| What you want | Where it lives |
| --- | --- |
| What the document gets wrong, claim by claim | [`docs/superseded-requirements-corrections.md`](../docs/superseded-requirements-corrections.md) |
| The decisions that shape the build | [`docs/ADR/`](../docs/ADR/README.md) |
| The vocabulary tickets, tests and UI copy use | [`CONTEXT.md`](../CONTEXT.md) |
| The requirements themselves | GitHub issue #1 and its slices |

Read a claim in the superseded document against the corrections record before acting on it. If
the two disagree, the corrections record wins — it is the one that gets tested.
