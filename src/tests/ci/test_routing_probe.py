"""The Routing probe: the residual measured without a browser (#54).

The centrepiece beat's remaining failure is the `Troubleshooting Agent` billed
on a question with nothing broken in it. Seven prompt clauses have been forked
on ``minimal_plan`` chasing it, each costing a twenty-minute deploy, and each
*reduced* the rate without removing it — because the only loop that can see the
fault is the Demo validator: a browser, a deployed build, ten runs, stop at the
first red.

`scripts/routing_probe.py` is the cheaper one. It drives the same Fast-lane turn
over plain HTTP and reads the same transparency frames the browser renders, N
samples at a time, and grades them into the ledger's own four outcomes. The
samples need a deployment; **the arithmetic over what they observed does not**,
and that is the seam under test here.

What is asserted is what the probe is allowed to *claim*:

- a turn is graded from the frames the deployment actually pushed, never from
  the absence of a frame the probe may simply have missed;
- an agent the request did not need is named, because that is the residual;
- sampling is not proof, and the report says by how much.
"""

import json
import os
import pathlib

from routing_probe import (BETWEEN_SAMPLES_SECONDS, CLARIFIED, GROUNDED, HONEST_MISS, NO_TOOL_CALL,
                           NOT_OBSERVED, FrameReader, Turn, collect,
                           format_report,
                           observe, outcome, procedure_agent, routing_fault,
                           smallest_fault_caught, summarise, turn_is_over,
                           unneeded_agents)


def frame(kind, **data):
    """One WebSocket envelope, shaped as `send_status_update_async` sends it."""
    return {"type": kind, "data": dict(data)}


def token_usage(agent, total=1000):
    return frame(
        "token_usage",
        agent_name=agent,
        executor_id=agent.lower().replace(" ", "_"),
        input_tokens=total // 2,
        output_tokens=total // 2,
        total_tokens=total,
    )


def source_used(citations=("SOP-102 Store Closing Procedure.docx",),
                tool_query="Please look up the store closing procedure",
                retrieval_query="How do I close the store?"):
    return frame(
        "source_used",
        platform="Copilot Studio",
        source="Dataverse",
        agent_name="Store SOP Assistant",
        tool_query=tool_query,
        retrieval_query=retrieval_query,
        citations=[
            {"position": index + 1, "name": name, "snippet": "", "url": None}
            for index, name in enumerate(citations)
        ],
    )


def final_result(content):
    return frame("final_result_message", content=content)


CLOSING_ANSWER = (
    "**Store closing procedure (SOP-102)**\n"
    "1. Cash up the tills and reconcile the drawer.\n"
    "2. Complete the hot-food case cleardown."
)

INTERROGATION = (
    "- Which equipment is blocking closing right now: coffee brewer, hot "
    "food case, fuel dispensers, walk-in cooler, self-checkout, handhelds, "
    "or something else?\n"
    "- What have you already tried?"
)


class TestObserve:
    """One sample's frames folded into what that turn did."""

    def test_names_every_agent_the_meter_billed(self):
        turn = observe([
            token_usage("Shift Tasks Agent", 3888),
            source_used(),
            token_usage("Troubleshooting Agent", 6906),
            final_result(CLOSING_ANSWER),
        ])

        assert turn.agents_billed == (
            "Shift Tasks Agent", "Troubleshooting Agent")

    def test_reports_the_grounding_the_panel_would_have_shown(self):
        turn = observe([source_used(), final_result(CLOSING_ANSWER)])

        assert turn.grounded is True
        assert turn.honest_miss is False
        assert turn.citations == ("SOP-102 Store Closing Procedure.docx",)
        assert turn.retrieval_query == "How do I close the store?"


class TestOutcome:
    """The ledger's four outcomes, from the two signals that distinguish them."""

    def test_a_grounded_cited_answer_is_grounded(self):
        assert outcome(observe([
            source_used(), final_result(CLOSING_ANSWER)])) == GROUNDED

    def test_no_grounding_panel_is_no_tool_call(self):
        assert outcome(observe([final_result(CLOSING_ANSWER)])) == NO_TOOL_CALL

    def test_a_hop_that_cited_nothing_is_the_honest_miss(self):
        assert outcome(observe([
            source_used(citations=()), final_result("I could not find it.")
        ])) == HONEST_MISS

    def test_a_question_asked_back_is_clarified_even_though_it_is_cited(self):
        """The outcome that hides inside a success.

        Every other signal on this turn says the beat worked: the hop
        completed, `SOP-102` is cited, the panel is full. The presenter is
        still standing in front of a question. Reported as `grounded` it says
        the beat works and the harness is broken, which is what it looked like
        for a day (#54).
        """
        assert outcome(observe([
            token_usage("Shift Tasks Agent"),
            source_used(),
            token_usage("Troubleshooting Agent"),
            final_result(INTERROGATION),
        ])) == CLARIFIED


class TestTurn:
    """A `Turn` is what one sample saw, and it may have seen nothing."""

    def test_a_sample_with_no_frames_is_not_a_turn_that_answered(self):
        """Broken is not intermittent.

        A sample whose socket carried nothing observed no turn at all — the
        replica restarted under it, the connect lost the race. Grading that as
        `no-tool-call` would report the orchestrator's routing for a run in
        which the orchestrator was never heard from, which is the guess this
        issue exists to forbid.
        """
        turn = observe([])

        assert turn.observed is False
        assert Turn(frames=0).observed is False


def grounded_turn(agents=("Shift Tasks Agent",)):
    return observe(
        [token_usage(name) for name in agents]
        + [source_used(), final_result(CLOSING_ANSWER)]
    )


class TestProcedureAgent:
    """Which agent the rehearsed question needs, read out of the pack."""

    def test_is_the_agent_the_pack_gave_the_sop_toolbox_to(self, tmp_path):
        """Derived, never pinned.

        The rehearsed question is a procedure lookup, and the agent that can
        answer one is the agent holding ``search_store_procedures`` — which the
        pack says, in `toolbox_filter`. A probe carrying its own copy of the
        name grades a roster the repository has since renamed.
        """
        pack = tmp_path / "team.json"
        pack.write_text(json.dumps({"agents": [
            {"name": "TroubleshootingAgent", "toolbox_filter": "troubleshooting"},
            {"name": "ShiftTasksAgent", "toolbox_filter": "sop"},
        ]}))

        assert procedure_agent(str(pack)) == "ShiftTasksAgent"

    def test_the_deployed_pack_still_names_one(self):
        assert procedure_agent() == "ShiftTasksAgent"


class TestUnneededAgents:
    """The residual, named: an agent billed that the request did not need."""

    def test_is_empty_when_only_the_procedure_agent_was_billed(self):
        assert unneeded_agents(grounded_turn(), "ShiftTasksAgent") == ()

    def test_matches_the_display_name_the_meter_actually_sends(self):
        """`ShiftTasksAgent` on the roster is `Shift Tasks Agent` on the meter.

        Compared with the separators removed rather than by re-implementing
        `format_agent_display_name` here — the probe runs with nothing but
        `python3` and must not import the backend, and a second copy of that
        formatter is a second thing to drift.
        """
        assert unneeded_agents(
            grounded_turn(("Shift_Tasks_Agent",)), "ShiftTasksAgent") == ()

    def test_names_the_troubleshooter_billed_on_a_question_with_no_fault(self):
        turn = grounded_turn(("Shift Tasks Agent", "Troubleshooting Agent"))

        assert unneeded_agents(turn, "ShiftTasksAgent") == (
            "Troubleshooting Agent",)

    def test_does_not_count_the_manager_that_routes_every_turn(self):
        """MagenticManager is on every turn by construction.

        It plans and compiles; it is not a specialist answering a request that
        did not ask for it. Counted, every sample would name an unneeded agent
        and the rate this probe exists to measure would read 100%.
        """
        turn = grounded_turn(("Magentic Manager", "Shift Tasks Agent"))

        assert unneeded_agents(turn, "ShiftTasksAgent") == ()


class TestRoutingFault:
    """Why one sample is not the beat. `None` when it is."""

    def test_a_grounded_turn_billed_only_to_the_procedure_agent_is_clean(self):
        assert routing_fault(grounded_turn(), "ShiftTasksAgent") is None

    def test_a_sample_that_observed_nothing_is_not_a_routing_fault(self):
        """Broken is not intermittent, and neither is a lost socket.

        Reported as a routing fault it inflates the rate with runs the
        orchestrator was never heard on, and the next iteration reads a number
        that is partly about this probe.
        """
        fault = routing_fault(observe([]), "ShiftTasksAgent")

        assert fault is not None
        assert "did not observe" in fault
        assert "routing" not in fault

    def test_names_every_fault_a_sample_had_not_only_the_first(self):
        """The two halves send a reader to different layers.

        A turn that both asked a question back *and* billed the troubleshooter
        is one fault's cause and effect; a turn that asked back while only the
        procedure agent was billed is neither, and is a different bug. A report
        naming one of them sends the next iteration at one of them.
        """
        turn = observe([
            token_usage("Shift Tasks Agent"),
            source_used(),
            token_usage("Troubleshooting Agent"),
            final_result(INTERROGATION),
        ])

        fault = routing_fault(turn, "ShiftTasksAgent")

        assert "Troubleshooting Agent" in fault
        assert "question back" in fault

    def test_reports_the_honest_miss_as_the_retrieval_it_is(self):
        """Not everything red here is the routing.

        The honest miss on the rehearsed question implicates the corpus or the
        agent's index — the layer `bf7792a7` measured — and calling it routing
        would send the next iteration at a prompt for a retrieval failure.
        """
        turn = observe([source_used(citations=()), final_result("No match.")])

        fault = routing_fault(turn, "ShiftTasksAgent")

        assert "honest miss" in fault
        assert "index" in fault
        assert "not the routing" in fault


class TestSummarise:
    """The rate, over N samples."""

    def test_counts_each_outcome_and_the_agents_billed_across_samples(self):
        summary = summarise([
            grounded_turn(),
            grounded_turn(),
            observe([
                token_usage("Shift Tasks Agent"),
                source_used(),
                token_usage("Troubleshooting Agent"),
                final_result(INTERROGATION),
            ]),
        ], "ShiftTasksAgent")

        assert summary.samples == 3
        assert summary.outcomes[GROUNDED] == 2
        assert summary.outcomes[CLARIFIED] == 1
        assert summary.unneeded == {"Troubleshooting Agent": 1}
        assert summary.clean == 2

    def test_samples_that_observed_nothing_are_not_in_the_rate(self):
        """The denominator is turns observed, not requests sent.

        A replica restart under the probe is not evidence about the routing,
        and dividing by it reports a rate that is partly about this probe's own
        luck.
        """
        summary = summarise(
            [grounded_turn(), observe([])], "ShiftTasksAgent")

        assert summary.samples == 2
        assert summary.observed == 1
        assert summary.clean == 1
        assert summary.outcomes[NOT_OBSERVED] == 1


class TestFormatReport:
    """What the operator reads, which is the only thing they read."""

    def test_a_clean_run_says_what_it_is_not_evidence_of(self):
        report = format_report(
            summarise([grounded_turn()] * 12, "ShiftTasksAgent"))

        assert "12 of 12" in report
        assert f"{smallest_fault_caught(12):.1f}%" in report

    def test_a_run_with_the_residual_names_the_agent_and_the_rate(self):
        turns = [grounded_turn()] * 8 + [observe([
            token_usage("Shift Tasks Agent"),
            source_used(),
            token_usage("Troubleshooting Agent"),
            final_result(INTERROGATION),
        ])] * 2

        report = format_report(summarise(turns, "ShiftTasksAgent"))

        assert "Troubleshooting Agent" in report
        assert "2 of 10" in report
        assert CLARIFIED in report

    def test_a_run_that_observed_nothing_reads_as_broken_not_as_a_rate(self):
        report = format_report(summarise([observe([])] * 4, "ShiftTasksAgent"))

        assert "no sample observed a turn" in report
        assert "%" not in report.split("no sample observed a turn")[1]


class TestSmallestFaultCaught:
    """Sampling is not proof, and this is the number that says by how much."""

    def test_one_sample_is_a_coin_flip(self):
        assert round(smallest_fault_caught(1)) == 50

    def test_twelve_samples_reach_the_rate_the_issue_measured(self):
        """`0.94ⁿ ≤ ½` first holds at twelve — `0fc3c351`'s arithmetic.

        Shared with `deployed_surface.py` deliberately: two instruments that
        sample the same fault and quote different odds for it is how a number
        stops being believed.
        """
        assert smallest_fault_caught(12) < 6.0
        assert smallest_fault_caught(11) > 6.0


class TestFrameReader:
    """The WebSocket read, done by hand.

    `files.pythonhosted.org` is not reachable from every environment this
    repository is worked in, and `.github/requirements.txt` is a stamped input
    to every feedback loop — so adding a dependency to read one socket costs a
    reinstall of the whole developer virtualenv. The frames the backend sends
    are server-to-client text, which is a header and a length; that is what is
    read here, and it is read in a pure class so it can be tested without one.
    """

    def server_frame(self, payload, opcode=0x1, fin=True):
        """One unmasked server frame, as RFC 6455 puts it on the wire."""
        body = payload.encode() if isinstance(payload, str) else payload
        header = bytes([(0x80 if fin else 0) | opcode])
        if len(body) < 126:
            header += bytes([len(body)])
        elif len(body) < 1 << 16:
            header += bytes([126]) + len(body).to_bytes(2, "big")
        else:
            header += bytes([127]) + len(body).to_bytes(8, "big")
        return header + body

    def test_reads_one_text_frame(self):
        reader = FrameReader()

        assert reader.feed(self.server_frame('{"type":"ping"}')) == [
            '{"type":"ping"}']

    def test_holds_a_frame_that_arrived_in_pieces(self):
        """A socket read is a byte count, not a message.

        The `source_used` frame carries every citation and its snippets, so it
        is routinely larger than one read — and a decoder that dropped a
        partial frame would lose the one frame the Grounding panel is made of.
        """
        whole = self.server_frame('{"type":"source_used"}')
        reader = FrameReader()

        assert reader.feed(whole[:4]) == []
        assert reader.feed(whole[4:]) == ['{"type":"source_used"}']

    def test_joins_a_fragmented_message(self):
        reader = FrameReader()

        assert reader.feed(self.server_frame('{"type":', fin=False)) == []
        assert reader.feed(
            self.server_frame('"token_usage"}', opcode=0x0)) == [
                '{"type":"token_usage"}']

    def test_reads_a_payload_too_long_for_a_short_header(self):
        payload = '{"c":"' + "x" * 400 + '"}'
        reader = FrameReader()

        assert reader.feed(self.server_frame(payload)) == [payload]

    def test_reports_the_close_the_server_sent(self):
        reader = FrameReader()
        reader.feed(self.server_frame(b"\x03\xe8", opcode=0x8))

        assert reader.closed is True


def streamed(agent, content, is_final=False):
    return frame(
        "agent_message_streaming",
        agent_name=agent, content=content, is_final=is_final)


class TestTheAnswerIsStreamed:
    """There is no final-result frame on the Fast lane.

    Measured against `rg-macae-flw-v1` on 2026-08-14, build `8f0b77c7b83e`: a
    complete rehearsed turn pushed 512 `agent_message_streaming` frames, one
    `source_used` and one `token_usage`, and **no** `final_result_message` at
    all. A probe that waited for one graded every working turn as unanswered —
    and it did, until this was measured.
    """

    def test_the_answer_is_the_latest_agent_turn(self):
        """Mirrors `plan.latestAgentTurn`, which is what the presenter reads.

        Assembled per agent and not as one transcript, because the outcome that
        matters is a *second* agent speaking after the first answered: joined
        into one string the procedure's steps and the troubleshooter's
        questions read as one turn that both answered and asked.
        """
        turn = observe([
            streamed("Shift Tasks Agent", "**Store closing procedure**\n"),
            streamed("Shift Tasks Agent", "1. Cash up the tills.\n"),
            source_used(),
            streamed("Troubleshooting Agent", "- What is stopping closing?"),
        ])

        assert turn.answer == "- What is stopping closing?"
        assert turn.agents_spoke == (
            "Shift Tasks Agent", "Troubleshooting Agent")

    def test_a_grounded_answer_the_troubleshooter_buried_is_clarified(self):
        """The red run of the last ten-run rehearsal, reproduced from frames.

        `SOP-102` retrieved and cited, and the presenter left in front of a
        question. Every signal except the last agent's turn says the beat
        worked.
        """
        turn = observe([
            streamed("Shift Tasks Agent", CLOSING_ANSWER),
            source_used(),
            token_usage("Shift Tasks Agent"),
            streamed("Troubleshooting Agent", INTERROGATION),
            token_usage("Troubleshooting Agent"),
        ])

        assert outcome(turn) == CLARIFIED

    def test_a_final_result_frame_still_wins_when_one_arrives(self):
        """The Deliberate lane and the error path both send one."""
        turn = observe([
            streamed("Shift Tasks Agent", INTERROGATION),
            final_result(CLOSING_ANSWER),
        ])

        assert turn.answer == CLOSING_ANSWER

    def test_reads_the_content_out_of_the_frame_the_backend_double_wraps(self):
        """`run_orchestration` passes an envelope to a method that envelopes.

        So the final result arrives as `data.data.content`, not
        `data.content` — the same double wrap `WebSocketService.handleMessage`
        already had to learn about, and a reader written against the dataclass
        finds nothing there.
        """
        turn = observe([frame(
            "final_result_message",
            type="final_result_message",
            data={"content": CLOSING_ANSWER, "status": "completed"},
        )])

        assert turn.answer == CLOSING_ANSWER


class TestAgentsThatSpokeAreNotAgentsThatWereBilled:
    """Two signals, deliberately not merged.

    `token_usage` is what the browser's cost table renders and what the ledger
    records as `agentsBilled`; a streamed turn is what the presenter reads. The
    meter is silent when the framework reports no usage — `token_usage`
    returns `None` rather than a zero — so an agent can speak without being
    billed, and merging them would report the meter as having said something it
    did not.
    """

    def test_an_agent_that_spoke_unbilled_is_still_an_unneeded_agent(self):
        turn = observe([
            streamed("Shift Tasks Agent", CLOSING_ANSWER),
            source_used(),
            token_usage("Shift Tasks Agent"),
            streamed("Troubleshooting Agent", INTERROGATION),
        ])

        assert turn.agents_billed == ("Shift Tasks Agent",)
        assert unneeded_agents(turn, "ShiftTasksAgent") == (
            "Troubleshooting Agent",)


class TestTheProbeIsSerial:
    """One turn at a time, and it is not a throughput decision.

    Two mechanisms in the backend resolve their recipient as *the sole
    connected user*, on purpose: `_push_source_used` — the Grounding panel's
    own frame, emitted from the `/sop/ask` bridge the MCP container calls with
    no user of its own — and `send_status_update_async`'s fallback. With two
    probe samples connected at once neither can resolve, and `source_used` is
    dropped.

    Measured before it was understood: the first concurrent run of this probe
    reported `no-tool-call` on **2 of 2** samples against a deployment that
    answers the same question from the corpus on nearly every serial one. A
    faster probe would have sent the next iteration at the routing prompt for a
    fault that was its own.
    """

    def test_takes_one_sample_at_a_time(self):
        overlaps = []
        in_flight = []

        def take(*_args):
            in_flight.append(1)
            overlaps.append(len(in_flight))
            in_flight.pop()
            return [source_used()]

        collect(3, "url", "team", "question", "task", "fast", take=take,
                settle=lambda _seconds: None)

        assert overlaps == [1, 1, 1]

    def test_it_waits_between_samples_for_the_last_one_to_be_forgotten(self):
        """A closed socket the backend has not noticed is still a second user.

        `sole_user()` refuses to guess with two registered, so a sample that
        connects before the previous one has been unregistered loses the
        Grounding panel's frame — and is graded `no-tool-call`, which is
        exactly the fault this probe exists to measure. Measured: a 12-sample
        run reported two, both immediately after the run's two longest turns.
        """
        waits = []

        collect(3, "url", "team", "q", "task", "fast",
                take=lambda *_a: [source_used()], settle=waits.append)

        assert waits == [BETWEEN_SAMPLES_SECONDS] * 2

    def test_a_sample_that_raised_observed_nothing_rather_than_failing_the_run(self):
        """One socket that could not be opened is not a verdict on the rest."""
        def take(*_args):
            raise RuntimeError("the socket closed during the handshake")

        assert collect(2, "url", "team", "q", "task", "fast", take=take,
                       settle=lambda _seconds: None) == [[], []]


class TestBilledIsNotSpoken:
    """Two different bugs wear the same name in the report otherwise.

    An unneeded agent the manager *invoked* and an unneeded agent that reached
    the presenter's screen implicate different halves of the same layer — the
    plan that included it, and the manager's choice of who answers. The browser
    only ever saw the second, because the first is invisible on the surface.
    """

    def test_an_unneeded_agent_that_only_cost_money_is_counted_apart(self):
        summary = summarise([observe([
            token_usage("Shift Tasks Agent"),
            source_used(),
            token_usage("Troubleshooting Agent"),
            streamed("Shift Tasks Agent", "1. Count the till."),
        ])], "ShiftTasksAgent")

        assert summary.unneeded == {"Troubleshooting Agent": 1}
        assert summary.unneeded_spoke == {}
        report = format_report(summary)
        assert "spoke on none of them" in report

    def test_an_unneeded_agent_that_reached_the_presenter_says_so(self):
        summary = summarise([observe([
            token_usage("Shift Tasks Agent"),
            source_used(),
            token_usage("Troubleshooting Agent"),
            streamed("Shift Tasks Agent", "1. Count the till."),
            streamed("Troubleshooting Agent", "Is the till drawer jammed?"),
        ])], "ShiftTasksAgent")

        assert summary.unneeded_spoke == {"Troubleshooting Agent": 1}
        assert "spoke on 1 of them" in format_report(summary)


class TestWhenTheTurnIsOver:
    """The drain's end condition, which decides what the probe never saw.

    There is no `final_result_message` on the Fast lane — a complete rehearsed
    turn pushes streaming chunks, one `source_used` and one `token_usage` per
    executor, and nothing that says *done*. So the turn ends on quiet, and
    every mistake in this predicate is a **false clean or a false fault** that
    looks exactly like the deployment's own behaviour.
    """

    def test_quiet_after_the_meter_has_fired_is_the_turn_ending(self):
        assert turn_is_over(frames=40, metered=True, quiet_for=31, settle=30)

    def test_quiet_before_the_meter_has_fired_is_a_model_thinking(self):
        """Measured, and it cost a sample.

        One 12-sample run graded a turn `no-tool-call` on the strength of a
        single frame: the header the backend streams *before* the agent's
        content, then quiet while the model thought. The meter fires at the end
        of every executor's turn, so `token_usage` is the earliest frame that
        means anything at all has finished.
        """
        assert not turn_is_over(frames=1, metered=False, quiet_for=31,
                                settle=30)

    def test_a_socket_that_carried_nothing_waits_for_the_deadline(self):
        assert not turn_is_over(frames=0, metered=False, quiet_for=999,
                                settle=30)

    def test_a_metered_turn_still_streaming_is_not_over(self):
        assert not turn_is_over(frames=400, metered=True, quiet_for=2,
                                settle=30)


class TestTheProbeIsWiredAndIsNotALoop:
    """It exists, it runs, and no workflow may ever run it.

    Every sample is a live conversation with the deployed agent pool, billed to
    Foundry and to Copilot Studio. That is the Demo validator's own rule (see
    `docs/demo-validator.md`) multiplied by N: a pull request cannot run it,
    and a scheduled run would spend credits on nobody's behalf.
    """

    ROOT = pathlib.Path(__file__).resolve().parents[3]

    def test_the_entry_point_exists_and_is_executable(self):
        entry = self.ROOT / "scripts" / "measure-routing.sh"

        assert entry.exists(), "nothing runs the routing probe"
        assert os.access(entry, os.X_OK), "measure-routing.sh is not executable"

    def test_no_workflow_runs_it(self):
        for workflow in (self.ROOT / ".github" / "workflows").glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            assert "measure-routing" not in text, (
                f"{workflow.name} runs the routing probe: every sample is a "
                "live conversation with the deployed agent pool"
            )

    def test_the_record_explains_every_outcome_the_report_can_print(self):
        """An operator reading an outcome with nowhere to go is the drift that
        costs most — `deployed_surface.py` bought that lesson already."""
        record = (self.ROOT / "docs" / "routing-probe.md").read_text(
            encoding="utf-8")

        for name in (GROUNDED, HONEST_MISS, NO_TOOL_CALL, CLARIFIED,
                     NOT_OBSERVED):
            assert name in record, f"the record does not explain {name!r}"

    def test_agents_md_lists_it_beside_the_other_measurers(self):
        agents = (self.ROOT / "AGENTS.md").read_text(encoding="utf-8")

        assert "measure-routing.sh" in agents, (
            "AGENTS.md does not name the routing probe, so the next agent "
            "rebuilds it or guesses an eighth prompt clause instead"
        )
