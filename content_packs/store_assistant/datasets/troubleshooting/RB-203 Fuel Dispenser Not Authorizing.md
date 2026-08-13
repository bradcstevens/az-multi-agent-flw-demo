# RB-203 Fuel Dispenser Not Authorizing

Document ID: RB-203
Site: Brightpath Convenience Store 223
Equipment: Eight forecourt dispensers, positions 1 to 8
Asset tag: BC-223-DSP-01 to BC-223-DSP-08
Owner: Forecourt Support
Version: 2.1

## Symptom

A customer lifts the nozzle and the dispenser does not authorize: the display holds on "PLEASE
WAIT", "SEE CASHIER" or stays blank, and no fuel is delivered.

## Ask First

- Which dispenser position, and does the same happen on the other side of the same dispenser?
- Does the console show that position as available, stopped or in error?
- Has the position been authorized from the console and then declined?
- Has anyone pressed the forecourt emergency stop in the last hour?

## Safety

- Nothing in this runbook is a repair. An associate never opens a dispenser, never touches a hose
  fitting and never resets anything inside the pump housing.
- If there is fuel on the ground, a smell of vapour, or a hose or nozzle that is damaged, stop
  reading and follow SOP-105 Forecourt Emergency Stop and Fuel Spill Response.
- Do not re-authorize a position that has stopped twice for the same customer.

## Branches

### Branch A - Emergency stop has been pressed

If the console shows every position stopped, or the emergency stop button is depressed:

1. Do not reset it yourself. The emergency stop is reset by a trained shift lead only, and only
   after the reason it was pressed is known.
2. Find the shift lead. If there is no shift lead on site, call the duty manager on the number in
   the store profile.
3. Keep customers away from the forecourt until the reset is authorized.
4. This is not a dispenser fault. Do not raise a dispenser ticket for it.

### Branch B - One position, console shows it available

If only one position is affected and the console shows it available:

1. Ask the customer to hang up the nozzle fully and lift it again. A nozzle not seated in the boot
   leaves the position mid-transaction.
2. Authorize the position from the console and watch the console response.
3. If the console authorizes and the dispenser still does nothing, ask the customer to move to
   another position and serve them there first. The customer comes before the diagnosis.
4. Put the out-of-service cover on the affected nozzle and go to Stop and Escalate.

### Branch C - One position, console shows an error

If the console shows an error against the position:

1. Read the error text on the console and write it down exactly, including any number.
2. Put the out-of-service cover on that position's nozzles.
3. Do not clear the error from the console more than once. A cleared error that returns is
   evidence the service engineer needs.
4. Go to Stop and Escalate with the console error text.

### Branch D - Every position, console is up

If no position authorizes but the console is working normally:

1. Check the console's forecourt controller status line. A controller offline message means the
   site is down, not a single pump.
2. Check whether card payment is also failing indoors. If it is, this is a site communications
   fault and the ticket is raised against the site, not a dispenser.
3. Serve indoor sales on the fallback procedure and tell waiting customers the forecourt is down.
4. Go to Stop and Escalate and report it as a whole-forecourt outage.

## Stop and Escalate

Stop and raise a service ticket when any of these is true:

- A position shows a console error that returns after one clear.
- A position is authorized by the console and still delivers nothing.
- The whole forecourt is not authorizing and the console is otherwise healthy.

The ticket needs the dispenser position, its asset tag, the exact console error text and the steps
already tried. A forecourt outage is priority 1: it stops trade. Tell the duty manager as well as
raising the ticket.

## Related Documents

- SOP-105 Forecourt Emergency Stop and Fuel Spill Response
- STORE-223 Store Profile
- TKT-001 Service Incident Ticket Template
