"""The escalation ticket: what the assistant claims on the associate's behalf
(issue #22).

A **Simulated ticket** is the one artefact this assistant produces that leaves
the conversation. Everything else it says is read by the associate who can see
the equipment; a ticket is read by somebody who cannot, later, and acted on. So
the rule the whole build runs on — a surface may say nothing, but it may not say
something that is not so — is at its sharpest here, and this package is where it
is enforced rather than instructed.

Two decisions carry the package:

**The attempted steps are filled from the troubleshooting record and a
caller-supplied value is discarded.** "Never re-typed" is the requirement; a
model asked to carry them will sometimes paraphrase them, and a paraphrase of
what an associate tried is not what they tried.

**There is no submit tool.** The draft is all the agent can make. Submission
happens deterministically at the plan-approval seam
(``orchestration_manager._handle_plan_reviews``), which is what makes the
approval step *be* the confirmation rather than merely precede it.
"""
