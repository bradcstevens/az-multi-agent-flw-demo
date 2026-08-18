# The Mocked unlock

The demo's closing beat (issue #27). An associate asks *"my name is Tanya, how much PTO do I
have?"* and is refused. They tap **Sign in to continue**, the header gains a named identity, and
the same question — unedited, through the same gate — answers out of a mocked associate record.

The delta between those two moments is the licensing and governance conversation the customer has
been avoiding. Nothing else in the walkthrough makes that argument, so everything here exists to
make the two moments comparable and the second one honest.

## What is mocked, and where the record says so

The handoff is mocked **end to end**. There is no Entra, no Okta, no Auth0, no MSAL, no OAuth
anywhere in the flow — `POST /api/v4/session_state/{id}/sign_in` writes an authored name into
server-side **Session state** and that is the whole of the identity provider.

The header states only the **Session identity** it was given. When the identity boundary gate admits
the personal question, the associate record carries a **Provenance line** naming the payroll system
that was not queried. That line travels with the record into a screenshot or the **Recorded
fallback**, where browser-authored prose would not.

Asserted rather than assumed, on both sides of the socket:
`test_router.py::test_no_identity_provider_is_involved` reads the backend modules the flow runs
through, and `test_personal_answer_contract.py` reads the browser's.

## Not a second gate

ADR-014 settles that the unlock is a **parameter of the Identity boundary gate, not a second
gate**. The same classifier refuses before sign-in and admits after it, and the gate reports
*which* admitted question it saw rather than letting the request path ask again:

```python
GateVerdict(refused=False, reason=GateReason.SIGNED_IN, personal=True)
```

A second classifier could disagree with the first, and the disagreement would be invisible.

Three properties of `personal` are load-bearing:

* **It is not a synonym for `refused`.** A request refused because the embedding tier was
  unreachable is `refused, not personal` — *could not tell* is a different fact from *decided it
  was personal*.
* **It costs no embedding call.** The classification a signed-in request needs is the pure
  **Keyword fast path**'s, so the closing beat cannot be taken down by an unreachable embedding
  deployment.
* **It runs one way only.** It may miss a personal question — that one reaches the ordinary agents
  and is honestly declined — but it may never claim a store question as personal, which would
  answer *"how do I close the store?"* out of somebody's PTO balance. Five of the walkthrough's six
  beats run signed-in once the presenter has tapped, and every one of them has to still reach the
  agents.

## The answer costs what the refusal cost

The unlock short-circuits in `process_request` immediately below the refusal: no agent invoked, no
plan persisted, no tokens spent. The point of the beat is that the *governance* changed, not that a
second and more expensive machine was started — and an answer that ran an orchestration would put
an approval step between the tap and the payoff.

So it arrives on a **successful** request carrying a null `plan_id`. That null is not a failure to
create a plan, and the surface checks for the answer before it checks the plan id; reading it the
other way round renders the demo's payoff as an error toast.

## The Associate record

`src/backend/associate/records.py`. Authored demo content, and the demo's most sensitive: every
other invented thing here is about a store, and this is about a person's pay and time off.

* **Looked up by whole name**, or whole first name — never by substring. `Tan` is not Tanya. A
  loose match answers one associate's question out of another associate's record, which is the
  identity form of the claim the gate exists to refuse, made by the code that was supposed to be
  the reward for passing it.
* **No record is a true answer.** A name nobody authored a record for resolves to nothing and the
  request falls through to the ordinary agents, which hold nothing about an individual. Degrading
  towards *we hold nothing about you* is the direction the gate degrades in.
* **The record is shown whole.** The answer does not pick out the field the question asked about.
  Deciding *which* number a phrasing wants would be a third classifier behind the gate's two, and a
  third classifier can report the wrong number — which, for a claim about somebody's pay, is the
  worst thing this system could say. A record shown whole answers *"how much PTO do I have?"*,
  *"what am I owed?"* and a phrasing nobody rehearsed.
* **A half-written fact is dropped, not blanked**, at both ends. A label with no value renders as
  *nothing owed*, and that is a claim about an associate's entitlement nobody authored.

## The Signed-in device

`src/App/src/models/signedInDevice.ts` is the browser's half, and it is **not** the identity.

A session is one conversation — one **Simulated ticket**, one **Lane** taken, one troubleshooting
record — so the tab cannot simply re-use the session it signed in on; that would give every
conversation in the tab a shared ticket and a shared lane. Instead the device remembers the *name
the route returned*, and `TaskService.createPlan` writes the identity into each new session as it
creates it.

| Rule | Why |
| --- | --- |
| `sessionStorage`, not `localStorage` | A fresh tab is an anonymous shared store device, which is where the demo has to start. Nothing to reset between rehearsals. |
| Signing out is **forgetting** | There is nothing to revoke: there was never an identity provider to revoke it with, and the next session is created anonymous. |
| A **Policy block** forgets it too | A refusal *is* the gate stating that nobody is signed in. A header that went on naming an associate the gate just declined to answer for is the one thing no surface here may do. |
| A failed sign-in forgets it | Fails closed, like the gate. The request goes anonymous and is refused, and the header returns to matching it. |
| The browser authors no name | The name the header shows and the name the record is keyed by would otherwise be two strings free to drift. |
| The header ignores the EasyAuth principal | Two identities that can disagree are one too many, and the gate reads **Session state** and nothing else. EasyAuth is off on this deployment, so that second identity would have claimed a signed-in user while every personal question was refused. |

## The door, not a second wall

The affordance renders **inside** the refusal, not beside it, so the boundary and the way through
it are visibly one thing. Tapping it signs in and re-asks the *same words* — the refused question
is kept for exactly this, because the beat is a comparison and re-typing puts a typo or an
autocorrect between the presenter and the payoff, the reason the **Rehearsed replies** exist (#26).

A sign-in that signed nobody in does **not** re-ask. Asking again anonymously would show the
identical refusal a second time and read on stage as the tap having done nothing at all.

## What is not covered

* **Nothing here has run against a deployment.** The route, the gate's classification and the
  browser's flow are asserted against the real gate and a fake store, never against a live Cosmos
  container or a live embedding deployment.
* **The phone breakpoint has not been seen on a phone.** jsdom does not evaluate media queries.
