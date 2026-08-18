# Copyright (c) Microsoft. All rights reserved.
"""One allowlist, read by everything that asks whether a model is usable.

There used to be two, and they did not agree (#113). ``validate_team_models``
decided at **upload** time by comparing against the deployments Foundry lists,
with four model names — ``gpt-5.4-mini``, ``gpt-5.4``, ``gpt-5``, ``o3`` —
hard-bypassed by name and the whole body wrapped in an ``except`` that returned
*valid*. ``create_agent_from_config`` decided at **run** time by reading the
environment's ``SUPPORTED_MODELS``. So an upload could pass on a model the
factory would then refuse, the refusal was caught and logged as a warning, and
the team ran one agent short with nothing on the surface saying so.

Which mattered more once the **Agent dossier** landed
(:doc:`ADR-039 <../../../docs/ADR/039-an-agent-dossier-shows-what-the-agent-was-told-verbatim>`):
the dossier reads the roster, so it rendered a full record — model and verbatim
prompt included — for an agent that could never answer. ADR-039 assigns that
repair here by name: *"No wording in the browser can fix two disagreeing
allowlists."*

So the question is asked once, in this module, and three callers read the
answer: the factory that constructs an agent, the upload check that admits a
team definition, and ``/init_team``, which now says which agents the factory
would refuse rather than handing the client a roster it cannot honour.

Everything here is pure apart from :func:`configured_supported_models`, which is
the single line that touches app config.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional, Sequence

from common.config.app_config import config


class SupportedModelsNotConfigured(Exception):
    """``SUPPORTED_MODELS`` is unset, unparseable, or not a list of names.

    A configuration error, raised rather than defaulted. ``SUPPORTED_MODELS``
    is read from app config as *optional with no default*, so an unset value
    used to reach ``json.loads(None)`` and raise ``TypeError`` **inside** the
    factory's per-agent ``try`` — where the broad ``except Exception`` caught it
    exactly like a per-agent fault and dropped every agent in turn. A team of
    none, from one missing environment variable, reported as four warnings
    nobody reads.

    Defaulting to a model list would be the same failure wearing a nicer face:
    which models a deployment supports is a deployment's decision, and guessing
    it here would put an agent on a model this project never chose.
    """


@dataclass(frozen=True)
class RefusedAgent:
    """An agent the factory would refuse to build, and why.

    Carried rather than logged. The warning was the defect.
    """

    name: str
    deployment_name: Optional[str]
    reason: str


def parse_supported_models(raw: Any) -> List[str]:
    """The allowlist, out of the raw configuration value.

    Raises:
        SupportedModelsNotConfigured: when the value is absent, is not JSON, or
            is not a list of model names.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise SupportedModelsNotConfigured(
            "SUPPORTED_MODELS is not set. It is the allowlist every agent's "
            "deployment_name is checked against, so with it unset no agent can "
            "be built and the team would be silently empty. Set it to a JSON "
            'list of deployment names, e.g. \'["gpt-5.4-mini","gpt-5.4"]\'.'
        )

    if isinstance(raw, (list, tuple)):
        parsed: Any = list(raw)
    else:
        if not isinstance(raw, str):
            raise SupportedModelsNotConfigured(
                f"SUPPORTED_MODELS is a {type(raw).__name__}, which cannot be "
                "read as a list of model names."
            )
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise SupportedModelsNotConfigured(
                f"SUPPORTED_MODELS is not valid JSON ({exc}). Expected a JSON "
                'list of deployment names, e.g. \'["gpt-5.4-mini","gpt-5.4"]\'.'
            ) from exc

    if not isinstance(parsed, list) or not all(
        isinstance(name, str) for name in parsed
    ):
        raise SupportedModelsNotConfigured(
            "SUPPORTED_MODELS must be a JSON list of deployment names, but "
            f"parsed to {parsed!r}."
        )

    if not parsed:
        raise SupportedModelsNotConfigured(
            "SUPPORTED_MODELS is an empty list, so no agent can be built. An "
            "empty allowlist and an unset one fail the same way, and neither "
            "is a deployment anybody meant to make."
        )

    return [name for name in parsed]


def configured_supported_models() -> List[str]:
    """The deployment's allowlist. The only line here that reads app config."""
    return parse_supported_models(getattr(config, "SUPPORTED_MODELS", None))


def agent_field(agent: Any, field: str) -> Any:
    """Read a field off an agent that may be a mapping or an object.

    A team definition arrives as JSON at upload time and as a
    ``TeamAgent``/``SimpleNamespace`` afterwards, and both shapes reach this
    module. Reading them through one accessor is what stops the answer
    depending on which caller asked.
    """
    if isinstance(agent, Mapping):
        return agent.get(field)
    return getattr(agent, field, None)


def is_supported(deployment_name: Any, supported_models: Iterable[str]) -> bool:
    """Whether the factory would accept this ``deployment_name``.

    Compared **exactly**, because ``create_agent_from_config`` compares exactly.
    A case-insensitive answer here would be a third allowlist.
    """
    return deployment_name in set(supported_models)


def unsupported_reason(
    deployment_name: Any, supported_models: Sequence[str]
) -> str:
    """The sentence a refusal carries, wherever it is reported.

    Authored once so the upload rejection, the factory's log line and the
    ``/init_team`` roster cannot describe the same refusal three ways.
    """
    if deployment_name in (None, ""):
        return (
            "No model deployment is named for this agent, so it cannot be "
            f"built. Supported models: {list(supported_models)}."
        )
    return (
        f"Model '{deployment_name}' is not supported. "
        f"Supported models: {list(supported_models)}"
    )


def refused_agents(
    agents: Iterable[Any], supported_models: Sequence[str]
) -> List[RefusedAgent]:
    """Every agent in the definition that the factory would refuse to build.

    An absent ``deployment_name`` is refused exactly like a misspelled one:
    the factory reads it with a ``None`` default and then asks whether it is in
    the allowlist.
    """
    refused: List[RefusedAgent] = []
    for agent in agents or []:
        deployment_name = agent_field(agent, "deployment_name")
        if is_supported(deployment_name, supported_models):
            continue
        refused.append(
            RefusedAgent(
                name=agent_field(agent, "name") or "",
                deployment_name=deployment_name,
                reason=unsupported_reason(deployment_name, supported_models),
            )
        )
    return refused


def roster_availability(
    agents: Iterable[Any], supported_models: Sequence[str]
) -> List[dict]:
    """The roster ``/init_team`` hands the client, each agent with its verdict.

    ``available`` is the surface's own word (**Available vs participating**):
    the roster states who *could* answer, and an agent the factory would refuse
    could not. It is reported **alongside** the agent rather than by leaving the
    agent out, because absence and a stated refusal are not interchangeable —
    the roster's version of **Not reported vs measured**. An agent nobody can
    build, silently dropped from the list, is indistinguishable from an agent
    the pack never had; stated, it is a thing the surface can name and stop
    claiming. ``unavailable_reason`` renders only where there is one, which is
    the same rule the dossier's optional fields follow.
    """
    roster: List[dict] = []
    for agent in agents or []:
        deployment_name = agent_field(agent, "deployment_name")
        entry = {
            "name": agent_field(agent, "name") or "",
            "deployment_name": deployment_name,
            "available": is_supported(deployment_name, supported_models),
        }
        if not entry["available"]:
            entry["unavailable_reason"] = unsupported_reason(
                deployment_name, supported_models
            )
        roster.append(entry)
    return roster
