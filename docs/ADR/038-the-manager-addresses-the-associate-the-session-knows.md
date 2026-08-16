# ADR-038: The manager addresses the associate the session knows, and the addressing stays out of the record

## Status

Accepted

## Date

2026-08-16

## Issue

#94 (map #81, spec 2)

## Context

`BRIEF.md` asks for *"the group chat manager personable through voice and text… if Clara Workman,
our demo user, logs in and opens a new chat, the group chat manager should reply with, 'Hey Clara,'
followed by a response based on Clara's input in the chat thread. It's not necessary to always say
'Hey Clara'… but let's aim for a natural approach to make it feel very personable."*

Seven facts found while grilling shape everything below.

1. **The manager has no persona at all.** It is `Agent(manager_chat_client, name="MagenticManager")`
   (`src/backend/orchestration/orchestration_manager.py:153`), running framework-default Magentic
   prompts imported from `agent_framework_orchestrations._magentic` and *appended to* by
   `get_magentic_prompt_kwargs` (`plan_review_helpers.py:77-320`). There is nothing to make warmer;
   there is only somewhere to author warmth.

2. **Its one existing tone directive is a suppression.** `plan_review_helpers.py:172`: *"Do NOT
   offer further help. Provide the answer and end with a polite closing."* Somebody wrote that on
   purpose. A personability clause appended below it contradicts the line above it, and the model
   resolves that contradiction differently on every run, live.

3. **The manager speaks the answer.** The final reply is generated from
   `ORCHESTRATOR_FINAL_ANSWER_PROMPT + final_append`; the specialists' text goes to the collapsed
   *AI Thinking Process* scratchpad (#88). *Personable manager* and *personable answer* are the same
   change, and no specialist prompt needs touching.

4. **The backend never receives a display name.** `get_authenticated_user_details`
   (`auth/auth_utils.py:6-30`) yields a GUID and an email; the router uses only the id
   (`router.py:176`). The **only** human-readable name in the system is `identity.display_name`,
   written into **Session state** by the **Mocked unlock** and resolved per-turn at `router.py:344`.

5. **The surface starts anonymous on purpose,** and that is the demo's centrepiece.
   `docs/mocked-unlock.md`: *"A fresh tab is an anonymous shared store device, which is where the
   demo has to start,"* and *"the delta between those two moments is the licensing and governance
   conversation the customer has been avoiding."* There is no log-in in this product except the
   simulated one in beat 6. The brief's *"logs in"* describes a door that exists exactly once.

6. **The manager's prompt cannot learn a name mid-session.** The team is cached by **`user_id`**
   (`connection_config.py:26` — `# user_id -> workflow instance`) and built eagerly at `/init_team`
   (`router.py:235`), while identity is stored per **`session_id`** (`store.py:33`).
   `get_magentic_prompt_kwargs` is called only at build time (`orchestration_manager.py:176`) and
   takes three static team-level arguments. Both rebuild predicates —
   `orchestration_manager.py:293` and `router.py:527` — contain **no identity term**. Sign-in
   happens strictly after `/init_team`, so a name in the prompt would never arrive; and if it were
   made to arrive, it would arrive on the wrong key, greeting an associate by name in the next chat,
   which is supposed to be anonymous.

7. **`task_text` is not a private local.** It is the default input to everything below
   `orchestration_manager.py:419`: the team-scope classifier (`:427`), `convert_plan_review_to_mplan`
   (`:493`), and `mplan.user_request` (`:830`), which the frontend prints as a literal heading —
   `StreamingPlanResponse.tsx:381`: `` `Proposed Plan for ${planApprovalRequest.user_request || 'Task'}` ``.
   Prepending to it puts scaffolding on a projector and into a classifier's judgement. Upstream is
   clean: the **Identity boundary gate** (`router.py:347`), the **Lane router** (`:505`) and
   `Plan.initial_goal` (`:462`) all read `input_task.description` unmutated, and the chat bubble is
   rendered client-side from what was typed.

## Decision

**The manager addresses the associate the session knows, and the addressing stays out of the
record.** Ten things follow, and they are part of this decision rather than separate work.

1. **Named address is gated on the Mocked unlock.** Before sign-in the manager is warm and
   **unnamed**; after it, it uses the name freely. This is not a concession to the beat — it
   *recruits* the greeting as evidence for it. On one tap the room watches an assistant that was
   polite-but-generic learn who it is talking to, in the same gesture that unlocks the PTO answer.
   Personability becomes a second, felt demonstration of the governance argument instead of a
   contradiction of it.

2. **The greeting rides the first reply; it is never an unsolicited utterance.** The brief's own
   sentence settles this — there is no *"Clara's input"* to respond to until she has typed. A
   welcome produced on chat-open would have to either wait on `init_team`'s synchronous rebuild
   (#86) — a greeting arriving after you have started typing — or be authored in the frontend, which
   is words attributed to an agent that never ran, ADR-023's rule applied to a speaker instead of a
   phase. It would also be built in the same spec that *removes* the manager's accidental unsolicited
   repeats (#87), and on stage nobody can distinguish the deliberate one from the defect. An instant
   greeting on open is permitted only as **surface chrome that does not claim to be the manager** — a
   heading, not a message bubble — and that is spec 1's decision, not this one.

3. **Disposition is authored in the prompt; the addressee is carried per turn.** They are different
   kinds of thing and they have different lifetimes. Tone is static and team-level, so it belongs in
   `get_magentic_prompt_kwargs` beside the rules already there. The name is per-session and arrives
   mid-session, so it cannot live there at all (fact 6).

4. **`task_text` stays pristine; the augmented string is the narrowly-named one.** A second local —
   `manager_task_text`, or similar — is composed and used at **exactly one call site**,
   `workflow.run()` (`:461`). The scope classifier, the plan conversion and `mplan.user_request`
   keep reading `task_text` and are correct **without being modified at all**. This is chosen over
   prepending-and-fixing-the-leaks specifically for which way the default points: under the
   alternative, the safe thing requires remembering, and every future consumer of an innocuously
   named variable inherits the leak. This repo has twice shipped exactly that failure —
   `FollowOnTask` consulting no clarification state, and `/v4/user_clarification` ungated for its
   whole life (#91, ADR-034).

   The principle, stated so it can be applied elsewhere: **the associate's words are the record; the
   addressing is a view.** Everything stored, classified or shown reads what the associate actually
   typed. Only the model's view of the turn carries who is asking, so a bug in the addressing can
   never corrupt a record, a routing decision or a heading — and `user_request` stays honestly named.

5. **Warmth is address; offers stay controls.** *"Do NOT offer further help"* **survives**, and
   personability enters as a separate, positively-framed clause about addressing the associate —
   never as a general *"be friendly,"* which is the instruction most likely to erode every other
   rule in that prompt by tone alone. The line is not arbitrary: ADR-033 already decided that what
   comes next is *"an edge in a graph rooted at the task that produced the current turn"* — an offer
   of further help **is** an offer of a next action, and it already has a deterministic owner in the
   **Follow-on task** graph. Prose can offer a step that does not exist; a chip cannot.

6. **The address name is authored on the record, never computed from it.** `AssociateRecord`
   (`records.py:44`) gains an authored address name — `display_name="Clara Workman"` alongside
   *"Clara"*. No name-splitting anywhere, on either side, ever. `docs/mocked-unlock.md` already made
   this argument one level up: *"The record is shown whole… deciding which number a phrasing wants
   would be a third classifier behind the gate's two, and a third classifier can report the wrong
   number."* Splitting a name is code guessing which part of a person's name to say, which is wrong
   for mononyms, for compound given names, and for a large fraction of humans. It is correct today
   only because there is exactly one authored associate whose name is two ASCII words — and spec 4's
   peer-approval workflow is specifically going to add more.

7. **It fails towards silence.** An absent or blank address name yields a manager that is warm and
   **unnamed** — never a fallback to the full display string. This matches
   `resolve_session_identity` (`identity.py:38-58`), where missing, malformed and blank all yield
   `ANONYMOUS`, and it matches the record's own rule: *"No record is a true answer… degrading
   towards we hold nothing about you is the direction the gate degrades in."* The **Associate
   record** stays the single source; **Session state** keeps carrying only `display_name`, which is
   the lookup key, because two name fields written to two places are two strings free to drift.

8. **One check at the seam, and deliberately nothing that judges prose.** Decision 4 makes the rule
   structural, so it is exactly assertable: *when the resolved identity is `ANONYMOUS`, the string
   handed to `workflow.run()` is byte-identical to `input_task.description`; when it is signed in,
   it and only it carries the addressee.* That is a pure unit test — no model, no embedding, no
   deployment, no flake — and it lands on the two tests decision 4 already forces
   (`test_orchestration_manager.py:900`, `:918`). It is the only thing standing between the demo and
   a later regression that threads identity into the team prompt "for convenience"; that failure is
   silent, shows only on stage, and lands on the one beat the walkthrough exists to deliver.

   **No e2e assertion on the greeting.** `docs/demo-validator.md:90` already forbids it — assertions
   are *"never on the wording of anything a model wrote"* — and such a test would go red on a good
   build because a model phrased a greeting differently. The structural half is checked exactly, the
   prose half deliberately not, and the asymmetry is recorded here so nobody later "fixes" it.

9. **The runbook states the invariant, not the wording.** Beat 6 now shows two things changing on
   one tap. `docs/presenter-runbook.md` is asserted string-for-string by `test_presenter_runbook.py`,
   and a runbook promising *"the manager will say 'Hey Clara'"* writes a cheque a model can decline
   to cash — so it says that before sign-in the assistant cannot know your name, and after it, it
   does. This rides with the say-out-loud lines ADR-036 decision 6 is already adding to that beat.

10. **Voice inherits the words; spec 6 owns delivery.** Everything above is about *what is said* and
    is transport-independent, so voice reuses it whole. A second persona authored for voice would be
    a second set of words free to drift, and the drift reads on stage as two products. Spec 6 keeps
    the genuinely different half — prosody, voice selection, barge-in, the orb. It also inherits one
    constraint from here rather than rediscovering it: **a voice turn goes through the same seam.**
    #97 found both WebRTC paths hand back a real `MediaStream`, which makes a direct-to-model voice
    path easy to build and would bypass the gate, the Lane router and this addressing rule together —
    ADR-034's failure a third time. A bypass has one legitimate trigger, and ADR-013 already made it
    a measured number rather than a preference.

**Warmth is uniform.** It applies on refusals and honest misses exactly as on successes. The
alternative makes *tone a signal* — the room learns to read bad news from the register before the
words arrive, and warmth conditional on outcome is what makes warmth feel manufactured. The content
is untouched: ADR-017 and ADR-023 keep governing what may be said, unamended, and decision 5 already
removes the way warmth actually corrupts a miss, which is by offering. The demo's highest-stakes
refusal is unaffected **by construction** — the **Policy block** is raised at `router.py:347`,
upstream of orchestration, so the manager is never invoked and there is no warm sentence to write.

This is the *decision*, not the change. Per #81 this ticket produces ADRs; the implementation is
spec 2's.

## Considered Options

- **Bake the name into the manager's prompt**, threading `display_name` into
  `get_magentic_prompt_kwargs` beside the tone rules. The obvious implementation, and the reason
  this ADR exists — the next reader will propose it again. Rejected on fact 6: it never arrives, and
  forcing it to arrive rekeys a `user_id` cache against `session_id` identity and greets people by
  name in chats that are supposed to be anonymous.
- **Prepend the addressing to `task_text` and fix the two leak sites.** The honest runner-up; it
  works. Rejected on decision 4, for which way the default points.
- **Let the manager greet by name from first paint,** taking the brief literally. Rejected on
  decision 1 and on `docs/mocked-unlock.md`: *"A header that went on naming an associate the gate
  just declined to answer for is the one thing no surface here may do."*
- **A general "be personable and friendly" clause** appended to `final_append`. Rejected on decision
  5: it contradicts the line directly above it, and its blast radius is every other rule in a prompt
  whose job is to stop the assistant sounding more certain than its evidence.
- **Drop *"Do NOT offer further help"*** as incompatible with warmth. Rejected on decision 5 — it
  hands prose a job ADR-033 gave to a checked control.
- **Split the display name on the first space.** One line, works today. Rejected on decision 6.
- **Write the address name into Session state at sign-in** alongside `display_name`, avoiding a
  lookup. Rejected on decision 7: two name fields in two places drift, which is the failure
  `docs/mocked-unlock.md` already names for the browser — *"the name the header shows and the name
  the record is keyed by would otherwise be two strings free to drift."*
- **Assert the greeting in the Demo validator.** Rejected on decision 8; it breaks the validator's
  stated policy and is flaky in the worst direction.
- **Badge the greeting with the Simulated label.** Overtaken by ADR-036, which deletes the badge
  outright — see Consequences.
- **Make specialist agents personable too.** Rejected on fact 3: the manager speaks the answer, the
  specialists' prose reaches only a collapsed scratchpad, so this would be cost without a visible
  effect and would put tone instructions into seven prompts instead of one.
- **Author a separate voice persona.** Rejected on decision 10.

## Consequences

- **Positive — the rule is structural, not instructed.** When nobody is signed in, the model is
  never given the name, so it cannot say it for the same reason it cannot state a PTO balance: it
  was never told. That survives a model swap, a temperature change, and a prompt-injection attempt
  in the associate's own text, none of which an instruction survives.
- **Positive — the diff is small and lands where the check lands.** One authored field, one prompt
  clause, one new local, one changed argument, two updated tests.
- **ADR-036 removed this decision's original justification, and the conclusion survives.** The
  badge question was answered here as *"no new badge — the name is already badged where it is
  asserted, on the header and the personal answer."* ADR-036 landed while this was being decided and
  **deletes both of those badges** (`SimulatedBadge` and `SIMULATED_LABEL` deleted;
  `PERSONAL_ANSWER_NOTE` deleted). The premise is gone; the answer is unchanged and now simpler —
  there is no badge to add. It also restates cleanly in ADR-036's surviving vocabulary: disclosure
  *"stays in the words,"* and the surviving prose disclosure is `HomeInput`'s sign-in line, *"Simulated
  sign-in — no identity provider is involved,"* which decision 2 of that ADR keeps unchanged. **That
  line and the greeting are produced by the same tap.** The disclosure and the personalisation are
  not merely compatible, they are simultaneous.
- **Negative — the manager's warmth is unmeasured, permanently.** Decision 8 checks the structure
  and refuses to check the prose, so *"is it too much?"* is answered by a person watching a
  rehearsal and never by CI. That is the correct trade, but it means tone regressions are found on
  stage or not at all, and `scripts/sop-rehearsal.sh` is the only instrument that would see one.
- **Negative — decision 2 leaves a real gap.** Opening a new chat still shows the associate nothing
  personable at all, because the only honest instant greeting is chrome and chrome is spec 1's. If
  spec 1 declines it, the brief's *"opens a new chat"* is satisfied only from the first reply
  onwards.
- **A live contradiction is named, not resolved here.** `plan_review_helpers.py:112` — *"MagenticManager
  NEVER asks questions directly — it only routes tasks to agents"* — flatly contradicts `BRIEF.md`
  line 7's premise that the manager asks the clarifying questions. That is #87 and spec 1's
  territory; it is recorded here because specs 1 and 2 must not answer it differently.
- **Spec 4 inherits decision 6.** Peer associates and an approving manager are more authored people,
  and each needs an authored address name rather than a split. ADR-037 governs how those personas
  are *presented*; decision 6 governs what they are *called*.
- **Testing.** Nothing here is implemented by this ADR. Decision 8's assertion lands in the Backend
  tests loop (`src/tests/backend/orchestration/test_orchestration_manager.py`); decision 9 lands in
  the CI-tooling loop (`src/tests/ci/test_presenter_runbook.py`). No loop changes shape, and the
  Guardrail corpus is untouched — it scores the incoming request (`router.py:347`), never the
  manager's output.

## References

- [ADR-013: Vary Plan review per request instead of building an orchestrator bypass](./013-per-request-plan-review-over-orchestrator-bypass.md)
  — the measured trigger decision 10 defers to
- [ADR-014: The identity boundary gate is deterministic code, not a prompt](./014-deterministic-identity-boundary-gate.md)
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md)
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md)
- [ADR-033: A one-tap control never invents the words it offers](./033-a-one-tap-control-never-invents-the-words-it-offers.md)
  — decision 5 is its boundary applied to prose
- [ADR-034: The Identity boundary gate covers the clarification seam](./034-the-identity-boundary-gate-covers-the-clarification-seam.md)
  — the failure decision 10 exists to prevent a third time
- [ADR-036: The Simulated badge comes off, and the disclosure stays in the words](./036-the-simulated-badge-comes-off-and-the-disclosure-stays-in-the-words.md)
  — removed this ADR's original badge justification; see Consequences
- [ADR-037: A fabricated human decision is never indistinguishable from a real one](./037-a-fabricated-human-decision-is-never-indistinguishable-from-a-real-one.md)
- `CONTEXT.md` — **Address name**, **Addressed turn**, **Mocked unlock**, **Associate record**,
  **Signed-in device**, **Session state**, **Identity boundary gate**, **Policy block**,
  **Follow-on task**, **Lane router**
- [docs/mocked-unlock.md](../mocked-unlock.md) — the anonymous start, and why the record is shown whole
- [docs/demo-validator.md](../demo-validator.md) — the policy decision 8 declines to break
- [#97](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/97) — the Azure Speech
  research decision 10 hands its constraint to
