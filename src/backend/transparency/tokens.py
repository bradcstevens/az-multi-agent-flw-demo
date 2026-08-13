"""What the Token meter is allowed to claim (issue #23).

Token accounting is net-new — the MACAE baseline emits no token telemetry at
all — so this module is the whole of it, and the whole of it is one question:
*what did this agent's turn cost?*

The counts are read by **duck typing**, not by importing the framework's
content types. ``agent_framework`` is stubbed in the backend test suite, so a
reader written against ``isinstance`` would be testing the stub. The shape read
is the framework's own: a ``Content`` whose ``type`` is ``"usage"`` carrying a
``usage_details`` mapping keyed ``input_token_count`` / ``output_token_count``
/ ``total_token_count``.
"""

import logging
from typing import Any, Iterable, Mapping, Optional

from transparency.payloads import TokenUsage

logger = logging.getLogger(__name__)

INPUT_KEYS = ("input_token_count", "prompt_tokens", "input_tokens")
OUTPUT_KEYS = ("output_token_count", "completion_tokens", "output_tokens")
TOTAL_KEYS = ("total_token_count", "total_tokens")


def _count(details: Any, keys: Iterable[str]) -> Optional[int]:
    """Read the first of ``keys`` that carries a number.

    ``UsageDetails`` is a ``TypedDict``, so it arrives as a plain mapping — but
    a provider-specific shape may arrive as an object instead, and the older
    OpenAI vocabulary (``prompt_tokens``) is still what some clients report.
    """
    for key in keys:
        if isinstance(details, Mapping):
            value = details.get(key)
        else:
            value = getattr(details, key, None)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _usage_details(item: Any) -> Any:
    """The ``usage_details`` on an item, if it has any.

    Matched on the payload rather than on ``type == "usage"`` alone: an update
    carrying counts under another content type would still be a real cost, and
    refusing to read it would under-report the meter.
    """
    return getattr(item, "usage_details", None)


def _candidates(item: Any) -> list:
    """Everywhere on one completion payload that a cost may be recorded.

    Three places, in the order the framework prefers them:

    - the item's own ``contents``, where a ``"usage"`` content sits;
    - an ``AgentExecutorResponse``'s wrapped ``agent_response`` — what an
      executor actually *sends*, and where the framework accumulates usage
      having stripped it out of the message contents on the way through;
    - the item itself, which is where ``AgentResponse`` carries it.

    The **first place that has a number wins**, and the rest are not read. The
    same cost is routinely visible in more than one of them, and a meter that
    double-counts is as wrong as one that reports nothing — this one gets
    quoted at a customer.
    """
    wrapped = getattr(item, "agent_response", None)
    for level in (
        list(getattr(item, "contents", None) or ()),
        [] if wrapped is None else [wrapped],
        [item],
    ):
        if any(_usage_details(candidate) is not None for candidate in level):
            return level
    return []


def token_usage(
    executor_id: str, agent_name: str, messages: Iterable[Any]
) -> Optional[TokenUsage]:
    """Sum one executor's reported token cost, or return ``None``.

    ``agent_name`` is passed in rather than derived here: display formatting
    belongs to the callback layer that already owns it, and this module stays a
    pure reader of numbers with no import into the WebSocket machinery.

    ``None`` — not a zero — when the framework reported no usage. A zero would
    read on the meter as *this agent was free*, which is a claim, and precisely
    the claim the meter exists to make honestly. The absence of a number is not
    the number zero, and R7's guardrail column (a refused request adds nothing
    to the meter) depends on nothing being the only thing that looks like
    nothing.
    """
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    found = False

    for message in messages or ():
        for candidate in _candidates(message):
            details = _usage_details(candidate)
            if details is None:
                continue
            read_in = _count(details, INPUT_KEYS)
            read_out = _count(details, OUTPUT_KEYS)
            read_total = _count(details, TOTAL_KEYS)
            if read_in is None and read_out is None and read_total is None:
                continue
            found = True
            input_tokens += read_in or 0
            output_tokens += read_out or 0
            # A provider that reports only a total still has a total to report;
            # one that reports only the parts has its total derived here.
            total_tokens += (
                read_total
                if read_total is not None
                else (read_in or 0) + (read_out or 0)
            )

    if not found:
        return None

    return TokenUsage(
        agent_name=agent_name,
        executor_id=executor_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
