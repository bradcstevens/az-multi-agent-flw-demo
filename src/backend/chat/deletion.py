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
from typing import Any, Iterable, Tuple

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

# What the surface says about a chat whose turn is still in flight. ADR-026's
# own noted cost, answered rather than restated: a running Chat cannot be
# deleted *as it stands*, so the refusal has to explain itself rather than read
# as a control that simply did not work. #122 makes it a door — `end_turn=true`
# ends the turn first, through the same primitive **Leaving a Chat** uses — so
# this names the act rather than the wall.
STILL_RUNNING_DETAIL = "This chat is still running, so deleting it ends its turn first."


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


@dataclass(frozen=True)
class ChatsDeletion:
    """The result of asking for **every** Chat to be deleted (#76).

    One chat's delete says what happened in an HTTP status. A sweep of the
    whole list cannot: its chats do not all end the same way, and a status code
    that reported the worst of them would throw away the fact that the rest are
    gone — leaving the panel unable to say which rows to drop. So the
    accounting *is* the result, and the surface reads it rather than the status.

    Three buckets, and every chat lands in exactly one:

    * ``deleted`` — the sessions that went, **named** rather than counted. The
      panel prunes those rows and navigates away from the open conversation
      only if it is among them; a number cannot say which.
    * ``kept_running`` — chats refused by the same fail-closed rule the single
      delete uses. ADR-026's noted cost at list scale: refusing the whole
      operation because one chat is running would make the control useless at
      the moment it is wanted, and dropping the chat quietly would be the
      surface saying something that is not so.
    * ``failed`` — anything else, including a chat only partly swept. A
      half-deleted chat is still in Cosmos and is not a deletion.
    """

    deleted: Tuple[str, ...] = ()
    kept_running: int = 0
    failed: int = 0
    documents_deleted: int = 0

    @property
    def status(self) -> str:
        """``deleted`` only when nothing was left behind."""
        return "incomplete" if self.failed else "deleted"

    @classmethod
    def tally(
        cls, results: Iterable[Tuple[str, ChatDeletion]]
    ) -> "ChatsDeletion":
        """Add up one sweep per Chat, by what each actually managed.

        **Total**, and that is the point: an outcome added to
        ``DeletionOutcome`` later falls into ``failed`` rather than off the
        end, so the surface can never report a shorter list than was swept.
        """
        deleted = []
        kept_running = 0
        failed = 0
        documents_deleted = 0

        for session_id, result in results:
            documents_deleted += result.deleted

            if result.outcome is DeletionOutcome.deleted:
                deleted.append(session_id)
            elif result.outcome is DeletionOutcome.still_running:
                kept_running += 1
            else:
                failed += 1

        return cls(
            deleted=tuple(deleted),
            kept_running=kept_running,
            failed=failed,
            documents_deleted=documents_deleted,
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
