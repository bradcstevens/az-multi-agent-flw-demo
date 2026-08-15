# The store surface

Issue #25. The rebrand from the accelerator's Contoso-branded "Multi-Agent Planner" to the
**Circle K Frontline Store Assistant**, and the point at which the demo stops looking like a
solution accelerator with a feature bolted on.

It lands after the centrepiece deliberately: if the **Identity boundary gate** is not convincing,
the rest is decoration. It is also the last thing #26's Quick Tasks and #27's sign-in need in
place, because both of them are affordances *on* this surface.

The rule the transparency panels run on (#23, #24) carries over, applied to **identity**:

> A surface may say nothing, but it may not say something that is not so.

Rendering the accelerator's HR Onboarding roster under a Circle K header is that rule broken — and
broken in the way that is hardest to notice, because nothing on screen looks wrong.

## What the surface claims

Every string the surface says about itself lives in `src/App/src/models/storeSurface.ts`. Four
places would otherwise have to agree by inspection: the left panel's toolbar, the conversation's
header, the browser tab and the identity chip. A demo that calls itself two things in one
screenshot has already lost the argument it exists to make.

| Claim | Value |
| --- | --- |
| Assistant | Circle K Frontline Store Assistant |
| Store | Store 223 — **labelled simulated** |
| User | *No user signed in*, until the **Mocked unlock** (#27) names one |
| Team identifier | `00000000-0000-0000-0000-000000000223` |

The user chip reads the **Session identity** and nothing else — never the EasyAuth principal.
Two identities that can disagree are one identity too many, and the Identity boundary gate reads
server-side **Session state** (ADR-014); on this deployment EasyAuth is off, so a chip driven by it
would have claimed a signed-in user while every personal question was refused. See
[mocked-unlock.md](mocked-unlock.md).

The mark beside the name is an abstract storefront, **not** a reproduction of Circle K's trademark.
This is a demonstration built for a customer conversation, not a licensed use of their brand
assets, and a wrong-looking copy of a real logo on a stakeholder's screen is worse than an honest
placeholder.

## One assistant, and no picker

There is no team picker. Choosing between specialists is the **Lane router**'s job and the
orchestrator's job; an associate mid-shift has no basis for the choice, and asking them to make it
turns getting an answer into a routing decision they cannot make.

`TeamSelector`, `TeamSelected`, `useTeamSelection` and the EasyAuth `LoginButton` were **deleted**
rather than left unrendered. A picker that is merely not rendered is one prop away from returning,
and the upload dialog inside it was also the last route by which a suppressed stock content pack
could reach the surface.

The resolution stays; only the choice goes. `HomePage` still asks the backend for the teams it
holds — it just does not offer them.

## Suppressing the stock content packs

The spec puts this inside R1's single-assistant surface, and it needs two halves because either
alone leaks:

| Half | Where | What it stops |
| --- | --- | --- |
| Surface | `selectStoreAssistant` | A pack already in Cosmos being shown under the Circle K header |
| Deploy | `installs_use_case`, `MACAE_USE_CASE=none` | Six unused agent teams being seeded at all |

### The surface half

`selectStoreAssistant` **recognises** the store assistant rather than taking whatever the backend
listed first: by `STORE_ASSISTANT_TEAM_ID`, and failing that by name, because the pack is uploaded
by a script and re-uploaded by hand more than once.

There is deliberately **no `teams[0]` fallback.** That fallback *is* the suppression failing. A
deployment that still holds the HR Onboarding or RFP Evaluation packs — and this one does — would
otherwise put one of them under the Circle K header the moment the store assistant's own pack was
missing or renumbered.

So **no assistant is a state the surface can be in**, and it says so plainly:

> The Circle K Frontline Store Assistant is not loaded on this deployment.

That is a worse-looking demo and a more honest one. It is also self-diagnosing: the message names
exactly what is missing, where the accelerator's copy ("Select a team to see available tasks")
blamed the associate for not making a choice that no longer exists.

### The deploy half

`post_deploy.sh` and `post_deploy.ps1` gain an eighth selection, `none`, and honour
`MACAE_USE_CASE` so the whole choice can be made non-interactively — `azd hooks run postdeploy` on
the rehearsal machine must not stop on a `read -rp` nobody is watching.

Two smaller decisions inside that:

- **An unrecognised override is refused, not defaulted.** Defaulting would quietly seed six stock
  packs because somebody typed `None` with a capital N.
- **The six upload guards go through one predicate**, `installs_use_case`. Six inline comparisons
  that have to agree by inspection are six chances for one to be missed; one predicate is a thing
  `src/tests/ci/test_stock_pack_suppression.py` can **source and call**, rather than reading the
  menu text and agreeing with itself about what it means.

`test.yml` names both post-deploy scripts in its paths — those two files only, not `infra/**`,
since widening it would run the backend suite for a Bicep edit. Without that, the one change that
can break these tests is the one change that would not have run them.

## The phone

The associate is holding a phone, in a store, on a shared device. The accelerator's shell is three
columns — chat history, conversation, transparency rail — which is roughly 900px of furniture
before the conversation gets any width at all.

At **900px** the columns stack, the transparency rail moves beneath the conversation, and the
task-history panel is dropped rather than squeezed. That prevents the 641-900px band from leaving
the conversation narrow beside a rail styled as a stacked band. The panel is presenter furniture,
not associate furniture.

Getting there required moving `CoralShellRow`'s layout out of an inline style, and that is the
whole reason it has a test: **an inline `flex-direction: row` beats a media query**, so the shared
stacking breakpoint would have been present, correct and completely inert.
`CoralShellRow.test.tsx` asserts the element carries no inline `display` or `flexDirection` at all.

That test also reads the breakpoint's selectors **out of the stylesheet** and checks each one is a
class something actually renders. A list of class names written in the test would agree with itself
forever; a rename in a component while the breakpoint keeps the old name is a layout that silently
stops applying, and it would be discovered on a phone, on stage.

### Every column stacks, not only the rail

The rail is a direct child of the shell on the home surface and a **grandchild** on the plan
surface, where `PlanPanelRight` wraps it. Moving the breakpoint fixed the rail and left its
container behind: `.plan-panel-right` kept `width: 280px`, `height: 100vh` and a `border-left`
below the breakpoint, so on the chat surface the stacked rail was a 280px band, a viewport tall,
with a left border on the outside and a top border on the inside. A side column wearing the styling
of a stacked one — the ticket's own complaint, one level up.

The rule the surface runs on now: **a fixed pixel width plus a `border-left` is what a side column
looks like**, and every rendered class declaring both must be released by the stacking breakpoint —
to `width: 100%` and `border-left: none`, or to `display: none`. `CoralShellRow.test.tsx` parses
every stylesheet under `src/styles` for that pair and requires it, so a column added beside the
conversation cannot quietly decline to stack. The `height: 100vh` pin is checked the same way: the
stacked shell scrolls as one, and a column still a viewport tall puts a screen of furniture between
the answer and the panels that explain it.

`PlanPanelRight.test.tsx` carries the inline-style guard for that panel, for the same reason
`CoralShellRow.test.tsx` carries it for the shell.

A released column is also `box-sizing: border-box`. Both the panel and the rail carry their own
padding and the shell clips horizontally, so a content-box column at `width: 100%` is the viewport
*plus* its padding wide and the right-hand end of it is cut off with no scrollbar to say so — in
the token meter, that end is the estimated Copilot Credits column. Measured in a headless Chromium
against these stylesheets and a synthetic shell DOM: stacked, the panel and the rail now render
exactly the viewport width at 320, 390, 768 and 900px, where before the fix the panel rendered
430px into a 390px viewport.

### The rail fits its own box, and the column owns one width

Stacking the right boxes is not the same as sizing them. Both were wrong underneath (#60), and each
failure was invisible in a different way.

The rail was a **content box**: 320px declared plus 16px of padding on each side is 353px rendered,
so every width in the stylesheet was 33px short of the truth. Its container declared 280px — a
second number for the same column — and `overflow: hidden`, so on the chat surface a 353px rail
rendered into a 321px box and **53px of it was amputated at every desktop width**, with no scrollbar
to say so. Because `.token-meter` cells could not wrap, the end that fell outside was the estimated
Copilot Credits column: the panel that exists to prove what an answer cost, losing the number.

Stacked, the shell crushed what it held instead of scrolling. Every column in it has a non-visible
`overflow`, and a flex item with one has an **automatic minimum size of zero** — so `overflow-y:
auto` on the shell was a promise it could never keep: its children shrank to fit before it ever
scrolled. Measured at 320px, a conversation 900px tall rendered **17px**, and `.plan-section` held
456px of plan in 382px of box, taking a `max-height: 550px` from a `(max-width: 1920px) and
(max-height: 1080px)` query that a phone matches.

Four rules now, each read out of the stylesheets by the frontend loop:

- **Declared is rendered.** A padded, fixed-width box carries `box-sizing: border-box`, or it is
  wider than every container sized to its number.
- **One width per column.** The rail declares it; `.plan-panel-right` takes `width: min-content`,
  which is the rail's number rather than a second one.
- **One scroll region per column.** The panel scrolls; the rail inside it does not, and stacked
  neither does. A box that caps its own height inside an already-scrolling page hides content behind
  a second scrollbar nobody looks for.
- **Nothing shrinks when stacked.** `.coral-shell-row > * { flex-shrink: 0 }`, so the shell's own
  scrolling is what absorbs the height.

None of that reaches the conversation while its layout is an inline style. `Content` declared
`flex: 1`, `height: 100%` and `min-width: 320px` inline, every one of which beats a media query —
the same trap that made #25's breakpoint inert, one column over, and the column the stacked shell
crushed first. Its layout now lives in `storeSurface.css`, and its minimum width is 280px rather
than 320: 320 plus the task-history panel's 280 plus the rail's 320 is 920px of furniture in a shell
that stacks at 900, so between 901 and 919px the shell — which clips horizontally — silently cut the
end off the rail.

The token meter gives its width up in the **names**, not the figures: `white-space: nowrap` is
scoped to `.token-meter__number`, and `table-layout: fixed` makes the columns shares of the rail
rather than a negotiation the largest token total wins. Measured across 320, 390, 768, 900, 1024 and
1440px on both surfaces: the rail renders exactly its declared width, nothing overflows it in either
axis, and stacked the shell scrolls as one — 961px of page in an 844px viewport at 320px, where
before nothing scrolled at all.

## The heading outline

A query for every heading element on the deployed page returned an **empty list**. Not the wrong
levels — none at all. Fluent's typography components render a generic `span` unless they are told
what element to be, so "How can I help?", "Quick tasks", "Plan Overview", "Grounding", "What this
cost" and "Agent Team" were styled spans, and a screen-reader user had no structure to move
through: the whole surface was one undifferentiated run of text. WCAG 2.1 Level A, 1.3.1.

It matters more here than it would on an ordinary surface, because the **transparency rail**'s
whole job is to be skimmed. The rail exists so that the audience can see where an answer came from
and what it cost without reading every word, and the panel titles are what make that possible.
Rendering them as spans took the rail's argument away from exactly the users who most need it
stated in structure rather than in layout.

Two levels, declared once in `models/headingOutline.ts`:

| Level | What | Where |
| --- | --- | --- |
| `SURFACE_HEADING` (`h1`) | The assistant's name | `ContentToolbar` — the conversation's header |
| `SECTION_HEADING` (`h2`) | "How can I help?", "Quick tasks", "Plan Overview", each rail panel | `HomeInput`, `PlanPanelRight`, the three transparency panels |

The levels live in the module rather than beside each title for the reason `storeSurface.ts` holds
the surface's strings: a level chosen at each call site is a level that drifts, and an outline that
skips one is the same defect this fixes in a different shape.

The page heading has to be the **conversation's header** and not the left panel's, even though both
say the assistant's name. The left panel is dropped at the stacking breakpoint, and a heading the
associate's phone never renders is not an outline.

It is applied with Fluent's `as` override — `TextSlots.root` accepts `h1` through `h6` — rather
than by hand-rolled markup, so the typography classes are still there and still beat the user-agent
sheet. One thing does change, and it had to be measured rather than assumed: a flex item and a flex
container are both **block boxes**, so a blockified `h2` picks up the user-agent's `margin: .83em
0`. In a headless Chromium against the real stylesheets, unzeroed, each `.transparency-panel` grew
from 48px to 71.22px and the Quick tasks header from 20px to 43.22px — about seventy pixels of rail
given up to nothing. Every class that heads a section now declares its own margin, and with those
rules in place all five regions measure identically before and after.

`src/App/src/pages/headingOutline.test.tsx` renders both surfaces and reads the outline off them —
one top-level heading each, every section reachable, no level skipped. jsdom exposes heading roles
and levels, so this is a rendered assertion rather than a source-read one. The exception is the
panel titles: a *new* panel shipping a span is the regression a list of the three that exist today
would never catch, so that one check reads the components' source and requires every renderer of
`transparency-panel__title` to take its level from the module. Confirmed red by moving
`SECTION_HEADING` to `h3` (skips a level) and to `h1` (a second top-level heading on both
surfaces).

### A reply may not head the surface

The words in a reply come from a language model, and `react-markdown` renders a `#` as a real
`<h1>`. So a reply that opened with one put a **second top-level heading** on the chat surface,
above the very panels that explain where that reply came from and what it cost. A screen-reader
user skimming by heading would meet the model's prose before **Grounding** and **What this cost**,
with nothing to tell the surface's structure apart from the answer's. The backend makes it likelier
than it sounds: `orchestration_manager` emits `### {display_name}` into the reply stream, which is
an `h3` arriving before the rail's `h2`s — a skipped level in document order.

The outline is the surface's to declare. `components/content/streaming/replyHeadings.tsx` gives the
element its **role** rather than its tag: `role="presentation"`, so nothing at all changes on
screen and no styling has to be restated in order to strip a semantic. Demoting them instead was
rejected — the conversation has no section heading of its own to descend from, so every reply
heading would skip a level rather than stop skipping one.

It applies to all three Markdown renderers, and the test finds them by searching the source for
`<ReactMarkdown` rather than by naming them: two of the three shipped with react-markdown's
defaults precisely because nobody had asked. The two rendered assertions feed a reply containing
`#`, `##` and `###` and require the surface to expose no heading from it; the plan-surface outline
test carries the same reply, so "exactly one top-level heading" is asserted with an agent talking
rather than only on a silent page. Mutation-checked by dropping the role.

## Labelling what is simulated

`SimulatedBadge` marks anything whose content was authored for the walkthrough rather than produced
by a connected system:

| Labelled | Why |
| --- | --- |
| **Store 223** | A fictional store, with fictional employees and invented procedures |
| The **Presenter alert** | Its words come from a rehearsed roster in `transparency.alert` (#23), not from a shift-task system |
| The **Simulated ticket** | When #22 lands |

The converse matters as much, and is easier to get wrong: a badge on a **real** Foundry answer, a
real Copilot Studio hop or a measured token count gives away the demo's strongest evidence. A
stakeholder who is told everything is simulated has been told nothing. Label the invented things,
and only those.

## Which agent answered

Already true, and now pinned. `StreamingAgentMessage` renders `getAgentDisplayName(msg.agent)` in
the reply's header, which is the executor identifier the backend attributed the output to — the
same attribution the **Token meter** keys its rows by, and the one that survives **Plan review**
being off (ADR-013).

The **Agent Team** panel lists who *could* have answered. Only this says who did, which is the
difference between the assistant reading as several specialists and reading as one black box. An
unnamed executor renders `Assistant` rather than a blank, because a blank where a name belongs
reads as a broken layout.

## Not verified live

Nothing here has rendered against a deployed backend. In particular:

- **The store assistant's pack is authored** (#19) under
  `00000000-0000-0000-0000-000000000223`, and `post_deploy.{sh,ps1}` upload it whatever the stock
  use-case selection is. Recorded in [store-content-pack.md](store-content-pack.md). What is still
  unverified is that the upload lands: nothing here has been run against a deployment, so
  `selectStoreAssistant` has never resolved against a real Cosmos team.
- **The stacking breakpoint has not been seen on a phone.** jsdom does not evaluate media queries,
  so the tests prove the stylesheet can reach the elements, not that the result is usable at 390px.
  The widths in the section above were measured in a headless Chromium against the stylesheets and
  a synthetic shell DOM, which is a stronger claim than jsdom and a weaker one than a phone: it
  proves the boxes are the size they say, not that the panels read well on a handset.
