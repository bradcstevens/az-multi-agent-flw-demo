# ADR-040: The Grounding panel names the hop it observed

## Status

Accepted — corrects what the **Grounding panel** may claim, and closes the brief's *"Direct Line MCP
server"* as a factual error rather than a feature

## Date

2026-08-16

## Issue

#99 (map #81, spec 5)

## Context

`BRIEF.md` asks for *"specific details to the front end concerning which MCP servers are used, if
any, in agent interactions"*, and explains what it expects to find: *"a direct line MCP server might
be utilized to facilitate interactions with a Co-pilot Studio Agent."*

**No such thing exists**, and this repository had already written down why.
[#96](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/96) verified it against the
code:

- `search_store_procedures`' entire body is `await self.backend.post_json(SOP_ASK_PATH, …)` where
  `SOP_ASK_PATH = "/api/v4/sop/ask"` (`sop_service.py`). **Plain HTTP.** No Direct Line.
- The only Direct Line client in the system is `src/backend/sop/direct_line.py`, and it is **not in
  the MCP container**. `docs/copilot-studio/direct-line-client.md` already states the correction:
  *"The tool is there. **The transport is not**."*
- Microsoft's real MCP feature runs the **opposite direction** — an agent *consumes* an external MCP
  server as tools. No Microsoft documentation exists for exposing a Copilot Studio agent *as* an MCP
  server, which is precisely what [ADR-011](./011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md)
  rejected: *"no Microsoft Learn documentation exists for it. Do not plan on it."*

So the requirement cannot be built as written. What *can* be built is better, because it is true.

### What the panel says today, and what it leaves out

The **Grounding panel** leads with the platform and the route — *Foundry orchestrator → Copilot
Studio → Dataverse* — because the claim it exists to make is that **this one answer left Foundry**.
That is correct as far as it goes, and it silently omits the middle of its own sentence. The real
path is `search_store_procedures` → `POST /sop/ask` → `DirectLineClient` → Copilot Studio, and the
MCP tool call — the thing the brief was asking to see — is the step the route skips.

### Two facts of different kinds

MCP shows up on this surface in two shapes, and conflating them is what makes the requirement look
like one decision:

| | Kind | Source | True when |
| --- | --- | --- | --- |
| Which tools an agent holds | **standing**, per-agent | `use_toolbox` / `toolbox_filter`, already in Redux | always, before a question is typed |
| Which hop this answer took | **observed**, per-answer | the `source_used` signal | only of the reply on screen |

Put both in the Grounding panel and the standing fact inherits the panel's scope — it is dark for
every Foundry-answered question and goes dark the moment the next question is submitted, so the
audience learns nothing about MCP through most of the walkthrough. Put both on the dossier and the
actual hop is never named at the moment it happens, which is the only moment it can be *proved*.

### A field that already looks like the answer

`use_mcp?: boolean` exists on the `Agent` interface (`models/Team.tsx:15`) and is `undefined`
everywhere. It reads like the field this requirement wants and would render nothing — or, populated
naively, would render **false** about an agent holding an MCP tool.

## Decision

**Standing tool attachment belongs to the agent; the observed hop belongs to the answer. Each is
disclosed where it is true.**

1. **The Grounding panel's route names the MCP tool.** The corrected route is *Foundry orchestrator →
   `search_store_procedures` (MCP tool, plain HTTP) → `POST /sop/ask` → Direct Line → Copilot Studio
   → Dataverse*. This is the panel's existing claim made complete, not a new claim: it still asserts
   only what `source_used` reported, still leads with the platform, still has its three states, and
   still goes dark on `requestStarted`.

2. **The Agent dossier lists the agent's MCP tools**, read from `toolbox_filter` — `sop` →
   `search_store_procedures`, held by **ShiftTasksAgent alone**; `troubleshooting`, `escalation` and
   `workforce` likewise. Standing, per-agent, available before anything is typed and for agents that
   never speak.

3. **There is no fourth transparency panel.** Same measured arithmetic as
   [ADR-038](./039-an-agent-dossier-shows-what-the-agent-was-told-verbatim.md): a 320px rail that
   already carries three panels and collapses to 32px when stacked (#60, #70).

4. **The phrase "Direct Line MCP server" never renders anywhere on the surface.** This is not a
   wording preference. It names a component that does not exist, in the panel whose entire purpose is
   that its claims are checkable, and it would be the one false statement standing beside a set of
   true ones.

5. **Tool names render literally, with a plain-English gloss beside them.** #95 was right that raw
   identifiers need humanising in *prose*; here the literal `search_store_procedures` **is** the
   disclosure — it is the string an engineer in the room can go and find — and the gloss is what
   makes it legible to everyone else. Both, not either.

6. **`use_mcp` is deleted from `models/Team.tsx`.** It is not merely unset, it is *wrong*: these
   agents do use MCP, and the honest source is `toolbox_filter`. A dead boolean that reads like the
   answer is worse than no field, on the reasoning `CONTEXT.md` already applies to the deleted team
   picker under **One assistant**.

## Considered Options

**A fourth "MCP" panel.** The most literal reading of the brief, and rejected on the rail's measured
width and on scope: half its content would be standing and half observed, so the panel would need two
scopes — the thing `docs/transparency-panels.md` exists to keep straight.

**The Grounding panel only.** Rejected because the panel is **scoped to one answer** and emits
nothing for a Foundry-answered question. MCP disclosure would then be absent for most of the
walkthrough and would vanish the instant the presenter asked the next question.

**The dossier only.** Rejected because it never names the hop *as it happens*. The standing fact that
an agent holds a tool is weaker evidence than the observed fact that this answer went through it, and
the beat the demo turns on is the observed one.

**Building what the brief describes.** Not available. There is no supported way to expose a Copilot
Studio agent as an MCP server; ADR-011 rejected it on the same evidence, and #96 re-confirmed it
against current documentation.

**Populating `use_mcp` instead of deleting it.** Rejected: a boolean cannot say *which* tools, and the
information it would flatten is exactly the information the requirement asks for.

## Consequences

- **The panel's route string is now checkable against the code**, which cuts both ways: if the
  transport ever changes, a stale route is a lie in the panel that exists to prevent them.
- **The brief keeps a wrong sentence in it.** This ADR is the record that it was read, tested and
  found false — the same service `docs/superseded-requirements-corrections.md` performs for the
  reference material.
- **`docs/transparency-panels.md` gains a distinction**, between a panel's scope and a dossier's, and
  the rail still has exactly three panels.
- **Nothing new crosses the wire.** `toolbox_filter` is already in Redux and `source_used` already
  carries the platform; this is a rendering decision, not a protocol one.

## References

- [`CONTEXT.md`](../../CONTEXT.md) — **Grounding panel**, **Source used**, **Agent dossier**,
  **Transparency rail**, **Citation appearance**
- [ADR-011: Direct Line over A2A for the Copilot Studio SOP agent](./011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md) — rejected the same premise first
- [ADR-039: An agent dossier shows what the agent was told, verbatim](./039-an-agent-dossier-shows-what-the-agent-was-told-verbatim.md) — where the standing half lives
- [ADR-041: The Copilot Studio chat URL is a credential](./041-the-copilot-studio-chat-url-is-a-credential.md) — the link the corrected route does *not* carry
- [docs/copilot-studio/direct-line-client.md](../copilot-studio/direct-line-client.md) — *"The tool is there. The transport is not."*
- [docs/transparency-panels.md](../transparency-panels.md) — the panels and their scopes
- #96 — the topology, verified against the code and against Microsoft's documentation
