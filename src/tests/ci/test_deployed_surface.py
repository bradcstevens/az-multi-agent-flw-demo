"""Tests for the deployed-surface check (issue #44).

`deployed-environment` proves the infrastructure: the right regions, the right
models, three application hosts running an image from our own registry. It is
green against a deployment whose Container Apps are running last month's code,
because an image's *provenance* is not its *currency* — which is exactly the
state `macae-flw-v1` was found in, serving the accelerator's own page title
while every declared loop passed.

This check asks the other question: whatever is running, is the surface it
serves **this** demonstration? The seam under test is the pure evaluation —
given what the deployed frontend, backend and Container App actually answered,
`evaluate` decides whether the shipped surface is the authored one. The live
HTTP and `az` reads sit outside it.
"""

import json
from pathlib import Path

from preflight.deployed_surface import (
    Expected,
    authored_expectation,
    direct_sop_answer_check,
    direct_sop_repeats_check,
    evaluate,
    main,
    rehearsed_question,
)

EXPECTED = Expected(
    assistant="Circle K Frontline Store Assistant",
    team_id="00000000-0000-0000-0000-000000000223",
    quick_tasks=(
        ("task-223-procedure", "fast"),
        ("task-223-honest-miss", "fast"),
        ("task-223-troubleshooting", "fast"),
        ("task-223-escalation", "deliberate"),
        ("task-223-identity", "fast"),
        ("task-223-shift-tasks", "fast"),
        ("task-223-shift-swap", "fast"),
    ),
    documents=(
        "SOP-101 Store Opening Procedure.docx",
        "SOP-102 Store Closing Procedure.docx",
        "SOP-103 Restroom Cleaning and Inspection.docx",
        "SOP-104 Coffee Bar Setup and Shutdown.docx",
        "SOP-105 Forecourt Emergency Stop and Fuel Spill Response.docx",
        "SOP-106 Cash Handling and Safe Drops.docx",
        "SOP-107 Hot Food Case Temperature Control.docx",
        "SOP-108 Age-Restricted Sales Verification.docx",
        "SOP-109 Delivery Receiving and Backroom Stocking.docx",
        "SOP-110 Shift Handover and Task Board.docx",
    ),
    require_all_agents=False,
)

ACCELERATOR_TITLE = "Multi-Agent - Custom Automation Engine"


def observed(**overrides):
    """What a healthy deployment answered, as the live reads return it."""
    base = {
        "title": EXPECTED.assistant,
        "team": {
            "team_id": EXPECTED.team_id,
            "name": EXPECTED.assistant,
            "starting_tasks": [
                {"id": identifier, "lane": lane}
                for identifier, lane in EXPECTED.quick_tasks
            ],
            "require_all_agents": EXPECTED.require_all_agents,
        },
        "tokenEndpoint": (
            "https://powervamg.us-il102.gateway.prod.island.powerapps.com"
            "/api/botmanagement/v1/directline/directlinetoken?botId=b&tenantId=t"
        ),
    }
    base.update(overrides)
    return base


class TestStoreSurface:
    """The page the frontend serves is the store surface, not the accelerator's."""

    def test_the_authored_assistant_name_passes(self):
        verdict = evaluate(observed(), EXPECTED)

        assert verdict.check("store-surface").ok

    def test_the_accelerators_own_title_fails(self):
        # The whole finding in one string: the deployment served
        # `Multi-Agent - Custom Automation Engine` while `src/App/index.html`
        # read `Circle K Frontline Store Assistant` and nothing sets the title
        # at run time, so the served title *is* the deployed build's identity.
        verdict = evaluate(observed(title=ACCELERATOR_TITLE), EXPECTED)

        check = verdict.check("store-surface")
        assert not check.ok
        assert ACCELERATOR_TITLE in check.detail

    def test_a_surface_that_did_not_answer_fails(self):
        # A cold Container App and a wrong build are indistinguishable from a
        # missing title, and both are reasons not to walk on stage.
        verdict = evaluate(observed(title=None), EXPECTED)

        assert not verdict.check("store-surface").ok


class TestQuickTasks:
    """The six taps the presenter drives the walkthrough with are on the surface."""

    def test_every_authored_task_and_its_lane_passes(self):
        verdict = evaluate(observed(), EXPECTED)

        assert verdict.check("quick-tasks").ok

    def test_a_team_the_backend_does_not_hold_fails(self):
        # The store pack lives in Cosmos, not in the image, so a current build
        # and an unseeded deployment look identical from the registry. The
        # surface reports the assistant is not loaded and every beat has to be
        # typed.
        verdict = evaluate(observed(team=None), EXPECTED)

        check = verdict.check("quick-tasks")
        assert not check.ok
        assert EXPECTED.team_id in check.detail

    def test_a_missing_task_fails_and_names_it(self):
        team = observed()["team"]
        team["starting_tasks"] = [
            task for task in team["starting_tasks"]
            if task["id"] != "task-223-escalation"
        ]
        verdict = evaluate(observed(team=team), EXPECTED)

        check = verdict.check("quick-tasks")
        assert not check.ok
        assert "task-223-escalation" in check.detail

    def test_a_team_that_is_not_the_authored_one_fails(self):
        # The team the backend answers with is not necessarily the team that
        # was asked for: an earlier pack under a renumbered identifier can be
        # left in Cosmos, carrying tasks that satisfy every name below while
        # the surface — which recognises the authored identifier — shows none
        # of them.
        team = observed()["team"]
        team["team_id"] = "00000000-0000-0000-0000-000000000007"
        verdict = evaluate(observed(team=team), EXPECTED)

        check = verdict.check("quick-tasks")
        assert not check.ok
        assert EXPECTED.team_id in check.detail

    def test_a_task_that_lost_its_declared_lane_fails(self):
        # A Quick Task that declares no lane falls to the keyword router, and
        # the escalation beat quietly runs without its approval gate — which
        # looks like a working demonstration right up to the ticket.
        team = observed()["team"]
        for task in team["starting_tasks"]:
            if task["id"] == "task-223-escalation":
                task["lane"] = "fast"
        verdict = evaluate(observed(team=team), EXPECTED)

        check = verdict.check("quick-tasks")
        assert not check.ok
        assert "deliberate" in check.detail


class TestMandatoryAgents:
    """The flag that decides whether one agent may answer the opening question.

    A default team cannot be deleted, so every re-deploy leaves another
    document with the same team_id behind. Six were live when this was
    written and five of them predated the flag. Which one the backend reads
    is not visible from the repository, so it is asked (#54).
    """

    def test_the_authored_value_passes(self):
        verdict = evaluate(observed(), EXPECTED)

        assert verdict.check("mandatory-agents").ok

    def test_a_team_predating_the_flag_fails(self):
        # This is the live failure: a document written before the field
        # existed. The backend defaults it to on, and the opening question
        # goes back through three specialists.
        team = dict(observed()["team"])
        del team["require_all_agents"]

        check = evaluate(observed(team=team), EXPECTED).check("mandatory-agents")

        assert not check.ok
        assert "require_all_agents" in check.detail

    def test_a_reverted_flag_fails(self):
        team = dict(observed()["team"], require_all_agents=True)

        check = evaluate(observed(team=team), EXPECTED).check("mandatory-agents")

        assert not check.ok
        assert "older than the pack" in check.detail

    def test_the_expectation_is_read_out_of_the_pack(self):
        # Never pinned here: the pack is where the flag is authored, and a
        # check carrying its own copy passes a revert it never saw.
        assert authored_expectation().require_all_agents is False


class TestDirectLineEndpoint:
    """The backend can reach the Copilot Studio SOP agent at all."""

    def test_the_endpoint_pva_returned_passes(self):
        verdict = evaluate(observed(), EXPECTED)

        assert verdict.check("direct-line-endpoint").ok

    def test_an_unset_endpoint_fails(self):
        # The bicep plumbs the setting through unconditionally, so this was
        # never an infrastructure gap — the value was simply never set, and
        # unset the SOP tool answers with its fixed failure message.
        verdict = evaluate(observed(tokenEndpoint=None), EXPECTED)

        check = verdict.check("direct-line-endpoint")
        assert not check.ok
        assert "COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT" in check.detail

    def test_an_endpoint_assembled_from_the_direct_line_hostname_fails(self):
        # ADR-011: the token endpoint comes from the environment's own regional
        # channel settings service and is never assembled from the default
        # Direct Line hostname. A hand-built one is a plausible-looking URL that
        # issues no token, which reads on stage as the agent being down.
        verdict = evaluate(
            observed(
                tokenEndpoint="https://directline.botframework.com/v3/directline/tokens/generate"
            ),
            EXPECTED,
        )

        assert not verdict.check("direct-line-endpoint").ok


def answer(**overrides):
    """What `/api/v4/sop/ask` replied, as the probe reads it."""
    reply = {
        "question": "How do I close the store?",
        "failed": False,
        "platform": "Copilot Studio",
        "source": "Dataverse",
        "citations": ["SOP-102 Store Closing Procedure.docx"],
        "text": "1. At 60 minutes before close, begin the coffee bar shutdown...",
    }
    reply.update(overrides)
    return reply


class TestGroundedAnswer:
    """One real procedure question, all the way to Copilot Studio and back.

    Named `direct-sop-answer` rather than `grounded-answer` because it asks the
    **easier** question (#54): the corpus's own wording, straight at
    `/api/v4/sop/ask`, with no orchestrator in front of it. The presenter's tap
    goes through one that rephrases. This check was green on every attempt over
    the afternoon the browser saw the beat fail twice in eight, and a name that
    reads as *the grounded answer works* is what let both be true at once.
    """

    def test_a_cited_answer_from_dataverse_passes(self):
        check = direct_sop_answer_check(answer(), EXPECTED)

        assert check.ok
        assert "SOP-102 Store Closing Procedure.docx" in check.detail

    def test_a_pass_says_out_loud_that_it_asked_the_easier_question(self):
        # The acceptance criterion, as a test. This check must stop being able
        # to pass while the browser fails *silently* — so a green one names the
        # gap between what it asked and what the presenter asks, and names the
        # loop that closes it.
        check = direct_sop_answer_check(answer(), EXPECTED)

        assert check.ok
        assert "directly" in check.detail
        assert "orchestrator" in check.detail
        assert "sop-rehearsal.sh" in check.detail

    def test_an_unasked_question_is_unproven_rather_than_passed(self):
        # The centrepiece claim is that the answer came from Dataverse through
        # Copilot Studio. A run that asked nothing has no evidence of that, and
        # reporting it as a pass is how the deployment shipped unreachable in
        # the first place.
        check = direct_sop_answer_check(None, EXPECTED)

        assert not check.ok
        assert "not" in check.detail

    def test_the_fixed_failure_message_fails(self):
        check = direct_sop_answer_check(answer(failed=True, citations=[]), EXPECTED)

        assert not check.ok

    def test_an_uncited_answer_fails(self):
        # There is no fallback to model knowledge by design, but an answer with
        # no citations is exactly what a fallback would look like, and the
        # Grounding panel would have nothing to render.
        check = direct_sop_answer_check(answer(citations=[]), EXPECTED)

        assert not check.ok

    def test_a_citation_this_repository_did_not_author_fails(self):
        # The token endpoint check accepts any endpoint that is not the
        # assembled Direct Line hostname, so a second Dataverse-grounded agent
        # in the same tenant would answer, cite something, and pass. The
        # citation naming a document out of `content/sop/` is what ties the
        # answer back to the corpus this repository uploaded.
        check = direct_sop_answer_check(
            answer(citations=["HR-201 Benefits Enrolment.docx"]), EXPECTED)

        assert not check.ok
        assert "HR-201 Benefits Enrolment.docx" in check.detail

    def test_an_answer_from_somewhere_else_fails(self):
        # Platform and source are the two facts the Grounding panel is a claim
        # about. An answer the orchestrator produced itself is a working demo
        # of the wrong thing.
        check = direct_sop_answer_check(answer(platform="Azure AI Foundry"), EXPECTED)

        assert not check.ok
        assert "Copilot Studio" in check.detail


class TestEveryAsking:
    """The gate asks more than once, because one asking is a coin flip.

    `direct-sop-answer` grades one reply and was the whole of this gate's
    evidence until #54 measured the fault it is named after at about 6% per
    conversation (`bf7792a7`). One asking of that comes back clean nineteen
    times in twenty, and `deploy-main.yml` goes green on this check — so a
    deploy could be gated on a coin landing heads.
    """

    def test_every_asking_answering_from_the_corpus_passes(self):
        check = direct_sop_repeats_check([answer(), answer(), answer()], EXPECTED)

        assert check.ok
        assert "3 of 3" in check.detail

    def test_a_green_row_names_the_fault_size_it_would_still_have_missed(self):
        # The reason to state it in the row rather than in a doc: the operator
        # reads the row. `--samples 5` catches a 6%-per-conversation fault about
        # a quarter of the time, so "5 of 5" on its own reads as far stronger
        # evidence than it is. The rate quoted is the smallest fault this many
        # askings is likelier than not to catch — 50% at one asking, 12.9% at
        # five, 5.6% at twelve.
        assert "50.0%" in direct_sop_repeats_check([answer()], EXPECTED).detail
        assert "12.9%" in direct_sop_repeats_check(
            [answer()] * 5, EXPECTED).detail
        assert "5.6%" in direct_sop_repeats_check(
            [answer()] * 12, EXPECTED).detail

    def test_one_missed_asking_is_reported_as_intermittent(self):
        check = direct_sop_repeats_check(
            [answer(), answer(citations=[]), answer()], EXPECTED)

        assert not check.ok
        assert "2 of 3" in check.detail
        assert "intermittent" in check.detail

    def test_nothing_answering_is_broken_rather_than_intermittent(self):
        # They want different next moves. Intermittent is a rate to measure;
        # broken is a state to fix, and an operator reading "intermittent" of a
        # beat that never worked goes looking for a rate that is not there.
        check = direct_sop_repeats_check(
            [answer(citations=[]), answer(citations=[])], EXPECTED)

        assert not check.ok
        assert "broken rather than intermittent" in check.detail

    def test_a_repeat_that_failed_differently_is_reported_too(self):
        # The first fault is usually the one `direct-sop-answer` already
        # printed. A repeats row that echoed it would hide the asking that
        # failed for another reason — and the reason is which layer to go to.
        check = direct_sop_repeats_check(
            [answer(), answer(citations=[]), answer(platform="Azure AI Foundry")],
            EXPECTED,
        )

        assert not check.ok
        assert "no citations" in check.detail
        assert "Azure AI Foundry" in check.detail

    def test_a_repeat_is_graded_by_the_same_rule_as_the_first_asking(self):
        # One grading rule, two checks. A repeat held to a laxer bar than the
        # first asking is a green row that means less than the row above it.
        for reply in (
            answer(failed=True, citations=[]),
            answer(citations=[]),
            answer(citations=["HR-201 Benefits Enrolment.docx"]),
            answer(platform="Azure AI Foundry"),
        ):
            assert not direct_sop_answer_check(reply, EXPECTED).ok
            assert not direct_sop_repeats_check([reply], EXPECTED).ok

    def test_an_asking_the_backend_never_answered_is_not_the_honest_miss(self):
        # Both carry no citations and only one of them means the corpus is
        # wrong — the distinction `/sop/ask`'s own reply log was given for the
        # same reason (#54).
        check = direct_sop_repeats_check([answer(), None], EXPECTED)

        assert not check.ok
        assert "did not answer" in check.detail
        assert "not the honest miss" in check.detail

    def test_an_unasked_question_is_unproven_rather_than_passed(self):
        check = direct_sop_repeats_check(None, EXPECTED)

        assert not check.ok
        assert "--no-probe" in check.detail


class TestTheRecordAndTheCheck:
    """`docs/preflight/deployed-surface.md` is the record this check backs.

    AGENTS.md's contract is one record per verified precondition, each backed by
    a re-runnable check. A row the check prints and the record does not explain
    is drift in the direction that costs the most: an operator reading a FAIL
    with nowhere to go.
    """

    def test_the_record_explains_every_row_the_check_prints(self, capsys):
        main(
            argv=["--samples", "2"],
            read=lambda *_: observed(),
            ask=lambda backend, question: answer(question=question),
        )
        printed = [
            line.split(":", 1)[0].split()[-1]
            for line in capsys.readouterr().out.splitlines()
            if line.startswith(("  PASS", "  FAIL"))
        ]
        record = (
            Path(__file__).resolve().parents[3]
            / "docs" / "preflight" / "deployed-surface.md"
        ).read_text(encoding="utf-8")

        assert printed, "the report printed no check rows to compare"
        for name in printed:
            assert f"`{name}`" in record, (
                f"the check prints a {name!r} row that its own record does not "
                "explain"
            )


class TestTheReport:
    """What the operator is told, and what the exit code says."""

    def test_a_healthy_deployment_passes_every_check(self, capsys):
        exit_code = main(
            argv=[],
            read=lambda *_: observed(),
            ask=lambda backend, question: answer(question=question),
        )
        out = capsys.readouterr().out

        assert exit_code == 0
        for name in (
            "store-surface",
            "quick-tasks",
            "mandatory-agents",
            "direct-line-endpoint",
            "direct-sop-answer",
        ):
            assert f"PASS  {name}" in out

    def test_a_green_run_does_not_claim_the_walkthrough_works(self, capsys):
        # Every check here asks the deployment a question the presenter never
        # asks, and the closest one asks it past the orchestrator that
        # rephrases it. A row of PASSes that ended with "shippable" is how the
        # centrepiece beat came to be believed while it failed one run in four.
        main(
            argv=[],
            read=lambda *_: observed(),
            ask=lambda backend, question: answer(question=question),
        )
        out = capsys.readouterr().out

        assert "sop-rehearsal.sh" in out
        assert "#54" in out

    def test_the_probe_asks_the_corpus_its_own_rehearsed_question(self, capsys):
        # Never a copy pinned in this module. `[rehearsed_hit]` names the
        # question the walkthrough opens with, and a probe carrying its own
        # copy asks one the corpus no longer guarantees an answer to.
        asked = []
        main(
            argv=[],
            read=lambda *_: observed(),
            ask=lambda backend, question: (
                asked.append(question) or answer(question=question)),
        )

        assert asked == [rehearsed_question()]

    def test_samples_asks_the_question_that_many_times(self, capsys):
        # One sample of a fault that fires 6% of the time comes back clean
        # nineteen times in twenty, and this check is the gate `deploy-main.yml`
        # goes green on (#54, `bf7792a7`). Each asking is its own request, so
        # each is its own Direct Line conversation.
        asked = []
        main(
            argv=["--samples", "3"],
            read=lambda *_: observed(),
            ask=lambda backend, question: (
                asked.append(question) or answer(question=question)),
        )

        assert asked == [rehearsed_question()] * 3

    def test_one_missed_asking_in_three_fails_the_gate(self, capsys):
        # The whole of AC5. Before this, the gate asked once: a beat that misses
        # one asking in three passed it two runs in three, which is how this
        # check stayed green across the afternoon the browser saw the beat fail
        # twice in eight.
        replies = iter([answer(), answer(citations=[]), answer()])
        exit_code = main(
            argv=["--samples", "3"],
            read=lambda *_: observed(),
            ask=lambda backend, question: next(replies),
        )
        out = capsys.readouterr().out

        assert exit_code == 1
        assert "FAIL  direct-sop-answers-every-time" in out
        assert "2 of 3" in out

    def test_a_single_sample_green_says_it_is_not_evidence_the_beat_always_works(
        self, capsys
    ):
        # AC5's rule applied to the sample count. The default is one asking,
        # and one asking of a 6% fault is clean nineteen times in twenty — so
        # the row that reports it names what it did not prove and how to prove
        # more of it, rather than reading as "the grounded answer works".
        main(
            argv=[],
            read=lambda *_: observed(),
            ask=lambda backend, question: answer(question=question),
        )
        out = capsys.readouterr().out

        assert "PASS  direct-sop-answers-every-time" in out
        assert "1 of 1" in out
        assert "--samples" in out

    def test_no_probe_reports_the_grounded_answer_as_unproven_and_exits_nonzero(
        self, capsys
    ):
        # The same rule the roster probe follows: a run that asked nothing must
        # not report the cross-platform hop as working.
        exit_code = main(argv=["--no-probe"], read=lambda *_: observed())
        out = capsys.readouterr().out

        assert exit_code == 1
        assert "FAIL  direct-sop-answer" in out

    def test_a_pre_rebrand_deployment_exits_nonzero(self, capsys):
        exit_code = main(
            argv=[],
            read=lambda *_: observed(title=ACCELERATOR_TITLE),
            ask=lambda backend, question: answer(question=question),
        )

        assert exit_code == 1
        assert "FAIL  store-surface" in capsys.readouterr().out


class TestWhatCountsAsAuthored:
    """The expectation is read out of the repository, never pinned in the check."""

    def test_the_repository_is_the_source_of_the_expectation(self):
        # The ADR-019 lesson: a check carrying its own copy of the surface's
        # strings passes a rebrand it never saw. These literals are this test's
        # independent record of what the walkthrough currently claims — when
        # the surface is renamed, this is what has to be changed alongside it.
        authored = authored_expectation()

        assert authored.assistant == EXPECTED.assistant
        assert authored.team_id == EXPECTED.team_id
        assert authored.quick_tasks == EXPECTED.quick_tasks
        assert authored.documents == EXPECTED.documents

    def test_a_renamed_assistant_is_followed_rather_than_ignored(self, tmp_path):
        surface = tmp_path / "storeSurface.ts"
        surface.write_text("export const ASSISTANT_NAME = 'Renamed Assistant';\n")
        pack = tmp_path / "pack.json"
        pack.write_text(json.dumps({
            "team_id": "00000000-0000-0000-0000-000000000999",
            "starting_tasks": [{"id": "task-999-only", "lane": "deliberate"}],
        }))

        authored = authored_expectation(surface=str(surface), pack=str(pack))

        assert authored.assistant == "Renamed Assistant"
        assert authored.quick_tasks == (("task-999-only", "deliberate"),)


class TestTheRehearsedQuestion:
    """Which question the probe asks, read out of the corpus that answers it."""

    def test_the_repositorys_own_manifest_names_the_opening_question(self):
        assert rehearsed_question() == "How do I close the store?"

    def test_the_honest_misss_question_is_never_the_one_asked(self, tmp_path):
        # The sharpest way to get this wrong, and the reason the read is
        # section-scoped rather than a search of the whole file: `question` is
        # a key under **both** sections, and a last-key-wins parse probes the
        # deployment with the question the corpus deliberately cannot answer —
        # reporting a working SOP agent as a broken one.
        manifest = tmp_path / "corpus.toml"
        manifest.write_text(
            '[rehearsed_hit]\n'
            'question = "How do I close the store?"\n'
            'doc_id = "SOP-102"\n'
            '\n'
            '[honest_miss]\n'
            'question = "How do I restart the car wash?"\n',
            encoding="utf-8",
        )

        assert rehearsed_question(str(manifest)) == "How do I close the store?"

    def test_a_manifest_without_the_section_is_an_error_rather_than_a_guess(
        self, tmp_path
    ):
        manifest = tmp_path / "corpus.toml"
        manifest.write_text('[honest_miss]\nquestion = "anything"\n',
                            encoding="utf-8")

        try:
            rehearsed_question(str(manifest))
        except RuntimeError as error:
            assert "rehearsed_hit" in str(error)
        else:
            raise AssertionError("a corpus with no rehearsed hit was accepted")
