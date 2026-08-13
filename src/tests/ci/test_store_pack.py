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
import subprocess
import sys
from pathlib import Path

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
    # Spans the seam between the authored prompt and the container that serves
    # the tools. A rename on either side is an agent calling a tool that is not
    # there, and the framework's answer to that is silence.
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
    ):
        assert text.count(f"'{path}'") >= 2, (
            f"a change to {path} does not run the CI-tooling tests on both "
            "push and pull_request"
        )

    assert "'src/App/**'" not in text, (
        "test.yml triggers on the whole frontend — a CSS edit now runs the "
        "backend suite"
    )
