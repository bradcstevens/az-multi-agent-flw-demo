"""The Reviewable-plan frame carries the same person-step shape at both ends."""

from pathlib import Path
from typing import get_args

from models.plan_models import AgentAssignee, MStep, PersonAssignee

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_MODEL = REPO_ROOT / "src" / "App" / "src" / "models" / "plan.tsx"
PLAN_PARSER = REPO_ROOT / "src" / "App" / "src" / "store" / "PlanDataService.tsx"


def test_the_browser_reads_every_person_step_field_the_backend_frame_carries():
    parser = PLAN_PARSER.read_text(encoding="utf-8")

    for field in ("id", "action", "assignee", "waitsOn"):
        assert f"step.{field}" in parser, (
            f"the browser no longer reads the Reviewable-plan step's {field!r}"
        )


def test_the_person_relation_is_closed_to_the_same_three_values_on_the_wire():
    relation = PersonAssignee.model_fields["relation"].annotation

    assert get_args(relation) == ("associate", "peer", "manager")
    assert "'associate' | 'peer' | 'manager'" in PLAN_MODEL.read_text(
        encoding="utf-8"
    )


def test_the_browser_declares_every_field_of_both_assignee_variants():
    browser = PLAN_MODEL.read_text(encoding="utf-8")

    assert set(AgentAssignee.model_fields) == {"kind", "name"}
    assert set(PersonAssignee.model_fields) == {
        "kind",
        "name",
        "relation",
        "simulated",
    }
    for field in (*AgentAssignee.model_fields, *PersonAssignee.model_fields):
        assert field in browser, (
            f"the browser's Assignee union no longer declares {field!r}"
        )


def test_the_backend_step_keeps_the_legacy_agent_field_alongside_the_new_shape():
    # A stored MPlan from before #106 contains agent/action only. Keeping agent
    # optional on the browser type lets those existing records remain readable.
    assert {"agent", "action", "assignee", "waitsOn"} <= set(MStep.model_fields)
