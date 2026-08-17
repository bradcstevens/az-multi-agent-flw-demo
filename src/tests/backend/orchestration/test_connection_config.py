"""Unit tests for backend.orchestration.connection_config.

Covers OrchestrationConfig (approval/clarification event helpers),
ConnectionConfig (WebSocket registry + status broadcasting), and
TeamConfig. WebSockets are represented by AsyncMock/MagicMock.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


def _import_connection_config():
    """Import backend.orchestration.connection_config with the REAL flat
    ``models.*`` / ``common.models.*`` packages, undoing any bare-Mock or
    empty-ModuleType pollution installed by earlier test modules in the same
    single-process collection run, then restore sys.modules exactly.
    """
    snapshot = dict(sys.modules)
    force_real = [
        "common",
        "common.models",
        "common.models.messages",
        "models",
        "models.messages",
        "models.plan_models",
        "backend.orchestration.connection_config",
    ]
    try:
        for name in force_real:
            sys.modules.pop(name, None)
        import backend.orchestration.connection_config as cc  # noqa: WPS433
        return cc
    finally:
        cc_mod = sys.modules.get("backend.orchestration.connection_config")
        for key in list(sys.modules):
            if key not in snapshot and not key.startswith("backend"):
                sys.modules.pop(key, None)
        sys.modules.update(snapshot)
        if cc_mod is not None:
            sys.modules["backend.orchestration.connection_config"] = cc_mod


_cc = _import_connection_config()
ConnectionConfig = _cc.ConnectionConfig
OrchestrationConfig = _cc.OrchestrationConfig
TeamConfig = _cc.TeamConfig
connection_config = _cc.connection_config
orchestration_config = _cc.orchestration_config
team_config = _cc.team_config


# ----------------------------------------------------------------------- #
# OrchestrationConfig
# ----------------------------------------------------------------------- #
class TestOrchestrationApproval:
    def test_get_current_orchestration(self):
        cfg = OrchestrationConfig()
        cfg.orchestrations["u1"] = "wf"
        assert cfg.get_current_orchestration("u1") == "wf"
        assert cfg.get_current_orchestration("missing") is None

    def test_set_approval_pending_creates_and_resets(self):
        cfg = OrchestrationConfig()
        cfg.set_approval_pending("p1")
        assert cfg.approvals["p1"] is None
        ev = cfg._approval_events["p1"]
        ev.set()
        cfg.set_approval_pending("p1")  # existing -> clear
        assert not cfg._approval_events["p1"].is_set()

    def test_set_approval_result_triggers_event(self):
        cfg = OrchestrationConfig()
        cfg.set_approval_pending("p1")
        cfg.set_approval_result("p1", True)
        assert cfg.approvals["p1"] is True
        assert cfg._approval_events["p1"].is_set()

    @pytest.mark.asyncio
    async def test_wait_for_approval_already_decided(self):
        cfg = OrchestrationConfig()
        cfg.approvals["p1"] = True
        assert await cfg.wait_for_approval("p1") is True

    @pytest.mark.asyncio
    async def test_wait_for_approval_missing_raises_keyerror(self):
        cfg = OrchestrationConfig()
        with pytest.raises(KeyError):
            await cfg.wait_for_approval("nope")

    @pytest.mark.asyncio
    async def test_wait_for_approval_waits_then_returns(self):
        cfg = OrchestrationConfig()
        cfg.set_approval_pending("p1")

        async def approve():
            await asyncio.sleep(0.01)
            cfg.set_approval_result("p1", True)

        task = asyncio.create_task(approve())
        result = await cfg.wait_for_approval("p1", timeout=1.0)
        await task
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self):
        cfg = OrchestrationConfig()
        cfg.set_approval_pending("p1")
        with pytest.raises(asyncio.TimeoutError):
            await cfg.wait_for_approval("p1", timeout=0.01)
        assert "p1" not in cfg.approvals  # cleaned up

    def test_cleanup_approval(self):
        cfg = OrchestrationConfig()
        cfg.set_approval_pending("p1")
        cfg.cleanup_approval("p1")
        assert "p1" not in cfg.approvals
        assert "p1" not in cfg._approval_events


class TestOrchestrationClarification:
    def test_set_clarification_pending_and_reset(self):
        cfg = OrchestrationConfig()
        cfg.set_clarification_pending("r1")
        assert cfg.clarifications["r1"] is None
        cfg._clarification_events["r1"].set()
        cfg.set_clarification_pending("r1")
        assert not cfg._clarification_events["r1"].is_set()

    def test_set_clarification_result(self):
        cfg = OrchestrationConfig()
        cfg.set_clarification_pending("r1")
        cfg.set_clarification_result("r1", "answer")
        assert cfg.clarifications["r1"] == "answer"
        assert cfg._clarification_events["r1"].is_set()

    @pytest.mark.asyncio
    async def test_wait_for_clarification_already_answered(self):
        cfg = OrchestrationConfig()
        cfg.clarifications["r1"] = "done"
        assert await cfg.wait_for_clarification("r1") == "done"

    @pytest.mark.asyncio
    async def test_wait_for_clarification_missing_keyerror(self):
        cfg = OrchestrationConfig()
        with pytest.raises(KeyError):
            await cfg.wait_for_clarification("nope")

    @pytest.mark.asyncio
    async def test_wait_for_clarification_waits(self):
        cfg = OrchestrationConfig()
        cfg.set_clarification_pending("r1")

        async def answer():
            await asyncio.sleep(0.01)
            cfg.set_clarification_result("r1", "hi")

        task = asyncio.create_task(answer())
        result = await cfg.wait_for_clarification("r1", timeout=1.0)
        await task
        assert result == "hi"

    @pytest.mark.asyncio
    async def test_wait_for_clarification_timeout(self):
        cfg = OrchestrationConfig()
        cfg.set_clarification_pending("r1")
        with pytest.raises(asyncio.TimeoutError):
            await cfg.wait_for_clarification("r1", timeout=0.01)
        assert "r1" not in cfg.clarifications

    def test_cleanup_clarification(self):
        cfg = OrchestrationConfig()
        cfg.set_clarification_pending("r1")
        cfg.cleanup_clarification("r1")
        assert "r1" not in cfg.clarifications
        assert "r1" not in cfg._clarification_events


class TestTheTurnInFlight:
    """Which Chat a user's in-flight turn belongs to (#120, ADR-031 §6).

    The registry was keyed by ``user_id`` alone, so nothing here could tell
    which conversation the task it holds was answering. **Ending a turn** has
    to know: one associate with two Chats open must not have the second one
    cancelled by leaving the first. One associate, one tab, one live turn is
    true in rehearsal, which is exactly why the failure would surface once, in
    front of an audience.
    """

    @staticmethod
    async def _pending():
        """A task that is genuinely in flight, and cleans up when cancelled."""
        async def _sleep():
            await asyncio.sleep(60)

        return asyncio.create_task(_sleep())

    @pytest.mark.asyncio
    async def test_a_registered_turn_names_the_chat_it_belongs_to(self):
        cfg = OrchestrationConfig()
        task = await self._pending()
        cfg.register_active_turn("user-1", "sess-1", "plan-1", task)

        turn = cfg.active_turn("user-1")
        assert turn is not None
        assert turn.session_id == "sess-1"
        assert turn.task is task

        task.cancel()

    @pytest.mark.asyncio
    async def test_a_registered_turn_names_the_plan_it_is_answering(self):
        # A Chat holds more than one Plan (#71) and a second turn in the same
        # session mints another, so the session alone does not identify the
        # record this turn's end should settle. `process_request` writes the new
        # Plan *before* it replaces this entry, so "the session's latest" is,
        # for that window, a turn that has not started yet.
        cfg = OrchestrationConfig()
        task = await self._pending()
        cfg.register_active_turn("user-1", "sess-1", "plan-1", task)

        assert cfg.active_turn("user-1").plan_id == "plan-1"

        task.cancel()

    @pytest.mark.asyncio
    async def test_one_associates_turn_is_never_anothers(self):
        # The slot is per associate, and an associate with no turn in flight
        # has none rather than somebody else's — the registry is what
        # **Ending a turn** reads before it cancels anything.
        cfg = OrchestrationConfig()
        mine = await self._pending()
        theirs = await self._pending()
        cfg.register_active_turn("user-1", "sess-1", "plan-1", mine)
        cfg.register_active_turn("user-2", "sess-2", "plan-2", theirs)

        assert cfg.active_turn("user-1").task is mine
        assert cfg.active_turn("user-2").task is theirs
        assert cfg.active_turn("user-3") is None

        mine.cancel()
        theirs.cancel()

    @pytest.mark.asyncio
    async def test_a_finished_turn_is_no_longer_in_flight(self):
        cfg = OrchestrationConfig()

        async def _done():
            return None

        task = asyncio.create_task(_done())
        await task
        cfg.register_active_turn("user-1", "sess-1", "plan-1", task)

        assert cfg.active_turn("user-1") is None

    @pytest.mark.asyncio
    async def test_a_turn_releases_only_its_own_slot(self):
        # The orchestration task clears its slot as it ends, and by then the
        # associate's *next* request may already have registered a new turn
        # there. Releasing by identity is what keeps the cleanup of a cancelled
        # turn from taking its successor with it.
        cfg = OrchestrationConfig()
        first = await self._pending()
        second = await self._pending()
        cfg.register_active_turn("user-1", "sess-1", "plan-1", first)
        cfg.register_active_turn("user-1", "sess-2", "plan-2", second)

        cfg.release_active_turn("user-1", first)

        turn = cfg.active_turn("user-1")
        assert turn is not None and turn.task is second

        first.cancel()
        second.cancel()

    @pytest.mark.asyncio
    async def test_releasing_the_registered_turn_empties_the_slot(self):
        cfg = OrchestrationConfig()
        task = await self._pending()
        cfg.register_active_turn("user-1", "sess-1", "plan-1", task)

        cfg.release_active_turn("user-1", task)

        assert cfg.active_turn("user-1") is None
        task.cancel()


# ----------------------------------------------------------------------- #
# ConnectionConfig
# ----------------------------------------------------------------------- #
class TestConnectionRegistry:
    @pytest.mark.asyncio
    async def test_add_connection_simple(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.add_connection("proc1", ws)
        assert cc.get_connection("proc1") is ws

    @pytest.mark.asyncio
    async def test_add_connection_with_user(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.add_connection("proc1", ws, user_id="u1")
        assert cc.user_to_process["u1"] == "proc1"

    @pytest.mark.asyncio
    async def test_add_connection_replaces_existing_process(self):
        cc = ConnectionConfig()
        old = AsyncMock()
        cc.add_connection("proc1", old)
        new = AsyncMock()
        cc.add_connection("proc1", new)  # triggers close of old via create_task
        await asyncio.sleep(0)
        assert cc.get_connection("proc1") is new

    @pytest.mark.asyncio
    async def test_add_connection_closes_old_process_for_user(self):
        cc = ConnectionConfig()
        first = AsyncMock()
        cc.add_connection("procA", first, user_id="u1")
        second = AsyncMock()
        cc.add_connection("procB", second, user_id="u1")
        await asyncio.sleep(0)
        assert cc.user_to_process["u1"] == "procB"
        assert "procA" not in cc.connections

    def test_remove_connection(self):
        cc = ConnectionConfig()
        cc.connections["proc1"] = MagicMock()
        cc.user_to_process["u1"] = "proc1"
        cc.remove_connection("proc1")
        assert "proc1" not in cc.connections
        assert "u1" not in cc.user_to_process

    @pytest.mark.asyncio
    async def test_close_connection_found(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.connections["proc1"] = ws
        await cc.close_connection("proc1")
        ws.close.assert_awaited_once()
        assert "proc1" not in cc.connections

    @pytest.mark.asyncio
    async def test_close_connection_missing(self):
        cc = ConnectionConfig()
        await cc.close_connection("nope")  # warns, no error

    @pytest.mark.asyncio
    async def test_close_connection_error(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        ws.close.side_effect = RuntimeError("boom")
        cc.connections["proc1"] = ws
        await cc.close_connection("proc1")
        assert "proc1" not in cc.connections

    @pytest.mark.asyncio
    async def test_a_superseded_socket_does_not_evict_the_one_that_replaced_it(self):
        """The Connection window, closed from the other end (#63, ADR-021).

        A second socket for one process supersedes the first, and
        ``add_connection`` closes the first — whose endpoint then reaches its
        ``finally`` and asks for the process to be closed. Keyed on the process
        alone, that request finds the *replacement* and unregisters it, and
        every frame after that is dropped with nothing said. The browser
        reconnects into exactly this shape, and so does React 18 StrictMode
        mounting the plan page twice.
        """
        cc = ConnectionConfig()
        superseded = AsyncMock()
        replacement = AsyncMock()
        cc.add_connection("proc1", superseded, user_id="u1")
        cc.add_connection("proc1", replacement, user_id="u1")
        await asyncio.sleep(0)

        await cc.close_connection("proc1", connection=superseded)

        assert cc.get_connection("proc1") is replacement
        assert cc.user_to_process["u1"] == "proc1"
        replacement.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_socket_that_is_still_the_current_one_is_closed(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.add_connection("proc1", ws, user_id="u1")

        await cc.close_connection("proc1", connection=ws)

        ws.close.assert_awaited_once()
        assert "proc1" not in cc.connections
        assert "u1" not in cc.user_to_process


class TestSoleUser:
    """Who an out-of-band push goes to (issue #23).

    The Grounding panel's signal is emitted from the ``/sop/ask`` bridge, which
    the MCP container calls with no user of its own, and the Presenter alert is
    fired by a hidden route. Neither asks the model for a ``user_id`` the way
    ``ask_user`` does: a model mis-copying a UUID must not be able to make the
    demo's centrepiece panel go dark. This is the same sole-connection rule
    ``send_status_update_async`` already applies, named so a caller can ask for
    it deliberately.
    """

    def test_one_connected_user_is_the_recipient(self):
        cc = ConnectionConfig()
        cc.user_to_process["u1"] = "proc1"

        assert cc.sole_user() == "u1"

    def test_nobody_connected_is_nobody_to_tell(self):
        assert ConnectionConfig().sole_user() is None

    def test_two_connected_users_is_a_guess_and_it_refuses(self):
        """The demo runs single-replica with one presenter. If that ever stops
        being true, a panel that guessed would attribute one associate's answer
        to another's screen."""
        cc = ConnectionConfig()
        cc.user_to_process["u1"] = "proc1"
        cc.user_to_process["u2"] = "proc2"

        assert cc.sole_user() is None


class TestDeliveryIsReported:
    """Whether a push reached a socket (issue #23).

    Every pre-existing caller ignores the answer, which is right for them — a
    lost streaming chunk is not worth a branch. The Presenter alert is the one
    caller that needs it, because the presenter pressed a key and being told
    nothing happened is the difference between a bug and a chord that missed.
    """

    @pytest.mark.asyncio
    async def test_a_push_that_reached_a_socket_says_so(self):
        cc = ConnectionConfig()
        cc.connections["proc1"] = AsyncMock()
        cc.user_to_process["u1"] = "proc1"

        assert await cc.send_status_update_async({"k": "v"}, user_id="u1") is True

    @pytest.mark.asyncio
    async def test_nobody_connected_is_not_delivered(self):
        cc = ConnectionConfig()

        assert await cc.send_status_update_async({"k": "v"}, user_id="u1") is False

    @pytest.mark.asyncio
    async def test_a_socket_that_refused_the_write_is_not_delivered(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        ws.send_text.side_effect = RuntimeError("socket gone")
        cc.connections["proc1"] = ws
        cc.user_to_process["u1"] = "proc1"

        assert await cc.send_status_update_async({"k": "v"}, user_id="u1") is False

    @pytest.mark.asyncio
    async def test_a_mapping_with_no_socket_behind_it_is_not_delivered(self):
        cc = ConnectionConfig()
        cc.user_to_process["u1"] = "proc-gone"

        assert await cc.send_status_update_async({"k": "v"}, user_id="u1") is False


class TestSendStatusUpdateAsync:
    @pytest.mark.asyncio
    async def test_no_user_id(self):
        cc = ConnectionConfig()
        await cc.send_status_update_async("m", user_id="")  # early return

    @pytest.mark.asyncio
    async def test_fallback_single_user(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.connections["proc1"] = ws
        cc.user_to_process["real"] = "proc1"
        await cc.send_status_update_async({"k": "v"}, user_id="wrong")
        ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_process_multiple_users(self):
        cc = ConnectionConfig()
        cc.user_to_process["a"] = "p1"
        cc.user_to_process["b"] = "p2"
        await cc.send_status_update_async("m", user_id="wrong")  # returns, no send

    @pytest.mark.asyncio
    async def test_message_with_to_dict(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.connections["p1"] = ws
        cc.user_to_process["u1"] = "p1"
        msg = MagicMock()
        msg.to_dict.return_value = {"x": 1}
        await cc.send_status_update_async(msg, user_id="u1")
        ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_to_dict_error_falls_back_to_str(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.connections["p1"] = ws
        cc.user_to_process["u1"] = "p1"
        msg = MagicMock()
        msg.to_dict.side_effect = RuntimeError("bad")
        await cc.send_status_update_async(msg, user_id="u1")
        ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_error_removes_connection(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        ws.send_text.side_effect = RuntimeError("boom")
        cc.connections["p1"] = ws
        cc.user_to_process["u1"] = "p1"
        await cc.send_status_update_async("m", user_id="u1")
        assert "p1" not in cc.connections

    @pytest.mark.asyncio
    async def test_no_connection_for_process(self):
        cc = ConnectionConfig()
        cc.user_to_process["u1"] = "p1"  # mapped but no connection object
        await cc.send_status_update_async("m", user_id="u1")
        assert "u1" not in cc.user_to_process


class TestSendStatusUpdateSync:
    @pytest.mark.asyncio
    async def test_sync_send_found(self):
        cc = ConnectionConfig()
        ws = AsyncMock()
        cc.connections["p1"] = ws
        cc.send_status_update("hello", "p1")
        await asyncio.sleep(0)
        ws.send_text.assert_awaited_once_with("hello")

    def test_sync_send_not_found(self):
        cc = ConnectionConfig()
        cc.send_status_update("hello", "missing")  # warns, no error


# ----------------------------------------------------------------------- #
# TeamConfig
# ----------------------------------------------------------------------- #
class TestTeamConfig:
    def test_set_and_get(self):
        tc = TeamConfig()
        team = MagicMock()
        tc.set_current_team("u1", team)
        assert tc.get_current_team("u1") is team

    def test_get_missing(self):
        tc = TeamConfig()
        assert tc.get_current_team("nope") is None


def test_module_singletons():
    assert isinstance(orchestration_config, OrchestrationConfig)
    assert isinstance(connection_config, ConnectionConfig)
    assert isinstance(team_config, TeamConfig)
