"""What the Token meter is allowed to claim (issue #23).

The counts are read out of the framework's own usage content by duck typing:
``agent_framework`` is stubbed in this suite, so a test that imported its
``Content`` would be testing the stub. The shape pinned here is the real one —
a ``Content`` whose ``type`` is ``"usage"`` carrying a ``usage_details``
mapping with ``input_token_count`` / ``output_token_count`` /
``total_token_count``.
"""

from types import SimpleNamespace

from transparency.tokens import token_usage


def _usage_content(**counts):
    """A framework usage content, as the executor-completed branch sees it."""
    return SimpleNamespace(type="usage", usage_details=dict(counts))


def _message(*contents):
    return SimpleNamespace(contents=list(contents))


class TestTokenUsage:
    def test_a_usage_content_becomes_the_agents_counts(self):
        message = _message(
            _usage_content(
                input_token_count=120,
                output_token_count=45,
                total_token_count=165,
            )
        )

        usage = token_usage("shift_tasks_agent", "Shift Tasks Agent", [message])

        assert usage.input_tokens == 120
        assert usage.output_tokens == 45
        assert usage.total_tokens == 165

    def test_no_usage_reported_is_no_event_rather_than_a_zero(self):
        """The absence of a number is not the number zero.

        A zero reads on the meter as *this agent was free*, which is a claim —
        and R7's guardrail column, where a refused request adds nothing, needs
        nothing to be the only thing that looks like nothing.
        """
        assert token_usage("shift_tasks_agent", "Shift Tasks Agent", [_message()]) is None

    def test_no_messages_at_all_is_no_event(self):
        assert token_usage("shift_tasks_agent", "Shift Tasks Agent", []) is None
        assert token_usage("shift_tasks_agent", "Shift Tasks Agent", None) is None

    def test_two_turns_of_usage_are_summed_into_one_cost(self):
        """One executor-completed event can carry several messages, and the
        meter is a per-agent total, not a per-message one."""
        messages = [
            _message(_usage_content(input_token_count=10, output_token_count=4)),
            _message(_usage_content(input_token_count=7, output_token_count=3)),
        ]

        usage = token_usage("troubleshooting_agent", "Troubleshooting Agent", messages)

        assert (usage.input_tokens, usage.output_tokens) == (17, 7)

    def test_a_provider_reporting_only_the_parts_still_gets_a_total(self):
        message = _message(_usage_content(input_token_count=60, output_token_count=20))

        assert token_usage("escalation_agent", "Escalation Agent", [message]).total_tokens == 80

    def test_the_openai_vocabulary_is_read_too(self):
        """Some clients still report ``prompt_tokens``/``completion_tokens``.
        Reading only the framework's names would meter those agents at nothing,
        which looks identical to an agent that was never called."""
        message = _message(
            SimpleNamespace(usage_details={"prompt_tokens": 9, "completion_tokens": 2})
        )

        usage = token_usage("escalation_agent", "Escalation Agent", [message])

        assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (9, 2, 11)

    def test_usage_attached_to_the_message_itself_is_read(self):
        """``AgentResponse`` carries ``usage_details`` at the top level rather
        than as a content item."""
        message = SimpleNamespace(
            contents=[],
            usage_details={"input_token_count": 5, "output_token_count": 1},
        )

        assert token_usage("orchestrator", "Orchestrator", [message]).total_tokens == 6

    def test_the_cost_is_attributed_to_the_executor_that_incurred_it(self):
        """Attribution the meter shares with the streaming header — and the one
        attribution that survives plan review being off, because with no plan
        there is no plan to read a name out of. The display name is the
        caller's to supply; the identifier is what the meter keys on."""
        message = _message(_usage_content(total_token_count=3))

        usage = token_usage("shift_tasks_agent", "Shift Tasks Agent", [message])

        assert usage.executor_id == "shift_tasks_agent"
        assert usage.agent_name == "Shift Tasks Agent"

    def test_the_same_cost_reported_twice_is_counted_once(self):
        """A framework object can expose the same usage both as a content item
        and on itself. Reading both doubles the bill, and a meter that
        over-reports is as wrong as one that under-reports — this one exists to
        be quoted at a customer."""
        counts = {"input_token_count": 100, "output_token_count": 20}
        message = SimpleNamespace(
            contents=[SimpleNamespace(type="usage", usage_details=dict(counts))],
            usage_details=dict(counts),
        )

        usage = token_usage("shift_tasks_agent", "Shift Tasks Agent", [message])

        assert (usage.input_tokens, usage.output_tokens) == (100, 20)

    def test_usage_wrapped_in_an_executor_response_is_found(self):
        """``executor_completed`` carries what the executor *sent*, and an
        ``AgentExecutor`` sends an ``AgentExecutorResponse`` wrapping the
        ``AgentResponse`` — which is where the framework accumulates usage,
        having stripped it out of the message contents on the way. Reading only
        the message would meter every agent at nothing."""
        wrapper = SimpleNamespace(
            agent_response=SimpleNamespace(
                messages=[],
                usage_details={"input_token_count": 300, "output_token_count": 90},
            )
        )

        usage = token_usage("troubleshooting_agent", "Troubleshooting Agent", [wrapper])

        assert usage.total_tokens == 390

    def test_usage_on_a_message_that_also_has_text_is_still_found(self):
        """The common shape: contents carry the answer, the container carries
        the cost. Stopping at the contents because they exist would meter every
        answering agent at nothing."""
        message = SimpleNamespace(
            contents=[SimpleNamespace(type="text", text="1. Count the drawer.")],
            usage_details={"input_token_count": 40, "output_token_count": 12},
        )

        usage = token_usage("shift_tasks_agent", "Shift Tasks Agent", [message])

        assert usage.total_tokens == 52
