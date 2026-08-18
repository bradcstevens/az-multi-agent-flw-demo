# The presenter runbook

Issue #53. Everything you need to run the **Circle K Frontline Store Assistant** demonstration
from a URL, alone, in front of the customer. You do not need to know how it is built.

Read the two boxes below before anything else. They are the only two things you have to do that
**nothing on screen tells you about**, and three of the seven beats depend on them.

> ### 1. The presenter chord — **Ctrl + Alt + Shift + A**
>
> There is no button and no hint. Pressing it makes the assistant post a shift-task alert on its
> own, which is beat 7. Press it once — holding it does nothing extra, by design.
>
> **It only works while a chat is open** — that is, on the screen you are on *after* asking
> something, not on the home screen with the six cards. On the home screen the key does nothing at
> all. That is why beat 7 taps the card first and fires the chord second.
>
> **If you miss it:** beat 7 has no opening. The last tap still answers, but the claim *"it can
> reach out to you, not just answer you"* never gets made.

> ### 2. The rehearsed-reply chips — beat 3 only
>
> When the assistant asks you *what have you already tried*, three one-tap answers appear **above
> the message box**. Tap them. Do not type your own.
>
> **If you type instead:** what you typed may not match anything the assistant recognises as a
> step it has already tried, and the ticket in beat 4 then comes up short — in front of the
> customer, contradicting the strongest claim in the whole demonstration, which is that nobody had
> to repeat themselves.

---

## Before you start

| | |
| --- | --- |
| **What you need** | The URL you were sent, and a laptop. Chrome or Edge. Nothing to install, nothing to sign into. |
| **Screen** | Full screen, and wide enough for the panels on the right to be visible — they are the evidence. Below 900px wide they stack underneath, which is fine to *show* and awkward to *drive*. |
| **Rehearse** | Run the eight taps once end to end before the meeting. It takes about ten minutes and it is the only way to know today's deployment is healthy. |
| **Do not reload the page** mid-demonstration | The cost meter on the right accumulates across the whole walkthrough and is the only thing that does. A reload empties it, and the comparison in beat 5 is gone. |
| **Between beats** | Use **New chat** between beats 1, 2 and 3. Beat 4 continues beat 3 from its follow-on card. Beats 5 and 6 never leave the home screen: the refusal and the answer appear directly under the message box, which is what makes them a before-and-after. If you leave a conversation by mistake, you can reopen it and carry on — see [If you lose your place](#if-you-lose-your-place--reopen-the-chat-and-keep-going). |

**Ask an engineer to clear the deployment before a customer session.** One command does it:
`bash scripts/sop-rehearsal.sh` ([sop-rehearsal.md](sop-rehearsal.md)) — ten Demo validator runs
against the deployed surface, and it stops at the first red one and names the layer to fix. Ten
because the opening beat has never been proved ten times in a row (#54) and a single green run
cannot tell you that. The honest miss that used to cost it two runs in eight was traced to the SOP
agent's own Fallback topic and fixed on 2026-08-14 — nine of ten runs since, and the tenth was the
answer arriving correctly and then being buried under a troubleshooting question. Keep the video and HTML report from one of those runs — that is the recording at the bottom of
the fallback ladder, and it only counts if it is from a green run. A direct probe of the procedure
library is **not** a substitute: it answers whether Copilot Studio is up, not whether the Foundry
orchestrator reaches it, and the hop is the whole claim.

**The rail says who is available before you type anything.** Once the page has finished loading the
assistant, the Agent Team panel on the right reads **4 specialists available**, with nothing sent
and no question asked. Point at it in the first thirty seconds — it is the *"several specialists,
not one black box"* claim made before a single token has been spent, and it costs nothing to show.
Note what it does **not** say: it says *available*, never that any of them took a question. Which
ones take part is named as each one answers, and on beat 5 the answer is **none of them**. If the
panel is not there yet, the assistant is still starting; give it a moment rather than reloading.

**The demonstration opens with nobody signed in**, and that is deliberate — say so early. The
header reads **Store 223** and **No user signed in**. This is a **shared store device**: one
tablet behind the counter, used by whoever is on shift, with no individual identity in the
session. That is the real deployment shape for frontline retail, it is the reason the licensing
conversation is hard, and it is the setup for beat 6. If you skip past it, beat 6 has nothing to
be a contrast with.

---

## The eight taps

Tap the card, then send. Use **New chat** between conversations, except where beat 4 continues beat 3.

### 1. Close the store — the cross-platform hop

**Tap:** `Close the store` — *"How do I close the store?"*

**Say:** *"This is an ordinary store question. Watch the panel on the right while it answers."*

**They should be looking at:** the **Grounding** panel on the right.

**What lands:** numbered closing steps, and the Grounding panel lights up reading **Copilot
Studio**, over the route *Foundry orchestrator → Copilot Studio → Dataverse*, citing
**SOP-102**.

**The claim:** this one answer left Azure AI Foundry, was produced by a low-code agent your
business team owns in Copilot Studio, and came out of Dataverse — while every other answer in
this demonstration stays in Foundry. Two platforms, one conversation, and the panel is a live
trace rather than a diagram. **This is the beat the whole demonstration exists to make.**

### 2. Restart the car wash — the honest miss, on purpose

**Tap:** `Restart the car wash` — *"How do I restart the car wash after a vehicle stalls in the
bay?"*

**Say, before it answers:** *"Store 223 has no car wash, so there is no procedure for this. I want
you to see what it does when it does not know."*

**They should be looking at:** the answer, then the Grounding panel.

**What lands:** the assistant says plainly that it has no such procedure. The Grounding panel
shows the same route and *"found no matching procedure"*.

**The claim:** it is grounded, not generative-with-confidence. **This miss is deliberate and
rehearsed** — the question was chosen because the library genuinely does not cover it. Frame it
before it happens, never after, or it reads as the demonstration failing. It is also why beat 1
is believable: the same surface that answered SOP-102 refuses to invent this one.

### 3. The coffee brewer is down — memory of one shift

**Tap:** `The coffee brewer is down` — *"The coffee brewer is down. It is not brewing on the left
head."*

**What happens:** the assistant asks what you have already tried. **Three chips appear above the
message box.** Tap them — one at a time, sending each:

- *"I switched it off at the wall and back on again."*
- *"I put a fresh paper filter in and rinsed the brew head."*
- *"I reseated the brew basket in its rails."*

**Say:** *"I am telling it what I have already done. Notice it never walks me back through any of
it."*

**They should be looking at:** the conversation itself — specifically that no suggested step
repeats one you just gave.

**The claim:** the assistant remembers what this shift already tried and skips it. Keep tapping
until it offers to escalate.

### 4. I can't fix it — the approval *is* the ticket

**Tap:** `I can't fix it` — the follow-on card above the message box — *"I have tried everything
and I can't fix it. I need someone to come out."*

**What happens:** this one takes the **deliberate lane** — a plan appears and waits for you. Press
**Approve Task Plan**. A service ticket card appears, marked *Simulated*.

**Say, while they read the ticket:** *"Everything I told it three minutes ago is already in this
ticket. Nobody re-typed it, and there was one confirmation, not two — approving the plan **is**
raising the ticket."*

**They should be looking at:** the attempted-steps rows on the ticket.

**The claim:** the two lanes are visibly different — a procedure lookup comes straight back, while
anything that acts on the associate's behalf stops and asks. And context survives the handoff to
the service desk.

### 5. How much PTO do I have? — the boundary

**Tap:** `How much PTO do I have?` — *"My name is Tanya, how much PTO do I have?"*

**What lands:** it is refused, immediately, under the heading **Store-scoped assistant**. The
refusal explains that the assistant is set up for the store rather than for individuals, that on a
shared device it cannot tell who is asking, and where to take a personal question instead.

**They should be looking at:** the **What this cost** panel — the refusal's row reads **0** tokens
and **0** credits.

**Say:** *"That was refused by code, before any agent ran and before a single token was spent. The
cheapest guardrail is the one that never reaches a model."*

**Then improvise.** Type your own paraphrase — *"When do I get paid next?"*, *"How many days off
have I got left this year?"*, or better, one the audience gives you — and it fires again. Do this.
It is the answer to *"you just hardcoded that"*, and it is worth more than the scripted tap.

### 6. Sign in to continue — the door in the wall

**Tap:** the **Sign in to continue** button **inside the refusal**. It is deliberately not a
separate login screen.

**Say, before you tap:** *"Simulated sign-in — no identity provider is involved."* Say it out
loud, unprompted. A stakeholder who works this out for themselves afterwards stops believing
everything else you showed them.

**What happens:** the header gains a name, and the *same question, unedited* is asked again — and
answered out of an authored associate record. Alongside its *Simulated* badge, the record carries a
Provenance line that no payroll system was queried.

**They should be looking at:** the header changing, and the same words getting a different
outcome.

**The claim:** this is the entire licensing and governance conversation in ten seconds. Anonymous
on the shared device is cheap, useful and strictly store-scoped. A named, licensed, audited
identity is what buys a personal answer. The boundary is a **door, not a wall** — and where you
put that door is the decision they have been avoiding.

### 7. What is due this shift? — it reaches out first

**Tap:** `What is due this shift?` — *"What tasks are due on this shift?"* and let it answer. You
need to be in a chat for the next part to work.

**Then press the chord: Ctrl + Alt + Shift + A.** Say nothing about the keyboard, and keep talking
while you do it.

**What lands:** an alert card arrives on its own, with the conversation already finished — visibly
not an answer, with its own heading, a *Simulated* badge, and a Provenance line naming the
shift-task system that did not push it — about the coffee station deep clean due before the 15:00
handover, naming SOP-104.

**Say:** *"Nobody asked it anything just then. It can act on a shift event and put the procedure
one tap away."*

**The claim:** the assistant is not only reactive, and a proactive message is visibly a different
object from an answer. On a real deployment that trigger is a rota or a task system; here it is
fired by hand, on cue, because a timer that goes off thirty seconds early interrupts the sentence
that was going to explain it.

---

### 8. Swap a shift — the fourth specialist

**Tap:** `Swap a shift` — *"How do I swap a shift with another associate?"*

**Say:** *"This one is not about the store at all. It is about employment — the thing an associate
would otherwise take to a manager, or to a portal they have to be at a desk to use."*

**What lands:** an answer about offering the swap, the other associate accepting it and the shift
lead approving it, quoting `WF-401`, and saying out loud that the procedure library is simulated.
On the right, the **Agent Team** panel shows **four** specialists and the cost table bills the
**Workforce Agent** for the turn — a different specialist from the one that answered beat 1.

**Say:** *"Four specialists, and the orchestrator picked the right one. Nobody wrote a rule that
said 'shift swap goes here' — it chose from what each one says it does."*

**The claim:** the routing story, made legible. And the boundary: this specialist answers **how a
thing is done**, never **what somebody is owed**. Beat 5 is the other half of that sentence, and
this beat is what makes it a boundary rather than a limitation — *"it will tell you how to swap a
shift; it will not tell you Tanya's leave balance on a shared device."*

**Do not claim an HR integration.** There is no employment system behind this. The procedure
library is mocked and says so on every answer. If somebody asks, *"this is where Workday or UKG
would sit, and that is a connector, not a rewrite"* — say it out loud rather than letting the
screen imply it.

---

### If you lose your place — reopen the chat and keep going

**When you need it:** you tapped **New chat** by mistake, or you closed the tab, or a question from
the room took you off the screen and back to the list. Beat 3 into beat 4 is the sequence this
protects: the ticket's whole claim is that nothing had to be repeated.

**What to do:** open the conversation again from **Chat history** on the left — every chat is listed
there, in whatever state it is in, and the one you want is usually the one at the top that did not
finish — then type into the message box at the bottom. It invites you with *"Ask another question in
this chat..."*, and what you send continues **that** conversation rather than starting a new one.

**Say nothing about it.** It is a repair, not a beat. Use it and carry on.

**What it does *not* do, and this matters if you are asked:** the assistant does not re-read the
conversation on your screen. The transcript is there for you, not for it. What carries across is
what the system wrote down as it went — the steps you said you had already tried, who is signed in,
which lane the request took, and the ticket. That is precisely what beat 4 needs, and it is the
whole of what resume promises. Do not say *"it remembers everything we said"*; say *"it kept what it
recorded"*.

**The follow-on card is still the way to drive beat 4.** Tapping **I can't fix it** is rehearsed,
carries the right lane and needs no keyboard. Reopening and typing is what you do when you are
already off the path.

---

## What the three panels prove

They are on the right, on both screens. Point at them; they are the evidence, not decoration.

| Panel | The claim it supports |
| --- | --- |
| **Grounding** | *This one answer left Foundry.* It leads with the **platform** — `Copilot Studio` — and then the document. That is the cross-platform architecture proof, made live, per answer. It goes dark when a new question is asked, on purpose: an answer that never left Foundry must not be shown crediting Copilot Studio. |
| **What this cost** | *Two billing models, side by side, visibly not uniform.* Foundry agents spend **tokens**; the Copilot Studio agent spends **Copilot Credits** (2 per answer, Microsoft's published rate for a generative answer, labelled *Est.*); the refusal spends nothing. The **model** column is how *"cheap models on cheap work"* stops being a slide. |
| **Agent Team** | *Several specialists, not one black box* — who was **available**, and which model each one runs on. It says availability, which is true from the moment the page loads; who actually answered is named in each reply and billed in the cost table. On beat 5 those are four and zero, on the same screen, and that is the point. |

One rule runs through all three, and it is worth saying to an engineering audience: **a dash means
nobody reported it, a zero means we measured nothing.** The Copilot Studio row's tokens are a dash
because Direct Line reports no count. The refusal's zeros are real measurements — that row is the
proof that a refused request costs nothing at all.

---

## Simulation register

These are the invented things in the walkthrough. The record rows include their exact **Provenance
line**, which names the system that did not produce the content. That is ADR-037's floor: an
invented person's action is disclosed in the record that carries it, never only here.

| Invented thing | What the presenter can say |
| --- | --- |
| Store 223 setting | The store number and its setting were authored for this walkthrough; no connected store system supplied them. |
| Procedure library | The procedures are invented demonstration content; no customer procedure library supplied them. |
| Simulated service ticket | No service desk receives this ticket and no engineer is dispatched. |
| Simulated sign-in | No identity provider signed the associate in; the name is authored session state for this walkthrough. |
| Associate record | No payroll system was queried — these figures were authored for this walkthrough. |
| Presenter alert | No shift-task system pushed this alert — it was authored for this walkthrough. |
| Workforce procedure library | No employment system supplied the procedure; the Workforce agent describes authored process content. |

When a later walkthrough record is invented, add its **Provenance line** constant in
`src/backend/provenance.py`, carry it on the record's payload, and add the exact line to this
register. The CI guard enumerates that module's constants, so the register cannot silently fall
behind the records it explains.

---

## Questions you will be asked

**"Are these our procedures?"** No. Every procedure in the library is **invented** for this
demonstration — written to look like a convenience-store SOP, numbered like one, and reviewed by
nobody at Circle K. The only thing here that is yours is the banner on the front. Real procedures
would be uploaded to the same Copilot Studio agent by whoever owns them today, without an engineer
in the loop; that is the point of putting them there rather than in code.

**"Is that a real ticket?"** No — it is marked *Simulated* on the card. Nothing here writes to a
service desk. Everything invented carries that badge, and nothing that is real does: the Copilot
Studio hop, the token counts and the model assignments are not badged, because they are measured.

**"Is that a real sign-in?"** No. There is no Entra, no MSAL, no identity provider anywhere in the
flow — the name is written into the session and that is the whole of it. The point of the beat is
the governance delta, not the plumbing, and the plumbing is the customer's existing identity
provider on the day this ships.

**"Did you hardcode the guardrail?"** Ask them for a phrasing and type it in live. It is a
deterministic keyword pass plus a similarity check on the phrasing, running before any agent — not
a prompt instruction a model can be talked out of.

**"How much did that cost?"** Read the meter out loud. That is what it is for.

---

## If a beat fails

**The two rules that matter more than the table:** never re-ask a failed beat twice in a row — say
what should have happened, move on, and come back to it if there is time. And never apologise for
beat 2; it is not a failure.

| Beat | What failure looks like | Continue? | What to say |
| --- | --- | --- | --- |
| 1 | The Grounding panel never lights at all, or it lights and says *found no matching procedure* for the closing question, or the answer says it could not reach the store procedure assistant | **Yes** — re-ask once by typing the same words; it is intermittent (#54) | If the panel is empty, another agent answered from what it already had and never called out to Copilot Studio — say *"the procedure tool was not invoked on this run, so the system is not making a cross-platform grounding claim"* and re-ask once. If it says it found nothing, say *"that is an honest miss: the published procedure library did not return a match, so the assistant will not invent closing steps"*. If it misses twice, stop re-asking — go to beat 2, which makes the same point about grounding, and come back to beat 1 afterwards or fall back to the recording. Whatever you say, **do not describe a citation that did not arrive** and do not fill in the closing steps from memory — a narrated `SOP-102` is the one failure the customer cannot see and cannot forgive |
| 1a | The panel lights and cites `SOP-102`, and the assistant still **asks you a question back** — *"what is stopping the store from closing?"* | **Yes** — answer it in a few words, or re-ask | The answer is already there: the Grounding panel on the right names Copilot Studio, Dataverse and the document. Say so — *"it has the procedure, and it is checking whether I am asking about a blocker rather than the routine close"* — then point at the citation, which is the claim. Do not treat this as a miss: nothing failed to retrieve |
| 2 | It answers the car-wash question with plausible steps | **Yes** | Say plainly that the library has no such procedure and that an answer here would be the failure. Do not pretend it went well |
| 3 | No chips appear, or the assistant asks for something else | **Yes** — type a short answer naming one thing you tried | *"It is asking what I have already tried."* The beat survives typing; only the ticket in beat 4 gets thinner |
| 4 | No plan appears, or the ticket has no attempted steps | **Yes** | If the steps are missing, say so — *"those should be carried across, and that is the claim I would want you to test in a pilot"* — and do not read the empty rows out as if they were full |
| 5 | The personal question is answered instead of refused | **Stop and re-run it once** | This is the one beat with nothing to fall back on. If it answers again, move to beat 6 and be straight: the boundary is the piece to prove in a pilot |
| 6 | The header does not change, or the same refusal appears again | **Yes** | Tap it once more. If it still refuses, describe the delta rather than showing it, and keep the argument — the argument is what they came for |
| 7 | The chord does nothing | **Yes** | Check you are in a chat and not the home screen — the key is dead there — and press it again. If nothing arrives, describe the alert instead of showing it |
| 8 | The question is **refused** as a personal one, or another specialist answers it | **Yes** | A refusal is the identity boundary being over-cautious, not the assistant being broken — say *"it is treating a shift question as a personal one; that is the boundary erring on the safe side, and it is the direction you want it to err in"* and move on. If the answer arrives from another specialist, the answer is still right; make the routing point from the **Agent Team** panel, which shows four, rather than from the cost table |

---

## If the surface is down

Three rungs, in this order. Each one is a weaker claim than the one above it, so do not jump.

1. **The deployed surface** — the URL you were sent. This is the demonstration: live, on Azure, in
   front of them. Everything above assumes it.
2. **A local run** — an engineer runs the app on a laptop and you present from `localhost:3001`.
   The same seven beats, the same panels; you are now demonstrating a build rather than a
   deployment, so say that. Needs someone who can run the repository — it is not something to
   attempt in the room.
3. **The recording** — the walkthrough on video, captured by the Demo validator on every run (see
   [demo-validator.md](demo-validator.md)). It proves the software did this, not that it is doing
   it now. Narrate it in the present tense of the recording, offer a live session afterwards, and
   do not pretend it is live.

---

## Notes for whoever maintains this

Every string quoted above is asserted, by `src/tests/ci/test_presenter_runbook.py`, to be the
string the repository actually authors — the chord from `src/App/src/models/presenterChord.ts`,
the taps, prompts and chips from the store pack, the opening beat's `SOP-102` and the car-wash
question from `content/sop/corpus.toml`, the header's words from
`src/App/src/models/storeSurface.ts`. That is ADR-019's lesson applied to prose: a runbook
carrying its own copy of the surface passes a rebrand it never saw, and the presenter finds out in
the room.

The **Simulation register** and `src/backend/provenance.py` are the extension points for invented
records. Keep the disclosure with the record that carries the invented action, then register the
same source-owned line here; a runbook-only disclosure does not survive a screenshot or the
Recorded fallback.

**What is not asserted, and what nobody has watched.** Only beat 1 has been driven through a real
browser against the deployment ([demo-validator.md](demo-validator.md)); beats 2 through 7 are
described from the code and the tests that cover them, not from an observed run. The first live
walkthrough is issue #46, and its findings belong here when it happens — particularly the wording
the troubleshooting agent actually asks with, which is what the chips in beat 3 assume.

**Known and open:** the simulated ticket still stamps its site as *Brightpath Convenience Store
223* — the name from before the rebrand — so beat 1 cites Circle K and beat 4 may not. If a
stakeholder notices, it is a content bug, not an architecture one.
