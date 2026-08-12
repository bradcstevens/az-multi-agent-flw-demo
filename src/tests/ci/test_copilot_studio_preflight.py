"""Tests for the Copilot Studio data-policy and egress preflight (issue #5).

The demo's cross-platform proof rests on three Copilot Studio capabilities that a
tenant data policy (formerly "DLP") can block outright: publishing to **Direct Line
channels**, chatting **without Microsoft Entra ID authentication**, and grounding on
**document knowledge sources**. Agent data-policy exemption was withdrawn in early
2025, so a block has no exemption route — it has to be found before the build, not
on stage.
"""

import base64
import fnmatch
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from preflight.copilot_studio_preflight import (
    REQUIRED_CONNECTORS,
    REQUIRED_ENDPOINTS,
    Endpoint,
    admin_visibility_error,
    blocked_group_inventory,
    confirm_direct_line_websocket,
    ProbeResult,
    exit_code,
    format_report,
    main,
    probe,
    stream_transport,
    applicable_policies,
    classify_connectors,
    split_group_violations,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = REPO_ROOT / "scripts" / "preflight" / "copilot_studio_preflight.py"

DEFAULT_ENVIRONMENT = "Default-0f87abfb-0840-4199-96b7-1882c01a998b"
DIRECT_LINE = "Direct Line channels in Copilot Studio"
NO_AUTH_CHAT = "Chat without Microsoft Entra ID authentication in Copilot Studio"
DOCUMENT_KNOWLEDGE = "Knowledge source with documents in Copilot Studio"


def connector(display_name):
    slug = display_name.lower().replace(" ", "")
    return {
        "id": f"/providers/Microsoft.PowerApps/apis/shared_{slug}",
        "name": f"shared_{slug}",
        "displayName": display_name,
        "type": "Microsoft.PowerApps/apis",
    }


def policy(name, environment_type, environments=(), groups=(), default="General"):
    return {
        "policyName": name,
        "displayName": name,
        "environmentType": environment_type,
        "environments": [{"name": e} for e in environments],
        "defaultConnectorsClassification": default,
        "connectorGroups": [
            {"classification": classification, "connectors": [connector(c) for c in connectors]}
            for classification, connectors in groups
        ],
    }


def finding_for(findings, display_name):
    return next(f for f in findings if f.connector_name == display_name)


def test_given_a_tenant_wide_policy_when_scoped_then_it_governs_the_default_environment():
    policies = [policy("tenant-wide", "AllEnvironments")]

    assert [p["policyName"] for p in applicable_policies(policies, DEFAULT_ENVIRONMENT)] == [
        "tenant-wide"
    ]


def test_given_a_policy_scoped_to_other_environments_when_scoped_then_it_is_ignored():
    policies = [
        policy("elsewhere", "OnlyEnvironments", ["Sandbox-1"]),
        policy("here", "OnlyEnvironments", [DEFAULT_ENVIRONMENT]),
    ]

    assert [p["policyName"] for p in applicable_policies(policies, DEFAULT_ENVIRONMENT)] == ["here"]


def test_given_direct_line_in_a_blocked_group_when_classified_then_it_is_blocked():
    policies = [
        policy(
            "no-external-channels",
            "AllEnvironments",
            groups=[("Blocked", [DIRECT_LINE])],
        )
    ]

    finding = finding_for(classify_connectors(policies, DEFAULT_ENVIRONMENT), DIRECT_LINE)

    assert finding.verdict == "blocked"
    assert finding.policy_name == "no-external-channels"


def test_given_an_unlisted_connector_when_the_policy_default_group_is_blocked_then_it_is_blocked():
    """The failure mode the Copilot Studio data-policy docs single out.

    Connectors introduced after 2019 — Direct Line channels among them — land in
    a policy's default group when nobody classified them, and a tenant whose
    default group is Blocked blocks them without ever naming them.
    """
    policies = [policy("block-by-default", "AllEnvironments", default="Blocked")]

    findings = classify_connectors(policies, DEFAULT_ENVIRONMENT)

    assert [f.verdict for f in findings] == ["blocked", "blocked", "blocked"]
    assert finding_for(findings, DIRECT_LINE).policy_name == "block-by-default"


def test_given_the_three_connectors_split_across_data_groups_then_the_split_is_reported():
    """Unblocked is not sufficient: data cannot be shared across data groups.

    A policy that leaves all three connectors unblocked but puts them in
    different groups still stops the agent working, and the per-connector
    verdicts alone would read as a clean pass.
    """
    policies = [
        policy(
            "mixed-groups",
            "AllEnvironments",
            groups=[
                ("Confidential", [DIRECT_LINE]),
                ("General", [NO_AUTH_CHAT, DOCUMENT_KNOWLEDGE]),
            ],
        )
    ]

    assert all(f.verdict == "unblocked" for f in classify_connectors(policies, DEFAULT_ENVIRONMENT))

    violations = split_group_violations(policies, DEFAULT_ENVIRONMENT)

    assert len(violations) == 1
    assert violations[0].policy_name == "mixed-groups"
    assert violations[0].groups == {"Confidential": [DIRECT_LINE], "General": [NO_AUTH_CHAT, DOCUMENT_KNOWLEDGE]}


def test_given_the_three_connectors_in_one_data_group_then_there_is_no_split():
    policies = [
        policy(
            "one-group",
            "AllEnvironments",
            groups=[("General", [DIRECT_LINE, NO_AUTH_CHAT, DOCUMENT_KNOWLEDGE])],
        )
    ]

    assert split_group_violations(policies, DEFAULT_ENVIRONMENT) == []


class RecordingHandler(BaseHTTPRequestHandler):
    """A one-shot server that records the request and answers with a fixed status."""

    status = 200
    seen = {}

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's contract
        type(self).seen = {"path": self.path, "headers": dict(self.headers)}
        self.send_response(type(self).status)
        self.end_headers()

    def log_message(self, *_args):
        pass


@pytest.fixture
def local_server():
    server = HTTPServer(("127.0.0.1", 0), RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def test_given_a_websocket_endpoint_when_probed_then_a_websocket_handshake_is_sent(local_server):
    RecordingHandler.status = 101
    endpoint = Endpoint(
        domain="*.directline.botframework.com",
        probe_host="127.0.0.1",
        path="/v3/directline/conversations/probe/stream",
        protocol="WS",
        required=True,
        uses="Web socket connection to support Chat",
    )

    result = probe(endpoint, port=local_server.server_port, use_tls=False)

    assert result.reachable is True
    assert result.status == 101
    headers = {k.lower(): v for k, v in RecordingHandler.seen["headers"].items()}
    assert headers["upgrade"].lower() == "websocket"
    assert "upgrade" in headers["connection"].lower()
    assert headers["sec-websocket-version"] == "13"


def test_given_an_endpoint_a_firewall_refuses_when_probed_then_it_reads_as_unreachable(
    local_server,
):
    """The probe must never mistake a refused connection for a pass."""
    closed_port = local_server.server_port
    local_server.shutdown()
    local_server.server_close()

    result = probe(
        Endpoint(
            domain="*.directline.botframework.com",
            probe_host="127.0.0.1",
            path="/v3/directline/conversations",
            protocol="HTTPS",
            required=True,
            uses="Access to Bot Framework Web Chat",
        ),
        timeout=2.0,
        port=closed_port,
        use_tls=False,
    )

    assert result.reachable is False
    assert result.status is None
    assert "ConnectionRefusedError" in result.detail


def endpoint(domain, required=True, protocol="HTTPS"):
    return Endpoint(
        domain=domain,
        probe_host=domain.replace("*.", "unitedstates."),
        path="/",
        protocol=protocol,
        required=required,
        uses="",
    )


def test_given_an_optional_endpoint_is_unreachable_when_scored_then_the_preflight_passes():
    probes = [
        ProbeResult(endpoint("*.directline.botframework.com"), True, 405, "", True),
        ProbeResult(
            endpoint("pipe.aria.microsoft.com", required=False), False, None, "timed out", False
        ),
    ]

    assert exit_code(classify_connectors([], DEFAULT_ENVIRONMENT), [], probes) == 0


def test_given_a_required_endpoint_is_unreachable_when_scored_then_the_preflight_fails():
    probes = [
        ProbeResult(
            endpoint("*.directline.botframework.com", protocol="WS"), False, None, "", False
        )
    ]

    assert exit_code(classify_connectors([], DEFAULT_ENVIRONMENT), [], probes) == 1


def test_given_a_blocked_connector_when_scored_then_the_preflight_fails():
    policies = [policy("block-direct-line", "AllEnvironments", groups=[("Blocked", [DIRECT_LINE])])]

    findings = classify_connectors(policies, DEFAULT_ENVIRONMENT)

    assert exit_code(findings, [], []) == 1


def test_given_a_split_data_group_when_scored_then_the_preflight_fails():
    policies = [
        policy(
            "mixed-groups",
            "AllEnvironments",
            groups=[("Confidential", [DIRECT_LINE]), ("General", [NO_AUTH_CHAT])],
        )
    ]

    findings = classify_connectors(policies, DEFAULT_ENVIRONMENT)
    violations = split_group_violations(policies, DEFAULT_ENVIRONMENT)

    assert all(f.verdict == "unblocked" for f in findings)
    assert exit_code(findings, violations, []) == 1


def test_given_a_blocked_connector_when_reported_then_the_report_names_the_owning_policy():
    """There is no exemption route, so the report has to say who to go to."""
    policies = [
        policy("central-governance", "AllEnvironments", groups=[("Blocked", [DIRECT_LINE])])
    ]
    findings = classify_connectors(policies, DEFAULT_ENVIRONMENT)

    report = format_report(findings, split_group_violations(policies, DEFAULT_ENVIRONMENT), [])

    assert "BLOCKED" in report
    assert "Direct Line channels in Copilot Studio" in report
    assert "central-governance" in report
    assert "no exemption route" in report


def test_given_every_connector_unblocked_when_reported_then_each_is_recorded_by_capability():
    """The issue asks for the finding recorded per connector, not one verdict."""
    report = format_report(classify_connectors([], DEFAULT_ENVIRONMENT), [], [])

    for required in REQUIRED_CONNECTORS:
        assert required.capability in report
        assert required.connector_name in report
    assert report.count("UNBLOCKED") == 3


def test_given_a_saved_policy_payload_when_run_as_a_human_runs_it_then_the_process_fails(tmp_path):
    """A recorded payload has to reproduce the verdict without a live token.

    Interactive re-authentication is the one thing an unattended run cannot do,
    so the saved payload is how the finding stays re-checkable.
    """
    payload = tmp_path / "policies.json"
    payload.write_text(
        json.dumps(
            {
                "value": [
                    policy(
                        "central-governance",
                        "AllEnvironments",
                        groups=[("Blocked", [DIRECT_LINE])],
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(PREFLIGHT),
            "--policies-file",
            str(payload),
            "--skip-egress",
            "--environment",
            DEFAULT_ENVIRONMENT,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert "BLOCKED" in result.stdout
    assert "central-governance" in result.stdout


def test_every_required_endpoint_is_probed_at_a_host_its_published_domain_covers():
    """A probe host that the published wildcard does not cover proves nothing."""
    for endpoint_under_test in REQUIRED_ENDPOINTS:
        assert fnmatch.fnmatch(endpoint_under_test.probe_host, endpoint_under_test.domain), (
            endpoint_under_test.probe_host,
            endpoint_under_test.domain,
        )


def test_the_direct_line_hostname_is_probed_over_both_https_and_websockets():
    """The acceptance criterion names both protocols, and a proxy can allow one."""
    protocols = {
        e.protocol for e in REQUIRED_ENDPOINTS if e.domain == "*.directline.botframework.com"
    }

    assert protocols == {"HTTPS", "WS"}


class BodyHandler(BaseHTTPRequestHandler):
    """A server that answers with a body, as the real hosts do."""

    status = 403
    body = b'{"error":{"code":"BadArgument","message":"Missing token or secret"}}'

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's contract
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(type(self).body)))
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, *_args):
        pass


def test_given_a_refused_websocket_upgrade_when_probed_then_the_service_reply_is_captured():
    """Without the reply body a 403 cannot be told apart from a proxy block.

    A proxy that swallows WebSocket upgrades is precisely the failure this
    check exists to catch, and it answers 403 too — so the evidence that the
    Direct Line service itself replied has to survive into the report.
    """
    BodyHandler.status = 403
    BodyHandler.body = b'{"error":{"code":"BadArgument","message":"Missing token or secret"}}'
    server = HTTPServer(("127.0.0.1", 0), BodyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = probe(
            Endpoint(
                domain="*.directline.botframework.com",
                probe_host="127.0.0.1",
                path="/v3/directline/conversations/preflight/stream",
                protocol="WS",
                required=True,
                uses="",
            ),
            port=server.server_port,
            use_tls=False,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.status == 403
    assert "Missing token or secret" in result.detail


def test_given_a_successful_response_with_a_body_when_probed_then_the_body_is_not_recorded():
    """Reply bodies are evidence for a refusal; on success they are just noise.

    The webchat bundle is the concrete case — it answers 200 with minified
    JavaScript that would otherwise land verbatim in the recorded finding.
    """
    BodyHandler.status = 200
    BodyHandler.body = b"!function(e,t){bundled webchat}"
    server = HTTPServer(("127.0.0.1", 0), BodyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = probe(
            Endpoint(
                domain="cdn.botframework.com",
                probe_host="127.0.0.1",
                path="/botframework-webchat/latest/webchat.js",
                protocol="HTTPS",
                required=False,
                uses="",
            ),
            port=server.server_port,
            use_tls=False,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.detail == "HTTP/1.0 200 OK"


def test_given_no_data_policy_at_all_when_classified_then_the_finding_says_so():
    """An empty tenant and an unexamined tenant must not read the same.

    "Nothing blocks it" is true when the check found no policies and true when
    it found several that allow it — but only one of those is evidence that the
    check looked, which is what a recorded finding has to carry.
    """
    finding = finding_for(classify_connectors([], DEFAULT_ENVIRONMENT), DIRECT_LINE)

    assert finding.verdict == "unblocked"
    assert finding.detail == "no data policy governs this environment"


def test_given_a_policy_that_allows_the_connector_then_the_finding_counts_the_policies():
    policies = [
        policy("permissive", "AllEnvironments", groups=[("General", [DIRECT_LINE])]),
        policy("also-permissive", "OnlyEnvironments", [DEFAULT_ENVIRONMENT]),
    ]

    finding = finding_for(classify_connectors(policies, DEFAULT_ENVIRONMENT), DIRECT_LINE)

    assert finding.verdict == "unblocked"
    assert finding.detail == "none of the 2 governing data policies block it"


def test_given_an_environment_level_policy_scope_when_scoped_then_it_governs():
    policies = [policy("env-level", "SingleEnvironment", [DEFAULT_ENVIRONMENT])]

    assert [p["policyName"] for p in applicable_policies(policies, DEFAULT_ENVIRONMENT)] == [
        "env-level"
    ]


def test_given_an_unrecognised_policy_scope_when_scoped_then_it_still_governs():
    """A scope this check has never seen must not silently drop the policy.

    Power Platform has added scope shapes before. Ignoring an unknown one turns
    a blocking policy into a clean pass, which is the one outcome a preflight
    must never produce.
    """
    policies = [policy("future-scope", "SomeScopeInventedLater", [DEFAULT_ENVIRONMENT])]

    assert [p["policyName"] for p in applicable_policies(policies, DEFAULT_ENVIRONMENT)] == [
        "future-scope"
    ]


def test_given_the_v2_policy_definition_envelope_when_classified_then_it_is_unwrapped():
    """The v2 list endpoint wraps each policy in a `policyDefinition` envelope.

    Left wrapped, every field the classifier reads is missing, and a blocking
    policy reads as a clean pass.
    """
    wrapped = [
        {
            "policyDefinition": policy(
                "wrapped", "AllEnvironments", groups=[("Blocked", [DIRECT_LINE])]
            ),
            "policyLinkedResourcesUri": "https://example.invalid/linked",
        }
    ]

    finding = finding_for(classify_connectors(wrapped, DEFAULT_ENVIRONMENT), DIRECT_LINE)

    assert finding.verdict == "blocked"
    assert finding.policy_name == "wrapped"


def test_given_a_governing_policy_with_no_connector_groups_then_the_verdict_is_indeterminate():
    """A policy summary without its classifications proves nothing either way.

    Some list endpoints return the policy without expanding its connector
    groups. Treating that silence as "not in a Blocked group" is exactly the
    false pass this preflight exists to prevent.
    """
    summary = {
        "policyName": "summary-only",
        "displayName": "summary-only",
        "environmentType": "AllEnvironments",
        "environments": [],
    }

    findings = classify_connectors([summary], DEFAULT_ENVIRONMENT)

    assert [f.verdict for f in findings] == ["indeterminate"] * 3
    assert "summary-only" == finding_for(findings, DIRECT_LINE).policy_name
    # Undetermined rather than failed: nothing is known to be blocked, but
    # nothing has been shown to be unblocked either.
    assert exit_code(findings, [], []) == 2


def test_given_the_environment_is_not_visible_to_the_token_then_an_empty_list_is_not_trusted():
    """An empty policy list from an under-privileged read looks identical to a
    tenant that genuinely has no policies. Only administrative visibility of
    the target environment tells them apart, so that is what is checked.
    """
    assert admin_visibility_error([], DEFAULT_ENVIRONMENT) is not None
    assert admin_visibility_error([{"name": "Sandbox-1"}], DEFAULT_ENVIRONMENT) is not None
    assert admin_visibility_error([{"name": DEFAULT_ENVIRONMENT}], DEFAULT_ENVIRONMENT) is None


def test_given_a_run_that_checks_nothing_when_invoked_then_it_refuses_rather_than_passing(
    tmp_path,
):
    """Disabling both halves must not print a clean report and exit 0."""
    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), "--egress-only", "--skip-egress"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "UNBLOCKED" not in result.stdout


def test_given_a_saved_payload_that_is_not_a_policy_list_then_it_is_refused(tmp_path):
    """A malformed file must not be read as a tenant with no policies."""
    payload = tmp_path / "policies.json"
    payload.write_text('{"unexpected": true}', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), "--policies-file", str(payload), "--skip-egress"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "UNBLOCKED" not in result.stdout


def ws_endpoint(host="127.0.0.1"):
    return Endpoint(
        domain="*.directline.botframework.com",
        probe_host=host,
        path="/v3/directline/conversations/preflight/stream",
        protocol="WS",
        required=True,
        uses="Web socket connection to support Chat",
    )


def serve(handler_class):
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_given_a_websocket_upgrade_answered_with_an_error_then_it_is_not_confirmed():
    """A refusal proves the request arrived, not that the upgrade was allowed.

    A proxy can strip Upgrade and Connection headers and forward the request as
    ordinary HTTPS; Direct Line then answers the same 403 it answers a plain
    GET with. Only 101 distinguishes the two, so only 101 confirms.
    """
    BodyHandler.status = 403
    BodyHandler.body = b'{"error":{"code":"BadArgument","message":"Missing token or secret"}}'
    server = serve(BodyHandler)
    try:
        result = probe(ws_endpoint(), port=server.server_port, use_tls=False)
    finally:
        server.shutdown()
        server.server_close()

    assert result.reachable is True
    assert result.confirmed is False


def test_given_an_unconfirmed_required_endpoint_then_the_report_does_not_read_as_a_pass():
    unconfirmed = ProbeResult(ws_endpoint(), True, 403, "HTTP/1.1 403", confirmed=False)

    report = format_report([], [], [unconfirmed])

    assert "UNCONFIRMED" in report
    assert "OK  " not in report


class DirectLineStub(BaseHTTPRequestHandler):
    """Direct Line as far as this check uses it: start a conversation, then stream.

    The stream URL is handed back by the service rather than composed by the
    caller, which is how the endpoint gets resolved at runtime instead of being
    hardcoded.
    """

    port = 0
    secrets_seen = []

    def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler's contract
        type(self).secrets_seen.append(self.headers.get("Authorization"))
        body = json.dumps(
            {
                "conversationId": "preflight-conversation",
                "token": "preflight-token",
                "streamUrl": f"ws://127.0.0.1:{type(self).port}/v3/directline/stream",
            }
        ).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's contract
        if self.headers.get("Upgrade") != "websocket":
            self.send_response(400)
            self.end_headers()
            return
        key = self.headers.get("Sec-WebSocket-Key", "")
        digest = hashlib.sha1((key + HandshakeHandler.GUID).encode()).digest()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", base64.b64encode(digest).decode())
        self.end_headers()

    def log_message(self, *_args):
        pass


def test_given_a_direct_line_secret_then_the_websocket_upgrade_is_confirmed_end_to_end():
    """With a published agent this stops being an argument and becomes a 101.

    The check starts a real conversation, dials the stream URL the service
    hands back, and only reports the WebSocket row confirmed on 101 — which a
    proxy that strips the upgrade cannot produce.
    """
    DirectLineStub.secrets_seen = []
    server = serve(DirectLineStub)
    DirectLineStub.port = server.server_port
    try:
        result = confirm_direct_line_websocket(
            "a-direct-line-secret",
            base_url=f"http://127.0.0.1:{server.server_port}/v3/directline/conversations",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.confirmed is True
    assert result.status == 101
    assert DirectLineStub.secrets_seen == ["Bearer a-direct-line-secret"]


def serve_fragmented(head, first, rest, delay=0.05):
    """A raw socket server that splits a reply across TCP segments."""
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def run():
        connection, _ = listener.accept()
        connection.recv(4096)
        connection.sendall(head + first)
        time.sleep(delay)
        connection.sendall(rest)
        connection.close()

    threading.Thread(target=run, daemon=True).start()
    return listener


def test_given_a_reply_split_across_segments_then_the_whole_promised_body_is_read():
    """The reply body is the evidence, and a truncated one is a truncated finding.

    Nothing guarantees a reply arrives in one segment, and stopping at the
    first body byte turns Direct Line's error contract into a lone brace.
    """
    body = b'{"error":{"code":"BadArgument","message":"Missing token or secret"}}'
    head = (
        b"HTTP/1.1 403 Forbidden\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n"
    )
    listener = serve_fragmented(head, body[:1], body[1:])
    try:
        result = probe(ws_endpoint(), port=listener.getsockname()[1], use_tls=False)
    finally:
        listener.close()

    assert result.status == 403
    assert "Missing token or secret" in result.detail


def test_given_a_blocked_group_of_unrecognised_connectors_then_the_report_lists_them():
    """The by-name match is the check's weakest link, so it shows its working.

    Policy entries keep the connector name they were written with, so a
    renamed connector is matched by nobody and falls through to the default
    group. Printing every Blocked group verbatim lets a reader catch what the
    matcher missed.
    """
    policies = [
        policy(
            "central-governance",
            "AllEnvironments",
            groups=[("Blocked", ["Power Virtual Agents (legacy name)", "Facebook channel"])],
        )
    ]

    inventory = blocked_group_inventory(policies, DEFAULT_ENVIRONMENT)
    report = format_report(
        classify_connectors(policies, DEFAULT_ENVIRONMENT), [], [], blocked_inventory=inventory
    )

    assert inventory == {"central-governance": ["Facebook channel", "Power Virtual Agents (legacy name)"]}
    assert "Power Virtual Agents (legacy name)" in report
    assert "Facebook channel" in report


class BareUpgradeHandler(BaseHTTPRequestHandler):
    """Answers 101 without completing the handshake, as a proxy might."""

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's contract
        self.send_response(101)
        self.end_headers()

    def log_message(self, *_args):
        pass


class HandshakeHandler(BaseHTTPRequestHandler):
    """Completes RFC 6455: echoes the accept token derived from the client key."""

    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's contract
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = base64.b64encode(hashlib.sha1((key + self.GUID).encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

    def log_message(self, *_args):
        pass


def test_given_a_101_without_the_accept_token_then_the_websocket_is_not_confirmed():
    """101 alone is a status line; a handshake is a proof the peer did the work.

    Only a Sec-WebSocket-Accept derived from the key this probe generated shows
    the upgrade was completed by something speaking WebSocket.
    """
    server = serve(BareUpgradeHandler)
    try:
        result = probe(ws_endpoint(), port=server.server_port, use_tls=False)
    finally:
        server.shutdown()
        server.server_close()

    assert result.status == 101
    assert result.confirmed is False


def test_given_a_completed_handshake_then_the_websocket_is_confirmed():
    server = serve(HandshakeHandler)
    try:
        result = probe(ws_endpoint(), port=server.server_port, use_tls=False)
    finally:
        server.shutdown()
        server.server_close()

    assert result.confirmed is True


def test_given_an_https_stream_url_then_it_is_dialled_as_a_secure_websocket():
    """Direct Line returns the stream URL as https as well as wss.

    Treating https as insecure sends the handshake to port 80 in clear text,
    which the service does not answer — a confirmable row would read as a
    failure.
    """
    assert stream_transport("https://x.directline.botframework.com/v3/stream") == (443, True)
    assert stream_transport("wss://x.directline.botframework.com/v3/stream") == (443, True)
    assert stream_transport("ws://127.0.0.1:8080/v3/stream") == (8080, False)
    assert stream_transport("http://127.0.0.1:8080/v3/stream") == (8080, False)

    with pytest.raises(ValueError):
        stream_transport("ftp://x.directline.botframework.com/v3/stream")


def test_given_a_required_endpoint_that_could_not_be_confirmed_then_the_run_is_undetermined():
    """Unconfirmed is neither a pass nor a failure, and must not read as either.

    Exiting 0 would let an unproven WebSocket path read as verified; exiting 1
    would claim something is blocked when nothing is known to be.
    """
    unconfirmed = ProbeResult(ws_endpoint(), True, 403, "HTTP/1.1 403", confirmed=False)

    assert exit_code([], [], [unconfirmed]) == 2
    assert exit_code([], [], [ProbeResult(ws_endpoint(), True, 101, "", confirmed=True)]) == 0


def test_given_both_a_blocked_connector_and_an_unconfirmed_probe_then_the_block_wins():
    """A known block is actionable; an unconfirmed probe is not. Report the block."""
    policies = [policy("blocker", "AllEnvironments", groups=[("Blocked", [DIRECT_LINE])])]
    unconfirmed = ProbeResult(ws_endpoint(), True, 403, "", confirmed=False)

    findings = classify_connectors(policies, DEFAULT_ENVIRONMENT)

    assert exit_code(findings, [], [unconfirmed]) == 1


def test_given_a_policy_summary_without_its_groups_then_the_verdict_is_indeterminate():
    """A list response can carry the default group but omit connectorGroups.

    Applying the default to a policy whose groups were never returned would
    report an explicitly blocked connector as unblocked — the exact false pass
    this check exists to prevent.
    """
    summary = {
        "policyName": "summary",
        "environmentType": "AllEnvironments",
        "defaultConnectorsClassification": "General",
    }

    finding = finding_for(classify_connectors([summary], DEFAULT_ENVIRONMENT), DIRECT_LINE)

    assert finding.verdict == "indeterminate"
    assert "connectorGroups" in finding.detail


def test_given_a_policy_that_returned_an_empty_group_list_then_the_default_applies():
    """An empty list is an answer; a missing key is not."""
    empty = {
        "policyName": "empty",
        "environmentType": "AllEnvironments",
        "defaultConnectorsClassification": "General",
        "connectorGroups": [],
    }

    finding = finding_for(classify_connectors([empty], DEFAULT_ENVIRONMENT), DIRECT_LINE)

    assert finding.verdict == "unblocked"


def test_given_a_policies_file_that_does_not_exist_then_the_run_is_undetermined(capsys):
    """A mistyped path is an unanswered question, not a crash.

    A traceback would exit 1, which this check reserves for "something is
    blocked" — a reader would act on a finding that was never made.
    """
    assert main(["--policies-file", "/nonexistent/policies.json", "--skip-egress"]) == 2
    assert "could not be read" in capsys.readouterr().err


def test_given_a_policies_file_that_is_not_json_then_the_run_is_undetermined(tmp_path, capsys):
    not_json = tmp_path / "policies.json"
    not_json.write_text("<html>sign in</html>", encoding="utf-8")

    assert main(["--policies-file", str(not_json), "--skip-egress"]) == 2
    assert "could not be read" in capsys.readouterr().err
