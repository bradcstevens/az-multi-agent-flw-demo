"""Provenance lines for every invented record on the walkthrough surface.

This is the extension point for a later record: add its Provenance line here,
carry it on that record's payload, and add the exact line to the Simulation
register in ``docs/presenter-runbook.md``. A record states the origin of its
own invented action; the register makes that disclosure findable to a presenter.
"""

# ADR-036's behavioural floor: each line names the connected system that did not
# produce the record, so the record remains honest in a screenshot or transcript.
ASSOCIATE_RECORD_PROVENANCE = (
    "No payroll system was queried — these figures were authored for this walkthrough."
)
PRESENTER_ALERT_PROVENANCE = (
    "No shift-task system pushed this alert — it was authored for this walkthrough."
)
VERDICT_PROVENANCE = (
    "No workforce management system was consulted — this verdict was authored "
    "for this walkthrough."
)
PLAN_PROVENANCE = (
    "No workforce management system was consulted — the people named in this "
    "plan are stand-ins for this walkthrough."
)
