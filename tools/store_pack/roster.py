"""The roster's own rules, as predicates rather than prose.

The one that earns its place is :func:`silently_skipped`.
``AgentFactory.get_agents`` builds each agent inside a ``try`` and, when
``create_agent_from_config`` raises ``UnsupportedModelError`` because the
agent's ``deployment_name`` is not in the ``SUPPORTED_MODELS`` allowlist,
**logs a warning and moves on**. Nothing fails. The upload succeeded, the team
is in Cosmos, the surface shows the assistant, and one member of the cast never
arrives — which on stage presents as the orchestrator declining to answer a
whole class of question for no visible reason.

So "the full agent roster is verified present" is not a thing to eyeball after
a deploy. It is this function, called by the deploy path after the upload and
by the CI-tooling tests against the authored pack.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

#: The reasoning model, for the work that reasons: a branching runbook and a
#: ticket assembled out of a conversation.
REASONING_MODEL = "gpt-5.4"

#: The cheaper model, for the work that does not: relaying a procedure question
#: to Copilot Studio, and the orchestrator's own routing (ADR-003).
CHEAP_MODEL = "gpt-5.4-mini"

#: The environment allowlist this pack is authored against — the same list the
#: deployed environment sets as ``SUPPORTED_MODELS`` and the same list
#: ``AgentFactory`` filters on.
SUPPORTED_MODELS = [CHEAP_MODEL, REASONING_MODEL]

#: Who is in the roster, and on which model. This is the *specification*; the
#: team definition is the artefact, and a test asserts they agree. Putting
#: cheap models on cheap work is a claim the R7 meter renders on screen, so it
#: has to be true of the pack that is actually uploaded.
INTENDED_MODELS: Dict[str, str] = {
    "TroubleshootingAgent": REASONING_MODEL,
    "ShiftTasksAgent": CHEAP_MODEL,
    "EscalationAgent": REASONING_MODEL,
    # The fourth specialist (#52, ADR-017). Relay work like the shift-tasks
    # agent's — look a procedure up in a library and quote what came back — so
    # it takes the cheaper model, and the meter says so on screen.
    "WorkforceAgent": CHEAP_MODEL,
}


def model_assignment(team: Mapping[str, Any]) -> Dict[str, str]:
    """Each agent in the definition, and the model it was given."""
    return {
        agent.get("name", ""): agent.get("deployment_name", "")
        for agent in team.get("agents", [])
    }


def silently_skipped(
    team: Mapping[str, Any], supported_models: Iterable[str]
) -> List[str]:
    """The agents ``AgentFactory.get_agents`` would drop with only a warning.

    An absent ``deployment_name`` is skipped exactly like a misspelled one: the
    factory reads it with a ``None`` default and then asks whether it is in the
    allowlist.
    """
    allowed = set(supported_models)
    return [
        agent.get("name", "")
        for agent in team.get("agents", [])
        if agent.get("deployment_name") not in allowed
    ]


def referenced_models(team: Mapping[str, Any]) -> List[str]:
    """Every model deployment this definition names, agents and team alike."""
    named = {
        agent.get("deployment_name")
        for agent in team.get("agents", [])
        if agent.get("deployment_name")
    }
    if team.get("deployment_name"):
        named.add(team["deployment_name"])
    return sorted(named)


def missing_models(team: Mapping[str, Any], deployed_models: Iterable[str]) -> List[str]:
    """Models the definition references that the Foundry project does not have.

    Checked **before** the upload, because a model that does not exist is not
    an upload failure — the upload's own model check bypasses this family of
    names outright — and the consequence surfaces later as a silently missing
    agent.
    """
    deployed = set(deployed_models)
    return [name for name in referenced_models(team) if name not in deployed]


def missing_indexes(pack: Any, existing_indexes: Iterable[str]) -> List[str]:
    """Search indexes the pack declares that the search service does not have.

    A knowledge base whose index is absent is not a failed deploy either: it
    answers nothing, and an agent grounded on nothing improvises.
    """
    existing = set(existing_indexes)
    return sorted(name for name in pack.index_names if name not in existing)
