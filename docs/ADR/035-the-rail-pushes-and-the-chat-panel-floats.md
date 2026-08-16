# ADR-035: The rail pushes and the chat panel floats

## Status

Accepted

## Date

2026-08-16

## Issue

#90 (map #81, spec 1)

## Context

`BRIEF.md` opens with a single sentence asking for two drawers: *"Without a button to toggle the
plan-panel-right and its visibility, basically create a drawer where you can expand or minimize the
view of this panel. Do the same for panel-left."*

Read as written, that is one mechanism applied twice. Three facts make it two decisions.

**The ground is already owned, and by an answer that is not a button.** #60 closed with a follow-up
left open deliberately: *"a rail that starts compact and expands once it has something to report. It
is now a change to one number in one place."* That is an **automatic** rail. The brief asks for a
**manual** one. Both answer #60's last acceptance criterion — *"the conversation is not paying for
empty panels"* — and left unreconciled they are two owners of one width, which is
[the defect #60 spent a whole ticket removing](./025-chat-is-the-unit-of-the-surface.md) restated in
the time dimension rather than the space dimension.

**#79 removed the premise the automatic answer rested on.** #60 complained of *"two empty-state
paragraphs before anything has been asked."* Commit a7f7b5ff — *"The rail states who is available,
before a question is typed"* — then put the Agent Team roster on the home surface's rail, with, as
[docs/transparency-panels.md](../transparency-panels.md) records, *"no request of the panel's own and
nothing on the socket."* The rail is now never empty. "Compact until it has something to report" no
longer names a state that can be computed, so any automatic behaviour must key on a **named signal**
instead.

**The two panels are not the same object.** The brief's `.plan-panel-left` does not exist anywhere in
the codebase; the left panel is `ChatPanelLeft` wrapping `PanelLeft`.

| | Rail | Chat-history panel |
| --- | --- | --- |
| Holds | The transparency argument | Navigation |
| Read | **Beside the answer** | Instead of the answer |
| Layout declared in | `planpanelright.css`, `transparency.css` | **Inline**, `PanelLeft.tsx:82` |
| Affordance today | none | drag-resize, 256–500px |
| Has a signal | `source_used` | **none exists** |
| In the **Heading outline** | three `SECTION_HEADING`s | not at all |

The last row is load-bearing. #78 made the outline conditional because *"a heading a non-visual user
skims to and finds nothing behind is the same defect one step further on"* — so whatever collapsed
means for the rail, it cannot mean *titles without their content*.

## Decision

**The rail pushes and the chat panel floats. Both drawers are desktop-only, and the presenter's
choice lasts exactly one conversation.**

The asymmetry is the decision. It follows from what each panel is *for*: the rail exists to be
skimmed **alongside** the answer it explains, so covering the answer to reveal the rail defeats it;
chat history is a transient act of navigation that nobody reads alongside anything, so re-wrapping
the answer to show it is a cost paid for nothing.

**The rail — reflow.**

- Closing it returns its width to the conversation. The third state is a width, governed by the
  rules `CoralShellRow.test.tsx` already reads out of the stylesheets.
- It **auto-expands on the first `source_used` of the conversation** — the cross-platform hop, and
  the only signal that proves *which platform answered*. At most one expansion, so at most one
  re-wrap.
- **A manual touch wins and pins the state for the conversation**, cleared at `conversationStarted`
  on the `alerts` precedent rather than the meter's. A layout choice that outlives the beat it was
  made for is how the hop gets hidden three beats later with nobody remembering why.
- **Collapsed is zero width**, and the three `SECTION_HEADING`s unmount rather than hide.
- The **toggle carries one indicator**, firing on `source_used` and nothing else — one signal, two
  consequences depending on whether the rail is pinned.
- **Default expanded**, because collapsed-by-default would silently reverse #79.

**The chat-history panel — overlay.**

- A Fluent `OverlayDrawer`: modal, dims, traps focus, closes on Escape, light-dismisses, returns
  focus to its trigger. Hand-rolling that is how focus return gets forgotten.
- **Closed by default**, which an overlay forces — a panel covering its own content at first paint is
  incoherent.
- **`New chat` is promoted out of it** into `ContentToolbar`, keeping its visible text label. If the
  chat list is going behind a control, the action that *starts* a chat must not go with it.
- **The drag-resize handle is deleted.** Under overlay it moves nothing, and a 2px mouse-only
  unlabelled target that has stopped doing anything is what this repository deletes rather than
  hides.
- No automatic behaviour, because no signal exists to drive one.

**Both.**

- Both toggles live in **`ContentToolbar`**, the only element on both surfaces. The rail's is called
  **Transparency panels**; labels are constants in `storeSurface.ts`.
- They are **disclosure buttons** — one static accessible name plus `aria-expanded` and
  `aria-controls`, never a label that flips between *Show* and *Hide*.
- **Nothing persists.** The state is Redux only.
- **The drawer is released at the 900px Stacking breakpoint**, exactly as width, `border-left` and
  `box-sizing` already are. Below it the rail is always expanded and the chat panel stays dropped.
  The toggles are `display: none` there rather than disabled — a control for a state that cannot
  exist is worse than no control.
- **No presenter chord.**

## Considered Options

**Symmetric reflow for both panels** — one idiom, one explanation from the stage, and the left
panel's existing drag-resize already pushes the conversation, so an overlay collapse would mean one
component that pushes when dragged and floats when toggled. Rejected because opening chat history
would then re-wrap the answer every time, and the surface is read from a projector where the
conversation sits below its own declared measure at every width under ~1400px.

**Automatic only, with no button** — #60's follow-up, taken literally. Rejected because #79 left
nothing to compute it from, and because the presenter is the one who knows which beat needs the rail;
every other control on this surface is presenter-driven rather than inferred.

**Both mechanisms with the automatic one winning** — rejected for the same reason the manual one must
win: a rail that reopens itself against a deliberate act is a control the presenter cannot trust
mid-sentence.

**A narrow icon strip as the collapsed rest state** — rejected twice over. It is a *fourth* declared
width in a column whose width has already been got wrong twice, and a rail of icons is a rail that
cannot be skimmed, which is the only thing the rail is for. A strip that kept the panel titles would
rebuild #78's defect exactly.

**Persisting the state in `sessionStorage`**, on the **Signed-in device** precedent — rejected
because it would make [the Demo validator](../demo-validator.md) and [the Stage
driver](../stage-driver.md) order-dependent: a rehearsal that ended with the rail collapsed would
open the next run collapsed, and the presenter runbook is asserted string-for-string. Server-side
**Session state** was never a candidate; it *"deliberately carries only what the client cannot
re-derive"*, and a panel's open state is the most re-derivable thing on the surface.

**A second presenter chord** — rejected. The alert chord is hidden because the alert has no visible
affordance at all; these have one. It would double what `CONTEXT.md` calls *"the one place this
codebase departs from its inline `onKeyDown` convention"*, and `usePresenterChord` is mounted by
`ChatPage` alone while the toggles are on both surfaces. A rehearsal that shows a real fumble is what
reopens this, on the same measure-first discipline as
[ADR-013](./013-per-request-plan-review-over-orchestrator-bypass.md).

## Consequences

**The Heading outline gains a third axis.** It is already asserted per lane; a collapsed rail
unmounts three section headings, so `headingOutline.test.tsx` must assert a collapsed outline and an
expanded one.

**The conversation gets one declared measure.** Reflow that widens a line nobody capped is half a
change, and the measure is currently declared nine times and disagrees with itself: `maxWidth:
'800px'` inline in eight components, `768px` in three stylesheets, `800px` in two, and `960px` in
`ChatPage.css`. Inline wins over all of them, which is `CONTEXT.md`'s own warning in the column this
decision hands width to.

**`PanelLeft`'s inline layout must move to a stylesheet first, and that is a blocking prerequisite.**
`PanelLeft.tsx:82` declares width, display and flex-direction inline — the trap #25 paid for on
`CoralShellRow` and #60 paid for on `Content`. Until it moves, any breakpoint rule on that panel is
*present, correct and completely inert*, and invisible to `CoralShellRow.test.tsx`, which reads only
`src/App/src/styles/*.css`.

**Two dead declarations go.** `.plan-left-panel` and `.plan-right-panel` in `ChatPage.css` are
rendered nowhere and carry their own breakpoints at 1200px and 768px — one letter from the live
`.plan-panel-right`, in a repository where #58 was entirely about two breakpoints disagreeing.
`PanelRightToggles.tsx` goes too: dead accelerator code with the right icons and an `eventBus` this
surface no longer uses, and *"one prop away from returning"*.

**The collapse rule must name two containers.** `HomePage.tsx` renders a bare `.transparency-rail`
while `PlanPanelRight.tsx` wraps it in `.plan-panel-right`, and the stacking rules already pair them.
A collapse that names only one leaves the home surface's rail stuck open.

**The default desktop view changes.** The chat list and #76's delete-all move behind a control. That
is visible at beat 0 of every walkthrough, so the presenter runbook and the `e2e/` page objects
change in the same commit as the surface.

**Below 900px nothing changes at all.** The phone still has no chat history and a rail that is always
expanded — #60 fought specifically to make that rail readable there, and a mobile collapse would
re-open the defect #60 closed.

## References

- [`CONTEXT.md`](../../CONTEXT.md) — **Panel drawer**, **Stacking breakpoint**, **Transparency
  rail**, **Heading outline**, **Send control**, **Presenter chord**, **Signed-in device**
- [docs/transparency-panels.md](../transparency-panels.md) — the three scopes, and why the meter is
  not one of them
- [ADR-013](./013-per-request-plan-review-over-orchestrator-bypass.md) — measure first, then reopen
- [ADR-025](./025-chat-is-the-unit-of-the-surface.md) — chat is the unit of the surface
- #58, #60 — the Stacking breakpoint and the three side-column sizing rules
- #78, #79 — the conditional Heading outline, and the roster on screen before a question is typed
