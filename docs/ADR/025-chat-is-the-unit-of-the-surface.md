# ADR-025: Chat is the unit of the surface

## Status

Accepted

## Date

2026-08-14

## Issue

#72 (spec #1)

## Context

The surface calls the conversation a chat while the durable domain objects are `Plan` and
`session_id`. That is a legitimate split, but it becomes misleading when a reader finds a chat
route served by a plans endpoint and a history grouped by session, then "normalizes" one side to
match the other.

[ADR-024](./024-the-escalation-continues-the-troubleshooting-conversation.md) made the split
load-bearing: the troubleshooting turn and its escalation are separate plans that deliberately
share a session. They are one conversation to the associate even though the domain persists two
plans.

## Decision

**A Chat is a Session on the surface.** A Chat may contain multiple Plans, and the surface groups
them as one conversation. The domain retains `Plan`, `PlanStatus`, plan endpoints, and `session_id`
because each still names a distinct model concept.

The surface uses chat vocabulary for its history, routes, new-conversation affordance, and
conversation page. This is not a model rename.

## Considered Options

- **Call each Plan a chat.** Rejected: escalation proves that one session can contain multiple
  plans, so this turns the surface term into a false one-to-one mapping.
- **Rename the domain to chat.** Rejected: a Plan remains the orchestration object that can be
  reviewed or completed, while a Chat is the associate-facing conversation that contains it.
- **Keep task and plan vocabulary on the surface.** Rejected: it hides the conversation boundary
  that determines history grouping, deletion, and resume.

## Consequences

- **Positive:** The history can correctly show one row for the troubleshooting turn and its
  escalation, because both belong to one Chat.
- **Positive:** The distinction lets later work make Chat management ordinary product behavior
  without making the orchestration model less precise.
- **Risk accepted:** The route and API names differ by design. A reader must follow the
  surface/domain boundary rather than use matching words as a proxy for it.

## References

- [ADR-024: The escalation continues the troubleshooting conversation](./024-the-escalation-continues-the-troubleshooting-conversation.md)
- `CONTEXT.md` — **Chat**, **Session state**, and **Follow-on task**
