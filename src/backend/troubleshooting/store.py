"""The troubleshooting record, read and written through the memory container
(issue #21).

Framework checkpoint state is in-memory and must not be relied on, so what an
associate reports having tried is persisted here **explicitly**. The record is
an ordinary document in the schemaless memory container, exactly like the
session state beside it: partitioned by session, discriminated by data type,
reached through the generic CRUD. No new database method, and no migration.

Every method here is **total**. The record is a memory of one shift, and the
answer it rides back on is the associate's; an unreachable container costs one
repeated step, while raising costs the turn. So a read that fails is an empty
record, and a write that fails is a warning.
"""

import logging
from typing import Iterable, Optional, Sequence

from common.models.messages import TroubleshootingRecord
from troubleshooting.steps import attempted_note, merge_attempted

logger = logging.getLogger(__name__)


def troubleshooting_record_id(session_id: str) -> str:
    """The document id of a session's troubleshooting record.

    Derived from the session rather than freshly generated, which is what makes
    a read a point read on the session's own partition and makes a second write
    replace the first instead of accumulating a log nobody reads.
    """
    return f"troubleshooting:{session_id}"


class TroubleshootingStore:
    """Reads and writes one session's attempted steps."""

    def __init__(self, memory_store, user_id: str = ""):
        self._memory_store = memory_store
        self._user_id = user_id

    def _empty(self, session_id: str) -> TroubleshootingRecord:
        """A session on which nothing has been tried yet."""
        return TroubleshootingRecord(
            id=troubleshooting_record_id(session_id),
            session_id=session_id,
            user_id=self._user_id or None,
        )

    def _owns(self, record: TroubleshootingRecord) -> bool:
        """Whether the caller owns a stored record.

        An unowned record — one written before the owner was recorded — is
        readable by anyone, the same reading the container's other ownership
        predicates take of a missing owner.
        """
        return not record.user_id or record.user_id == self._user_id

    async def read(self, session_id: str) -> TroubleshootingRecord:
        """Read a session's record, defaulting to nothing having been tried.

        Total: a session nobody has written to reads back as an empty record
        rather than ``None``, because the caller that matters is the one about
        to offer the runbook, and its default is "offer all of it".
        """
        stored = await self._memory_store.get_item_by_id(
            troubleshooting_record_id(session_id), session_id, TroubleshootingRecord
        )
        if isinstance(stored, TroubleshootingRecord) and self._owns(stored):
            return stored
        return self._empty(session_id)

    async def record(
        self,
        session_id: str,
        steps: Iterable[str],
        *,
        equipment: Optional[str] = None,
    ) -> TroubleshootingRecord:
        """Fold newly reported steps into a session's record and return it.

        A merge rather than a replace: the steps a *first* turn recorded are
        exactly the ones a later turn must not repeat, so a replace would
        un-record the thing the record exists for. ``equipment`` is likewise
        only ever written, never cleared — the turn that reports a step is
        rarely the turn that named what broke.
        """
        try:
            record = await self.read(session_id)
        except Exception:
            logger.warning(
                "Could not read the troubleshooting record for session '%s' — "
                "recording against an empty one",
                session_id,
                exc_info=True,
            )
            record = self._empty(session_id)

        record.id = troubleshooting_record_id(session_id)
        record.session_id = session_id
        record.user_id = self._user_id or record.user_id
        record.attempted = merge_attempted(record.attempted, steps)
        if equipment:
            record.equipment = equipment

        try:
            await self._memory_store.update_item(record)
        except Exception:
            logger.warning(
                "Could not persist the troubleshooting record for session '%s' — "
                "this turn's attempted steps will not survive it",
                session_id,
                exc_info=True,
            )
        return record

    async def note(self, session_id: str) -> str:
        """What the agent is told about the record, or nothing.

        Nothing is also what an unreadable container produces: the note rides
        the associate's answer back to the agent, and no answer may be lost
        because the memory of this shift could not be read.
        """
        try:
            record = await self.read(session_id)
        except Exception:
            logger.warning(
                "Could not read the troubleshooting record for session '%s' — "
                "the agent is told nothing rather than something untrue",
                session_id,
                exc_info=True,
            )
            return ""
        return attempted_note(record.attempted)

    @staticmethod
    def note_for(attempted: Sequence[str]) -> str:
        """The note for a record that has already been read."""
        return attempted_note(attempted)
