"""Server-side session state, read and written through the memory container
(issue #20).

The store is driven against a fake that implements only the generic CRUD the
container already exposes — `get_item_by_id`, `add_item`, `update_item` — which
is the point: a new record type is one enumeration member and one model, with
no migration and no new database method.
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
    """Import ``session.store`` against the *real* message models.

    Earlier-collected suites replace flat modules such as
    ``common.models.messages`` with bare ``Mock()`` objects in ``sys.modules``,
    so a plain import here would bind ``SessionState`` to a mock attribute
    rather than to the model class. Install proper package stubs for the flat
    namespaces the store walks, import it for real, then restore ``sys.modules``
    to its exact prior state so no other test file is affected — the same
    containment ``api/test_router.py`` uses.
    """
    snapshot = dict(sys.modules)
    try:
        for name in ("common", "common.models", "session"):
            package = ModuleType(name)
            package.__path__ = [os.path.join(_backend_path, *name.split("."))]
            sys.modules[name] = package
        for name in ("common.models.messages", "session.store"):
            sys.modules.pop(name, None)
        import session.store as store_module

        return store_module
    finally:
        for key in list(sys.modules):
            if key not in snapshot:
                del sys.modules[key]
        sys.modules.update(snapshot)


store_module = _import_store()
SessionState = store_module.SessionState
SessionStateStore = store_module.SessionStateStore


class FakeMemoryStore:
    """The generic CRUD surface of the memory container, in a dictionary.

    Keyed the way Cosmos keys it — by ``(id, partition key)`` — so a record
    written under the wrong partition is invisible to a read, exactly as it
    would be in the deployed container.
    """

    def __init__(self):
        self.documents = {}
        self.reads = []

    async def get_item_by_id(self, item_id, partition_key, model_class):
        self.reads.append((item_id, partition_key, model_class))
        document = self.documents.get((item_id, partition_key))
        if document is None:
            return None
        return model_class.model_validate(document)

    async def add_item(self, item):
        self.documents[(item.id, item.session_id)] = item.model_dump(mode="json")

    async def update_item(self, item):
        self.documents[(item.id, item.session_id)] = item.model_dump(mode="json")


@pytest.fixture
def memory_store():
    return FakeMemoryStore()


@pytest.fixture
def store(memory_store):
    return SessionStateStore(memory_store)


class TestReadingASessionThatHasNoRecordYet:
    """A session nobody has written to is not an error — it is the state the
    demo opens in."""

    @pytest.mark.asyncio
    async def test_it_reads_back_a_state_rather_than_nothing(self, store):
        state = await store.read("sess-1")
        assert isinstance(state, SessionState)
        assert state.session_id == "sess-1"

    @pytest.mark.asyncio
    async def test_the_identity_defaults_to_anonymous(self, store):
        state = await store.read("sess-1")
        assert state.identity.display_name is None

    @pytest.mark.asyncio
    async def test_nothing_is_written_by_a_read(self, store, memory_store):
        await store.read("sess-1")
        assert memory_store.documents == {}


class TestWritingSessionState:
    @pytest.mark.asyncio
    async def test_a_written_value_survives_the_round_trip(self, store):
        await store.write("sess-1", lane="fast")
        assert (await store.read("sess-1")).lane == "fast"

    @pytest.mark.asyncio
    async def test_the_record_is_partitioned_by_session(self, store, memory_store):
        await store.write("sess-1", lane="fast")
        (_, partition_key), document = next(iter(memory_store.documents.items()))
        assert partition_key == "sess-1"
        assert document["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_the_record_is_discriminated_by_data_type(self, store, memory_store):
        await store.write("sess-1", lane="fast")
        document = next(iter(memory_store.documents.values()))
        assert document["data_type"] == "session_state"

    @pytest.mark.asyncio
    async def test_one_session_cannot_read_another_sessions_state(self, store):
        await store.write("sess-1", lane="fast")
        assert (await store.read("sess-2")).lane is None

    @pytest.mark.asyncio
    async def test_a_second_write_replaces_the_same_record(self, store, memory_store):
        """One record per session, not an append-only log.

        The store reads a session's state by a point read on a deterministic
        id, so a second write that landed under a fresh uuid would be written
        and then never read again.
        """
        await store.write("sess-1", lane="fast")
        await store.write("sess-1", lane="deliberate")
        assert len(memory_store.documents) == 1
        assert (await store.read("sess-1")).lane == "deliberate"


class TestWritingIsAMerge:
    """Two surfaces write this record — the sign-in beat writes an identity and
    the request path writes the lane taken — and neither may erase the other."""

    @pytest.mark.asyncio
    async def test_an_unmentioned_field_is_left_alone(self, store):
        await store.write("sess-1", identity={"display_name": "Tanya"})
        await store.write("sess-1", lane="fast")
        state = await store.read("sess-1")
        assert state.identity.display_name == "Tanya"
        assert state.lane == "fast"

    @pytest.mark.asyncio
    async def test_an_explicit_none_clears_the_field(self, store):
        """Signing out is a write, not the absence of one."""
        await store.write("sess-1", identity={"display_name": "Tanya"})
        await store.write("sess-1", identity=None)
        assert (await store.read("sess-1")).identity.display_name is None


class TestTheRecordsOwner:
    """The container's records carry their owner and reads are scoped by it, so
    this one is too — a session record must not unlock another user's gate."""

    @pytest.mark.asyncio
    async def test_the_record_carries_the_user_who_wrote_it(self, memory_store):
        await SessionStateStore(memory_store, user_id="user-1").write(
            "sess-1", lane="fast"
        )
        document = next(iter(memory_store.documents.values()))
        assert document["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_another_users_record_reads_back_as_the_opening_state(
        self, memory_store
    ):
        await SessionStateStore(memory_store, user_id="user-1").write(
            "sess-1", identity={"display_name": "Tanya"}
        )

        other = await SessionStateStore(memory_store, user_id="user-2").read("sess-1")
        assert other.identity.display_name is None

    @pytest.mark.asyncio
    async def test_another_users_record_cannot_unlock_the_gate(self, memory_store):
        await SessionStateStore(memory_store, user_id="user-1").write(
            "sess-1", identity={"display_name": "Tanya"}
        )

        identity = await SessionStateStore(
            memory_store, user_id="user-2"
        ).resolve_identity("sess-1")
        assert identity.is_anonymous

    @pytest.mark.asyncio
    async def test_the_writing_user_reads_their_own_record_back(self, memory_store):
        store = SessionStateStore(memory_store, user_id="user-1")
        await store.write("sess-1", identity={"display_name": "Tanya"})

        assert (await store.read("sess-1")).identity.display_name == "Tanya"


class TestTheIdentityTheGateReads:
    """The Identity boundary gate's parameter, resolved from the record.

    Fail-closed in every direction: anonymous is the *refusing* state, so a
    record that cannot be read must resolve to it rather than to a name.
    """

    @pytest.mark.asyncio
    async def test_a_session_with_no_record_is_anonymous(self, store):
        assert (await store.resolve_identity("sess-1")).is_anonymous

    @pytest.mark.asyncio
    async def test_a_written_name_is_resolved(self, store):
        await store.write("sess-1", identity={"display_name": "Tanya"})
        identity = await store.resolve_identity("sess-1")
        assert identity.display_name == "Tanya"
        assert not identity.is_anonymous

    @pytest.mark.asyncio
    async def test_a_blank_name_is_anonymous(self, store):
        await store.write("sess-1", identity={"display_name": "   "})
        assert (await store.resolve_identity("sess-1")).is_anonymous

    @pytest.mark.asyncio
    async def test_an_unreadable_container_is_anonymous(self, store, memory_store):
        """A Cosmos outage must refuse personal questions, not admit them."""

        async def boom(*args, **kwargs):
            raise RuntimeError("cosmos is down")

        memory_store.get_item_by_id = boom
        assert (await store.resolve_identity("sess-1")).is_anonymous
