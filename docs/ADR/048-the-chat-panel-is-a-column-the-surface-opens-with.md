# ADR-048: The chat panel is a column the surface opens with

## Status

Accepted — supersedes the chat-panel half of
[ADR-035](./035-the-rail-pushes-and-the-chat-panel-floats.md); its rail half stands unchanged

## Date

2026-08-18

## Issue

#168

## Context

Two defects in one screenshot of the deployed chat surface, at a desktop width. They are recorded
together because they are the same defect: the conversation was not where the eye goes.

**The conversation was pinned to the left edge.** `.conversation-measure` declared `max-width: 800px`
and no horizontal margin. In a `.content` column around 1600px wide the whole transcript rendered in
the left 800px, and the other 800px was empty background between the answer and the
**Transparency rail** that explains it. ADR-035 introduced that measure as its own consequence —
*"the conversation gets one declared measure"* — and capping a line is genuinely half the change;
the half it did not state is that a cap says how wide a line may be and says nothing about where the
block sits in the column it caps. From a projector the gutter was the widest thing on the surface.

**The chat-history panel was closed at first paint.** ADR-035 made it a modal `OverlayDrawer`,
closed by default, and gave the reason plainly: *"a panel covering its own content at first paint is
incoherent."* That sentence is true, and it is an argument about **overlays**. It was read as an
argument about **defaults**, and the two were carried together into a surface that opens as two
columns with a hole where the third belongs — the presenter has to find a control before the chat
list exists at all, at beat 0 of every walkthrough.

What ADR-035 got right is the asymmetry's premise: *"chat history is a transient act of navigation
that nobody reads alongside anything, so re-wrapping the answer to show it is a cost paid for
nothing."* The reasoning is about the **cost of re-wrapping on open**. A column that is already open
when the surface paints has no open to pay for — the reflow happens once, before anybody is reading,
which is the same moment the rail's default-expanded state already resolves. The cost the overlay
was avoiding is a cost only a drawer that starts closed can incur.

Three further facts had accumulated under the overlay and are what make this cheap rather than a
rewrite.

**The drag-resize handle was already deleted.** ADR-035 removed it as *"a 2px mouse-only unlabelled
target that has stopped doing anything"*. What it left behind was the width that handle ranged over:
`--panel-width, 500px`. Under an overlay that number floats above the layout and costs nothing.
As a column it is furniture: 500 + the conversation's 280 minimum + the rail's 320 is 1100px under a
shell that stacks at 900, which is exactly the band #58 was about — two rules disagreeing about when
a column may exist.

**`PanelLeft`'s inline layout had already moved to a stylesheet.** ADR-035 called that a *blocking
prerequisite* and #116 did it. A breakpoint rule on this panel is now visible to
`CoralShellRow.test.tsx`, which reads side-column rules out of `src/App/src/styles/*.css` — so the
column can be declared where every other side column is declared, rather than being *"present,
correct and completely inert"*.

**The rail on the other edge is already this mechanism.** It pushes, it is desktop-only, it is
released at the **Stacking breakpoint**, and its disclosure is a static label plus `aria-expanded`.
Nothing in that idiom needed inventing for this edge.

## Decision

**Both drawers push. The chat-history panel is a column the surface opens with, and the
`Chat history` disclosure closes it.**

- **Open by default.** The surface paints three columns with no control pressed. Navigation is not
  something to go looking for.
- **Closed is not rendered.** `ChatPanelLeft` returns `null`, and the width goes back to the
  conversation. There is deliberately **no collapsed rule** to declare — unlike the rail, whose
  *container* declares the width it gives up, a column that is not rendered occupies nothing and
  has nothing to release. This is the one place the two edges are not mirror images, and the
  asymmetry is in the stylesheet rather than in the behaviour.
- **280px, and not a new number.** It is the one `storeSurface.css` already reasons with: 280 here,
  the conversation's 280 minimum and the rail's 320 is 880px of furniture under a shell that stacks
  at 900. The inherited 500px overran that by 220px.
- **The hairline is on the right**, the edge it meets the conversation at — the mirror of the rail's
  `border-left`, declared in the same place for the same reason.
- **Navigation leaves the panel alone.** Opening a chat, or the logo, no longer closes it. The
  overlay closed itself there because it was covering the conversation it had just been asked to
  open; a column covers nothing, and closing it would take the presenter's next choice off the
  screen at the moment they made this one.
- **The conversation is centred**: `.conversation-measure` gains `margin-inline: auto`.
  `margin-inline` rather than `margin: 0 auto`, because the vertical margins belong to the
  components that stack these blocks and this rule owns only where the block sits across the column.
- **Below the Stacking breakpoint nothing changes.** The panel and its toggle are both absent, and
  the toggle keeps its static accessible name plus `aria-expanded` — which now reports `true` at
  first paint, so the first press closes.

## Considered Options

**Keep the overlay and merely open it by default** — rejected, and it is the option the issue's
wording most invites. It is incoherent for the reason ADR-035 gave: a modal that dims the surface
and traps focus, covering its own content before anybody has asked for it, means the first thing
every walkthrough does is dismiss a dialog. The default and the mechanism cannot be separated.

**Keep the overlay, and centre the conversation only** — rejected as a half-fix that fixes the
louder half. The gutter is the more visible defect from the back of a room, but the hole where the
third column belongs is the one that costs the presenter an interaction at beat 0.

**Collapse to a narrow icon strip rather than unmounting** — rejected for the reason ADR-035
rejected it on the other edge, and this is the second time: a fourth declared width in a column
whose width has already been wrong twice, and a strip of icons carrying chat *names* is a strip that
cannot be read, which is the only thing a chat list is for.

**Give the column a zero-width collapsed rule, mirroring `.plan-panel-right`** — rejected as a rule
with nothing behind it. The rail's container needs one because the container is rendered whatever
the rail does; here the component itself is the column, so the collapsed rule would be a declaration
about an element that is not in the tree. `CoralShellRow.test.tsx` requires the breakpoint to
release side-column rules, and `display: none` is one of the releases it accepts, so a column that
is simply absent satisfies it without a second way of saying so.

**Persisting the open state** — rejected on ADR-035's own grounds, unchanged: it would make the
**Demo validator** and the **Stage driver** order-dependent, and the presenter runbook is asserted
string-for-string.

## Consequences

**The presenter runbook's recovery beat changes.** *"Choose Chat history in the content toolbar,
then open the conversation from the drawer"* named a drawer that had to be opened and that closed
itself afterwards. The panel is on screen, and it stays. `test_presenter_runbook.py` holds the
runbook to the repository's own strings, so it changes in this commit.

**Both `e2e/` page objects change in this commit.** They located chat history by `role=dialog` and
described it as *"a modal Panel drawer"*; `openChatHistory()` clicked the toggle and expected the
panel to appear, which against this surface **closes** it. The panel is a `role=navigation` region
named `Chat history`, and the helper's job is now to ensure it is open rather than to press.

**`CHAT_HISTORY_DRAWER_TOGGLE_ID` goes.** It existed so the overlay could return focus to its
trigger on close. Nothing takes focus away now, so the constant and the `setTimeout` that used it
are deleted rather than left as a focus dance nobody triggers.

**The default desktop view changes back**, and ADR-035's *"the chat list and #76's delete-all move
behind a control"* no longer holds. They are visible at beat 0 again.

**Tests that dismissed the modal must stop.** `leavingChat.test.tsx` opened its two `New chat` cases
with an Escape keypress against `role=dialog` — a preamble for getting out from under the overlay.
There is no dialog, so those tests were failing against this surface until the preamble was removed.

**Below 900px nothing changes at all**, exactly as under ADR-035: chat history is still dropped and
the toggle is still absent. 280px of navigation beside a 390px viewport leaves the conversation
unusable, and the conversation is the one thing that must still work there.

## References

- [`CONTEXT.md`](../../CONTEXT.md) — **Panel drawer**, **Stacking breakpoint**, **Transparency
  rail**, **Pinned panel**
- [ADR-035](./035-the-rail-pushes-and-the-chat-panel-floats.md) — the rail half stands; the chat
  panel's overlay and its default are superseded here
- [docs/presenter-runbook.md](../presenter-runbook.md) — the recovery beat this changes
- [docs/demo-validator.md](../demo-validator.md) — the page objects asserted against a deployment
- #58, #60 — two breakpoints disagreeing, and the three side-column sizing rules
- #116 — `PanelLeft`'s layout moved to a stylesheet, which ADR-035 named a blocking prerequisite
