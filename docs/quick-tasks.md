# The seven Quick Tasks

Issues #26 and #52. The presenter runs the whole scripted walkthrough by
tapping. Seven tasks, one per beat, each declaring the **Lane** it takes — and each held to
the corpus, the router and the gate it depends on by a test, because a Quick
Task is a claim about what will happen when somebody taps it. Six appear on
the home grid: **I can't fix it** is a follow-on inside the troubleshooting
conversation, so it carries that conversation's session into the escalation.

## The walkthrough

They render in this order, which is the order the demonstration runs in.

| # | Task | Prompt | Lane | The beat |
| --- | --- | --- | --- | --- |
| 1 | Close the store | *How do I close the store?* | fast | R2/R6 — the cross-platform hop, `Foundry orchestrator → Copilot Studio → Dataverse` |
| 2 | Restart the car wash | *How do I restart the car wash after a vehicle stalls in the bay?* | fast | R2 — the rehearsed honest miss |
| 3 | The coffee brewer is down | *The coffee brewer is down. It is not brewing on the left head.* | fast | R3 — multi-turn troubleshooting with **Attempted steps** |
| 4 | I can't fix it (follow-on) | *I have tried everything and I can't fix it. I need someone to come out.* | **deliberate** | R4 — the approval *is* the **Simulated ticket** being raised |
| 5 | How much PTO do I have? | *My name is Tanya, how much PTO do I have?* | fast | R5 — the **Identity boundary gate** refusing, and #27's sign-in |
| 6 | What is due this shift? | *What tasks are due on this shift?* | fast | R8 — where the **Presenter alert** leads |
| 7 | Swap a shift | *Marcus Bell and I have agreed to swap our Saturday shifts. Start the swap.* | **deliberate** | ADR-028 — the **Workforce agent** follows an agreed transaction into a **Reviewable plan** |

The opening tap is the cross-platform hop **deliberately**: it is the claim the
whole demonstration exists to make, and the honest miss that follows it only
reads as honesty once the audience has watched the same surface answer.

## Nothing here is a list this repository keeps twice

Three of the seven prompts are read out of the corpus they were written against
rather than restated, because the Quick Tasks are authored in `content_packs/`
and the SOP corpus in `content/sop/`, by different tools, and a prompt that
drifted a word away from the corpus would go unnoticed on both sides.

| Prompt | Read from | Asserted by |
| --- | --- | --- |
| Close the store | `corpus.toml` `[rehearsed_hit]` | `test_given_the_opening_task_when_read_then_it_is_the_cross_platform_hop` |
| Restart the car wash | `corpus.toml` `[honest_miss]` | `test_given_the_honest_miss_task_when_read_then_it_is_the_corpus_own_question` |
| How much PTO do I have? | `guardrail.corpus.POSITIVE_PROBES` | `test_given_the_boundary_probe_when_read_then_it_is_a_measured_probe` |
| Shift-swap process question | `guardrail.corpus.NEGATIVE_CONTROLS` | `test_given_the_shift_swap_process_question_when_read_then_it_stays_a_measured_control` |

`[rehearsed_hit]` is new, and it is the mirror image of `[honest_miss]`. The
honest miss has always been guarded — the corpus keeps its `absent_terms` out
so the question stays unanswered. Nothing guarded the other direction, and a
miss is what a **hit** decays into: rename `SOP-102` away and the opening tap
still resolves, honestly, as *that procedure is not in the library*. Nothing
goes red, no log line appears, and the centrepiece beat has quietly become the
honest-miss beat played twice. So the section names the document, and two tests
read it: one that the identifier exists in `content/sop/src`, one that the
document it points at is about closing the store.

## The lane is load-bearing in two directions

A Lane decides exactly one thing — whether the plan-review gate is built — and
`StartingTask.lane` is an unvalidated `Optional[str]` on purpose (#16): an
authoring slip must fail **open** in the lane router rather than reject the
whole team definition. That is the right failure mode and it is also a silent
one. `parse_lane("Fast lane")` returns `None`, the router falls open to the
Deliberate lane, and the only visible symptom is a procedure lookup that grew
an approval step. So every declared lane goes through the real `parse_lane`.

**A Quick Task submits in one interaction.** Its native button sends its
authored prompt with its declared Lane, so there is no filled box between the
tap and the request. A presenter who needs to adapt a prompt types it as a
free-text question; that request declares no Lane and belongs to the **Lane
keyword fallback**. The escalation and agreed shift-swap prompts are therefore
asserted to route Deliberate through the fallback *as well as* by declaration,
and every other prompt that reaches the router is asserted to route Fast.

The keyword fallback defaults to **Deliberate**, so a prompt carrying no fast
vocabulary at all is the trap here, and it is not hypothetical: *"Walk me
through the store closing procedure"* — the previous placeholder — matches
nothing in `FAST_LANE_TERMS` and would have grown an approval step the moment
anybody edited it.

## The boundary probe is caught by the keyword tier, not the threshold

R5's beat must fire on every rehearsal. The **Identity boundary gate** is
hybrid: a pure keyword fast path, then an embedding-similarity tier scored
against a threshold. The similarity tier is a live model call, and while the
gate fails closed either way, a beat that depends on infrastructure is a beat
that can be slow, or different, on the run that matters. So the one-tap probe
is asserted to be caught by `matches_personal_keyword` — deterministically, at
zero cost, which is also what keeps the Token meter's measured `0` for that row
true every time.

The converse is asserted too, and it is the more important half: **no other
Quick Task may trip the gate**. The keyword fast path's requirement runs one
way only — it may miss a personal question, but it may never trip on a
store-level one — and a false positive here does not slow the demonstration
down. It refuses the beat outright, with copy explaining that the assistant is
store-scoped, which is the most convincing possible way to look broken.

The probe is also where the walkthrough ends, so the name it gives is not
decoration. The **Mocked unlock** (#27) rides this same tap — refused, signed
in, asked again unedited — and it answers out of the **Associate record**, which
is keyed by name. A probe naming somebody the record does not hold would have
the beat answer one person's question with another person's PTO balance, which
is the closing argument making the opposite of its point. Asserted by putting
the prompt's own words through `lookup_associate`, not by restating the name.

## The probe declares the Fast lane, and the badge stopped promising an answer

The probe never reaches the lane router: the gate runs above it and above
orchestration, so the request takes no lane at all. Its declaration is still a
real fact about the task, and `LaneBadge`'s documented meaning on a Quick Task
is *the lane declared, before anything is submitted*. What was not true is what
the badge **said**: *"Answered straight away — no approval step"*. Two claims,
and this task falsifies both — it is never answered, and **Fast-lane latency is
still unmeasured**, which ADR-013 makes the sole trigger for reopening the
orchestrator-bypass question. A tooltip is not where that number gets asserted
for the first time.

The badge now says only what a Lane decides: *"No approval step — nothing is
submitted for you to confirm."*

## The one place the presenter would still have had to type

`TroubleshootingAgent` is instructed to *ask the associate what they have
already tried*, so R3 is multi-turn by design and answering a Clarification is
free text in the chat box. Seven taps on the home screen do not reach it, and a
walkthrough that is tap-only up to the third beat is a walkthrough with a
keyboard in it.

So the Quick Task that provokes a question authors the answers: **Rehearsed
replies**, rendered as one-tap chips above the box while a clarification is
pending, submitted through the same `OnChatSubmit` a typed answer takes.

They are load-bearing beyond the typing. The clarification seam records what
arrives there as **Attempted steps** (#21), and the **Simulated ticket** R4
raises carries them (#22). Three replies, each naming a step RB-201 branches on,
and the suite puts every one of them through the **real matcher**:

| Asserted | Why |
| --- | --- |
| Each reply parses to at least one Attempted step | A denial, a substituted answer or a single shared word records **nothing**, and a tap that records nothing looks exactly like a tap that worked. |
| Together they reach `ESCALATION_AFTER` | The escalation offer is what leads into R4. Replies that merge down to two steps leave a walkthrough where nobody is ever offered a ticket. |
| Two anchor words of each reply appear in a runbook | The skip rule is the beat. A reply naming something no runbook asks for is answered by a runbook that skips nothing, and the memory changed no behaviour. |
| None of them trips the **Identity boundary gate** | Same one-way requirement as the taps themselves: a refusal mid-repair ends the beat with copy about the assistant being store-scoped. |

**The pending-clarification gate is the component's own, not the call site's.**
Outside a clarification the chips are a second way to start a turn, competing
with the box — and a gate the caller owns is a gate the second caller forgets.
That is #22's move at a smaller seam.

**And they are resolved from the plan's own `initial_goal`, not carried in
router state.** State does not survive a reload, and a presenter who reloads
mid-beat is exactly the presenter who needs the tap — the same reason the lane
*taken* is read back from server-side session state (#20). A goal matching no
Quick Task prompt resolves to none, which is what an edited prompt is and what
the declared Lane already does with one.

## Six cards on a phone

Two findings that only six tasks expose, both of the shape #25 found in
`CoralShellRow` — a rule that is present, correct and completely inert.

* The cards were wrapped in a bare `<div>` **inside** the CSS grid, so the grid
  had one child and laid out one column. With two tasks that reads as a
  deliberate layout. With six it pushes the input box off the screen.
* `HomeInput.css` set `flex-wrap` and `flex` inside its breakpoints, on an
  element declared `display: grid`, where neither property does anything at
  all — and it declared them at 768px and 480px, neither of which is a width
  anything else on the surface reflows at.

The grid is now `repeat(auto-fit, minmax(200px, 1fr))`, so it reflows
continuously with the width it is given rather than at a breakpoint, and it
pins to one column at 640px. That is narrower than the **Stacking breakpoint**
and deliberately so: by 640px the shell has already stacked, so the floor is a
minimum on a fluid grid rather than a second orientation for the surface (#58).

The seventh card (#52) needed no layout change for that reason: `auto-fit` over
a `minmax` track reflows with the width it is given, so the row that held six
holds seven. That is what a rule fixed at a breakpoint would not have done, and
it is why the finding above was worth fixing rather than working around.

## The card stopped fighting itself for space (#59)

Six cards laid out correctly is not six cards anybody can read. Measured on the
deployed surface at 1440px, every one of the six titles wrapped onto two lines
and none of them needed to: the badge shared the title's flex row, so
*"I can't fix it"* — fourteen characters — was allotted 62.9px of the 203px the
card had, beside a 104.4px *Needs approval* pill. The badge suffered worst, and
the badge is the point: the Fast lane / Needs approval contrast is something the
demonstration says out loud, and it was the element being crowded out.

Three separate causes, and each of them a different layer:

* **The eyebrow.** The badge moved to a row of its own ahead of the title, and
  the icon followed it — a 20px glyph and its gap took 28px of the 205px the
  padding left, which is what asked *"The coffee brewer is down"* to fit in
  177px. Both are decoration for the card rather than for the words, and up
  there they land at the same position on all six cards, which is the whole
  reason a grid of badges can be scanned at all.
* **Two lines of description, always.** The descriptions are the tasks' own
  prompts, 25 to 71 characters, so they came out at one, two, two, three, two
  and two lines. Shortening them is not on offer — they are what the tap asks,
  and the corpus and the rehearsal marker are held to their exact wording — so
  the card clamps to two lines and reserves the second whether or not it is
  used. `fullDescription` is still what the tap submits.
* **`grid-auto-rows: 1fr`.** Grid rows are sized independently by default, so
  the row holding the one card that had to wrap was taller than the other and
  the six beats read as two unrelated strips. Measured at 118, 118, 118 then
  138, 138, 138.

Underneath, the card had been styled with inline styles and imperative hover —
`onMouseOver` / `onMouseOut` mutating `element.style`, one of which reassigned
the border it already had. That is why it had no theme-aware hover, no press
feedback at all on the touchscreen this is operated from, and no focus ring of
its own; `HomeInput.css` reached in at `.home-input-quick-tasks .fui-Button` to
add one, with `!important` twice, naming a class Fluent generates. It is Griffel
now: hover, press, disabled and `:focus-visible` are ordinary declarations on
the card, spacing comes from the Fluent spacing scale rather than from five
pixel literals, and the lift is dropped entirely under
`prefers-reduced-motion` — `index.css` only shortens transitions to 0.01ms,
which makes a lift *instant* rather than absent.

Measured after, in Chromium at 320, 768, 1024 and 1440px: no title wraps at any
of them, every card is 128px tall, and the badge sits 17px from the top of each.

## What is not covered here

* **Nothing has run against a deployment.** That tapping *Close the store*
  actually produces a Copilot Studio hop is asserted about the corpus and the
  roster, not measured against a live Direct Line conversation.
* **The seventh tap proves routing, not grounding.** The browser beat grades the
  **cost table** — that the `workforce` toolbox's holder was billed, read off
  the pack rather than named — and the **Policy block**'s
  absence. It does not require `WF-401` in the reply: the **Workforce procedure
  library** is reached as a tool with no `source_used` behind it, so its
  identifier lives only in prose a model wrote. See ADR-017's amendment.
* **Fast-lane latency is still unmeasured**, so "a few seconds with no approval
  prompt" is proven only in its second half — the approval step's absence is
  the Lane, and the Lane is asserted end to end.
* **The rehearsed replies are written against the question the system message
  tells the agent to ask, not against one a live model has been seen to ask.**
  If a turn asks for an observation instead — RB-201's branches want one — the
  chips answer a question nobody asked, and the presenter is back in the box.
  The failure is visible and recoverable, which is why the replies were written
  as attempted steps rather than as observations: an observation submitted to
  the clarification seam is **recorded as a step**, and a recorded step is one
  the assistant will skip.
* **`content/sop/corpus.toml`'s new section is read by `store_pack`, not by
  `tools/sop_corpus`.** That tooling's own tests are not in any declared
  feedback loop, so extending its verifier would have added an unrun
  assertion. The guard lives where the loop can run it.
* **The phone breakpoint has still not been seen on a phone.** jsdom does not
  evaluate media queries; what is asserted is that the stylesheet declares one
  and that no dead flexbox rule sits inside it.
