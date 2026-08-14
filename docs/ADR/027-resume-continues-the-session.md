# ADR-027: Resume continues the session

## Status

Accepted

## Date

2026-08-14

## Issue

#72 (spec #1)

## Context

ADR-024 rejected a "Continue this conversation" control because the surface had only one reliable
way to carry the troubleshooting session into escalation: the authored **Follow-on task** card.
That card remains the right rehearsed path, but it does not repair an ordinary recovery case such
as reopening a Chat and sending another turn.

The session already carries the records that can continue a conversation meaningfully: attempted
steps, identity, lane, and ticket. The **Workflow cache**, however, is process-local, in-memory,
and keyed by user rather than by session. There is no per-Chat agent thread to restore, and replaying
the displayed transcript into a new agent context would claim one.

## Decision

**Resume continues the Chat's Session.** A new turn sent from an open Chat carries that Chat's
`session_id`; a pending clarification still receives its clarification response.

Resume carries only explicitly persisted state: attempted steps, identity, lane, and ticket. The
stored transcript is display-only and is never replayed into an agent context. The **Follow-on
task** card remains unchanged as the rehearsed path: it supplies authored wording and a declared
lane without requiring a keyboard. Resume is the recovery path when the presenter has left or
reopened that conversation.

ADR-024 is superseded only as to its rejection of a continuation control; its decision that the
escalation joins the troubleshooting session through the Follow-on task remains in force.

## Considered Options

- **Replay the transcript into the agent context.** Rejected: it fabricates a per-Chat workflow
  history that the user-scoped, in-memory Workflow cache does not preserve.
- **Keep the Follow-on task as the only continuation path.** Rejected: it protects the rehearsed
  escalation but leaves an accidental return to the list unrecoverable.
- **Mint a new session when resuming.** Rejected: it loses the persisted troubleshooting and ticket
  state that makes the continuation meaningful.

## Consequences

- **Positive:** Reopening a Chat continues the persisted session without a backend reconstruction
  of agent memory.
- **Positive:** The follow-on escalation remains deterministic and keyboard-free for the
  walkthrough.
- **Negative:** Resume cannot promise that an agent remembers unpersisted conversational context;
  the transcript's presence on screen is not evidence of that memory.

## References

- [ADR-024: The escalation continues the troubleshooting conversation](./024-the-escalation-continues-the-troubleshooting-conversation.md)
- [ADR-025: Chat is the unit of the surface](./025-chat-is-the-unit-of-the-surface.md)
- `CONTEXT.md` — **Chat**, **Workflow cache**, **Follow-on task**, and **Troubleshooting record**
