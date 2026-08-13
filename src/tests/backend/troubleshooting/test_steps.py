"""Attempted steps, read out of what an associate actually typed (issue #21).

Pure and no I/O, like the lane keywords and the guardrail's keyword fast path.
The requirement it serves — *never walk an associate through the same failed
step twice* — is only mechanical if "the same step" is something code can
decide, so deciding it lives here rather than in a prompt.

Its hard requirement runs one way, like the Lane keyword fallback's: it may
**miss** a match and offer a step the associate already tried (they say so
again, and the record grows), but it may never claim a step was attempted that
was not, because that step is then silently skipped and the fault stays broken.
"""

from troubleshooting.steps import (ESCALATION_AFTER, already_attempted,
                                   attempted_note, escalation_due,
                                   merge_attempted, normalise_step,
                                   parse_attempted_steps)


class TestParseAttemptedSteps:
    def test_a_numbered_list_is_one_step_per_line(self):
        answer = "1. Power cycled the brewer\n2. Checked the water line\n3. Descaled it"

        assert parse_attempted_steps(answer) == [
            "Power cycled the brewer",
            "Checked the water line",
            "Descaled it",
        ]

    def test_bullets_and_dashes_are_stripped_the_same_way(self):
        answer = "- Refilled the hopper\n* Reseated the filter basket\n• Ran a rinse cycle"

        assert parse_attempted_steps(answer) == [
            "Refilled the hopper",
            "Reseated the filter basket",
            "Ran a rinse cycle",
        ]

    def test_one_sentence_naming_two_things_is_two_steps(self):
        """An associate mid-shift types a sentence, not a list."""
        answer = "I turned it off and on again and I checked the water line"

        assert parse_attempted_steps(answer) == [
            "turned it off and on again",
            "checked the water line",
        ]

    def test_a_leading_i_tried_is_not_part_of_the_step(self):
        assert parse_attempted_steps("I tried restarting it") == ["restarting it"]
        assert parse_attempted_steps("I already restarted it") == ["restarted it"]
        assert parse_attempted_steps("Tried the reset button") == ["the reset button"]

    def test_nothing_reported_is_no_steps_rather_than_one_empty_one(self):
        """A blank answer must not become a recorded step: an empty attempted
        step matches everything downstream, which would skip the whole runbook."""
        assert parse_attempted_steps("") == []
        assert parse_attempted_steps("   \n  \n") == []
        assert parse_attempted_steps(None) == []

    def test_a_denial_records_nothing(self):
        """'Nothing yet' is an answer to the question and not a step. Recording
        it would make the record claim the associate tried something."""
        for denial in ("nothing", "Nothing yet", "no", "I haven't tried anything"):
            assert parse_attempted_steps(denial) == []

    def test_a_timeout_answer_records_nothing(self):
        """The clarification path substitutes its own words on a timeout
        (300 s, issue #21's second named constraint). Those words are the
        backend's, not the associate's, and they are not a step."""
        assert parse_attempted_steps("No response received from user (timeout).") == []
        assert parse_attempted_steps("Error receiving response: boom") == []


class TestNormaliseStep:
    def test_wording_that_differs_only_in_case_and_padding_is_one_step(self):
        assert normalise_step("  Power Cycled the Brewer.  ") == normalise_step(
            "power cycled the brewer"
        )

    def test_filler_the_associate_types_is_not_part_of_the_step(self):
        assert normalise_step("I have already restarted the machine") == normalise_step(
            "restart machine"
        )

    def test_two_genuinely_different_steps_do_not_collapse(self):
        assert normalise_step("checked the water line") != normalise_step(
            "checked the power lead"
        )


class TestMergeAttempted:
    def test_a_second_report_of_the_same_step_does_not_duplicate_it(self):
        merged = merge_attempted(
            ["Power cycled the brewer"], ["I already power-cycled the brewer"]
        )

        assert merged == ["Power cycled the brewer"]

    def test_the_first_wording_is_the_one_kept(self):
        """The associate's own words go into #22's ticket; the second telling
        is the same fact, not a better one."""
        merged = merge_attempted(["Power cycled the brewer"], ["turned it off and on"])

        assert merged[0] == "Power cycled the brewer"

    def test_a_new_step_is_appended_in_the_order_it_was_reported(self):
        merged = merge_attempted(["Power cycled the brewer"], ["Checked the water line"])

        assert merged == ["Power cycled the brewer", "Checked the water line"]

    def test_merging_nothing_leaves_the_record_exactly_as_it_was(self):
        assert merge_attempted(["Power cycled the brewer"], []) == [
            "Power cycled the brewer"
        ]


class TestAlreadyAttempted:
    def test_a_step_the_associate_reported_is_recognised_however_they_said_it(self):
        record = ["I turned it off and on again"]

        assert already_attempted("Power cycle the brewer", record) is None
        assert already_attempted("Turn the brewer off and on again", record) == record[0]

    def test_a_step_nobody_tried_is_not_claimed_as_attempted(self):
        """The one-way requirement: a false claim here silently skips a step
        and leaves the equipment broken."""
        record = ["Power cycled the brewer"]

        assert already_attempted("Descale the brew head", record) is None
        assert already_attempted("Check the water line", record) is None

    def test_an_empty_record_claims_nothing(self):
        assert already_attempted("Power cycle the brewer", []) is None

    def test_a_single_shared_word_is_not_enough_to_claim_a_step(self):
        """'Check the drip tray' and 'checked the water line' share only
        *check*. Containment on one word claims a step nobody tried, which is
        the direction this module may never fail in."""
        record = ["Checked the water line"]

        assert already_attempted("Check the drip tray", record) is None
        assert already_attempted("Check it", record) is None

    def test_one_word_steps_still_match_themselves(self):
        """The guard is about *containment*, not about equality: an associate
        who typed one word and a runbook step of one word are still one step."""
        assert already_attempted("Descale", ["descaled"]) == "descaled"


class TestEscalationDue:
    def test_a_record_that_has_run_out_of_ideas_calls_for_escalation(self):
        assert escalation_due(["one", "two", "three", "four"]) is True

    def test_the_first_couple_of_attempts_are_not_an_escalation(self):
        """Offering a ticket after one attempt teaches the associate the
        assistant gives up, which is the opposite of the beat."""
        assert escalation_due([]) is False
        assert escalation_due(["one"]) is False

    def test_the_threshold_is_the_one_the_module_publishes(self):
        assert escalation_due(["s"] * ESCALATION_AFTER) is True
        assert escalation_due(["s"] * (ESCALATION_AFTER - 1)) is False


class TestAttemptedNote:
    def test_the_note_names_every_recorded_step(self):
        note = attempted_note(["Power cycled the brewer", "Checked the water line"])

        assert "Power cycled the brewer" in note
        assert "Checked the water line" in note

    def test_the_note_tells_the_agent_to_skip_rather_than_merely_listing(self):
        note = attempted_note(["Power cycled the brewer"]).lower()

        assert "do not" in note
        assert "skip" in note

    def test_an_empty_record_produces_no_note_at_all(self):
        """Nothing to say is said by saying nothing — an empty 'already tried'
        heading reads to the model as a list it may fill in."""
        assert attempted_note([]) == ""

    def test_a_record_that_has_run_out_of_ideas_asks_for_the_ticket_offer(self):
        note = attempted_note(["one", "two", "three", "four"]).lower()

        assert "ticket" in note

    def test_a_short_record_does_not_ask_for_the_ticket_offer(self):
        note = attempted_note(["one"]).lower()

        assert "ticket" not in note
