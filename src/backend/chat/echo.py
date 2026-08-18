"""The **echo** — what the browser still records, and what it stopped deciding
(#158, ADR-043 decision 7).

*One fact, one writer.* Once the server settles its own turns (#157), the
browser echoing `is_final` back through `POST /v4/agent_message` is a second
opinion on a question already answered, and two writers of one fact is how they
come to disagree. So the echo was narrowed rather than removed: it still carries
what an agent said and the streamed reply, neither of which anything else
persists — the associate's own answers reach the transcript through
`handle_human_clarification`, not here — and it no longer says whether the
conversation is over.

This module is the half of that with no Cosmos in it — what the echo can have
done, and, crucially, **what the route is allowed to call success**. That second
question is the one the old code got wrong in both directions at once: the
handler wrapped everything in a broad `except` and returned a falsy result the
route logged and discarded, so a store failure, a missing **Plan record** and
a clean write were all answered `{"status": "message recorded"}`.

Three outcomes, and they are told apart because only one of them is a write this
system believed it had made and had not:

* **`recorded`** — every write the echo asked for landed.
* **`no_such_plan_record`** — the transcript row landed; the **Plan record** it
  names is gone, so the streaming message had nowhere to go. Ordinary rather
  than a fault: #108's rejection path deletes a Plan record outright, and the
  echo is fire-and-forget — it can arrive after the server settled the turn
  (#157) and the associate deleted the Chat that settling made deletable. Not a
  store failure, and not a 500 — but not a clean write either, and the route
  says so. Named for the record rather than for the Chat, unlike
  `settle.SettleOutcome.no_such_chat`: that one is session-scoped and means the
  Chat holds no Plan record at all, while this one means the single record this
  message named is not there.
* **`refused`** — the store refused a write. **Not success.** The record does
  not say what this process believes it says, and the route is the last layer
  that can admit it.
"""

from dataclasses import dataclass
from enum import Enum

#: What the route tells a caller whose message did not reach the store. Stated
#: once, here, so the sentence the browser is given is the one this module's
#: rule produced rather than a second copy of it written at the route.
NOT_RECORDED_DETAIL = "The agent message did not reach the store."


class EchoOutcome(str, Enum):
    """What recording an echoed agent message did, in the three ways it differs."""

    #: The agent message — and the streaming message, when the echo carried one
    #: — are on the record.
    recorded = "recorded"
    #: The agent message is on the record. The **Plan record** it names is not,
    #: so its streaming message was not stored.
    no_such_plan_record = "no_such_plan_record"
    #: The store refused a write. **Not success.**
    refused = "refused"


@dataclass(frozen=True)
class MessageEchoed:
    """The result of recording what an agent said.

    Deliberately says nothing about `overall_status`. The terminal status of a
    turn is written by the server that ended the turn (ADR-043), and this type
    exists partly so that a future reader looking for the echo's verdict finds
    the absence of one.
    """

    outcome: EchoOutcome

    @property
    def persisted(self) -> bool:
        """Whether every write this echo asked for landed."""
        return self.outcome is EchoOutcome.recorded

    @property
    def store_failed(self) -> bool:
        """Whether a write this process believed it had made had not.

        True for `refused` alone. A **Plan record** that has gone is not a store
        failure — there was nothing to write to — and answering it with a 500
        would report an outage every time an associate deleted a settled Chat
        before its echo arrived.
        """
        return self.outcome is EchoOutcome.refused

    @property
    def status(self) -> str:
        """What the route may say it did — never more than it did.

        Total over the outcomes, including the one the route answers with an
        error, so this property can never be the reason a failure is described
        as a success.
        """
        if self.outcome is EchoOutcome.recorded:
            return "message recorded"
        if self.outcome is EchoOutcome.no_such_plan_record:
            return "message recorded without its streaming message"
        return "message not recorded"
