# TKT-001 Service Incident Ticket Template

Document ID: TKT-001
Site: Circle K Store 223
Owner: Store Operations
Version: 1.0

The shape every service ticket raised from this assistant takes. A ticket raised here is
**simulated**: no real service desk receives it, no engineer is dispatched, and no ticket number
issued here means anything outside this demonstration. Say so when the ticket is presented.

The associate confirms this ticket once. The confirmation is the approval step, and there is no
second confirmation after it.

## Fields

ticket_id: SIM-223-<sequence>, issued when the associate confirms
opened_at: the local time the associate confirmed, ISO 8601
status: draft until confirmed, then submitted
priority: 1 to 4, chosen against the service windows in STORE-223 Store Profile
site: Circle K Store 223
site_number: 223
site_contact: the shift lead on duty, or the duty manager out of hours
asset: the equipment in plain words, as the associate would name it
asset_tag: from the equipment register in STORE-223 Store Profile
category: equipment, food safety, forecourt, payment, or facilities
symptom: what the associate saw, in the associate's own words
first_noticed: when the associate first saw it
steps_attempted: every step already tried, carried from the conversation and never re-typed
runbook: the runbook that was followed, for example RB-201
impact: what the store cannot do while this is open
product_affected: whether product was moved or discarded, and roughly how much
requested_response: the service window for the chosen priority, quoted from the store profile
raised_by: the associate, if signed in; otherwise "shared device, Store 223, no user signed in"
notes: anything the associate wants to add

## How The Fields Are Filled

- **steps_attempted is never asked for again.** The associate already told the assistant what they
  tried while they were being walked through the runbook. Carrying it here is the whole reason the
  ticket is raised in this conversation rather than on a telephone call. If a step was skipped
  because it had already been tried, that still belongs in this field.
- **asset_tag comes from the equipment register**, not from the associate. An associate mid-shift
  does not know the asset tag and should not be asked for it.
- **priority comes from the service windows**, not from how urgent it feels. Trade stopped is
  priority 1. A food-safety fault is never below priority 2.
- **A field with no answer is written "not reported".** It is not left blank, it is not guessed,
  and it is not turned into another question.
- **raised_by records the anonymous case honestly.** The device is shared and nobody is signed in
  by default; a ticket that names an associate who did not sign in is a record that is not true.

## Worked Example

ticket_id: SIM-223-0041
opened_at: 2026-08-13T14:12:00
status: submitted
priority: 2
site: Circle K Store 223
site_number: 223
site_contact: shift lead on duty
asset: front counter coffee brewer, left head
asset_tag: BC-223-COF-01
category: equipment
symptom: left head runs a cycle but the coffee comes out cold and slow
first_noticed: this morning, first brew after open
steps_attempted: fresh paper filter and a new pre-measured pack; grind setting checked on the
  marked notch; machine switched off at the wall for sixty seconds and back on; water filter
  indicator noted as red
runbook: RB-201
impact: one of two brew heads out of service, coffee offer running on backup airpots
product_affected: none discarded
requested_response: on site within 1 working day
raised_by: shared device, Store 223, no user signed in
notes: water filter cartridge replaced from backroom stock, no change

## Related Documents

- STORE-223 Store Profile
- RB-201 Coffee Brewer Not Brewing
