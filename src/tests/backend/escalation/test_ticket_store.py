"""The Simulated ticket, read and written through the memory container
(issue #22).

Driven against the same fake the troubleshooting and session-state stores are
driven against — implementing only the generic CRUD the container already
exposes, because the point of the design is that a new record type costs one
enumeration member and one model, with no migration and no new database method.

Where this store deliberately differs from its sibling: the troubleshooting
record's reads are **total** (a session nobody wrote to reads back empty,
because the default that matters is "offer the whole runbook"). A ticket's are
not. No draft is ``None`` and must stay ``None``, because the caller that
matters is the plan-approval seam, and a seam that read an empty ticket would
raise a blank service ticket every time any plan on any lane was approved.
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
    """Import ``escalation.store`` against the *real* message models.

    Earlier-collected suites replace flat modules such as
    ``common.models.messages`` with bare ``Mock()`` objects in ``sys.modules``,
    so a plain import here would bind ``ServiceTicket`` to a mock attribute
    rather than to the model class. The same containment
    ``troubleshooting/test_store.py`` uses.
    """
    snapshot = dict(sys.modules)
    try:
        for name in ("common", "common.models", "escalation"):
            package = ModuleType(name)
            package.__path__ = [os.path.join(_backend_path, *name.split("."))]
            sys.modules[name] = package
        for name in (
            "common.models.messages",
            "escalation.ticket",
            "escalation.store",
        ):
            sys.modules.pop(name, None)
        import escalation.store as store_module

        return store_module
    finally:
        for key in list(sys.modules):
            if key not in snapshot:
                del sys.modules[key]
        sys.modules.update(snapshot)


store_module = _import_store()
ServiceTicket = store_module.ServiceTicket
TicketStore = store_module.TicketStore
ticket_record_id = store_module.ticket_record_id
TicketStatus = store_module.TicketStatus
NOT_REPORTED = store_module.NOT_REPORTED


class FakeMemoryStore:
    """The generic CRUD surface of the memory container, in a dictionary.

    Keyed the way Cosmos keys it — by ``(id, partition key)`` — so a record
    written under the wrong partition is invisible to a read, exactly as it
    would be in the deployed container.
    """

    def __init__(self):
        self.documents = {}
        self.updates = []
        self.fail_writes = False
        self.fail_reads = False

    async def get_item_by_id(self, item_id, partition_key, model_class):
        if self.fail_reads:
            raise RuntimeError("container unreachable")
        return self.documents.get((item_id, partition_key))

    async def update_item(self, item):
        if self.fail_writes:
            raise RuntimeError("container unreachable")
        self.updates.append(item)
        self.documents[(item.id, item.session_id)] = item


@pytest.fixture
def memory():
    return FakeMemoryStore()


@pytest.fixture
def store(memory):
    return TicketStore(memory, user_id="u-1")


class TestTheTicketIsAnOrdinaryDocument:
    def test_its_id_is_derived_from_the_session_not_freshly_generated(self):
        """One conversation raises one ticket. Derived, so a read is a point
        read and a re-draft replaces the draft it corrects instead of leaving
        two tickets for one fault."""
        assert ticket_record_id("s-1") == ticket_record_id("s-1")
        assert ticket_record_id("s-1") != ticket_record_id("s-2")

    def test_it_is_discriminated_by_its_own_data_type(self):
        assert ServiceTicket(session_id="s-1").data_type == "service_ticket"


class TestReadingATicketThatIsNotThere:
    @pytest.mark.asyncio
    async def test_reads_back_nothing_rather_than_an_empty_ticket(self, store):
        """Deliberately unlike the troubleshooting record beside it. An empty
        ticket read back here would be submitted by the approval seam, and
        every approved plan on every lane would raise a blank service ticket."""
        assert await store.read("s-1") is None

    @pytest.mark.asyncio
    async def test_and_so_does_an_unreadable_container(self, memory, store):
        memory.fail_reads = True

        assert await store.read("s-1") is None

    @pytest.mark.asyncio
    async def test_and_so_does_another_associates_ticket(self, memory, store):
        await store.draft("s-1", {"symptom": "cold coffee"}, attempted=["a step"])

        assert await TicketStore(memory, user_id="u-2").read("s-1") is None


class TestDrafting:
    @pytest.mark.asyncio
    async def test_the_draft_reaches_the_container(self, memory, store):
        await store.draft("s-1", {"symptom": "cold coffee"}, attempted=["a step"])

        stored = memory.documents[(ticket_record_id("s-1"), "s-1")]
        assert stored.fields["symptom"] == "cold coffee"

    @pytest.mark.asyncio
    async def test_the_attempted_steps_are_taken_from_the_record(self, store):
        ticket = await store.draft(
            "s-1", {}, attempted=["Fitted a fresh paper filter"]
        )

        assert "fresh paper filter" in ticket.fields["steps_attempted"]

    @pytest.mark.asyncio
    async def test_a_second_draft_corrects_the_first_rather_than_adding_one(
        self, memory, store
    ):
        """"The associate can correct it" is this: the agent re-drafts, and the
        correction replaces what it corrects. Two tickets for one fault is two
        engineers, or one engineer and one ticket nobody closes."""
        await store.draft("s-1", {"priority": "3"}, attempted=["a step"])
        await store.draft("s-1", {"priority": "1"}, attempted=["a step"])

        tickets = [
            key for key in memory.documents if key[0] == ticket_record_id("s-1")
        ]
        assert len(tickets) == 1
        assert memory.documents[tickets[0]].fields["priority"] == "1"

    @pytest.mark.asyncio
    async def test_a_correction_changes_the_field_it_corrects(self, memory, store):
        await store.draft("s-1", {"priority": "3"}, attempted=["a step"])
        await store.draft("s-1", {"priority": "1"}, attempted=["a step"])

        stored = memory.documents[(ticket_record_id("s-1"), "s-1")]
        assert stored.fields["priority"] == "1"

    @pytest.mark.asyncio
    async def test_and_leaves_the_fields_it_does_not_mention_alone(self, memory, store):
        """A correction is one field, said once. An agent re-drafting a whole
        ticket to change the priority would drop every field it did not
        happen to repeat — and the associate, who has already read the ticket,
        would not read it again to notice."""
        await store.draft(
            "s-1", {"symptom": "left head runs cold", "priority": "3"},
            attempted=["a step"],
        )

        await store.draft("s-1", {"priority": "1"}, attempted=["a step"])

        stored = memory.documents[(ticket_record_id("s-1"), "s-1")]
        assert stored.fields["symptom"] == "left head runs cold"
        assert stored.fields["priority"] == "1"

    @pytest.mark.asyncio
    async def test_a_ticket_already_raised_cannot_be_re_drafted(self, store):
        """The confirmation happened. Editing the ticket after it is raised
        would rewrite a record the associate was shown and told was submitted,
        and nothing on screen would look wrong."""
        await store.draft("s-1", {"priority": "3"}, attempted=["a step"])
        await store.submit("s-1")

        assert await store.draft("s-1", {"priority": "1"}, attempted=["a"]) is None

    @pytest.mark.asyncio
    async def test_a_draft_that_could_not_be_persisted_is_reported_as_no_draft(
        self, memory, store
    ):
        """An agent told the draft was kept would present a ticket to the
        associate that the approval seam will never find, and the approval
        would confirm nothing at all — silently."""
        memory.fail_writes = True

        assert await store.draft("s-1", {}, attempted=["a step"]) is None


class TestSubmitting:
    @pytest.mark.asyncio
    async def test_a_session_with_no_draft_submits_nothing(self, store):
        """The approval seam runs on **every** approved plan, and most plans
        are not tickets. No draft is the answer that keeps it that way."""
        assert await store.submit("s-1") is None

    @pytest.mark.asyncio
    async def test_the_draft_becomes_submitted(self, store):
        await store.draft("s-1", {"symptom": "cold coffee"}, attempted=["a step"])

        ticket = await store.submit("s-1")

        assert ticket.fields["status"] == TicketStatus.submitted

    @pytest.mark.asyncio
    async def test_and_only_then_is_a_number_issued(self, store):
        drafted = await store.draft("s-1", {}, attempted=["a step"])
        assert drafted.fields["ticket_id"] == NOT_REPORTED

        submitted = await store.submit("s-1")

        assert submitted.fields["ticket_id"].startswith("SIM-223-")

    @pytest.mark.asyncio
    async def test_what_was_submitted_is_what_the_associate_read(self, store):
        drafted = await store.draft(
            "s-1",
            {"symptom": "left head runs cold", "priority": "2"},
            attempted=["Fitted a fresh paper filter"],
            equipment="coffee brewer",
        )
        read_by_the_associate = dict(drafted.fields)

        submitted = await store.submit("s-1")

        for name, value in read_by_the_associate.items():
            if name in ("ticket_id", "opened_at", "status"):
                continue
            assert submitted.fields[name] == value, name

    @pytest.mark.asyncio
    async def test_submitting_twice_does_not_issue_a_second_ticket(self, store):
        """The approval seam is reached once per approved plan review, and a
        turn can carry more than one. A second submission that reissued the
        number would give the associate two numbers for one fault."""
        await store.draft("s-1", {}, attempted=["a step"])
        first = await store.submit("s-1")

        second = await store.submit("s-1")

        assert second.fields["ticket_id"] == first.fields["ticket_id"]
        assert second.fields["opened_at"] == first.fields["opened_at"]

    @pytest.mark.asyncio
    async def test_a_submission_that_could_not_be_persisted_submits_nothing(
        self, memory, store
    ):
        """A ticket the container never took is a ticket that does not exist,
        and a card on the associate's screen saying otherwise is the one lie
        this package exists to prevent."""
        await store.draft("s-1", {}, attempted=["a step"])
        memory.fail_writes = True

        assert await store.submit("s-1") is None
