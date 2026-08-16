# ADR-041: The Copilot Studio chat URL is a credential

## Status

Accepted — bounds the deep link `BRIEF.md` asks for; introduces the **Copilot Studio link** to
`CONTEXT.md`

## Date

2026-08-16

## Issue

#99 (map #81, spec 5)

## Context

`BRIEF.md`: *"If the agent is a co-pilot studio agent, a link that the user would click for Copilot
Studio agent should bring the user to the chat interface directly on Copilot Studio for the user to
interact with the Copilot Studio agent directly."*

[#96](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/96) established that such a
surface exists and that it costs more than it looks like it does.

### The URL is the access gate

The **Store SOP Assistant** (`cr48b_StoreSopAssistant`) is published with **no authentication**
(ADR-011). Microsoft is explicit about what that means: *"anyone who knows the agent ID can
immediately access the agent through the **Demo website** and **Custom website** channels"*, and of
the demo website itself, *"isn't intended for production use. Don't share the URL with customers."*

There is no sign-in between the URL and the agent. The URL **is** the credential — and every answer
it gives is generative, so it is metered at 2 **Copilot Credits** against this tenant.

**This repository is public.** Committing that URL publishes a working, unauthenticated, metered
entry point into the tenant to anyone who reads the source.

### It cannot be derived, only copied

`resolve_environment()` returns the Dataverse org URL; `PvaGetDirectLineEndpoint` returns a
token-minting endpoint. Neither is a chat page, and **no Microsoft Learn page publishes a formula**
for constructing one — the portal generates it and shows it to a licensed human. The community-guessed
shape is flagged in #96 as *unverified inference, not fact*. This is the **Direct Line base URL**
problem one step worse: there, no settings service answered; here there is no documented service at
all.

So the URL arrives by hand, once, and **nothing in this repository can ever verify it still points
anywhere** — the opposite of every other fact the surface asserts.

### Two live risks in the link itself

- **Authored here.** The agent is authored *from this repository* through the Dataverse Web API
  precisely so that no one edits it in the portal. A link puts a maker one click from the portal,
  and `_authored_check` then fails component by component.
- **Publish propagation.** A tab left open across a publish answers from the **superseded agent
  indefinitely**, silently. `direct_line.py` dodges this by opening a fresh conversation every call;
  a bookmark gets no such protection.

### And the demo does not need it

The **Grounding panel** already proves the cross-platform hop with a *real* Direct Line answer and
real citations, live, in the beat. Clicking out to Copilot Studio proves the agent exists; the
Grounding panel proves **this answer came from it**. The link is the weaker evidence.

## Decision

**No Copilot Studio chat URL is ever committed to this repository. The link is optional, absent by
default, and forces a fresh browser context when it is present at all.**

1. **The URL is never in git.** Not in `infra/environments/`, not in a content pack, not in a test
   fixture, not in a document. It is supplied — if at all — through an **environment variable that is
   unset by default**.

2. **Unset means absent, not disabled.** When no URL is configured the affordance does not render.
   A disabled control claims a destination exists that the surface cannot reach; this is **Not
   reported vs measured** applied to an affordance.

3. **It lives on ShiftTasksAgent's dossier, as the tool's destination.** The Copilot Studio agent has
   no `TeamAgent` record and no `system_message` this repository can render — its instructions live in
   Dataverse. It is reached *through* `search_store_procedures`, which **ShiftTasksAgent alone**
   holds, so that is where a link to it is a true statement. The wording makes the link plainly the
   *tool's destination* and not the agent whose prompt is on screen.

4. **A fresh browser context, every click.** `target="_blank"` with **no named target**, plus
   `rel="noopener noreferrer"`. The trap is the named target — `target="copilotStudio"` looks
   identical, reuses one tab, and reintroduces **Publish propagation** exactly. That prohibition is
   written in `CONTEXT.md` as domain language and asserted by a frontend test reading the anchor's
   attributes, on the precedent of `CoralShellRow.test` reading layout rules **out of the
   stylesheets** rather than restating them.

5. **Enabling it discloses the URL to the room.** Clicking the link on a projector puts the
   unauthenticated URL in the address bar in front of the audience, and a photograph of that slide is
   a working key. Keeping it out of git and then broadcasting it is not obviously the smaller leak.
   This is recorded rather than prevented — it is a presenter's judgement, and it must be a knowing
   one.

6. **The Grounding panel carries no link.** Its route is a claim about *this answer*, and it goes
   dark on the next question. The proof stays per-answer; the link stays a standing fact about a tool.

## Considered Options

**Hand-carry the URL into the repository and ship the link.** The literal reading of the brief.
Rejected: the repository is public, the URL is unauthenticated and metered, and nothing here could
verify it. It is a committed credential by any reasonable definition.

**No link at all.** Genuinely defensible, and the option this ADR is closest to. Rejected only
because the env var keeps every objection intact — nothing is published, nothing is asserted, and
the affordance simply is not there — while leaving a presenter who wants the beat a way to have it
deliberately.

**A link in the Grounding panel.** Rejected: the panel is scoped to one answer and dark for
Foundry-answered questions, so the link would appear and vanish with the beat, and the panel would be
making a standing claim inside a per-answer scope.

**A dossier of its own for the SOP assistant.** Rejected: it would be a dossier with **no prompt in
it**, which is the one thing every other dossier exists to show. Opened from a panel about agents'
instructions, it would teach the audience that the prompt is optional.

**Deriving the URL from the environment id and schema name.** Not available. No documented formula
exists, and the guessed shape is inference.

## Consequences

- **The affordance is absent in CI, in the Demo validator and on any clean checkout.** Every
  assertion about it is therefore an assertion about the *unset* state, and the configured state is
  exercised only by a presenter who configured it.
- **One more thing lives outside the repository.** The URL joins the small set of facts this build
  cannot verify from source, and like the others it gets a record rather than a silent assumption.
- **The `Authored here` rule stays enforceable but is now one click closer to being broken.** The
  record says so; `_authored_check` remains the thing that catches it.
- **If the agent is ever republished, an already-open tab is still wrong.** Rule 4 makes every
  *click* fresh; it cannot close a tab someone left open. That residue is the reason the Grounding
  panel, not the link, carries the proof.

## References

- [`CONTEXT.md`](../../CONTEXT.md) — **Copilot Studio link**, **Agent dossier**, **Grounding panel**,
  **Direct Line base URL**, **Conversation-scoped token**, **Not reported vs measured**
- [ADR-011: Direct Line over A2A for the Copilot Studio SOP agent](./011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md) — the no-auth publish this inherits
- [ADR-039: An agent dossier shows what the agent was told, verbatim](./039-an-agent-dossier-shows-what-the-agent-was-told-verbatim.md) — the object the link hangs off
- [ADR-040: The Grounding panel names the hop it observed](./040-the-grounding-panel-names-the-hop-it-observed.md) — the proof that makes the link optional
- [docs/copilot-studio/sop-agent.md](../copilot-studio/sop-agent.md) — the agent, and the **Authored here** rule
- [docs/copilot-studio/direct-line-client.md](../copilot-studio/direct-line-client.md) — the only Direct Line hop
- #96 — the surfaces, what each requires of whoever clicks, and what a link would leak
