# ADR-022: Completed tasks are hidden, never deleted

## Status

Accepted

## Date

2026-08-14

## Issue

#66 (spec #1)

## Context

A morning of rehearsals leaves a long list of completed tasks in the left panel and no way to clear
it. The presenter wants a clean panel before the customer walks in.

Who is actually looking at that panel matters. `CONTEXT.md`'s **Stacking breakpoint** drops the
task-history panel below 900px rather than squeezing it, because the associate is holding a phone
in a store. The list is therefore only ever seen on a laptop, and in this demonstration the laptop
is the presenter's. The feature is a stage-clearing convenience — but it is watched by an audience,
so it has to read as ordinary product behaviour rather than as a debug affordance.

That is where the trap is. `delete_plan_by_plan_id` is fully implemented at
`src/backend/common/database/cosmosdb.py:443` and is reachable from exactly one caller, the
human-feedback rejection path in `plan_service.py:173`. There is no REST route. Anyone
implementing "clear completed" will find that method, conclude the wiring was simply never
finished, and add the route — which is precisely the outcome this record exists to prevent.

The build's governing rule is that a surface may say nothing but may not say something that is not
so. A control labelled *delete* that does not delete fails it. A control that genuinely deletes
passes it, and buys a different problem: an irreversible destructive action three feet from a live
audience, and the loss of the very records that diagnosis depends on. The intermittency behind #54
was characterised from plans that were still in Cosmos afterwards.

## Decision

**The control hides completed tasks from view. No plan record is deleted, and no `DELETE` route is
added.**

Three parts, each load-bearing:

- **The label states that it hides.** "Delete" would be false. The name is the whole reason the
  hide is honest rather than a lie the audience cannot check, so it is not a copy detail.
- **The hidden set is a set of plan ids, not a global flag.** A task that completes *after* a clear
  still appears. "Stay hidden until I unhide" is a different feature and is deliberately not this
  one.
- **The set lives in `sessionStorage`**, following the **Signed-in device** precedent — *"so a
  fresh tab is a fresh device."* Within a run the clear survives a reload, so the reset actually
  holds; a fresh tab is a fresh demonstration with the whole history back. Both directions are what
  the presenter wants, and neither requires the server to know anything happened.

`delete_plan_by_plan_id` keeps its single existing caller. If a future requirement genuinely needs
deletion, it supersedes this ADR rather than quietly extending it.

## Considered Options

- **A real `DELETE` route.** Honest under any label, and the obvious path. Rejected: it is net-new
  irreversible API surface added for a presenter convenience, a mis-tap mid-walkthrough destroys
  the plan being demonstrated, and it throws away the records that the intermittency work reads.
- **Server-side archive** — record survives, moves out of the list. Rejected as the most work for
  the least benefit: it needs a schema field, a migration and a route, to achieve on the server
  what one browser already knows.
- **`localStorage` instead of `sessionStorage`.** Rejected. It would carry one demonstration's
  hidden list into the next, and the repository has already chosen the opposite discipline for the
  **Signed-in device**: a fresh tab is a fresh start. Two storage conventions on one surface is how
  they come to disagree.
- **Hide behind an ambiguous label and say nothing.** Rejected. It is the cheapest option and the
  only one that requires the audience not to look closely, which is not a property this
  demonstration is allowed to depend on.
- **A per-row hide instead of a list-level clear.** Not chosen, but genuinely arguable — the row
  already carries a dead `MenuTrigger` with no `MenuPopover` that would be its natural home. The
  clear is list-level because the need is list-level. The dead button is removed rather than
  filled, because a button that does nothing is worse than no button, especially on stage.

## Consequences

- **Positive:** The presenter gets a clean panel between runs with no backend change, no new API
  surface and no irreversible action anywhere near a live audience.
- **Positive:** Every plan stays in Cosmos, so the diagnosis path that #47 and #54 both relied on
  is unaffected.
- **Negative:** The list can be cleared on one machine and be full on another, because the state is
  a browser's and not the system's. For a presenter reset that is correct; as product behaviour it
  is a limitation the label has to carry.
- **Negative:** The Completed list needs an empty state it does not currently have — it renders
  blank space today. It must be worded to stay true whether the list is empty or merely hidden.
- **Risk accepted:** Someone will find the unrouted `delete_plan_by_plan_id` and wire it up. This
  record is the countermeasure, and it is the entire reason an otherwise easily-reversible decision
  was written down at all.

## References

- [ADR-020: Deploy `main` on every commit, and make the deploy prove its own result](./020-deploy-main-on-every-commit.md)
- `CONTEXT.md` — **Hidden completed tasks**, **Stacking breakpoint**, **Signed-in device**
- `src/backend/common/database/cosmosdb.py` — `delete_plan_by_plan_id`, and its one caller
