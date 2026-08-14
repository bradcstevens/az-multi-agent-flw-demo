"""What a pending tool approval puts to the associate — and what it does not.

Pure and no I/O, like ``troubleshooting.steps`` and ``lane.keywords``, because
*the associate is asked only what they can answer* is only mechanical if "a
question" is something code can decide.

The framework pauses on every approval-gated tool call, not only on
``request_user_clarification``. **The clarification seam** hands whatever it is
paused on to the associate as a **Clarification**, so a gated tool that asks
nobody anything — the observed one is ``list_attempted_steps`` — used to reach
the surface as the placeholder *"The agent needs clarification."* and hold the
turn for the full clarification wait. Three things are wrong with that and only
the first is cosmetic: a question with no words cannot be answered; a
**Rehearsed reply** tapped into it is spent on a call that will not read it;
and the answer is written into the **Troubleshooting record**, which is what the
**Simulated ticket**'s attempted steps are filled from, so an approval nobody
asked about can put words in the associate's mouth on a ticket.

The rule runs one way, like the record's own: this may leave a real question
unasked (the agent is told so, and the turn continues), but it may never put a
question to the associate that nothing will read the answer to.
"""

import json

# The one tool whose pause is a question. Restated here rather than imported,
# because this module stays free of ``agent_framework``; the test suite reads
# the real tool's own name and fails if the two ever disagree, the same guard
# the ticket signal's message type carries.
CLARIFICATION_TOOL = "request_user_clarification"

# What the agent is told when the turn asks the associate nothing. It says the
# associate was **not asked** — it does not invent an answer on their behalf,
# which is the one thing a ticket may never carry.
NOT_ASKED = (
    "The associate was not asked. This task raises the service ticket from "
    "this session's stored record when the plan is approved: the attempted "
    "steps are already filled in the associate's own words, and every field "
    "nobody reported is written 'not reported' rather than asked for. Do not "
    "ask the associate anything; acknowledge the approved plan."
)


def clarification_questions(function_call) -> str | None:
    """The questions this pending tool approval puts to the associate.

    ``None`` when it puts none: a gated tool that is not the clarification
    tool, or a clarification whose questions did not survive the model — an
    unparseable argument string, a missing ``questions``, or a blank one.
    """
    if getattr(function_call, "name", None) != CLARIFICATION_TOOL:
        return None

    raw = getattr(function_call, "arguments", None) or "{}"
    try:
        arguments = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(arguments, dict):
        return None

    questions = arguments.get("questions")
    # Coerced rather than required to be a string. The rule runs one way: a
    # real question must never be swallowed, and a model that emits its
    # questions as a JSON array — or as anything else with words in it — has
    # still asked one. Only *nothing* is nothing.
    if isinstance(questions, (list, tuple)):
        questions = "\n".join(
            str(one) for one in questions if str(one).strip()
        )
    elif questions is not None and not isinstance(questions, str):
        questions = str(questions)
    if not questions or not questions.strip():
        return None
    return questions
