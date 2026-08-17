"""The store assistant's content pack and Foundry agent roster (issue #19).

The surface has resolved to **no assistant** since #25, because
``selectStoreAssistant`` recognises the store assistant rather than taking
whatever the backend listed first and nothing had ever been uploaded under its
identifier. This is the pack that identifier names.

These tests read the **authored artefacts** — the team definition the deploy
path uploads, the documents it indexes — and call the **pure predicates the
deploy path calls**, rather than describing them. Three of them span a seam
that nothing else spans:

* the pack's identity against ``storeSurface.ts``, because a pack uploaded
  under a different identifier is a surface that says the assistant is not
  loaded while the roster sits in Cosmos, and nothing on either side looks
  wrong;
* every agent's ``deployment_name`` against the ``SUPPORTED_MODELS`` allowlist,
  because ``AgentFactory.get_agents`` **skips** an agent whose model it does
  not recognise with a ``logger.warning`` and no error — a misspelling there is
  a cast member who never arrives and a demo that is quietly one agent short;
* the runbooks against the SOP corpus' rehearsed honest miss, because a
  troubleshooting runbook that covers the car wash answers the question the
  walkthrough exists to have refused.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from store_pack import __main__ as main_mod  # noqa: E402
from store_pack import content as content_mod  # noqa: E402
from store_pack import pack as pack_mod  # noqa: E402
from store_pack import roster as roster_mod  # noqa: E402

STORE_SURFACE_TS = REPO_ROOT / "src" / "App" / "src" / "models" / "storeSurface.ts"


@pytest.fixture(scope="module")
def store_pack():
    return pack_mod.load_pack(REPO_ROOT)


# ---------------------------------------------------------------------------
# The pack is the one the surface recognises
# ---------------------------------------------------------------------------


def _ts_const(name: str) -> str:
    """Read a string constant out of the surface's own module.

    Read rather than restated: a copy in this file would agree with itself
    forever, and the failure it has to catch is precisely the two drifting
    apart.
    """
    source = STORE_SURFACE_TS.read_text(encoding="utf-8")
    for line in source.splitlines():
        if line.startswith(f"export const {name} = "):
            return line.split("=", 1)[1].strip().rstrip(";").strip("'\"")
    raise AssertionError(f"{name} is not exported from storeSurface.ts")


def test_given_the_pack_when_read_then_its_team_id_is_the_one_the_surface_looks_for(
    store_pack,
):
    assert store_pack.team["team_id"] == _ts_const("STORE_ASSISTANT_TEAM_ID")


def test_given_the_pack_when_read_then_its_name_is_the_one_the_surface_claims(
    store_pack,
):
    assert store_pack.team["name"] == _ts_const("ASSISTANT_NAME")


def test_given_the_team_id_when_read_then_it_is_hex_only(store_pack):
    assert pack_mod.is_hex_uuid(store_pack.team["team_id"])


@pytest.mark.parametrize(
    "identifier",
    [
        "00000000-0000-0000-0000-00000000022g",  # g is not a hex digit
        "store-assistant-223",
        "0000000000000000000000000000223",
        "",
    ],
)
def test_given_a_non_hex_identifier_when_checked_then_it_is_refused(identifier):
    assert not pack_mod.is_hex_uuid(identifier)


# ---------------------------------------------------------------------------
# The roster: who is in it, and on which model
# ---------------------------------------------------------------------------


def test_given_the_roster_when_read_then_every_intended_agent_is_present(store_pack):
    assert sorted(agent["name"] for agent in store_pack.agents) == sorted(
        roster_mod.INTENDED_MODELS
    )


def test_given_the_roster_when_read_then_each_agent_carries_its_intended_model(
    store_pack,
):
    assert roster_mod.model_assignment(store_pack.team) == roster_mod.INTENDED_MODELS


def test_given_the_roster_when_read_then_the_orchestrator_takes_the_cheaper_model(
    store_pack,
):
    # The manager's model is the team's `deployment_name` fallback and
    # `ORCHESTRATOR_MODEL_NAME` (ADR-003); both are the cheaper model, and the
    # team-level value is the half this pack owns.
    assert store_pack.team["deployment_name"] == roster_mod.CHEAP_MODEL


def test_given_the_roster_when_read_then_reasoning_work_is_on_the_reasoning_model():
    assert roster_mod.INTENDED_MODELS["TroubleshootingAgent"] == roster_mod.REASONING_MODEL
    assert roster_mod.INTENDED_MODELS["EscalationAgent"] == roster_mod.REASONING_MODEL
    assert roster_mod.INTENDED_MODELS["ShiftTasksAgent"] == roster_mod.CHEAP_MODEL


# ---------------------------------------------------------------------------
# The silent skip
# ---------------------------------------------------------------------------


def test_given_the_authored_roster_when_checked_then_no_agent_would_be_skipped(
    store_pack,
):
    assert roster_mod.silently_skipped(store_pack.team, roster_mod.SUPPORTED_MODELS) == []


def test_given_a_misspelled_deployment_name_when_checked_then_that_agent_is_named():
    team = {
        "agents": [
            {"name": "TroubleshootingAgent", "deployment_name": "gpt-5.4"},
            {"name": "ShiftTasksAgent", "deployment_name": "gpt-54-mini"},
        ]
    }
    assert roster_mod.silently_skipped(team, ["gpt-5.4", "gpt-5.4-mini"]) == [
        "ShiftTasksAgent"
    ]


def test_given_an_agent_with_no_deployment_name_when_checked_then_it_is_skipped():
    # `AgentFactory.create_agent_from_config` reads `deployment_name` with a
    # `None` default and then asks whether it is in the allowlist, so an
    # omitted model is a skipped agent exactly like a misspelled one.
    team = {"agents": [{"name": "ShiftTasksAgent"}]}
    assert roster_mod.silently_skipped(team, ["gpt-5.4-mini"]) == ["ShiftTasksAgent"]


def test_given_an_empty_allowlist_when_checked_then_every_agent_is_skipped(store_pack):
    assert roster_mod.silently_skipped(store_pack.team, []) == [
        agent["name"] for agent in store_pack.agents
    ]


def test_given_the_deployed_supported_models_when_read_then_they_match_the_environment():
    # The allowlist this pack is authored against is the deployed one, read out
    # of `.env.sample` rather than restated, so a roster naming a model the
    # environment does not permit is red here rather than a warning in a
    # container log nobody is reading.
    sample = (REPO_ROOT / "src" / "backend" / ".env.sample").read_text(encoding="utf-8")
    declared = None
    for line in sample.splitlines():
        if line.startswith("SUPPORTED_MODELS="):
            declared = json.loads(line.split("=", 1)[1].strip().strip("'\""))
    assert declared is not None, "SUPPORTED_MODELS is not in .env.sample"
    assert sorted(roster_mod.SUPPORTED_MODELS) == sorted(declared)


# ---------------------------------------------------------------------------
# Models and indexes exist before the upload
# ---------------------------------------------------------------------------


def test_given_every_model_deployed_when_checked_then_nothing_is_missing(store_pack):
    assert roster_mod.missing_models(store_pack.team, ["gpt-5.4", "gpt-5.4-mini"]) == []


def test_given_a_model_that_is_not_deployed_when_checked_then_it_is_named(store_pack):
    assert roster_mod.missing_models(store_pack.team, ["gpt-5.4-mini"]) == ["gpt-5.4"]


def test_given_a_team_model_that_is_not_deployed_when_checked_then_it_is_named():
    team = {"deployment_name": "gpt-5.4-mini", "agents": []}
    assert roster_mod.missing_models(team, ["gpt-5.4"]) == ["gpt-5.4-mini"]


def test_given_the_pack_when_read_then_every_index_it_declares_exists(store_pack):
    assert roster_mod.missing_indexes(store_pack, store_pack.index_names) == []


def test_given_an_index_that_was_never_created_when_checked_then_it_is_named(store_pack):
    assert roster_mod.missing_indexes(store_pack, []) == sorted(store_pack.index_names)


# ---------------------------------------------------------------------------
# The knowledge bases the roster names are the ones the deploy path seeds
# ---------------------------------------------------------------------------


def test_given_the_roster_when_read_then_every_knowledge_base_it_names_is_seeded(
    store_pack,
):
    seeded = pack_mod.seeded_knowledge_base_names(REPO_ROOT)
    assert set(store_pack.knowledge_base_names) <= seeded


def test_given_the_seeded_knowledge_bases_when_read_then_each_names_a_pack_index(
    store_pack,
):
    seeded = pack_mod.seeded_knowledge_base_indexes(REPO_ROOT)
    for kb_name in store_pack.knowledge_base_names:
        assert seeded[kb_name] <= set(store_pack.index_names)


def test_given_the_troubleshooting_grounding_when_read_then_it_is_its_own_knowledge_base(
    store_pack,
):
    # R6 shows provenance, and the claim is that the troubleshooting answer and
    # the procedure answer came from different places. A troubleshooting agent
    # sharing one knowledge base with anything else makes that claim unprovable
    # from the pack.
    troubleshooting = store_pack.agent("TroubleshootingAgent")
    others = [
        agent
        for agent in store_pack.agents
        if agent["name"] != "TroubleshootingAgent" and agent.get("use_knowledge_base")
    ]
    assert troubleshooting["use_knowledge_base"] is True
    assert troubleshooting["knowledge_base_name"] not in [
        agent.get("knowledge_base_name") for agent in others
    ]


# ---------------------------------------------------------------------------
# The cross-platform hop
# ---------------------------------------------------------------------------


def test_given_the_roster_when_read_then_exactly_one_agent_holds_the_sop_tool(
    store_pack,
):
    holders = [
        agent["name"]
        for agent in store_pack.agents
        if agent.get("use_toolbox") and agent.get("toolbox_filter") == "sop"
    ]
    assert holders == ["ShiftTasksAgent"]


def test_given_the_sop_tool_holder_when_read_then_it_has_no_foundry_knowledge_base(
    store_pack,
):
    # The load-bearing one. An agent holding both a knowledge-base tool and the
    # SOP tool chooses between them, and the branch it does not take is the
    # cross-platform hop the demo's centrepiece rests on — answered from
    # Foundry, the Grounding panel stays dark and the beat simply does not
    # happen, with nothing on screen looking wrong.
    holder = store_pack.agent("ShiftTasksAgent")
    assert holder.get("use_knowledge_base", False) is False
    assert holder.get("use_file_search", False) is False


# ---------------------------------------------------------------------------
# The memory of one shift (issue #21)
# ---------------------------------------------------------------------------


def test_given_the_roster_when_read_then_only_the_troubleshooter_holds_the_memory(
    store_pack,
):
    # The record is the memory of *this fault*, and the agent that offers
    # runbook steps is the one that must not offer a step twice. A second
    # holder would record a step nobody attributed to a fault.
    holders = [
        agent["name"]
        for agent in store_pack.agents
        if agent.get("use_toolbox") and agent.get("toolbox_filter") == "troubleshooting"
    ]
    assert holders == ["TroubleshootingAgent"]


def test_given_the_memory_holder_when_read_then_it_keeps_its_knowledge_base(
    store_pack,
):
    # Deliberately unlike the SOP tool's holder, which has no knowledge base at
    # all. That rule is about two *grounding* sources competing to answer one
    # question — the branch not taken there is the cross-platform hop. The
    # troubleshooting tools ground nothing: they answer "what has this
    # associate already tried", which the runbook knowledge base cannot answer
    # and which cannot answer an equipment question. There is no branch to take.
    holder = store_pack.agent("TroubleshootingAgent")
    assert holder["use_knowledge_base"] is True
    assert holder["knowledge_base_name"]


def test_given_the_memory_holder_when_read_then_it_can_still_ask_the_associate(
    store_pack,
):
    # The clarification turn is where the record is written: the backend
    # persists the answer at the seam it arrives on. An agent that cannot ask
    # never produces one.
    assert store_pack.agent("TroubleshootingAgent")["user_responses"] is True


def test_given_the_troubleshooting_prompt_when_read_then_it_names_both_tools(
    store_pack,
):
    # The tools are only reached if the agent is told to reach them, and the
    # names have to be the ones the MCP container registers — a prompt naming a
    # tool that does not exist is an agent that quietly answers from memory.
    message = store_pack.agent("TroubleshootingAgent")["system_message"]
    assert "list_attempted_steps" in message
    assert "record_attempted_steps" in message


def test_given_the_troubleshooting_prompt_when_read_then_it_offers_to_escalate(
    store_pack,
):
    # The acceptance criterion in the agent's own words: when the runbook runs
    # out, the next move is a ticket, not an invented repair step.
    message = store_pack.agent("TroubleshootingAgent")["system_message"].lower()
    assert "escalate" in message or "ticket" in message


def test_given_the_troubleshooting_tools_when_named_then_the_container_registers_them(
    store_pack,
):
    # The container still exposes the tool for correction flows outside this
    # authored task, but #62's escalation prompt makes it unreachable so the
    # approval seam, not a model choice, creates the record.
    service = (
        REPO_ROOT / "src" / "mcp_server" / "services" / "troubleshooting_service.py"
    ).read_text(encoding="utf-8")
    message = store_pack.agent("TroubleshootingAgent")["system_message"]

    for tool in ("list_attempted_steps", "record_attempted_steps"):
        assert f"async def {tool}(" in service, f"{tool} is not registered"
        assert tool in message

    domain = (
        REPO_ROOT / "src" / "mcp_server" / "core" / "factory.py"
    ).read_text(encoding="utf-8")
    assert 'TROUBLESHOOTING = "troubleshooting"' in domain, (
        "the roster's toolbox_filter names a domain the container does not serve"
    )


# ---------------------------------------------------------------------------
# The authored content
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def runbooks(store_pack):
    return [
        content_mod.parse_document(path)
        for path in store_pack.documents("datasets/troubleshooting")
    ]


@pytest.fixture(scope="module")
def operations(store_pack):
    return [
        content_mod.parse_document(path)
        for path in store_pack.documents("datasets/operations")
    ]


def test_given_the_runbooks_when_counted_then_there_are_three_to_five(runbooks):
    assert 3 <= len(runbooks) <= 5


def test_given_the_runbooks_when_read_then_each_carries_a_unique_identifier(runbooks):
    ids = [doc.doc_id for doc in runbooks]
    assert len(set(ids)) == len(ids)
    assert all(doc_id.startswith("RB-2") for doc_id in ids)


def test_given_a_runbook_when_read_then_its_identifier_matches_its_filename(runbooks):
    for doc in runbooks:
        assert doc.path.name.startswith(doc.doc_id + " ")


def test_given_a_runbook_when_read_then_it_branches(runbooks):
    # A runbook with one path is a list of steps. The requirement is a runbook
    # that asks the associate for an observation and takes a different path on
    # the answer, because that is what makes the multi-turn beat (#21) a
    # conversation rather than a recital.
    for doc in runbooks:
        assert len(doc.branches) >= 2, doc.doc_id


def test_given_a_runbook_when_read_then_every_branch_states_its_condition(runbooks):
    for doc in runbooks:
        for branch in doc.branches:
            assert branch.condition, f"{doc.doc_id}: {branch.heading}"


def test_given_a_runbook_when_read_then_it_names_what_is_usually_already_tried(
    runbooks,
):
    # The troubleshooting agent asks the associate what they have already
    # tried, and an open question mid-shift gets a shrug. The runbook supplies
    # the two or three things worth naming so the question can be answered in
    # one line.
    for doc in runbooks:
        assert len(doc.already_tried) >= 2, doc.doc_id


def test_given_a_runbook_when_read_then_it_says_where_to_stop(runbooks):
    for doc in runbooks:
        assert content_mod.STOP_HEADING in doc.headings, doc.doc_id


def test_given_the_operations_documents_when_read_then_the_store_profile_is_there(
    operations,
):
    assert [doc.doc_id for doc in operations if doc.doc_id.startswith("STORE-")] == [
        "STORE-223"
    ]


def test_given_the_operations_documents_when_read_then_the_ticket_template_is_there(
    operations,
):
    assert [doc.doc_id for doc in operations if doc.doc_id.startswith("TKT-")] == [
        "TKT-001"
    ]


def test_given_the_ticket_template_when_read_then_it_carries_the_attempted_steps(
    operations,
):
    # R4's requirement, in the shape the ticket is filled from: if the template
    # has no field for what the associate already tried, the ticket cannot
    # carry it and the associate ends up re-typing it.
    template = next(doc for doc in operations if doc.doc_id == "TKT-001")
    assert "steps_attempted" in template.fields


def test_given_the_ticket_template_when_read_then_it_is_a_service_incident(operations):
    template = next(doc for doc in operations if doc.doc_id == "TKT-001")
    for field in ("site", "asset_tag", "priority", "symptom", "raised_by", "status"):
        assert field in template.fields, field


def test_given_the_store_profile_when_read_then_it_is_store_223(operations, store_pack):
    profile = next(doc for doc in operations if doc.doc_id == "STORE-223")
    assert "Store 223" in profile.text


def test_given_every_document_when_read_then_it_never_answers_the_rehearsed_miss(
    store_pack,
):
    # The SOP corpus keeps these terms out so the out-of-corpus beat stays a
    # miss. A troubleshooting runbook is a *different* corpus, indexed by a
    # different tool into a different service — so without this, a runbook
    # covering the car wash would answer the question the walkthrough exists to
    # have refused, and the SOP corpus' own verifier would still be green.
    absent = pack_mod.honest_miss_absent_terms(REPO_ROOT)
    assert absent, "the SOP corpus manifest declares no absent terms"
    for path in store_pack.all_documents():
        haystack = path.read_text(encoding="utf-8").lower()
        for term in absent:
            assert term.lower() not in haystack, f"{path.name} covers {term!r}"


def test_given_every_document_when_read_then_it_is_english_and_plain_text(store_pack):
    # `index_datasets.py` decodes anything that is not a PDF or a DOCX as
    # UTF-8, which is why these are authored as the indexed artefact rather
    # than built into one. Keeping them ASCII keeps a smart quote out of an
    # answer an associate reads.
    for path in store_pack.all_documents():
        text = path.read_text(encoding="utf-8")
        offenders = sorted({ch for ch in text if ord(ch) > 127})
        assert not offenders, f"{path.name}: {offenders}"


def test_given_the_pack_when_read_then_every_source_directory_holds_documents(
    store_pack,
):
    for source in store_pack.sources:
        assert store_pack.documents(source), source


# ---------------------------------------------------------------------------
# The roster, read back out of a deployment
# ---------------------------------------------------------------------------


def test_given_the_authored_roster_uploaded_intact_when_compared_then_it_passes(
    store_pack,
):
    assert (
        main_mod.check_roster(
            store_pack.team, store_pack.team, roster_mod.SUPPORTED_MODELS
        )
        == []
    )


def test_given_an_agent_missing_from_the_deployment_when_compared_then_it_is_reported(
    store_pack,
):
    uploaded = dict(store_pack.team)
    uploaded["agents"] = [
        agent for agent in store_pack.agents if agent["name"] != "EscalationAgent"
    ]

    problems = main_mod.check_roster(
        uploaded, store_pack.team, roster_mod.SUPPORTED_MODELS
    )

    assert any("EscalationAgent" in problem for problem in problems)


def test_given_a_misspelled_model_in_the_deployment_when_compared_then_it_is_reported(
    store_pack,
):
    # The whole reason this check exists: this is what a typo in a team
    # definition looks like from outside — a 200, a team in Cosmos, and one
    # agent that never arrives.
    uploaded = json.loads(json.dumps(store_pack.team))
    uploaded["agents"][0]["deployment_name"] = "gpt-5.4-mni"

    problems = main_mod.check_roster(
        uploaded, store_pack.team, roster_mod.SUPPORTED_MODELS
    )

    assert any("skip it with only a warning" in problem for problem in problems)


def test_given_an_unexpected_agent_in_the_deployment_when_compared_then_it_is_reported(
    store_pack,
):
    uploaded = json.loads(json.dumps(store_pack.team))
    uploaded["agents"].append(
        {"name": "MarketingAgent", "deployment_name": "gpt-5.4-mini"}
    )

    problems = main_mod.check_roster(
        uploaded, store_pack.team, roster_mod.SUPPORTED_MODELS
    )

    assert any("MarketingAgent" in problem for problem in problems)


def test_given_the_authored_pack_when_verified_then_the_command_reports_no_problem(
    capsys,
):
    assert main_mod.main(["verify"]) == 0
    assert "Pack OK" in capsys.readouterr().out


def test_given_an_index_that_does_not_exist_when_verified_then_the_command_fails(
    capsys,
):
    assert main_mod.main(["verify", "--search-indexes", ""]) == 1
    assert "does not exist yet" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The deploy path installs it, whatever the stock selection is
# ---------------------------------------------------------------------------


POST_DEPLOY_SH = (
    REPO_ROOT / "infra" / "scripts" / "post-provision" / "post_deploy.sh"
)
POST_DEPLOY_PS1 = (
    REPO_ROOT / "infra" / "scripts" / "post-provision" / "post_deploy.ps1"
)


def _uploads_for(selection: str) -> list:
    """Which team configurations the deploy path uploads for a selection.

    Sources the real script and calls its real upload sequence with
    ``upload_team_config`` stubbed, rather than reading the script and agreeing
    with itself about what the guards mean.
    """
    script = (
        f'MACAE_POST_DEPLOY_LIB_ONLY=1 source "{POST_DEPLOY_SH}"\n'
        "upload_team_config() { echo \"$1\"; }\n"
        "info() { :; }\n"
        f'MACAE_USE_CASE="{selection}" select_use_case >/dev/null\n'
        "upload_all_team_configs\n"
    )
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_given_no_stock_pack_when_deployed_then_the_store_assistant_is_still_uploaded():
    # `none` means no *stock* pack. A deployment that seeded nothing at all is
    # the surface truthfully reporting that the assistant is not loaded, which
    # is honest and unusable.
    assert _uploads_for("none") == ["Circle K Frontline Store Assistant"]


def test_given_every_stock_pack_when_deployed_then_the_store_assistant_is_last():
    uploads = _uploads_for("all")
    assert uploads[-1] == "Circle K Frontline Store Assistant"
    assert len(uploads) == 7


def test_given_one_stock_pack_when_deployed_then_the_store_assistant_comes_too():
    assert _uploads_for("3") == [
        "HR Employee Onboarding",
        "Circle K Frontline Store Assistant",
    ]


def test_given_the_store_pack_when_uploaded_then_it_carries_the_surface_identifier(
    store_pack,
):
    script = (
        f'MACAE_POST_DEPLOY_LIB_ONLY=1 source "{POST_DEPLOY_SH}"\n'
        "echo \"$STORE_PACK_TEAM_ID\"\n"
    )
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == store_pack.team["team_id"]


def test_given_the_powershell_entry_point_when_read_then_it_installs_the_store_pack(
    store_pack,
):
    # There is no pwsh in CI, so this half is asserted by reading the file. The
    # failure it has to catch is the two entry points disagreeing about whether
    # the demonstration's own pack is installed — which would be found on the
    # machine that is on stage.
    source = POST_DEPLOY_PS1.read_text(encoding="utf-8")
    assert store_pack.team["team_id"] in source
    assert "content_packs/store_assistant/agent_teams" in source


def test_given_the_deploy_path_when_read_then_it_seeds_the_packs_knowledge_bases(
    store_pack,
):
    # The seeding step is scoped by an `--only` filter built from a use-case
    # map, and `none` has no entry in that map. The store assistant's two
    # knowledge bases are appended outside it, so an agent's grounding does not
    # depend on which stock pack somebody chose.
    script = (
        f'MACAE_POST_DEPLOY_LIB_ONLY=1 source "{POST_DEPLOY_SH}"\n'
        'echo "$STORE_PACK_KBS"\n'
    )
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    named = set(result.stdout.strip().split(","))
    assert named == set(store_pack.knowledge_base_names)


def test_given_the_powershell_entry_point_when_read_then_it_seeds_the_same_bases(
    store_pack,
):
    source = POST_DEPLOY_PS1.read_text(encoding="utf-8")
    for name in store_pack.knowledge_base_names:
        assert f'"{name}"' in source


def test_given_the_powershell_entry_point_when_read_then_its_upload_is_unguarded():
    # The bash half proves this behaviourally by sourcing the script. This half
    # can only read, so it checks the one thing a reader can check: that the
    # store pack's upload is not inside a `$useCaseSelection -in @(...)` block.
    source = POST_DEPLOY_PS1.read_text(encoding="utf-8")
    upload = source.index('-TeamId "00000000-0000-0000-0000-000000000223"')
    preceding = source[:upload]
    last_guard = preceding.rfind("$useCaseSelection -in @(")
    last_close = preceding.rfind("\n    }")
    assert last_close > last_guard, (
        "the store assistant's upload appears to sit inside a use-case guard"
    )


def test_a_change_to_the_pack_or_its_tooling_runs_these_tests():
    # This suite reads the authored artefacts, the verification tooling and the
    # knowledge-base registrations, and `test.yml` triggers on Python paths —
    # so the changes most likely to break it would not have run it. Asserted
    # rather than assumed, the same way #24 and #25 asserted theirs.
    text = (
        REPO_ROOT / ".github" / "workflows" / "test.yml"
    ).read_text(encoding="utf-8")

    for path in (
        "content_packs/store_assistant/**",
        "tools/store_pack/**",
        "infra/scripts/post-provision/seed_knowledge_bases.py",
        "src/App/src/models/storeSurface.ts",
        # The SOP corpus, since #26: two of the six Quick Tasks are read out of
        # its manifest and one of them names a document under its sources.
        "content/sop/corpus.toml",
        "content/sop/src/**",
    ):
        assert text.count(f"'{path}'") >= 2, (
            f"a change to {path} does not run the CI-tooling tests on both "
            "push and pull_request"
        )

    assert "'src/App/**'" not in text, (
        "test.yml triggers on the whole frontend — a CSS edit now runs the "
        "backend suite"
    )


# ---------------------------------------------------------------------------
# The Simulated ticket (issue #22)
# ---------------------------------------------------------------------------


def test_given_the_roster_when_read_then_the_escalation_agent_holds_the_ticket_tool(
    store_pack,
):
    # The ticket is drafted through a tool rather than written into a reply,
    # because a ticket that exists only in a transcript is not persisted, not
    # renderable and not something an approval can confirm.
    escalation = store_pack.agent("EscalationAgent")
    assert escalation["use_toolbox"] is True
    assert escalation["toolbox_filter"] == "escalation"


def test_given_the_roster_when_read_then_only_the_escalation_agent_holds_it(
    store_pack,
):
    # One holder. A second agent able to draft a ticket is a ticket raised from
    # a turn nobody planned to escalate.
    holders = [
        agent["name"]
        for agent in store_pack.agents
        if agent.get("use_toolbox") and agent.get("toolbox_filter") == "escalation"
    ]
    assert holders == ["EscalationAgent"]


def test_given_the_escalation_agent_when_read_then_it_cannot_ask_the_associate(
    store_pack,
):
    # The load-bearing one. `user_responses` is the clarification tool, and a
    # clarification at this point in the turn *is* the second confirmation step
    # the requirement says does not exist: the associate is about to approve
    # the plan, and the approval is the confirmation.
    assert store_pack.agent("EscalationAgent").get("user_responses", False) is False


def test_given_the_escalation_task_when_approved_then_it_requires_a_ticket_without_questions(
    store_pack,
):
    """The joined troubleshooting record is complete before escalation starts,
    so the approved turn has no unbounded interview left to conduct."""
    task = next(
        task
        for task in store_pack.team["starting_tasks"]
        if task["id"] == "task-223-escalation"
    )
    message = store_pack.agent("EscalationAgent")["system_message"].lower()

    assert task["ticket_on_approval"] is True
    assert "do not ask the associate any questions" in message


def test_given_the_ticketing_task_when_read_then_its_status_reply_is_authored_fast(
    store_pack,
):
    task = next(
        task
        for task in store_pack.team["starting_tasks"]
        if task["id"] == "task-223-escalation"
    )
    reply = task["ticket_status_reply"]

    assert reply["lane"] == "fast"
    assert reply["prompt"].strip()


def test_given_the_escalation_prompt_when_read_then_it_does_not_call_the_drafting_tool(
    store_pack,
):
    message = store_pack.agent("EscalationAgent")["system_message"].lower()
    assert "do not call draft_service_ticket" in message


def test_given_the_escalation_prompt_when_read_then_it_names_the_status_tool(
    store_pack,
):
    service = (
        REPO_ROOT / "src" / "mcp_server" / "services" / "escalation_service.py"
    ).read_text(encoding="utf-8")
    message = store_pack.agent("EscalationAgent")["system_message"]

    assert "async def get_ticket_status(" in service
    assert "get_ticket_status" in message


def test_given_the_escalation_prompt_when_read_then_it_never_asks_for_the_steps(
    store_pack,
):
    # The requirement in the agent's own words. The code discards a re-typed
    # value anyway — this is the half that stops the agent *asking*, which is
    # the half the associate would notice.
    message = store_pack.agent("EscalationAgent")["system_message"].lower()
    assert "attempted steps" in message
    assert "do not ask" in message


def test_given_the_escalation_prompt_when_read_then_the_approval_is_the_confirmation(
    store_pack,
):
    message = store_pack.agent("EscalationAgent")["system_message"].lower()
    assert "no second confirmation" in message


def test_given_the_escalation_prompt_when_read_then_it_says_the_ticket_is_simulated(
    store_pack,
):
    message = store_pack.agent("EscalationAgent")["system_message"].lower()
    assert "simulated" in message


def test_given_the_ticket_tool_when_named_then_the_container_registers_it(
    store_pack,
):
    # Spans the seam between the authored prompt and the container that serves
    # the tool, the same way the troubleshooting pair is spanned. A rename on
    # either side is an agent calling a tool that is not there, and the
    # framework's answer to that is silence.
    service = (
        REPO_ROOT / "src" / "mcp_server" / "services" / "escalation_service.py"
    ).read_text(encoding="utf-8")
    message = store_pack.agent("EscalationAgent")["system_message"]

    assert "async def draft_service_ticket(" in service
    assert "do not call draft_service_ticket" in message.lower()

    domain = (
        REPO_ROOT / "src" / "mcp_server" / "core" / "factory.py"
    ).read_text(encoding="utf-8")
    assert 'ESCALATION = "escalation"' in domain, (
        "the roster's toolbox_filter names a domain the container does not serve"
    )


def test_given_the_escalation_domain_when_filtered_then_the_allowlist_names_it(
    store_pack,
):
    # A domain with no allowlist entry gets **no filter at all**, and every
    # domain server also carries the shared `ask_user` — which is the second
    # confirmation step this whole slice exists to make unreachable. Its
    # absence was what #21 found by writing this test rather than by reading
    # the code.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_mcp_config_for_tests",
        REPO_ROOT / "src" / "backend" / "config" / "mcp_config.py",
    )
    source = (
        REPO_ROOT / "src" / "backend" / "config" / "mcp_config.py"
    ).read_text(encoding="utf-8")
    assert spec is not None
    assert '"escalation": [' in source

    filters = {
        agent.get("toolbox_filter")
        for agent in store_pack.agents
        if agent.get("use_toolbox")
    }
    for domain in filters:
        assert f'"{domain}": [' in source, (
            f"the roster gives an agent the '{domain}' toolbox but "
            "DOMAIN_ALLOWED_TOOLS has no entry, so no filter is applied"
        )


def test_given_the_escalation_allowlist_when_read_then_nothing_in_it_raises_a_ticket(
    store_pack,
):
    # An allowlist naming anything beyond the draft would put a second
    # confirmation step back within a model's reach.
    source = (
        REPO_ROOT / "src" / "backend" / "config" / "mcp_config.py"
    ).read_text(encoding="utf-8")
    block = source.split('"escalation": [')[1].split("]")[0]

    assert "draft_service_ticket" in block
    for forbidden in ("submit", "confirm", "raise", "ask_user"):
        assert forbidden not in block


def test_given_an_escalation_request_when_routed_then_it_takes_the_deliberate_lane(
    store_pack,
):
    # The acceptance criterion, against the real router rather than by
    # inspection of the keyword list: the plan-approval step has to appear,
    # because it is the confirmation.
    import importlib.util
    import sys

    backend = REPO_ROOT / "src" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    spec = importlib.util.spec_from_file_location(
        "_lane_router_for_tests", backend / "lane" / "router.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for phrasing in (
        "I can't fix it, raise a ticket",
        "escalate this to the service desk",
        "log a service ticket for the coffee machine",
    ):
        assert module.select_lane(None, phrasing).value == "deliberate", phrasing


# ---------------------------------------------------------------------------
# The Workforce agent (issue #52, ADR-017)
# ---------------------------------------------------------------------------


def test_given_the_roster_when_read_then_the_workforce_specialist_is_present(
    store_pack,
):
    # The fourth specialist. `INTENDED_MODELS` is the specification and the
    # team definition is the artefact; the two are asserted to agree above, so
    # this is the claim that the specification itself gained a fourth name.
    assert "WorkforceAgent" in roster_mod.INTENDED_MODELS
    assert store_pack.agent("WorkforceAgent")


def test_given_the_workforce_agent_when_read_then_it_is_named_for_its_function(
    store_pack,
):
    # ADR-017's naming decision, asserted over the whole team definition rather
    # than over the agent's name alone: the roster, the plan steps and the
    # token meter all render text authored here, and a vendor named in any of
    # them is the surface claiming an integration this build does not have.
    definition = json.dumps(store_pack.team).lower()

    for vendor in ("workday", "kronos", "ukg", "adp"):
        assert vendor not in definition, vendor


def test_given_the_workforce_agent_when_read_then_it_holds_only_its_own_toolbox(
    store_pack,
):
    agent = store_pack.agent("WorkforceAgent")

    assert agent["use_toolbox"] is True
    assert agent["toolbox_filter"] == "workforce"
    assert agent.get("use_knowledge_base", False) is False
    assert agent.get("use_file_search", False) is False


def test_given_the_workforce_agent_when_read_then_only_it_holds_that_toolbox(
    store_pack,
):
    holders = [
        agent["name"]
        for agent in store_pack.agents
        if agent.get("use_toolbox") and agent.get("toolbox_filter") == "workforce"
    ]

    assert holders == ["WorkforceAgent"]


def test_given_the_workforce_agent_when_read_then_it_does_not_ask_the_associate(
    store_pack,
):
    # `user_responses` is the clarification tool, and this beat is one tap and
    # one answer. An agent that can ask is an agent that can ask *who is
    # asking*, which is the question ADR-017 exists to keep it away from.
    assert store_pack.agent("WorkforceAgent").get("user_responses", False) is False


def test_given_the_workforce_prompt_when_read_then_it_refuses_the_personal_question(
    store_pack,
):
    # ADR-017's boundary in the agent's own words, behind the allowlist that
    # enforces it. The tools cannot return an individual's record; this is the
    # half that stops the agent *answering* one from its own knowledge.
    message = store_pack.agent("WorkforceAgent")["system_message"].lower()

    assert "record" in message
    assert "shift lead" in message or "cannot" in message


def test_given_the_workforce_tools_when_named_then_the_container_registers_them(
    store_pack,
):
    # The same seam the troubleshooting pair and the ticket draft are spanned
    # at. A rename on either side is an agent calling a tool that is not there,
    # and the framework's answer to that is silence.
    service = (
        REPO_ROOT / "src" / "mcp_server" / "services" / "workforce_service.py"
    ).read_text(encoding="utf-8")
    message = store_pack.agent("WorkforceAgent")["system_message"]

    for tool in ("list_workforce_procedures", "get_workforce_procedure"):
        assert f"async def {tool}(" in service, f"{tool} is not registered"
        assert tool in message

    domain = (
        REPO_ROOT / "src" / "mcp_server" / "core" / "factory.py"
    ).read_text(encoding="utf-8")
    assert 'WORKFORCE = "workforce"' in domain, (
        "the roster's toolbox_filter names a domain the container does not serve"
    )


def test_given_the_workforce_allowlist_when_read_then_nothing_in_it_reads_a_record(
    store_pack,
):
    # The tools are named explicitly, and what is *not* named is the point.
    # ADR-014 and the Mocked unlock keep a language model away from stating an
    # associate's pay; an allowlist entry naming a lookup would hand it back.
    source = (
        REPO_ROOT / "src" / "backend" / "config" / "mcp_config.py"
    ).read_text(encoding="utf-8")
    block = source.split('"workforce": [')[1].split("]")[0]

    assert "get_workforce_procedure" in block
    assert "list_workforce_procedures" in block
    for forbidden in ("balance", "pto", "pay", "hours", "ask_user"):
        assert forbidden not in block, forbidden


# ---------------------------------------------------------------------------
# The seven Quick Tasks (issues #26, #52)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workforce_library():
    """The container's own procedure library, imported by path.

    Pure — no MCP, no network — which is why it is a module of its own
    (`services/workforce_library.py`). Loaded by path rather than by dotted
    name because the container's `services` package shares its name with the
    backend's, and this file already has the backend's on `sys.path`.
    """
    import importlib.util

    path = REPO_ROOT / "src" / "mcp_server" / "services" / "workforce_library.py"
    spec = importlib.util.spec_from_file_location("_workforce_library", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shift_swap_task(store_pack):
    """The beat's own Quick Task, found by the agent that answers it."""
    return next(
        task
        for task in store_pack.starting_tasks
        if task["id"] == "task-223-shift-swap"
    )


def test_given_the_shift_swap_task_when_read_then_the_library_answers_it(
    store_pack, workforce_library
):
    # The seam the opening beat has (`[rehearsed_hit]`) and this one would
    # otherwise not: a one-tap question the library does not cover resolves —
    # honestly — as *that is not in the workforce procedure library*, and the
    # fourth specialist's whole beat becomes a second honest miss with nothing
    # going red. Put through the container's real lookup, not read.
    task = _shift_swap_task(store_pack)
    procedure = workforce_library.find_procedure(task["prompt"])

    assert procedure is not None, task["prompt"]
    assert procedure is workforce_library.SHIFT_SWAP


def test_given_the_shift_swap_transaction_when_routed_then_it_takes_the_deliberate_lane(
    store_pack, lane_mod
):
    # The declaration, not the model, earns this Reviewable plan. The typed
    # transaction is also deliberate: the one-way keyword fallback must never
    # silently turn a confirmed swap into an unreviewed request.
    task = _shift_swap_task(store_pack)

    assert lane_mod.select_lane(task["lane"], task["prompt"]) is lane_mod.Lane.DELIBERATE
    assert lane_mod.select_lane(None, task["prompt"]) is lane_mod.Lane.DELIBERATE


def test_given_the_shift_swap_transaction_when_read_then_its_people_and_order_are_authored(
    store_pack,
):
    task = _shift_swap_task(store_pack)
    steps = task["plan_steps"]

    assert [(step["id"], step.get("waitsOn")) for step in steps] == [
        (1, None),
        (2, 1),
        (3, 2),
        (4, 3),
        (5, 4),
    ]
    assert [
        step["assignee"] for step in steps if step["assignee"]["kind"] == "person"
    ] == [
        {
            "kind": "person",
            "name": "You",
            "relation": "associate",
            "simulated": False,
        },
        {
            "kind": "person",
            "name": "Marcus Bell",
            "relation": "peer",
            "simulated": True,
        },
        {
            "kind": "person",
            "name": "Dana Reyes",
            "relation": "manager",
            "simulated": True,
        },
    ]


def test_given_the_shift_swap_transaction_when_read_then_it_trips_no_personal_scope_keyword(
    store_pack, gate_keywords
):
    task = _shift_swap_task(store_pack)

    assert not gate_keywords.matches_personal_keyword(task["prompt"])


def test_given_the_shift_swap_process_question_when_read_then_it_stays_a_measured_control(
    store_pack, guardrail_corpus, gate_keywords
):
    # ADR-017's hardest negative control stays measured even though the live
    # beat now starts a transaction with a named peer.
    task = _shift_swap_task(store_pack)
    measured = {
        gate_keywords.normalise(text) for text in guardrail_corpus.NEGATIVE_CONTROLS
    }

    retired_process_question = "How do I swap a shift with another associate?"
    assert gate_keywords.normalise(retired_process_question) in measured
    assert gate_keywords.normalise(task["prompt"]) not in measured





def test_given_the_roster_when_read_then_there_are_seven_quick_tasks(store_pack):
    assert len(store_pack.starting_tasks) == 7


def test_given_the_rehearsed_hit_when_read_then_it_names_a_document_that_exists():
    # The mirror image of the honest miss, and the one this suite would not
    # otherwise have. The opening beat is the cross-platform hop; a rehearsed
    # question whose document was renamed away still resolves — as a *miss* —
    # so nothing goes red and the centrepiece quietly becomes the honest-miss
    # beat played twice.
    hit = pack_mod.rehearsed_hit(REPO_ROOT)

    assert hit["doc_id"] in pack_mod.sop_doc_ids(REPO_ROOT)


def _backend_module(dotted: str):
    """Import one backend module, without booting the application.

    Imported by its real dotted name rather than loaded twice by path: the lane
    router imports ``lane.lane`` itself, and two copies of the module produce
    two ``Lane`` enums whose members are never the same object.

    Every module reached this way is pure — the lane router, its keyword
    fallback, the guardrail's keyword fast path and the Guardrail corpus all do
    no I/O — and importing them is the whole point. A list of lanes or personal
    terms restated in this file would agree with itself forever.
    """
    import importlib
    import sys

    backend = REPO_ROOT / "src" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    return importlib.import_module(dotted)


@pytest.fixture(scope="module")
def lane_mod():
    return _backend_module("lane")


@pytest.fixture(scope="module")
def gate_keywords():
    return _backend_module("guardrail.keywords")


@pytest.fixture(scope="module")
def guardrail_corpus():
    return _backend_module("guardrail.corpus")


def _boundary_probe(store_pack, gate_keywords):
    """The one task the Identity boundary gate is meant to refuse."""
    refused = [
        task
        for task in store_pack.starting_tasks
        if gate_keywords.matches_personal_keyword(task["prompt"])
    ]
    assert len(refused) == 1, [task["id"] for task in refused]
    return refused[0]


def test_given_each_quick_task_when_read_then_its_declared_lane_parses(
    store_pack, lane_mod
):
    # Against the real parser, not a string comparison. `parse_lane` is total
    # by design and `None` is its answer to anything it does not recognise —
    # which the router then fails **open** to the Deliberate lane. So a typo
    # here does not fail an upload and does not log an error: it puts an
    # approval step in front of a procedure lookup, on stage, and the only
    # visible symptom is a demo that got slower.
    for task in store_pack.starting_tasks:
        assert lane_mod.parse_lane(task.get("lane")) is not None, task["id"]


def test_given_the_quick_tasks_when_read_then_only_the_two_transactions_deliberate(
    store_pack, lane_mod
):
    deliberate = [
        task["id"]
        for task in store_pack.starting_tasks
        if lane_mod.parse_lane(task.get("lane")) is lane_mod.Lane.DELIBERATE
    ]

    assert deliberate == ["task-223-escalation", "task-223-shift-swap"]


def test_given_the_deliberate_quick_task_when_routed_then_it_takes_that_lane(
    store_pack, lane_mod
):
    # Through the real router, declaration and all: the approval step *is* the
    # associate confirming the ticket (#22), so this is the one task whose lane
    # is load-bearing rather than cosmetic.
    task = next(
        task
        for task in store_pack.starting_tasks
        if lane_mod.parse_lane(task.get("lane")) is lane_mod.Lane.DELIBERATE
    )

    assert lane_mod.select_lane(task["lane"], task["prompt"]) is lane_mod.Lane.DELIBERATE


def test_given_the_deliberate_quick_task_when_its_prompt_is_typed_then_it_still_deliberates(
    store_pack, lane_mod
):
    # The load-bearing one. Tapping a Quick Task fills the box; **editing that
    # text clears the declaration**, because edited text is free-typed input.
    # A presenter who taps the escalation task and adds a word has just handed
    # the routing decision to the keyword fallback — and a ticket raised
    # without an approval step is a ticket nobody confirmed.
    task = next(
        task
        for task in store_pack.starting_tasks
        if lane_mod.parse_lane(task.get("lane")) is lane_mod.Lane.DELIBERATE
    )

    assert lane_mod.select_lane(None, task["prompt"]) is lane_mod.Lane.DELIBERATE


def test_given_a_fast_quick_task_when_its_prompt_is_typed_then_it_stays_fast(
    store_pack, lane_mod, gate_keywords
):
    # The same seam from the other side, and what makes consecutive runs
    # identical: the walkthrough behaves the same whether the presenter taps
    # the task or types the words on it. The keyword fallback defaults to the
    # **Deliberate** lane, so a prompt carrying no fast vocabulary at all is a
    # procedure lookup that grows an approval step the moment anybody edits it.
    #
    # The boundary probe is excluded because it never reaches the router: the
    # Identity boundary gate refuses it above the lane router and above
    # orchestration, which is the next test.
    probe = _boundary_probe(store_pack, gate_keywords)
    for task in store_pack.starting_tasks:
        if task["id"] == probe["id"]:
            continue
        if lane_mod.parse_lane(task.get("lane")) is lane_mod.Lane.DELIBERATE:
            continue
        assert lane_mod.select_lane(None, task["prompt"]) is lane_mod.Lane.FAST, (
            task["id"]
        )


def test_given_the_boundary_probe_when_read_then_the_keyword_tier_catches_it(
    store_pack, gate_keywords
):
    # R5's beat has to fire on every rehearsal, and the similarity tier is a
    # live embedding call scored against a threshold — a network hiccup, and
    # the gate's fail-closed behaviour still refuses, but the beat now depends
    # on infrastructure. The keyword fast path is pure, so the one-tap probe
    # is refused deterministically at zero cost, which is also what makes the
    # Token meter's measured `0` (#24) true for this row every time.
    probe = _boundary_probe(store_pack, gate_keywords)

    assert gate_keywords.matches_personal_keyword(probe["prompt"])


def test_given_the_boundary_probe_when_read_then_it_is_a_measured_probe(
    store_pack, gate_keywords, guardrail_corpus
):
    # Not merely *a* personal question — one of the ten the Guardrail corpus
    # measures R5's 10/10 acceptance criterion against. A rehearsed question
    # the corpus has never scored is a beat whose behaviour is asserted
    # nowhere, and the corpus is the only thing in this build that has run
    # against the real embedding deployment.
    probe = _boundary_probe(store_pack, gate_keywords)
    measured = {
        gate_keywords.normalise(text) for text in guardrail_corpus.POSITIVE_PROBES
    }

    assert gate_keywords.normalise(probe["prompt"]) in measured


def test_given_the_boundary_probe_when_read_then_the_unlock_answers_for_it(
    store_pack, gate_keywords
):
    # The **Mocked unlock** (#27) rides this same tap: refused, signed in,
    # answered. So the name the probe gives has to be the name the **Associate
    # record** is keyed by — sign in as anybody else and the audience is
    # watching one person's question answered with another person's record,
    # which is the beat making the opposite of its point.
    #
    # Read out of `associate.records` rather than restated here, because a name
    # written in a test agrees with itself forever.
    from associate.records import lookup_associate

    probe = _boundary_probe(store_pack, gate_keywords)
    named = [
        word.strip(".,?!")
        for word in probe["prompt"].split()
        if lookup_associate(word.strip(".,?!")) is not None
    ]

    assert named, (
        "the boundary probe names nobody the mocked sign-in has a record for — "
        "the closing beat would answer as somebody the presenter never named"
    )


def test_given_the_other_quick_tasks_when_read_then_none_of_them_trips_the_gate(
    store_pack, gate_keywords
):
    # The keyword fast path's requirement runs one way only: it may miss a
    # personal question, but it may **never** trip on a store-level one. Five
    # of the six taps are store-level, and a false positive here does not slow
    # the demo down — it refuses the beat outright, with copy that says the
    # assistant is store-scoped, which is the most convincing possible way to
    # look broken.
    probe = _boundary_probe(store_pack, gate_keywords)

    for task in store_pack.starting_tasks:
        if task["id"] == probe["id"]:
            continue
        assert not gate_keywords.matches_personal_keyword(task["prompt"]), task["id"]
        assert not gate_keywords.matches_personal_keyword(task["name"]), task["id"]


def test_given_the_honest_miss_task_when_read_then_it_is_the_corpus_own_question(
    store_pack,
):
    # Read out of `content/sop/corpus.toml`, not restated. The corpus keeps its
    # `absent_terms` out so this question stays a miss; a Quick Task that
    # drifted a word away from it is a tap whose answer nobody guaranteed.
    miss = pack_mod.honest_miss(REPO_ROOT)
    prompts = {task["prompt"] for task in store_pack.starting_tasks}
    names = {task["name"] for task in store_pack.starting_tasks}

    assert miss["question"] in prompts
    assert miss["quick_task"] in names


def test_given_the_quick_tasks_when_read_then_exactly_one_is_the_honest_miss(
    store_pack,
):
    # Two out-of-corpus taps is a library that looks thin; none is a beat the
    # presenter has to type their way into.
    absent = [term.lower() for term in pack_mod.honest_miss_absent_terms(REPO_ROOT)]
    misses = [
        task["id"]
        for task in store_pack.starting_tasks
        if any(term in task["prompt"].lower() for term in absent)
    ]

    assert len(misses) == 1, misses


def test_given_the_opening_task_when_read_then_it_is_the_cross_platform_hop(
    store_pack,
):
    # First, deliberately. The hop through Copilot Studio to Dataverse is the
    # claim the whole demonstration exists to make, and the honest miss only
    # reads as honesty once the audience has watched the same surface answer.
    hit = pack_mod.rehearsed_hit(REPO_ROOT)
    first = store_pack.starting_tasks[0]

    assert first["prompt"] == hit["question"]
    assert first["name"] == hit["quick_task"]


def test_given_the_rehearsed_hit_when_read_then_its_document_answers_it(store_pack):
    # The document exists (asserted above) *and* covers the question. A corpus
    # holding an SOP-102 about something else entirely would keep this suite
    # green while the opening tap came back as a miss.
    hit = pack_mod.rehearsed_hit(REPO_ROOT)
    document = pack_mod.sop_doc_ids(REPO_ROOT)[hit["doc_id"]].read_text(
        encoding="utf-8"
    ).lower()

    for word in ("close", "closing", "store"):
        assert word in document, word


def test_given_the_troubleshooting_task_when_read_then_a_runbook_covers_it(
    store_pack, runbooks
):
    # The equipment named in the one-tap fault report has to be the equipment
    # a runbook branches on, or the multi-turn beat (#21) opens by admitting it
    # has nothing to walk through.
    prompts = " ".join(task["prompt"].lower() for task in store_pack.starting_tasks)
    covered = [
        doc.doc_id
        for doc in runbooks
        if sum(
            1
            for word in doc.path.stem.lower().split()
            if len(word) > 3 and word in prompts
        )
        >= 2
    ]

    assert covered, "no runbook covers any equipment a Quick Task reports"


def test_given_the_quick_tasks_when_read_then_each_carries_its_own_identifier(
    store_pack,
):
    ids = [task["id"] for task in store_pack.starting_tasks]

    assert len(set(ids)) == len(ids), ids
    assert all(task_id.startswith("task-223-") for task_id in ids), ids


# ---------------------------------------------------------------------------
# The rehearsed replies (issue #26)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def steps_mod():
    return _backend_module("troubleshooting.steps")


def test_given_the_troubleshooting_task_when_read_then_it_carries_rehearsed_replies(
    store_pack,
):
    # The one beat that asks the associate a question back.
    # `TroubleshootingAgent` is instructed to ask what they have already tried,
    # and answering a Clarification is the only place in the walkthrough the
    # presenter would otherwise have to type — which is the thing a typo or an
    # autocorrect derails in a stakeholder meeting.
    task = next(
        task
        for task in store_pack.starting_tasks
        if task["id"] == "task-223-troubleshooting"
    )

    assert task["rehearsed_replies"]


def test_given_the_troubleshooting_task_when_read_then_its_follow_on_is_the_escalation(
    store_pack,
):
    """The escalation is reached only from the conversation it continues."""
    troubleshooting = next(
        task
        for task in store_pack.starting_tasks
        if task["id"] == "task-223-troubleshooting"
    )
    escalation = next(
        task
        for task in store_pack.starting_tasks
        if task["id"] == troubleshooting["follow_on"]
    )

    assert escalation["id"] == "task-223-escalation"


def _rehearsed_replies(store_pack) -> List[str]:
    """Every rehearsed reply the pack authors, in the order they render."""
    return [
        reply
        for task in store_pack.starting_tasks
        for reply in task.get("rehearsed_replies", [])
    ]


def test_given_each_rehearsed_reply_when_answered_then_it_records_a_step(
    store_pack, steps_mod
):
    # Through the real matcher, because a reply that records nothing is a tap
    # that looks like it worked and leaves the record empty. `#21`'s matcher is
    # deliberately conservative in one direction — a denial, a substituted
    # answer and a single shared word all record nothing — so a rehearsed reply
    # is a claim that has to be put through it rather than read.
    for reply in _rehearsed_replies(store_pack):
        assert steps_mod.parse_attempted_steps(reply), reply


def test_given_the_rehearsed_replies_when_all_answered_then_escalation_is_due(
    store_pack, steps_mod
):
    # What hands R3 to R4. The escalation offer arrives after
    # `ESCALATION_AFTER` distinct attempts, and the Simulated ticket (#22)
    # carries the same record as its `steps_attempted`. Replies that merge down
    # to two steps leave a walkthrough where nobody is ever offered a ticket and
    # the one that #26's deliberate task raises reads `not reported`.
    recorded: List[str] = []
    for reply in _rehearsed_replies(store_pack):
        recorded = steps_mod.merge_attempted(
            recorded, steps_mod.parse_attempted_steps(reply)
        )

    assert len(recorded) >= steps_mod.ESCALATION_AFTER, recorded
    assert steps_mod.escalation_due(recorded)


def test_given_a_rehearsed_reply_when_read_then_a_runbook_branches_on_it(
    store_pack, runbooks
):
    # The skip rule is the point of the beat: an associate who is told to do the
    # thing they just said they did stops trusting the assistant. A reply naming
    # something no runbook asks for would be answered by a runbook that skips
    # nothing, and the beat would show a memory that changed no behaviour.
    covered = " ".join(doc.path.read_text(encoding="utf-8").lower() for doc in runbooks)

    for reply in _rehearsed_replies(store_pack):
        anchors = [
            word
            for word in re.findall(r"[a-z]+", reply.lower())
            if len(word) > 4 and word in covered
        ]
        assert len(anchors) >= 2, (reply, anchors)


def test_given_the_rehearsed_replies_when_read_then_none_of_them_trips_the_gate(
    store_pack, gate_keywords
):
    # The same one-way requirement as the Quick Tasks themselves. A reply the
    # Identity boundary gate refuses is a tap that ends the troubleshooting beat
    # with copy about the assistant being store-scoped, mid-repair.
    #
    # This assertion is now about the **authored strings and nothing else**.
    # Until #115 it was standing in for a runtime check that did not exist:
    # `identity_boundary_gate` was called once, inside `process_request`, so an
    # answer posted to `/v4/user_clarification` — tapped or typed — reached the
    # orchestration ungated, and these three strings were the only thing anyone
    # was checking. ADR-034 put the gate on that seam, and
    # `TestTheIdentityBoundaryGateOnTheClarificationSeam` in
    # `src/tests/backend/api/test_router.py` is where a refusal is asserted
    # against the real router. What is left here is ADR-033's rule: a one-tap
    # control's words are checked **before** the demo rather than judged on
    # stage, so a chip that would be refused is caught in CI instead of in
    # front of the room.
    for reply in _rehearsed_replies(store_pack):
        assert not gate_keywords.matches_personal_keyword(reply), reply


REHEARSED_REPLY_TS = REPO_ROOT / "src" / "App" / "src" / "models" / "rehearsedReply.ts"
TEAM_TS = REPO_ROOT / "src" / "App" / "src" / "models" / "Team.tsx"


def test_given_the_rehearsed_replies_when_read_then_the_browser_reads_that_field(
    store_pack,
):
    # The seam #24 found, at a third place. `rehearsedReply.test.ts` hand-writes
    # its own tasks, so renaming the field in the pack and the backend model
    # leaves the vitest suite green and the chips silently absent — a presenter
    # back to typing the one answer these six taps exist to remove, with nothing
    # red anywhere. This is a CI-tooling test because it is the only thing that
    # reads both files.
    field = "rehearsed_replies"
    task = next(
        task
        for task in store_pack.starting_tasks
        if task["id"] == "task-223-troubleshooting"
    )

    assert field in task
    assert field in REHEARSED_REPLY_TS.read_text(encoding="utf-8")
    assert field in TEAM_TS.read_text(encoding="utf-8")


def test_given_the_troubleshooter_when_read_then_it_defers_before_it_interrogates(
    store_pack,
):
    # The residual #54 failure, and it is an ordering bug in prose. With
    # `require_all_agents` off the manager usually routes "How do I close the
    # store?" to the shift-tasks specialist alone, but not always — run 7 of a
    # ten-run rehearsal put the troubleshooter in the plan too, and it asked
    # which piece of equipment was blocking closing. Nothing was broken.
    #
    # The instruction to hand procedures over was already there; it was the
    # last line, after "ask what they have already tried", so the model reached
    # the interrogation first. Order is the whole fix, so order is what is
    # pinned: a later edit that appends the deferral back at the bottom is the
    # exact regression, and it would leave every other assertion here green.
    message = next(
        agent["system_message"]
        for agent in store_pack.team["agents"]
        if agent["name"] == "TroubleshootingAgent"
    )
    defers_at = message.find("nothing is broken and this is not your question")
    interrogates_at = message.find("ask the associate what they have already tried")

    assert defers_at > 0, "the troubleshooter no longer hands procedures over"
    assert interrogates_at > 0, "the 'what have you tried' rule went missing"
    assert defers_at < interrogates_at, (
        "the troubleshooter asks what was tried before it decides whether "
        "anything is broken — that is how the rehearsed beat came back as "
        "'which equipment is blocking closing?' (#54)"
    )
