"""Provenance lines for invented records on the walkthrough surface.

Add every new Provenance line here and add it to the Simulation register in
``docs/presenter-runbook.md``. ADR-037 requires an invented person's action to
disclose its provenance in the record that carries it, never only in the
runbook.
"""

ASSOCIATE_RECORD_PROVENANCE = (
    "No payroll system was queried — these figures were authored for this walkthrough."
)

PRESENTER_ALERT_PROVENANCE = (
    "No shift-task system pushed this alert — it was authored for this walkthrough."
)
