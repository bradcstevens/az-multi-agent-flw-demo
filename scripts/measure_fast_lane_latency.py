"""Measure Fast-lane latency end to end against the live Foundry project.

ADR-013 declines a genuine orchestrator bypass and accepts that the Fast lane
still pays for orchestration setup, so the sub-10-second target is a
**measurement, not a guarantee** — and #15's acceptance criterion is that the
number is measured before any bypass is built.

What is timed, and why it is timed in two phases:

  * **Full workflow rebuild** — ``AgentFactory.get_agents`` plus
    ``OrchestrationManager.init_orchestration``. CONTEXT.md records that
    ``_team_id`` was never assigned, so *every* request took this branch; #15
    assigns it, which makes a warm cache reachable for the first time. Timing
    the rebuild separately is what says whether the cache fix is the thing that
    buys the target or merely helps.
  * **Fast-lane turn** — ``workflow.run(task, stream=True)`` drained to the
    final output with Plan review **off**. This is the number the target is
    about.

Not timed: the HTTP hop, the Cosmos plan write and the Identity boundary gate.
The gate is a keyword match plus one embedding call and the plan write is a
single point-write; both are tens of milliseconds against a multi-second
orchestration. Cosmos is read once only to retrieve the deployed Store Assistant
roster that the workflow builds.

The team is the **real, deployed Store Assistant roster**, read by its stable
team identifier. The probe does not upload or mutate any team configuration.

    az login
    cd src/backend && uv sync
    uv run python ../../scripts/measure_fast_lane_latency.py

The azd environment's settings are loaded automatically — ``AppConfig`` is
constructed on import and reads a dozen of them, so they are exported before
the first backend import rather than after. Anything already exported wins, and
``FAST_LANE_PROJECT_ENDPOINT`` overrides the project endpoint outright.

``--plan-review`` measures the Deliberate lane's build for comparison; it stops
at the first plan-review request rather than approving one, so it is a build
measurement only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FAST_LANE_TARGET_SECONDS = 10.0
STORE_ASSISTANT_TEAM_ID = "00000000-0000-0000-0000-000000000223"
PROBE_USER_ID = "fast-lane-probe"

DEFAULT_TASK = "How do I close the store at the end of the night?"


def load_azd_environment(repo_root: Path = REPO_ROOT) -> str | None:
    """Export the azd environment's settings, without overriding the caller's.

    ``AppConfig`` is constructed at *import* time and reads a dozen settings, so
    this has to run before any backend module is imported — importing first and
    exporting after leaves the probe configured against whatever happened to be
    in the shell. Returns the environment name, or None if there is no azd
    environment to load.
    """
    config_path = repo_root / ".azure" / "config.json"
    if not config_path.exists():
        return None
    env_name = json.loads(config_path.read_text()).get("defaultEnvironment")
    if not env_name:
        return None
    env_file = repo_root / ".azure" / env_name / ".env"
    if not env_file.exists():
        return None

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"'))
    return env_name


async def _load_store_assistant_team(memory_store):
    """Read the seeded Store Assistant roster without creating or changing it."""
    team = await memory_store.get_team(STORE_ASSISTANT_TEAM_ID)
    if team is None:
        raise RuntimeError(
            "The deployed Store Assistant roster "
            f"({STORE_ASSISTANT_TEAM_ID}) was not found. Run the store-pack "
            "deployment check before measuring latency."
        )
    return team


async def _drain(workflow, task: str, stop_on_plan_review: bool) -> int:
    """Consume the event stream to completion, returning the event count."""
    events = 0
    async for event in workflow.run(task, stream=True):
        events += 1
        if stop_on_plan_review and "PlanReview" in type(event).__name__:
            break
    return events


async def measure(task: str, plan_review: bool, project_endpoint: str) -> dict:
    # Imported here, not at module scope: AppConfig is constructed on import and
    # reads the environment, so main() must finish exporting before this runs.
    from agents.agent_factory import AgentFactory
    from common.database.database_factory import DatabaseFactory
    from orchestration.orchestration_manager import OrchestrationManager

    memory_store = await DatabaseFactory.get_database(user_id=PROBE_USER_ID)
    team = await _load_store_assistant_team(memory_store)

    build_started = time.perf_counter()
    factory = AgentFactory(team_service=None)
    agents = await factory.get_agents(
        user_id=PROBE_USER_ID, team_config_input=team, memory_store=memory_store
    )
    if not agents:
        raise RuntimeError(
            "No agents were created — every agent was skipped. A misspelled "
            "deployment name is skipped with a warning, not an error."
        )
    workflow = await OrchestrationManager.init_orchestration(
        agents=agents,
        team_config=team,
        memory_store=memory_store,
        user_id=PROBE_USER_ID,
        plan_review=plan_review,
    )
    build_seconds = time.perf_counter() - build_started

    turn_started = time.perf_counter()
    events = await _drain(workflow, task, stop_on_plan_review=plan_review)
    turn_seconds = time.perf_counter() - turn_started

    for agent in agents:
        close = getattr(agent, "close", None)
        if callable(close):
            try:
                await close()
            except Exception as exc:  # pragma: no cover - teardown only
                print(f"  (warning: failed to close an agent: {exc})")

    return {
        "agents": len(agents),
        "events": events,
        "build_seconds": build_seconds,
        "turn_seconds": turn_seconds,
        "total_seconds": build_seconds + turn_seconds,
    }


def report(result: dict, plan_review: bool) -> int:
    lane = "Deliberate" if plan_review else "Fast"
    print()
    print(f"{lane} lane, {result['agents']} agents, {result['events']} events")
    print(f"  Full workflow rebuild : {result['build_seconds']:8.2f}s")
    print(f"  Lane turn             : {result['turn_seconds']:8.2f}s")
    print(f"  End to end            : {result['total_seconds']:8.2f}s")

    if plan_review:
        print("\n  (Deliberate lane: stopped at the first plan-review request.)")
        return 0

    target = FAST_LANE_TARGET_SECONDS
    total = result["total_seconds"]
    print(f"  Target                : {target:8.2f}s")
    if total <= target:
        print(f"\n  MET — {target - total:.2f}s of headroom. ADR-013: do not build a bypass.")
        return 0
    print(
        f"\n  MISSED by {total - target:.2f}s. ADR-013 reopens the bypass question — "
        "and note the rebuild figure above: a warm cache costs nothing but the turn."
    )
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument(
        "--plan-review",
        action="store_true",
        help="Measure the Deliberate lane's build instead of the Fast lane.",
    )
    args = parser.parse_args(argv)

    # Everything the environment needs, before the first backend import.
    env_name = load_azd_environment()
    endpoint = os.environ.get("FAST_LANE_PROJECT_ENDPOINT") or os.environ.get(
        "AZURE_AI_PROJECT_ENDPOINT", ""
    )
    if not endpoint:
        print(
            "No Foundry project endpoint. This probe measures against the real "
            "Foundry project and will not measure a placeholder. Either run it "
            "from a checkout with an azd environment, or export the endpoint:\n\n"
            '    export FAST_LANE_PROJECT_ENDPOINT="$(grep AZURE_AI_PROJECT_ENDPOINT '
            ".azure/<env>/.env | cut -d= -f2- | tr -d '\"')\"",
            file=sys.stderr,
        )
        return 2

    os.environ["AZURE_AI_PROJECT_ENDPOINT"] = endpoint
    os.environ.setdefault("AZURE_AI_AGENT_ENDPOINT", endpoint)
    sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

    print(f"Foundry project : {endpoint}")
    if env_name:
        print(f"azd environment : {env_name}")

    result = asyncio.run(measure(args.task, args.plan_review, endpoint))
    return report(result, args.plan_review)


if __name__ == "__main__":
    raise SystemExit(main())
