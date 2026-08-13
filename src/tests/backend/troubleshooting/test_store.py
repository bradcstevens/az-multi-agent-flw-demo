"""The troubleshooting record, read and written through the memory container
(issue #21).

Driven against a fake that implements only the generic CRUD the container
already exposes — the point of the design being that a new record type costs
one enumeration member and one model, with no migration and no new database
method. The same fake shape ``session/test_session_state_store.py`` uses,
because the two records are siblings in the same container.
"""

import os
import sys
from types import ModuleType

import pytest

_backend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
)
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)


def _import_store():
    """Import ``troubleshooting.store`` against the *real* message models.

    Earlier-collected suites replace flat modules such as
    ``common.models.messages`` with bare ``Mock()`` objects in ``sys.modules``,
    so a plain import here would bind ``TroubleshootingRecord`` to a mock
    attribute rather than to the model class. The same containment
    ``session/test_session_state_store.py`` uses.
    """
    snapshot = dict(sys.modules)
    try:
        for name in ("common", "common.models", "troubleshooting"):
            package = ModuleType(name)
            package.__path__ = [os.path.join(_backend_path, *name.split("."))]
            sys.modules[name] = package
        for name in (
            "common.models.messages",
            "troubleshooting.steps",
            "troubleshooting.store",
        ):
            sys.modules.pop(name, None)
        import troubleshooting.store as store_module

        return store_module
    finally:
        for key in list(sys.modules):
            if key not in snapshot:
                del sys.modules[key]
        sys.modules.update(snapshot)


store_module = _import_store()
TroubleshootingRecord = store_module.TroubleshootingRecord
TroubleshootingStore = store_module.TroubleshootingStore
troubleshooting_record_id = store_module.troubleshooting_record_id


class FakeMemoryStore:
    """The generic CRUD surface of the memory container, in a dictionary.

    Keyed the way Cosmos keys it — by ``(id, partition key)`` — so a record
    written under the wrong partition is invisible to a read, exactly as it
    would be in the deployed container.
    """

    def __init__(self):
        self.documents = {}
        self.updates = []

    async def get_item_by_id(self, item_id, partition_key, model_class):
        return self.documents.get((item_id, partition_key))

    async def update_item(self, item):
        self.updates.append(item)
        self.documents[(item.id, item.session_id)] = item


@pytest.fixture
def memory():
    return FakeMemoryStore()


class TestTheRecordIsAnOrdinaryDocument:
    def test_its_id_is_derived_from_the_session_not_freshly_generated(self):
        """Derived, so a read is a point read on the session's own partition
        and a second write replaces the first instead of accumulating a log
        nobody reads."""
        assert troubleshooting_record_id("s-1") == troubleshooting_record_id("s-1")
        assert troubleshooting_record_id("s-1") != troubleshooting_record_id("s-2")

    def test_it_is_discriminated_by_its_own_data_type(self):
        record = TroubleshootingRecord(session_id="s-1")

        assert record.data_type == "troubleshooting"

    def test_a_new_record_reports_nothing_attempted(self):
        assert TroubleshootingRecord(session_id="s-1").attempted == []


class TestRead:
    @pytest.mark.asyncio
    async def test_a_session_nobody_has_written_to_reads_back_empty_not_none(
        self, memory
    ):
        """Total, like the session-state read: every caller would otherwise
        have to invent the default, and the default that matters is 'nothing
        has been tried', which offers the whole runbook."""
        record = await TroubleshootingStore(memory, user_id="u-1").read("s-1")

        assert isinstance(record, TroubleshootingRecord)
        assert record.attempted == []
        assert record.session_id == "s-1"

    @pytest.mark.asyncio
    async def test_a_record_belonging_to_somebody_else_reads_back_empty(self, memory):
        """The container's records carry their owner and its reads are scoped
        by it. One associate's fault is not another's."""
        store = TroubleshootingStore(memory, user_id="u-1")
        await store.record("s-1", ["Power cycled the brewer"])

        other = await TroubleshootingStore(memory, user_id="u-2").read("s-1")

        assert other.attempted == []


class TestRecord:
    @pytest.mark.asyncio
    async def test_what_the_associate_reported_survives_into_the_container(
        self, memory
    ):
        """Explicitly persisted, not left in framework checkpoint state, which
        is in-memory and must not be relied on."""
        store = TroubleshootingStore(memory, user_id="u-1")

        await store.record("s-1", ["Power cycled the brewer"])

        assert memory.documents[
            (troubleshooting_record_id("s-1"), "s-1")
        ].attempted == ["Power cycled the brewer"]

    @pytest.mark.asyncio
    async def test_a_second_turn_adds_to_the_record_rather_than_replacing_it(
        self, memory
    ):
        """A merge, not a replace: the first turn's steps are the ones a later
        turn must not repeat, so a replace would un-record them."""
        store = TroubleshootingStore(memory, user_id="u-1")
        await store.record("s-1", ["Power cycled the brewer"])

        record = await store.record("s-1", ["Checked the water line"])

        assert record.attempted == [
            "Power cycled the brewer",
            "Checked the water line",
        ]

    @pytest.mark.asyncio
    async def test_the_same_step_reported_twice_is_recorded_once(self, memory):
        store = TroubleshootingStore(memory, user_id="u-1")
        await store.record("s-1", ["Power cycled the brewer"])

        record = await store.record("s-1", ["I already power-cycled the brewer"])

        assert record.attempted == ["Power cycled the brewer"]

    @pytest.mark.asyncio
    async def test_the_equipment_is_remembered_and_not_erased_by_a_later_turn(
        self, memory
    ):
        """#22's ticket needs what broke as well as what was tried, and the
        turn that reports a step is rarely the turn that named the equipment."""
        store = TroubleshootingStore(memory, user_id="u-1")
        await store.record("s-1", [], equipment="coffee brewer, left head")

        record = await store.record("s-1", ["Power cycled it"])

        assert record.equipment == "coffee brewer, left head"

    @pytest.mark.asyncio
    async def test_recording_nothing_still_leaves_a_readable_record(self, memory):
        """The associate answering 'nothing yet' is a fact about the session,
        and the next turn reads the record either way."""
        store = TroubleshootingStore(memory, user_id="u-1")

        await store.record("s-1", [])

        assert (await store.read("s-1")).attempted == []

    @pytest.mark.asyncio
    async def test_the_record_carries_its_owner(self, memory):
        store = TroubleshootingStore(memory, user_id="u-1")

        record = await store.record("s-1", ["Power cycled the brewer"])

        assert record.user_id == "u-1"


class TestNoteForTheAgent:
    @pytest.mark.asyncio
    async def test_an_unreachable_container_says_nothing_rather_than_raising(
        self, memory
    ):
        """The note rides the answer back to the agent. An answer must never be
        lost because the memory of this shift could not be read — the cost of
        saying nothing is one repeated step, the cost of raising is the turn."""

        class Broken:
            async def get_item_by_id(self, *_args, **_kwargs):
                raise RuntimeError("cosmos is down")

        store = TroubleshootingStore(Broken(), user_id="u-1")

        assert await store.note("s-1") == ""

    @pytest.mark.asyncio
    async def test_the_note_names_the_recorded_steps(self, memory):
        store = TroubleshootingStore(memory, user_id="u-1")
        await store.record("s-1", ["Power cycled the brewer"])

        assert "Power cycled the brewer" in await store.note("s-1")

    @pytest.mark.asyncio
    async def test_a_session_with_nothing_recorded_produces_no_note(self, memory):
        assert await TroubleshootingStore(memory, user_id="u-1").note("s-1") == ""

    @pytest.mark.asyncio
    async def test_a_write_that_cannot_reach_the_container_does_not_lose_the_turn(
        self, memory
    ):
        """Same reasoning from the other end: a failed persist costs the memory
        of one step, and raising here would cost the associate their answer."""

        class Broken:
            async def get_item_by_id(self, *_args, **_kwargs):
                return None

            async def update_item(self, _item):
                raise RuntimeError("cosmos is down")

        store = TroubleshootingStore(Broken(), user_id="u-1")

        record = await store.record("s-1", ["Power cycled the brewer"])

        assert record.attempted == ["Power cycled the brewer"]
