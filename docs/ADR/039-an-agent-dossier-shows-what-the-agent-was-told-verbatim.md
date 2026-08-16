# ADR-039: An agent dossier shows what the agent was told, verbatim

## Status

Accepted — introduces the **Agent dossier** to `CONTEXT.md`, and is the surface half of what
[ADR-036](./036-the-simulated-badge-comes-off-and-the-disclosure-stays-in-the-words.md) left in the
words

## Date

2026-08-16

## Issue

#99 (map #81, spec 5)

## Context

`BRIEF.md` asks for *"a way for the user to click in the web interface… providing details that will
take the user to that agent's description and the prompt it's using."*

[#95](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/95) established that this costs
nothing to serve. `TeamAgent` carries `system_message` and `description`; `GET /init_team` returns
the whole `TeamConfiguration`; `models/Team.tsx` already declares `system_message?: string`. So
`selectedTeam.agents[i].system_message` is **populated on mount** and `AgentTeamPanel.tsx` renders
`agent.name` and `agent.deployment_name` and nothing else. There is no backend change here and no
new endpoint — only a surface that never read what it was already holding.

What the design has to survive is everything *around* that fact.

### The rail cannot hold it

The **Transparency rail** is 320px and already carries three panels. [#60](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/60)
and [#70](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/70) measured what that
really means: the **Token meter**'s table is ~257px of usable width, `Troubleshooting` alone
measures 96.4px, and below the **Stacking breakpoint** the rail was observed rendering **32px tall**
around 189px of content. A `system_message` runs to thousands of characters. Rendered in place it is
a grey wall at 257px; rendered as a fourth panel it makes a measured defect worse in the one column
whose job is to be the most credible thing in the room.

### The prompt lines that read badly are requirements

#95 flagged three lines as projector-hostile — EscalationAgent's *"there is no second confirmation or
correction step after it"* and *"every ticket is simulated"*, and WorkforceAgent's *"There is no
employment system connected… you must not describe one or name a product as though it were."*

They are not clumsy prose. `src/tests/ci/test_store_pack.py` asserts on `system_message` in twelve
places, including `assert "no second confirmation" in message`, and the comment above the companion
`user_responses` assertion explains why: *"a clarification at this point in the turn **is** the
second confirmation step the requirement says does not exist."* WorkforceAgent's line is
[ADR-017](./017-workforce-agent-answers-process-never-record.md) written down as an instruction.
Rewriting either for readability edits a requirement and a CI assertion in the same breath, and
`content_packs/**` is on `deploy-main.yml`'s trigger list, so every attempt costs a redeploy of the
demonstration environment ([ADR-020](./020-deploy-main-on-every-commit.md)).

### ADR-036 changed what this object is for

The **Simulated label** came off every surface a day earlier, and disclosure now lives **in prose,
never in chrome**. That makes a verbatim prompt one of the few places an audience can *watch* the
simulation being disclosed — EscalationAgent is told, in its own instructions, not to claim a real
service desk issued a ticket. A dossier that paraphrased that line would remove a disclosure the
surface had just finished relocating into words.

### A dossier can describe an agent that never speaks

Two different failures wear the same face. An agent that did not take *this* question is ordinary,
and **Available vs participating** already names the distinction. But `validate_team_models`
bypasses four model names and fails open, while `create_agent_from_config` reads the runtime
`SUPPORTED_MODELS`, raises `UnsupportedModelError`, and that is caught, warned and **silently
dropped**. A dossier reading `selectedTeam` — populated at roster time — would render a full record,
model and verbatim prompt included, for an agent the orchestration excluded and that can answer
nothing, ever.

## Decision

**The dossier shows what the agent was told, exactly, and claims nothing the surface cannot see.**

1. **The affordance is an overlay opened from the Agent Team panel.** Clicking an agent's name opens
   its **Agent dossier**. Not a fourth panel and not an in-rail expansion: the rail's own measured
   arithmetic rules both out. [ADR-035](./035-the-rail-pushes-and-the-chat-panel-floats.md)'s
   reasoning supports floating it — the rail *pushes* because it is read **beside** the answer it
   explains, and nobody reads a two-thousand-character prompt beside an answer.

2. **It is called the Agent dossier.** Not a card: "card" is already the **Quick Task** and the
   **Presenter alert**, whose rule is written as *"a stack of identical cards reads as a bug rather
   than a beat"*. The transparency surfaces are named for what they state, not for their shape, and
   a shape-named term becomes a lie the moment the shape changes.

3. **It reaches the home surface and every width.** The Agent Team panel has been on the home
   surface's rail since [#79](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/79),
   and a presenter opening a specialist's real prompt *before typing a question* is the moment the
   audience decides whether any of this is a mock-up. The **Panel drawer**'s desktop-only rule is
   **not inherited**: it is a side-column rule, and an overlay is not a side column.

4. **The prompt is verbatim, always.** `description` leads, an authored preamble frames what follows,
   and `system_message` renders **byte-identical** beneath it. Nothing paraphrases, summarises,
   redacts or reorders it. A surface that says *"the prompt it's using"* over anything else is
   asserting something no one can guarantee, in the object whose entire value is that it is checkable
   against the pack.

5. **The three flagged lines stay exactly as they are.** They are pinned by CI and by ADR-017. The
   preamble carries the framing instead — this is **Disclosure in words** applied to the prompt
   itself, and it is authored in the frontend's own copy module on the `storeSurface.ts` precedent,
   so it adds no field to `TeamAgent`.

6. **Participation is stated, and read from the narration's signal.** The dossier says *spoke in this
   answer* or *available, has not spoken*, and on the home surface — where there is no conversation —
   it states availability and claims nothing else. It **must not** read participation from the
   **Token meter**: *when no usage was reported the event is not sent*, so an agent that spoke and
   reported nothing has no row, and a dossier sourced from the meter would deny an agent the audience
   had just watched answer. That is **Not reported vs measured** turned into a participation lie.

7. **A field renders only when it is set.** The dossier carries display name, model, participation,
   `description`, the preamble, the verbatim `system_message`, MCP tools, `knowledge_base_name`,
   `user_responses` in plain English, `temperature`, and the Copilot Studio link — each **only where
   the pack gives it a value**. An empty row reading `use_file_search: false` is a claim about a
   feature nobody chose. This is the configuration form of **Not reported vs measured**.

8. **The manager is out.** Its instructions are the framework's `_magentic` defaults **composed per
   request** by `get_magentic_prompt_kwargs`, which injects the `USER CLARIFICATION POLICY` and
   `MANDATORY AGENTS` clauses differently by lane — and since
   [ADR-038](./038-the-manager-addresses-the-associate-the-session-knows.md) the manager's
   disposition is authored there too, with the addressee carried **per turn**, so the composed string
   now varies by session as well as by lane. There is no single string to show verbatim, so honouring
   rule 4 for the manager means capturing the composed prompt per request and shipping it — net-new
   backend work that puts framework-internal text on a projector. And the manager does not *answer*;
   it decides who does, so listing it would falsify `selectTeamAgentCount` and the **Available vs
   participating** claim beneath it.

9. **The silently dropped agent is a defect, filed separately.** No wording in the browser can fix
   two disagreeing allowlists, and the dossier must not pretend otherwise by hedging every claim it
   makes. The roster's truthfulness is the backend's to repair.

## Considered Options

**An in-rail expansion (accordion).** Rejected on measurement, not taste. 257px of usable width for
a multi-thousand-character prompt is unreadable on a projector, and the rail already collapses to a
32px scroll window when stacked.

**A fourth transparency panel.** Rejected for the same arithmetic one level up. #60 and #70 were each
paid for twice; a fourth panel lengthens the column that already fails to fit and dilutes a rail
whose value is that it can be skimmed.

**A link in the reply.** Rejected: the reply stream is per-answer, so the affordance would be absent
on the home surface and absent for every agent that did not speak — losing exactly the beat where
showing a real prompt is most persuasive.

**A summary, or an edited prompt.** Rejected on the question the ticket itself asked: *if edited, who
guarantees the edit still matches what the agent was told?* Nobody can, and nothing on the surface
would show the drift. A labelled summary is honest but throws away the whole point; an edited prompt
presented as the prompt is the surface's first invented claim, in its most load-bearing object.

**Rewriting the flagged lines and updating the tests.** Rejected. The tests are the requirement, not
an obstacle to it, and ADR-017's boundary is not a wording preference. If those lines ever change it
should be because the *behaviour* changed.

**Participation from the Token meter.** Rejected — it is the nearest data and the wrong data, for the
reason **Not reported vs measured** exists.

**The manager, named without a prompt.** Genuinely arguable and still rejected: any entry beside the
four corrupts the count that **Available vs participating** was carefully worded to protect. If the
audience needs to see who routes, that belongs to the **Progress narration**, not here.

## Consequences

- **The agent names become real buttons.** They are `Caption1Strong` text today. On stage nobody
  clicks prose, and a control outside the tab order is a control a keyboard user does not have —
  the same reasoning as the **Send control**'s `disabledFocusable`.
- **A new object inherits ADR-036's job.** With the badges gone, the dossier is where an audience can
  read the agent being *told* to disclose. That raises the cost of ever paraphrasing it later.
- **The dossier is only as true as the roster.** Until the two allowlists agree, it can describe an
  agent the orchestration dropped. That is recorded here so the next reader does not mistake it for
  an oversight.
- **`content_packs/` gains a reader it did not have.** Every prompt in the store pack is now
  audience-facing text. A future edit made for behaviour is also an edit to what the room reads.
- **The **Heading outline** gains nothing.** The dossier is an overlay, not a section of the surface,
  so it does not extend the rail's two levels.

## References

- [`CONTEXT.md`](../../CONTEXT.md) — **Agent dossier**, **Available vs participating**, **Disclosure
  in words**, **Not reported vs measured**, **Transparency rail**, **Panel drawer**, **Stacking
  breakpoint**, **Agent display name**
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md) — the boundary one flagged line states
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md) — the rule participation is read under
- [ADR-035: The rail pushes and the chat panel floats](./035-the-rail-pushes-and-the-chat-panel-floats.md) — why an overlay, and why the rail is not one
- [ADR-036: The Simulated badge comes off, and the disclosure stays in the words](./036-the-simulated-badge-comes-off-and-the-disclosure-stays-in-the-words.md) — what the verbatim prompt now carries
- [ADR-038: The manager addresses the associate the session knows](./038-the-manager-addresses-the-associate-the-session-knows.md) — why the manager's prompt is composed per session, not authored once
- [ADR-040: The Grounding panel names the hop it observed](./040-the-grounding-panel-names-the-hop-it-observed.md) — the other half of spec 5's transparency work
- #95 — the field-by-field survey this decision rests on
- #60, #70, #79 — the rail's measured width, the meter's columns, and the roster on the home surface
