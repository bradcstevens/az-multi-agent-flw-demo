#!/usr/bin/env python3
"""The Routing probe: ask the deployed orchestrator, without a browser (#54).

The centrepiece beat's remaining failure is a **routing** one — the
`Troubleshooting Agent` billed on *"How do I close the store?"*, a question with
nothing broken in it, and on the run it takes the last word the presenter is
asked what is stopping them from closing rather than shown the procedure.

Seven prompt clauses have been forked on ``minimal_plan`` chasing it. Each cost
a twenty-minute deploy and each *reduced* the rate without removing it, because
the only instrument that can see the fault is the **Demo validator**: a real
browser, a dated deployment, ten runs, stop at the first red. An instrument that
expensive is guessed around, and it was, seven times.

This is the cheaper instrument. It drives the same Fast-lane turn the presenter
taps — `POST /api/v4/process_request` with the rehearsed question, on the
deployed Store Assistant roster — and reads the same transparency frames the
browser renders, off the same WebSocket, N samples at a time. It grades them
into `e2e/evidence.ts`'s own four outcomes and reports the **rate**.

Three things it is deliberately not:

- **Not a feedback loop.** Every sample is a live orchestration and a live
  Direct Line conversation. `src/tests/ci/test_routing_probe.py` covers the
  arithmetic; nothing unattended may run the probe. Same rule as the Demo
  validator, for the same reason.
- **Not a replacement for the browser.** It observes the frames the deployment
  *pushed*, not the surface the presenter *sees*. A frame that arrives and
  renders wrong is invisible here and red there — which has happened, twice.
  The rehearsal remains the proof; this is what points it at the right layer.
- **Not proof.** Sampling never is, and the report says by how much.

Everything above the "Live reads" separator is pure and unit-tested.

    az login
    bash scripts/measure-routing.sh --samples 12
"""

import argparse
import base64
import json
import os
import re
import secrets
import socket
import ssl
import subprocess
import sys

import time
import urllib.error
import urllib.request
import uuid

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESOURCE_GROUP = "rg-macae-flw-v1"
BACKEND_CONTAINER_APP = "ca-macaeflwv1flrpd"

STORE_PACK = os.path.join(
    REPO_ROOT, "content_packs", "store_assistant", "agent_teams",
    "store_assistant.json")
SOP_MANIFEST = os.path.join(REPO_ROOT, "content", "sop", "corpus.toml")

#: Beside the Demo validator's own evidence, and appended to rather than
#: replaced: the rate this probe measures is a property of a *series* of runs,
#: and a file that only holds the last one cannot show a fix taking effect.
EVIDENCE = os.path.join(REPO_ROOT, "e2e", "artifacts", "routing-evidence.jsonl")

# The ledger's outcome vocabulary, shared with `e2e/evidence.ts` and
# `scripts/sop_rehearsal.py`. A fifth name for the same four things is how two
# instruments end up disagreeing about a run they both saw.
GROUNDED = "grounded"
HONEST_MISS = "honest-miss"
NO_TOOL_CALL = "no-tool-call"
CLARIFIED = "clarified"
NOT_OBSERVED = "not-observed"

#: Quiet after the last frame before the turn is called over. Generous, and
#: the generosity is the point: the manager is a reasoning model and streams
#: nothing while it decides who speaks next, so the gap between one
#: specialist finishing and the next starting is tens of seconds — and *that
#: gap is where the residual lives*. A probe that settled in eight seconds
#: would cut the recording exactly before the troubleshooter's turn and report
#: a clean rate for the fault it was built to measure.
SETTLE_SECONDS = 30


class Turn:
    """What one sample's socket said the deployment did.

    Frames only. A field this class cannot fill from a frame it received is
    left unfilled rather than inferred, because the probe's whole value is that
    it is cheap enough to run twenty times — and twenty inferences are twenty
    times the confidence in a guess.
    """

    def __init__(self, frames=0, agents_billed=(), grounded=False,
                 citations=(), tool_query=None, retrieval_query=None,
                 answer="", agents_spoke=()):
        self.frames = frames
        self.agents_billed = tuple(agents_billed)
        self.grounded = grounded
        self.citations = tuple(citations)
        self.tool_query = tool_query
        self.retrieval_query = retrieval_query
        self.answer = answer
        self.agents_spoke = tuple(agents_spoke)

    @property
    def observed(self):
        """Whether this sample observed a turn at all.

        **Broken is not intermittent** — the lesson `deployed_surface.py`
        already paid for, one layer out. A socket that carried nothing saw no
        orchestration: the replica restarted under it, or the connect lost its
        race with a fast turn. Graded as `no-tool-call` it would attribute the
        orchestrator's routing for a run in which the orchestrator was never
        heard from.
        """
        return self.frames > 0

    @property
    def honest_miss(self):
        """The hop happened and cited nothing.

        Exactly the condition `GroundingPanel` renders `grounding-miss` on, and
        it is derived here rather than sent: the backend pushes `source_used`
        with an empty citation list and the panel names the miss.
        """
        return self.grounded and not self.citations


def observe(frames):
    """Fold one sample's WebSocket envelopes into a `Turn`. Pure.

    Ordering matters for two fields. The Grounding panel is a claim about
    whichever SOP call answered **last**, so the last `source_used` wins — the
    same rule the panel itself follows, and the reason the rehearsal marker had
    to stop being one-shot. And the answer is the **latest agent's** turn,
    which is what the presenter is standing in front of.

    There is no final-result frame on the Fast lane. Measured against
    `rg-macae-flw-v1` on 2026-08-14: a complete rehearsed turn pushed 512
    `agent_message_streaming` frames, one `source_used`, one `token_usage` and
    no `final_result_message` at all. One is still read when it arrives — the
    Deliberate lane and the error path both send one — but waiting for one
    grades every working Fast-lane turn as unanswered.
    """
    billed = []
    spoke = []
    said = {}
    final = None
    turn = Turn(frames=len(frames))
    for envelope in frames:
        kind = envelope.get("type")
        data = envelope.get("data") or {}
        if kind == "token_usage":
            name = data.get("agent_name") or data.get("executor_id")
            if name and name not in billed:
                billed.append(name)
        elif kind == "source_used":
            turn.grounded = True
            turn.citations = tuple(
                citation.get("name")
                for citation in data.get("citations") or []
                if citation.get("name")
            )
            turn.tool_query = data.get("tool_query")
            turn.retrieval_query = data.get("retrieval_query")
        elif kind == "agent_message_streaming":
            name = data.get("agent_name") or "Assistant"
            if name not in spoke:
                spoke.append(name)
                said[name] = ""
            said[name] += data.get("content") or ""
        elif kind == "final_result_message":
            # `run_orchestration` hands an envelope to a method that
            # envelopes, so the content arrives one level deeper than the
            # dataclass this frame is named after — the same double wrap
            # `WebSocketService.handleMessage` had to learn about.
            inner = data.get("data") if isinstance(
                data.get("data"), dict) else data
            final = inner.get("content") or final
    turn.agents_billed = tuple(billed)
    turn.agents_spoke = tuple(spoke)
    turn.answer = final if final else (said.get(spoke[-1], "") if spoke else "")
    return turn


def asked_back(answer):
    """Whether a turn asked the presenter something instead of answering. Pure.

    The same three-signal rule as `isQuestionBack` in
    `e2e/specs/cross-platform.spec.ts`, and deliberately conservative for the
    same reason: a missed clarification costs a less specific report on a
    sample that is failing anyway, and a *false* one reports a working
    deployment as the residual and sends the next iteration at a prompt that is
    already right.

    So all three must agree, and none of them is the wording: nothing that is
    not a list item, at least one list item, and at least one of them
    punctuated as a question. `SOP-102`'s twelve steps are instructions and not
    one of them ends in a question mark.
    """
    spoken, asked = [], []
    for line in (answer or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^([-*+]|\d+[.)])\s+", line):
            asked.append(line)
        else:
            spoken.append(line)
    return (
        not spoken
        and bool(asked)
        and any(line.endswith("?") for line in asked)
    )


def outcome(turn):
    """Which of the ledger's outcomes this sample saw. Pure.

    The order is `outcomeOf`'s, and it is load-bearing. `clarified` is decided
    **before** `grounded` is reported because it is the outcome that hides
    inside a success: the hop completed, the citation arrived, and the turn
    still asked a question back.
    """
    if not turn.observed:
        return NOT_OBSERVED
    if not turn.grounded:
        return NO_TOOL_CALL
    if turn.honest_miss:
        return HONEST_MISS
    return CLARIFIED if asked_back(turn.answer) else GROUNDED


# The manager is on every turn by construction — it plans and it compiles. It
# is not a specialist doing its own job on a request that did not ask for it,
# which is the thing being counted, and counting it would report every sample
# as carrying the residual.
MANAGER = "magenticmanager"


def _key(name):
    """An agent name with the separators taken out, for comparison. Pure.

    `ShiftTasksAgent` on the roster is `Shift Tasks Agent` on the meter, and
    the formatter that does that lives in the backend. This check runs with
    nothing but `python3` on PATH and must not import it; a second copy of that
    formatter here is a second thing to drift.
    """
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def procedure_agent(pack=STORE_PACK):
    """The roster name of the agent the rehearsed question needs. Pure.

    Derived, never pinned. The rehearsed hit is a procedure lookup, so the
    agent that can answer it is the one the pack handed the SOP toolbox to —
    `toolbox_filter: "sop"`. A probe carrying its own copy of the name grades a
    roster this repository has since renumbered, which is the mistake
    `deployed_surface.py` avoids by reading the pack for everything it expects.
    """
    with open(pack, encoding="utf-8") as handle:
        team = json.load(handle)
    for agent in team.get("agents") or []:
        if agent.get("toolbox_filter") == "sop":
            return agent.get("name")
    raise RuntimeError(f"{pack} gives the sop toolbox to no agent")


def unneeded_agents(turn, needed):
    """Which agents the request did not need took part. Pure.

    The residual this probe exists to measure. On a team of **alternatives**
    rather than a pipeline, an agent that was not needed does not stay quiet:
    it does its own job on a request that did not ask for it, and the presenter
    is answered by the wrong specialist.

    Billed **or** spoken, and the two are not merged upstream: the meter is
    silent when the framework reports no usage — `token_usage` returns `None`
    rather than a zero — so an agent can take the turn without appearing on the
    cost table. Counting only the billed ones would miss exactly the run where
    the troubleshooter spoke last for free.
    """
    allowed = {_key(needed), MANAGER}
    seen = list(turn.agents_billed) + [
        name for name in turn.agents_spoke if name not in turn.agents_billed
    ]
    return tuple(name for name in seen if _key(name) not in allowed)


def routing_fault(turn, needed):
    """Why one sample is not the beat, or `None` when it is. Pure.

    **One grading rule**, and every count in the report is held to it — the
    lesson `sop_agent.py` and then `deployed_surface.py` each paid for once.

    Every fault is reported rather than the first, because they send a reader
    to different layers. A turn that asked a question back *and* billed the
    troubleshooter is one fault's cause beside its effect; a turn that asked
    back with only the procedure agent billed is neither, and is a different
    bug in a different place.
    """
    if not turn.observed:
        return (
            "the sample did not observe a turn at all — no frame arrived on "
            "its socket, so nothing here is evidence about the deployment's "
            "behaviour. Broken is not intermittent: check the replica was not "
            "restarting under the probe"
        )
    problems = []
    if not turn.grounded:
        problems.append(
            "no Grounding panel arrived: the SOP tool was never called, so "
            "the orchestrator answered from context or gave the turn to a "
            "specialist with no procedure knowledge"
        )
    elif turn.honest_miss:
        problems.append(
            f"the hop happened and cited nothing — the honest miss, retrieved "
            f"against {turn.retrieval_query!r}. That is the corpus or the "
            "agent's index, not the routing"
        )
    if asked_back(turn.answer):
        problems.append(
            "the turn asked the presenter a question back instead of "
            "answering"
        )
    unneeded = unneeded_agents(turn, needed)
    if unneeded:
        problems.append(
            f"{', '.join(unneeded)} took part in a question with nothing "
            "broken in it"
        )
    return "; ".join(problems) or None


def turn_is_over(frames, metered, quiet_for, settle=SETTLE_SECONDS):
    """Whether a drain that has been quiet for `quiet_for` may stop. Pure.

    There is no `final_result_message` on the Fast lane: a complete rehearsed
    turn pushes streaming chunks, one `source_used`, and one `token_usage` per
    executor — and nothing that says *done*. So the turn ends on quiet, which
    makes every mistake here a false clean or a false fault wearing the
    deployment's own face.

    Quiet counts only **after the meter has fired**. `token_usage` arrives at
    the end of an executor's turn, so it is the earliest frame that means
    anything has finished; before it, quiet is a model thinking. Measured, and
    it cost a sample: one 12-sample run graded a turn `no-tool-call` on the
    strength of one frame — the header the backend streams before an agent's
    content — followed by more than thirty seconds of thought.
    """
    if not frames or not metered:
        return False
    return quiet_for > settle


def evidence_line(turn, needed, index):
    """One sample, as the line an operator greps a week later. Pure.

    Graded facts rather than frames: the rate is what this probe measures, but
    the *rate is not the diagnosis*. Which agents took part, what wording
    actually reached the SOP tool, and what the last speaker said are what send
    the next reader to a layer, and they are four hundred times smaller than
    the frames they came from.
    """
    return {
        "sample": index,
        "outcome": outcome(turn),
        "fault": routing_fault(turn, needed),
        "agents_billed": list(turn.agents_billed),
        "agents_spoke": list(turn.agents_spoke),
        "unneeded": list(unneeded_agents(turn, needed)),
        "tool_query": turn.tool_query,
        "retrieval_query": turn.retrieval_query,
        "citations": list(turn.citations),
        "answer": turn.answer[:600],
        "frames": turn.frames,
    }


def smallest_fault_caught(samples):
    """The smallest per-sample fault rate `samples` is likelier than not to
    catch, as a percentage. Pure.

    The same arithmetic `deployed_surface.smallest_fault_caught` prints, and it
    is stated in both places on purpose rather than imported: two instruments
    that sample the same fault and quote different odds for it is how a number
    stops being believed. A fault firing on a fraction `p` survives `n`
    independent samples with probability `(1 - p)ⁿ`, so the rate at which that
    reaches an even chance is `1 - ½^(1/n)` — **50% at one, 12.9% at five,
    5.6% at twelve**.
    """
    return (1.0 - 0.5 ** (1.0 / max(1, samples))) * 100.0


class Summary:
    """What N samples said, and nothing they did not say."""

    def __init__(self, samples, observed, clean, outcomes, unneeded,
                 unneeded_spoke, faults):
        self.samples = samples
        self.observed = observed
        self.clean = clean
        self.outcomes = outcomes
        self.unneeded = unneeded
        self.unneeded_spoke = unneeded_spoke
        self.faults = faults


def summarise(turns, needed):
    """Fold every sample into the rate. Pure.

    The denominator is **turns observed**, not requests sent. A replica
    restarting under the probe is not evidence about the routing, and dividing
    by it reports a rate that is partly about this probe's own luck.
    """
    outcomes = {}
    unneeded = {}
    unneeded_spoke = {}
    faults = []
    observed = 0
    clean = 0
    for turn in turns:
        name = outcome(turn)
        outcomes[name] = outcomes.get(name, 0) + 1
        if not turn.observed:
            continue
        observed += 1
        fault = routing_fault(turn, needed)
        if fault is None:
            clean += 1
        else:
            faults.append(fault)
        for agent in unneeded_agents(turn, needed):
            unneeded[agent] = unneeded.get(agent, 0) + 1
            if agent in turn.agents_spoke:
                unneeded_spoke[agent] = unneeded_spoke.get(agent, 0) + 1
    return Summary(len(turns), observed, clean, outcomes, unneeded,
                   unneeded_spoke, faults)


def format_report(summary):
    """What the operator reads, which is the only thing they read. Pure.

    A green run ends on what it is *not* evidence of, because a report saying
    only "12 of 12" is the exact shape of evidence that let `grounded-answer`
    be believed across an afternoon the browser watched the same beat fail
    twice in eight.
    """
    lines = []
    for name in (GROUNDED, CLARIFIED, HONEST_MISS, NO_TOOL_CALL, NOT_OBSERVED):
        count = summary.outcomes.get(name, 0)
        if count:
            lines.append(f"  {count:3d}  {name}")

    if not summary.observed:
        lines.append(
            "  ----  no sample observed a turn "
            f"({summary.samples} sent). "
            "That is a state to fix and not a rate to measure: nothing here "
            "is evidence about the routing"
        )
        return "\n".join(lines)

    tallied = set()
    for agent, count in sorted(
            summary.unneeded.items(), key=lambda item: -item[1]):
        tallied.add(agent)
        spoke = summary.unneeded_spoke.get(agent, 0)
        reached = f"spoke on {spoke} of them" if spoke else "spoke on none of them"
        lines.append(
            f"  FAIL  {agent} took part in {count} of {summary.observed} "
            f"turns, on a question with nothing broken in it, and {reached}"
        )

    # A per-turn fault whose agent the tally above already named would say the
    # same thing a second time without its rate, which reads as two faults.
    for fault in dict.fromkeys(summary.faults):
        if any(agent in fault for agent in tallied):
            continue
        lines.append(f"  FAIL  {fault}")

    verdict = "PASS" if summary.clean == summary.observed else "----"
    lines.append(
        f"  {verdict}  {summary.clean} of {summary.observed} turns were "
        "answered from the corpus by the agent the question needed, and by "
        "nobody else. Sampling is not proof: a fault firing on fewer than "
        f"{smallest_fault_caught(summary.observed):.1f}% of turns is likelier "
        f"than not to survive {summary.observed} samples"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The WebSocket read
#
# By hand, and stdlib only. `.github/requirements.txt` is a stamped input to
# every feedback loop in this repository — `dev-venv.sh` reinstalls the whole
# developer virtualenv when its hash changes — so a dependency added to read
# one socket is a cost paid by every loop, in an environment that may not be
# able to reach an index at all. What the backend sends is server-to-client
# text: a header and a length, never masked. That is the whole of what is
# implemented, and it is implemented in a pure class so it can be tested with
# no socket.
# ---------------------------------------------------------------------------

class FrameReader:
    """RFC 6455 server frames, assembled out of whatever bytes arrived.

    A socket read returns a byte count, not a message. The `source_used` frame
    carries every citation and its snippet, so it routinely spans reads — and
    it is the one frame the Grounding panel is made of.
    """

    def __init__(self):
        self._buffer = b""
        self._partial = b""
        self.closed = False

    def feed(self, chunk):
        """Add bytes, and return every complete text message they finished."""
        self._buffer += chunk
        messages = []
        while True:
            frame = self._take()
            if frame is None:
                return messages
            opcode, fin, payload = frame
            if opcode == 0x8:
                self.closed = True
                return messages
            if opcode in (0x9, 0xA):  # ping/pong — the backend's heartbeat
                continue
            self._partial += payload
            if fin:
                messages.append(self._partial.decode("utf-8", "replace"))
                self._partial = b""

    def _take(self):
        """One whole frame off the front of the buffer, or None."""
        buffer = self._buffer
        if len(buffer) < 2:
            return None
        first, second = buffer[0], buffer[1]
        length = second & 0x7F
        offset = 2
        if length == 126:
            if len(buffer) < 4:
                return None
            length = int.from_bytes(buffer[2:4], "big")
            offset = 4
        elif length == 127:
            if len(buffer) < 10:
                return None
            length = int.from_bytes(buffer[2:10], "big")
            offset = 10
        # A server frame is never masked (RFC 6455 §5.1). Reading the bit
        # anyway means a proxy that does mask is a decode error rather than
        # silent nonsense on the Grounding panel.
        if second & 0x80:
            offset += 4
        if len(buffer) < offset + length:
            return None
        payload = buffer[offset:offset + length]
        self._buffer = buffer[offset + length:]
        return first & 0x0F, bool(first & 0x80), payload


# ---------------------------------------------------------------------------
# Live reads. Everything above this line is pure.
# ---------------------------------------------------------------------------

#: How long a Fast-lane turn is given before the sample is abandoned. The
#: measured lane runs in tens of seconds; this is generous on purpose, because
#: a sample cut short is recorded as "observed nothing" and dilutes the report
#: with the probe's own impatience.
TURN_TIMEOUT_SECONDS = 240

#: Quiet between samples, so the backend has unregistered the last one before
#: the next connects. Same reason `collect` is serial: two registered users and
#: `sole_user()` returns nothing.
BETWEEN_SAMPLES_SECONDS = 10


def _az(*args):
    """Run an `az` command and return its parsed JSON output."""
    result = subprocess.run(
        ["az", *args, "-o", "json"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"az {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "null")


def backend_url(resource_group=RESOURCE_GROUP, app=BACKEND_CONTAINER_APP):
    """The deployed backend's ingress, read from the deployment."""
    fqdn = _az(
        "containerapp", "show", "-g", resource_group, "-n", app,
        "--query", "properties.configuration.ingress.fqdn",
    )
    if not fqdn:
        raise RuntimeError(f"{app} in {resource_group} has no ingress")
    return f"https://{fqdn}"


def rehearsed_question(manifest=SOP_MANIFEST):
    """The question the walkthrough opens with, from the corpus that answers it.

    Read section-scoped, exactly as `e2e/authored.ts` and
    `deployed_surface.rehearsed_question` read it: `question` is a key under
    both `[rehearsed_hit]` and `[honest_miss]`, and a whole-file match would
    probe the deployment with the question the corpus deliberately cannot
    answer.
    """
    with open(manifest, encoding="utf-8") as handle:
        source = handle.read()
    start = source.find("[rehearsed_hit]")
    if start < 0:
        raise RuntimeError(f"{manifest} has no [rehearsed_hit] section")
    section = source[start + len("[rehearsed_hit]"):]
    end = re.search(r"^\[", section, re.MULTILINE)
    if end:
        section = section[: end.start()]
    match = re.search(r'^question\s*=\s*"([^"]*)"', section, re.MULTILINE)
    if not match:
        raise RuntimeError(f"{manifest} names no rehearsed question")
    return match.group(1)


def rehearsed_quick_task(pack=STORE_PACK, question=None):
    """The Quick Task the presenter taps, and the team it belongs to.

    The lane and the starting-task id are carried on the wire by the surface,
    and they decide which lane the request is routed into — so a probe that
    omitted them would measure the Deliberate lane's routing and report it of
    the Fast one.
    """
    with open(pack, encoding="utf-8") as handle:
        team = json.load(handle)
    question = question or rehearsed_question()
    for task in team.get("starting_tasks") or []:
        if task.get("prompt") == question:
            return team["team_id"], task["id"], task.get("lane")
    raise RuntimeError(
        f"{pack} has no Quick Task whose prompt is the rehearsed question "
        f"{question!r} — the pack and the corpus have drifted apart"
    )


def _post(url, body, principal, timeout=120):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("x-ms-client-principal-id", principal)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode() or "null")


class _Socket:
    """The transparency socket, opened before the request that fills it.

    Connected **first**, which ADR-021 made the browser do for the same reason:
    `process_request` schedules the orchestration before it returns, so
    everything emitted between that schedule and a later connect is pushed at a
    socket that does not exist and dropped. The browser cannot connect earlier
    than the response because it needs the plan id for the URL; this probe can,
    because `send_status_update_async` addresses a socket by **user**, and the
    path segment is only a key in a second map.
    """

    def __init__(self, base_url, process_id, user_id):
        host = base_url.split("://", 1)[1]
        self._reader = FrameReader()
        raw = socket.create_connection((host, 443), timeout=30)
        self._socket = ssl.create_default_context().wrap_socket(
            raw, server_hostname=host)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        self._socket.sendall((
            f"GET /api/v4/socket/{process_id}?user_id={user_id} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode())
        handshake = b""
        while b"\r\n\r\n" not in handshake:
            chunk = self._socket.recv(4096)
            if not chunk:
                raise RuntimeError("the socket closed during the handshake")
            handshake += chunk
        if b" 101 " not in handshake.split(b"\r\n", 1)[0]:
            status = handshake.split(b"\r\n", 1)[0]
            raise RuntimeError(f"the socket was refused: {status!r}")
        self._reader.feed(handshake.split(b"\r\n\r\n", 1)[1])

    def drain(self, deadline, settle=SETTLE_SECONDS):
        """Every frame until the turn has finished and the meter has settled.

        A turn ends in one of three ways and the probe waits for all of them:
        the socket closing, a `final_result_message` (the Deliberate lane and
        the error path), or `settle` seconds of quiet after the last frame. The
        quiet is what the Fast lane actually ends on, and it must be generous —
        the meter fills from `token_usage`, one frame per executor, *after* the
        answer has streamed. Reading it too early is the mistake the browser
        ledger already made once, recording one agent for a turn that billed
        three.
        """
        frames = []
        metered = False
        last = time.time()
        while time.time() < deadline:
            if turn_is_over(len(frames), metered, time.time() - last, settle):
                break
            self._socket.settimeout(2)
            try:
                chunk = self._socket.recv(65536)
            except (socket.timeout, ssl.SSLWantReadError):
                continue
            except OSError:
                break
            if not chunk:
                break
            for text in self._reader.feed(chunk):
                try:
                    envelope = json.loads(text)
                except ValueError:
                    continue
                # The heartbeat is not the turn: counted as a frame it would
                # hold the socket open for the whole timeout on a request that
                # never started, and — worse — make `Turn.observed` true for a
                # sample that observed nothing but a keepalive.
                if envelope.get("type") == "ping":
                    continue
                frames.append(envelope)
                metered = metered or envelope.get("type") == "token_usage"
                last = time.time()
            if self._reader.closed:
                break
        return frames

    def close(self):
        """Close politely, because the *next* sample depends on it.

        A slammed TCP socket leaves the backend's `user_to_process` entry
        standing until its endpoint notices, and `sole_user()` — which is how
        the Grounding panel's frame finds a screen — refuses to guess with two
        users registered. A close this probe did not announce is therefore a
        `no-tool-call` on the sample *after* it, indistinguishable in the
        report from the routing fault this probe exists to measure.
        """
        try:
            self._socket.sendall(b"\x88\x80" + secrets.token_bytes(4))
        except Exception:
            pass
        try:
            self._socket.close()
        except Exception:
            pass


def take_sample(base_url, team_id, question, task_id, lane):
    """Drive one Fast-lane turn and return the frames it pushed.

    A fresh principal per sample, which is this probe's equivalent of the fresh
    Direct Line conversation `check-sop-agent.sh` samples in: the workflow
    cache, the active orchestration task and the session's rehearsal marker are
    all per-user, so two samples sharing one would cancel each other's turn.
    """
    principal = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    _post(f"{base_url}/api/v4/select_team", {"team_id": team_id}, principal)
    channel = _Socket(base_url, session_id, principal)
    try:
        _post(f"{base_url}/api/v4/process_request", {
            "session_id": session_id,
            "description": question,
            "lane": lane,
            "starting_task_id": task_id,
        }, principal)
        return channel.drain(time.time() + TURN_TIMEOUT_SECONDS)
    finally:
        channel.close()


def collect(samples, base_url, team_id, question, task_id, lane,
            take=take_sample, settle=time.sleep):
    """Take `samples` turns, **one at a time**, and return their frames.

    Serial, and it is not a throughput decision. Two mechanisms in the backend
    resolve their recipient as *the sole connected user*, deliberately:
    `_push_source_used` — the Grounding panel's own frame, emitted from the
    `/sop/ask` bridge that the MCP container calls with no user of its own —
    and `send_status_update_async`'s fallback. With two samples connected at
    once neither can resolve and `source_used` is simply dropped.

    Measured before it was understood: this probe's first concurrent run
    reported `no-tool-call` on 2 of 2 samples against a deployment that answers
    the same question from the corpus on nearly every serial one. A probe four
    times faster would have sent the next iteration at the routing prompt for a
    fault that was its own.
    """
    collected = []
    for index in range(samples):
        try:
            frames = take(base_url, team_id, question, task_id, lane)
        except Exception as exc:  # a sample that failed observed nothing
            print(f"  sample {index + 1}: {exc}", file=sys.stderr)
            frames = []
        collected.append(frames)
        print(f"  sample {index + 1} of {samples}: {len(frames)} frames")
        if index + 1 < samples:
            settle(BETWEEN_SAMPLES_SECONDS)
    return collected


def record_evidence(path, turns, needed, question):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(path, "a", encoding="utf-8") as handle:
        for index, turn in enumerate(turns, start=1):
            line = evidence_line(turn, needed, index)
            line["at"] = stamp
            line["question"] = question
            handle.write(json.dumps(line) + "\n")
    print(f"  evidence appended to {path}")


def main(argv=None, collect_frames=collect):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--samples", type=int, default=12,
        help="how many turns to drive (default 12, the count deploy-main.yml "
             "samples the SOP agent with, and for the same arithmetic)",
    )
    parser.add_argument(
        "--evidence", default=str(EVIDENCE),
        help="where each sample's graded facts are appended as JSONL")
    parser.add_argument(
        "--resource-group", default=RESOURCE_GROUP)
    parser.add_argument("--backend-app", default=BACKEND_CONTAINER_APP)
    args = parser.parse_args(argv)

    question = rehearsed_question()
    team_id, task_id, lane = rehearsed_quick_task(question=question)
    needed = procedure_agent()
    base_url = backend_url(args.resource_group, args.backend_app)

    print(f"Routing probe: {args.samples} turns of {question!r}")
    print(f"  the {lane} lane, quick task {task_id}, on {base_url}")
    print(f"  the agent this question needs is {needed}\n")

    frames = collect_frames(
        args.samples, base_url, team_id, question, task_id, lane)
    turns = [observe(frame) for frame in frames]
    summary = summarise(turns, needed)
    if args.evidence:
        record_evidence(args.evidence, turns, needed, question)
    print()
    print(format_report(summary))
    if not summary.observed:
        return 2
    return 0 if summary.clean == summary.observed else 1


if __name__ == "__main__":
    sys.exit(main())
