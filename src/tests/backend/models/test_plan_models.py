# Copyright (c) Microsoft. All rights reserved.
"""Tests for models/plan_models.py — PlanStatus, MStep, MPlan, AgentDefinition,
PlannerResponseStep, PlannerResponsePlan."""

import uuid

from backend.models.plan_models import (AgentDefinition, MPlan, MStep,
                                        PlannerResponsePlan,
                                        PlannerResponseStep, PlanStatus,
                                        Verdict)
from provenance import VERDICT_PROVENANCE


class TestPlanStatus:
    def test_values(self):
        assert PlanStatus.CREATED == "created"
        assert PlanStatus.QUEUED == "queued"
        assert PlanStatus.RUNNING == "running"
        assert PlanStatus.COMPLETED == "completed"
        assert PlanStatus.FAILED == "failed"
        assert PlanStatus.CANCELLED == "cancelled"

    def test_is_str_enum(self):
        assert isinstance(PlanStatus.CREATED, str)

    def test_all_members(self):
        names = {m.name for m in PlanStatus}
        assert names == {"CREATED", "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}


class TestMStep:
    def test_defaults(self):
        step = MStep()
        assert step.agent == ""
        assert step.action == ""

    def test_explicit_values(self):
        step = MStep(agent="DataAgent", action="fetch records")
        assert step.agent == "DataAgent"
        assert step.action == "fetch records"

    def test_is_pydantic_model(self):
        from pydantic import BaseModel
        assert issubclass(MStep, BaseModel)

    def test_dict_round_trip(self):
        step = MStep(agent="A", action="do thing")
        d = step.model_dump()
        assert d == {
            "id": None,
            "agent": "A",
            "action": "do thing",
            "assignee": None,
            "waitsOn": None,
            "outcome": None,
        }

    def test_person_step_preserves_the_authored_assignee_and_order(self):
        for outcome in ("approved", "declined"):
            step = MStep.model_validate(
                {
                    "id": 3,
                    "action": "Ask Marcus Bell to confirm the agreed swap",
                    "assignee": {
                        "kind": "person",
                        "name": "Marcus Bell",
                        "relation": "peer",
                        "simulated": True,
                    },
                    "waitsOn": 2,
                    "outcome": outcome,
                }
            )

            assert step.model_dump(mode="json") == {
                "id": 3,
                "agent": "",
                "action": "Ask Marcus Bell to confirm the agreed swap",
                "assignee": {
                    "kind": "person",
                    "name": "Marcus Bell",
                    "relation": "peer",
                    "simulated": True,
                },
                "waitsOn": 2,
                "outcome": outcome,
            }


class TestTheVerdictCarriesItsProvenance:
    """An invented person's action is disclosed in the record that carries it
    (ADR-037). A Verdict needs that floor more than most records do: its
    outcome is authored but its words are generated per run, so the words read
    exactly like a colleague who really answered.
    """

    def _verdict(self, **overrides):
        fields = {
            "step_id": 3,
            "assignee": {
                "kind": "person",
                "name": "Marcus Bell",
                "relation": "peer",
                "simulated": True,
            },
            "outcome": "approved",
            "words": "I can confirm the Saturday swap works for me.",
        }
        fields.update(overrides)
        return Verdict.model_validate(fields)

    def test_the_verdict_names_the_workforce_system_that_was_not_consulted(self):
        assert self._verdict().provenance_line == VERDICT_PROVENANCE

    def test_there_is_no_provenance_flag_to_omit(self):
        """Every Verdict this system produces is an invented person's decision
        — there is no other kind — so the framing is a property of the record
        rather than a field a caller could leave off."""
        assert "provenance_line" in self._verdict().model_dump(mode="json")

    def test_the_line_is_the_same_whichever_way_the_person_decided(self):
        assert (
            self._verdict(outcome="declined").provenance_line
            == self._verdict(outcome="approved").provenance_line
        )

    def test_a_reader_who_knows_none_of_our_rules_can_tell_nothing_produced_it(self):
        """ADR-037's floor is behavioural, not a naming convention: the line
        alone must name the class of system that was not asked and say who
        authored the content instead."""
        line = self._verdict().provenance_line

        assert "No workforce management system was consulted" in line
        assert "authored for this walkthrough" in line


class TestMPlan:
    def test_defaults(self):
        plan = MPlan()
        assert plan.user_id == ""
        assert plan.team_id == ""
        assert plan.plan_id == ""
        assert plan.overall_status == PlanStatus.CREATED
        assert plan.user_request == ""
        assert plan.team == []
        assert plan.facts == ""
        assert plan.steps == []

    def test_auto_generated_id(self):
        p1 = MPlan()
        p2 = MPlan()
        assert p1.id != p2.id
        # Must be a valid UUID
        uuid.UUID(p1.id)

    def test_explicit_id(self):
        fixed_id = "aaaaaaaa-0000-0000-0000-000000000000"
        plan = MPlan(id=fixed_id)
        assert plan.id == fixed_id

    def test_steps_typed(self):
        plan = MPlan(steps=[MStep(agent="A", action="go")])
        assert len(plan.steps) == 1
        assert plan.steps[0].agent == "A"

    def test_overall_status_enum(self):
        plan = MPlan(overall_status=PlanStatus.RUNNING)
        assert plan.overall_status == PlanStatus.RUNNING

    def test_dict_round_trip(self):
        plan = MPlan(user_id="u1", team_id="t1", user_request="do x")
        d = plan.model_dump()
        assert d["user_id"] == "u1"
        assert d["team_id"] == "t1"
        assert d["user_request"] == "do x"


class TestAgentDefinition:
    def test_construction(self):
        ag = AgentDefinition(name="ResearchAgent", description="Looks things up")
        assert ag.name == "ResearchAgent"
        assert ag.description == "Looks things up"

    def test_repr(self):
        ag = AgentDefinition(name="X", description="Y")
        r = repr(ag)
        assert "X" in r
        assert "Y" in r

    def test_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(AgentDefinition)


class TestPlannerResponseStep:
    def test_construction(self):
        agent = AgentDefinition(name="Writer", description="Writes")
        step = PlannerResponseStep(agent=agent, action="draft report")
        assert step.agent.name == "Writer"
        assert step.action == "draft report"

    def test_is_pydantic_model(self):
        from pydantic import BaseModel
        assert issubclass(PlannerResponseStep, BaseModel)


class TestPlannerResponsePlan:
    def test_defaults(self):
        plan = PlannerResponsePlan(
            request="do x",
            team=[],
            facts="fact1",
        )
        assert plan.steps == []
        assert plan.summary == ""
        assert plan.clarification is None

    def test_with_steps(self):
        agent = AgentDefinition(name="A", description="d")
        step = PlannerResponseStep(agent=agent, action="act")
        plan = PlannerResponsePlan(
            request="req",
            team=[agent],
            facts="f",
            steps=[step],
            summary="done",
        )
        assert len(plan.steps) == 1
        assert plan.summary == "done"

    def test_clarification(self):
        plan = PlannerResponsePlan(
            request="r", team=[], facts="f", clarification="Please clarify X."
        )
        assert plan.clarification == "Please clarify X."

    def test_is_pydantic_model(self):
        from pydantic import BaseModel
        assert issubclass(PlannerResponsePlan, BaseModel)
