"""**Chat deletion** — what it is allowed to take, and what it reports (#75).

ADR-026: a Chat is deleted, not hidden, and deletion takes every document in
that Chat's session partition — plans, steps, transcript, `m_plan`,
**Troubleshooting record**, **Simulated ticket** and **Session state** — scoped
to its `user_id`.

This module is the half of that with no Cosmos in it. Two rules live here and
both are the sort a reviewer has to be able to check by reading:

* **Which chats may go.** A running Chat may not be deleted, and *running* is
  decided **fail-closed** — a status this module does not recognise, or no
  status at all, counts as running. The Identity boundary gate's discipline
  (ADR-014) applied to an irreversible action: *cannot tell* is not *safe to
  delete*, and the cheap side of the mistake is a refusal the associate can
  read.
* **What the caller is told.** `delete_plan_by_plan_id` returns `True` even
  when it deleted nothing, which is precisely the shape ADR-026 refuses to
  route. A sweep that left documents behind reports `incomplete`, because a
  half-deleted chat is a chat still in Cosmos and the surface may not say it is
  gone.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from common.models.messages import PlanStatus

# The three states a conversation stops in. Everything else — `created`,
# `approved`, `in_progress`, and anything added after this was written — is a
# chat something may still be happening to.
#
# Plain strings, not `PlanStatus` members: `PlanStatus` is a `str` Enum whose
# hash is the *member's*, so a set of members does not contain the wire value a
# Plan actually carries.
SETTLED_STATUSES = frozenset(
    {
        PlanStatus.completed.value,
        PlanStatus.failed.value,
        PlanStatus.canceled.value,
    }
)

# What the surface says when it keeps a chat. ADR-026's own noted cost: a
# running Chat cannot be deleted, so the refusal has to explain itself rather
# than read as a control that simply did not work.
STILL_RUNNING_DETAIL = "This chat is still running, so it cannot be deleted yet."


class DeletionOutcome(str, Enum):
    """What happened, in the five ways it can differ."""

    #: No Chat by that session id belongs to this user. Deliberately one
    #: outcome and not two: telling a caller that a chat exists but is somebody
    #: else's is telling them something about somebody else's chat.
    no_such_chat = "no_such_chat"
    #: The session holds a record belonging to a different user. Distinct from
    #: `no_such_chat` in the log and identical to it on the wire, for the
    #: reason above — the caller learns nothing either way.
    not_yours = "not_yours"
    #: The Chat's latest Plan has not settled.
    still_running = "still_running"
    #: Every document in the partition went.
    deleted = "deleted"
    #: Some went and some did not. Not success.
    incomplete = "incomplete"


@dataclass(frozen=True)
class ChatDeletion:
    """The result of asking for a Chat to be deleted."""

    outcome: DeletionOutcome
    deleted: int = 0
    failed: int = 0

    @classmethod
    def swept(cls, deleted: int, failed: int) -> "ChatDeletion":
        """Report a partition sweep by what it actually managed."""
        return cls(
            DeletionOutcome.incomplete if failed else DeletionOutcome.deleted,
            deleted=deleted,
            failed=failed,
        )


def is_running(status: Any) -> bool:
    """Whether a Chat in this state is one something may still be happening to.

    **Total**, and fail-closed with it: a status this module does not know, and
    a record reporting no status at all, are both running. A Chat's state is
    its **latest** Plan's `overall_status` (#71), so this is asked of one
    status rather than of the whole conversation.
    """
    reported = getattr(status, "value", status)
    if not isinstance(reported, str):
        return True

    return reported.strip() not in SETTLED_STATUSES
