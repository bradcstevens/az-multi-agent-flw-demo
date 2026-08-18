# Copyright (c) Microsoft. All rights reserved.
"""Tests for agents/model_allowlist.py — the one allowlist (#113).

This module is the repair for two allowlists that did not agree: an upload-time
check that bypassed four model names outright and a run-time check that read
``SUPPORTED_MODELS``. Everything here is pure apart from
:func:`configured_supported_models`, so it is tested without a factory, a
Foundry client or a network.
"""

import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

_backend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
)
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

# `agents` must stay a real package with a `__path__`: a bare Mock here would
# make `import agents.model_allowlist` fail for every test file that runs after
# this one in the same process.
if not isinstance(sys.modules.get("agents"), ModuleType):
    _agents_pkg = ModuleType("agents")
    _agents_pkg.__path__ = [os.path.join(_backend_path, "agents")]
    sys.modules["agents"] = _agents_pkg

_mock_app_config_mod = MagicMock()
_mock_app_config_mod.config = SimpleNamespace(
    SUPPORTED_MODELS='["gpt-5.4-mini", "gpt-5.4"]'
)
sys.modules.setdefault("common", MagicMock())
sys.modules.setdefault("common.config", MagicMock())
sys.modules.setdefault("common.config.app_config", _mock_app_config_mod)

from agents import model_allowlist  # noqa: E402
from agents.model_allowlist import (  # noqa: E402
    RefusedAgent,
    SupportedModelsNotConfigured,
    agent_field,
    configured_supported_models,
    is_supported,
    parse_supported_models,
    refused_agents,
    roster_availability,
    unsupported_reason,
)

ALLOWLIST = ["gpt-5.4-mini", "gpt-5.4"]


class TestParseSupportedModels:
    """A configuration error is raised, never defaulted around."""

    def test_a_json_list_is_the_allowlist(self):
        assert parse_supported_models('["gpt-5.4-mini", "gpt-5.4"]') == ALLOWLIST

    def test_an_actual_list_is_accepted(self):
        assert parse_supported_models(["gpt-5.4"]) == ["gpt-5.4"]

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_unset_is_a_configuration_error(self, raw):
        """The defect: ``SUPPORTED_MODELS`` has no default in app config.

        Unset, it reached ``json.loads`` inside the factory's per-agent
        ``try``, raised ``TypeError`` once per agent, and emptied the entire
        team while every caller carried on as though nothing had happened.
        """
        with pytest.raises(SupportedModelsNotConfigured) as exc:
            parse_supported_models(raw)
        assert "SUPPORTED_MODELS" in str(exc.value)

    def test_unparseable_says_what_was_expected(self):
        with pytest.raises(SupportedModelsNotConfigured) as exc:
            parse_supported_models("gpt-5.4, gpt-5.4-mini")
        assert "JSON" in str(exc.value)

    def test_a_magicmock_is_not_an_allowlist(self):
        """A stubbed config is the shape this fails on most often in tests."""
        with pytest.raises(SupportedModelsNotConfigured):
            parse_supported_models(MagicMock())

    @pytest.mark.parametrize("raw", ['{"a": 1}', '"gpt-5.4"', "[1, 2]"])
    def test_json_that_is_not_a_list_of_names_is_refused(self, raw):
        with pytest.raises(SupportedModelsNotConfigured):
            parse_supported_models(raw)

    def test_an_empty_list_fails_like_an_unset_one(self):
        """No agent can be built from an empty allowlist, so say so loudly."""
        with pytest.raises(SupportedModelsNotConfigured) as exc:
            parse_supported_models("[]")
        assert "empty" in str(exc.value)


class TestConfiguredSupportedModels:
    def test_reads_app_config(self, monkeypatch):
        monkeypatch.setattr(
            model_allowlist, "config", SimpleNamespace(SUPPORTED_MODELS='["only"]')
        )
        assert configured_supported_models() == ["only"]

    def test_a_config_without_the_attribute_is_an_error(self, monkeypatch):
        monkeypatch.setattr(model_allowlist, "config", SimpleNamespace())
        with pytest.raises(SupportedModelsNotConfigured):
            configured_supported_models()


class TestIsSupported:
    def test_named_model_is_supported(self):
        assert is_supported("gpt-5.4", ALLOWLIST) is True

    def test_unnamed_model_is_not(self):
        assert is_supported("o3", ALLOWLIST) is False

    def test_the_comparison_is_exact(self):
        """``create_agent_from_config`` compares exactly, so this does too.

        A case-insensitive answer here would be a third allowlist, which is the
        shape of the defect this module exists to remove.
        """
        assert is_supported("GPT-5.4", ALLOWLIST) is False

    def test_a_missing_deployment_name_is_not_supported(self):
        assert is_supported(None, ALLOWLIST) is False


class TestAgentField:
    """One accessor, because a team definition arrives in two shapes."""

    def test_reads_a_mapping(self):
        assert agent_field({"name": "Ops"}, "name") == "Ops"

    def test_reads_an_object(self):
        assert agent_field(SimpleNamespace(name="Ops"), "name") == "Ops"

    def test_absent_field_is_none(self):
        assert agent_field({}, "deployment_name") is None
        assert agent_field(SimpleNamespace(), "deployment_name") is None


class TestRefusedAgents:
    def test_a_buildable_team_refuses_nobody(self):
        agents = [{"name": "Ops", "deployment_name": "gpt-5.4"}]
        assert refused_agents(agents, ALLOWLIST) == []

    def test_an_unsupported_model_is_carried_not_logged(self):
        agents = [{"name": "Ghost", "deployment_name": "o3"}]
        refused = refused_agents(agents, ALLOWLIST)
        assert refused == [
            RefusedAgent(
                name="Ghost",
                deployment_name="o3",
                reason=unsupported_reason("o3", ALLOWLIST),
            )
        ]

    def test_an_agent_with_no_model_is_refused_the_same_way(self):
        refused = refused_agents([{"name": "Ghost"}], ALLOWLIST)
        assert len(refused) == 1
        assert refused[0].deployment_name is None

    def test_object_shaped_agents_are_read_too(self):
        agents = [SimpleNamespace(name="Ghost", deployment_name="o3")]
        assert [a.name for a in refused_agents(agents, ALLOWLIST)] == ["Ghost"]

    def test_only_the_refused_are_returned(self):
        agents = [
            {"name": "Ops", "deployment_name": "gpt-5.4"},
            {"name": "Ghost", "deployment_name": "o3"},
        ]
        assert [a.name for a in refused_agents(agents, ALLOWLIST)] == ["Ghost"]


class TestRosterAvailability:
    """The roster reports a refusal; it does not hide the agent."""

    def test_every_agent_appears(self):
        agents = [
            {"name": "Ops", "deployment_name": "gpt-5.4"},
            {"name": "Ghost", "deployment_name": "o3"},
        ]
        roster = roster_availability(agents, ALLOWLIST)
        assert [entry["name"] for entry in roster] == ["Ops", "Ghost"]

    def test_a_refused_agent_is_marked_not_dropped(self):
        """Absence and a stated refusal are not interchangeable.

        Dropped from the list, an agent nobody can build is indistinguishable
        from an agent the pack never had — and the surface has no way to tell
        *not constructible* from *has not participated yet*.
        """
        roster = roster_availability([{"name": "Ghost", "deployment_name": "o3"}], ALLOWLIST)
        assert roster[0]["available"] is False
        assert "o3" in roster[0]["unavailable_reason"]

    def test_an_available_agent_carries_no_reason(self):
        """A field renders only when it is set, per ADR-039."""
        roster = roster_availability([{"name": "Ops", "deployment_name": "gpt-5.4"}], ALLOWLIST)
        assert roster[0]["available"] is True
        assert "unavailable_reason" not in roster[0]

    def test_the_deployment_name_is_reported_verbatim(self):
        roster = roster_availability([{"name": "Ghost", "deployment_name": "o3"}], ALLOWLIST)
        assert roster[0]["deployment_name"] == "o3"

    def test_no_agents_is_an_empty_roster(self):
        assert roster_availability([], ALLOWLIST) == []
        assert roster_availability(None, ALLOWLIST) == []


class TestUnsupportedReason:
    """One sentence, so three callers cannot describe one refusal three ways."""

    def test_names_the_model_and_the_allowlist(self):
        reason = unsupported_reason("o3", ALLOWLIST)
        assert "o3" in reason
        assert "gpt-5.4-mini" in reason

    def test_a_missing_model_gets_its_own_sentence(self):
        reason = unsupported_reason(None, ALLOWLIST)
        assert "No model deployment is named" in reason
