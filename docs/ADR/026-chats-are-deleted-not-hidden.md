# ADR-026: Chats are deleted, not hidden

## Status

Accepted

## Date

2026-08-14

## Issue

#72 (spec #1)

## Context

[ADR-022](./022-completed-tasks-are-hidden-never-deleted.md) chose hiding because the panel was a
stage-clearing convenience, so a control labelled delete would have claimed an action it did not
perform. ADR-025 reframes that panel as Chat management. Under that premise, hiding is the weaker
choice: a user managing their chats reasonably expects a delete action to delete them.

The available `delete_plan_by_plan_id` method is not that operation. It deletes one plan document,
does not scope the query by `user_id`, and leaves the transcript, `m_plan`, troubleshooting record,
ticket, and session state in the same session partition. It keeps its single human-feedback
rejection caller and must not be routed as Chat deletion.

## Decision

**Chats are deleted, not hidden.** Deletion is scoped to both the Chat's session partition and its
`user_id`. It removes every document in the partition: plans, transcript, `m_plan`,
**Troubleshooting record**, **Simulated ticket**, and **Session state**.

ADR-022 is superseded. The hide feature is removed rather than retained beside deletion, and
`delete_plan_by_plan_id` remains unchanged with its one existing caller.

## Considered Options

- **Keep hiding completed tasks.** Rejected: it was honest only under the stage-clearing premise
  that Chat management replaces.
- **Route `delete_plan_by_plan_id`.** Rejected: it leaves a partial Chat behind and would permit a
  caller who knows a plan id to target another user's record.
- **Delete only a plan from the Chat.** Rejected: the transcript and session-scoped records would
  survive a control that promised to delete the conversation.

## Consequences

- **Positive:** The surface's delete label describes what happens, and the panel can state plainly
  when there are no chats.
- **Negative:** Deletion is irreversible. A presenter can destroy the diagnosis trail that #47,
  #54, #61, and #62 used during rehearsal.
- **Negative:** A running Chat cannot be deleted, so the surface must explain when it keeps one.

## References

- [ADR-022: Completed tasks are hidden, never deleted](./022-completed-tasks-are-hidden-never-deleted.md)
- [ADR-025: Chat is the unit of the surface](./025-chat-is-the-unit-of-the-surface.md)
- `CONTEXT.md` — **Chat deletion**, **Troubleshooting record**, and **Simulated ticket**
