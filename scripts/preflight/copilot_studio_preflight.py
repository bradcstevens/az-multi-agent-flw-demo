"""Copilot Studio data-policy and network-egress preflight (issue #5).

Two independent preconditions for the Copilot Studio SOP agent, checked here
because neither can be recovered from once the demo is live:

1. **Data policy** (formerly "DLP"). Three Copilot Studio connectors have to be
   left unblocked for the Default environment. Agent data-policy exemption was
   withdrawn in early 2025, so a block has no exemption route, and publishing
   fails outright when no non-blocked channel remains.
2. **Network egress**. The demo machine has to reach the Direct Line hostname
   over both HTTPS and WebSockets, plus the Power Virtual Agents and Bot
   Framework CDN hosts.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BLOCKED = "Blocked"


@dataclass(frozen=True)
class RequiredConnector:
    """A Copilot Studio capability the demo cannot be published without.

    ``connector_name`` is the name the Power Platform admin center shows; the
    data-policy API identifies connectors by opaque ``shared_*`` ids, so the
    name is normalised and matched against every string field of a connector
    entry rather than against one field.
    """

    capability: str
    connector_name: str
    breaks: str


REQUIRED_CONNECTORS = (
    RequiredConnector(
        capability="Direct Line channels",
        connector_name="Direct Line channels in Copilot Studio",
        breaks=(
            "The SOP agent cannot be published to Direct Line, so the orchestrator's SOP "
            "MCP tool has no endpoint to call and the cross-platform proof is gone. "
            "Publishing fails outright when no non-blocked channel remains."
        ),
    ),
    RequiredConnector(
        capability="Chat without Entra ID authentication",
        connector_name="Chat without Microsoft Entra ID authentication in Copilot Studio",
        breaks=(
            "The agent would be forced onto 'Authenticate with Microsoft', and a no-auth "
            "Direct Line session has no user identity to present."
        ),
    ),
    RequiredConnector(
        capability="Document-based knowledge sources",
        connector_name="Knowledge source with documents in Copilot Studio",
        breaks=(
            "The SOP corpus is grounded in Dataverse-uploaded documents (Grounding Option A). "
            "There is no fallback: SharePoint grounding needs an authenticated user."
        ),
    ),
)


@dataclass(frozen=True)
class ConnectorFinding:
    capability: str
    connector_name: str
    verdict: str
    classification: str | None
    policy_name: str | None
    detail: str


@dataclass(frozen=True)
class SplitGroupViolation:
    policy_name: str
    groups: dict


def applicable_policies(policies, environment_id):
    """The data policies that govern ``environment_id``.

    Fails closed on scope: a policy whose scope shape this check does not
    recognise is treated as governing, because dropping it would turn a
    blocking policy into a clean pass.
    """
    governing = []
    for candidate in _normalise_policies(policies):
        scope = candidate.get("environmentType")
        listed = _environment_names(candidate)
        if scope == "ExceptEnvironments":
            if environment_id not in listed:
                governing.append(candidate)
        elif scope in ("OnlyEnvironments", "SingleEnvironment"):
            if environment_id in listed:
                governing.append(candidate)
        else:
            governing.append(candidate)
    return governing


def _normalise_policies(policies):
    """Unwrap the ``policyDefinition`` envelope the v2 list endpoint uses."""
    return [
        entry.get("policyDefinition", entry) if isinstance(entry, dict) else entry
        for entry in policies
    ]


def classify_connectors(policies, environment_id):
    """One finding per required connector, against every governing policy."""
    governing = applicable_policies(policies, environment_id)
    return [_classify(required, governing) for required in REQUIRED_CONNECTORS]


def split_group_violations(policies, environment_id):
    """Policies that spread the three required connectors across data groups.

    Unblocked is necessary but not sufficient: within one policy the connectors
    have to share a data group, because data cannot be shared between groups.
    """
    violations = []
    for policy in applicable_policies(policies, environment_id):
        groups = {}
        for required in REQUIRED_CONNECTORS:
            classification = _explicit_classification(policy, required)
            if classification is None:
                classification = policy.get("defaultConnectorsClassification")
            groups.setdefault(classification, []).append(required.connector_name)
        if len(groups) > 1:
            violations.append(SplitGroupViolation(_policy_name(policy), groups))
    return violations


def _classify(required, governing):
    indeterminate = None
    for policy in governing:
        classification = _explicit_classification(policy, required)
        if classification is None and "connectorGroups" not in policy:
            indeterminate = indeterminate or _indeterminate(
                required,
                policy,
                "this policy governs the environment but was returned without its "
                "connectorGroups, so an explicit block could not be ruled out",
            )
            continue
        if classification is None:
            classification = policy.get("defaultConnectorsClassification")
            detail = f"not listed, so the policy's default group ({classification}) applies"
        else:
            detail = f"listed in the {classification} group of this policy"
        if classification == BLOCKED:
            return ConnectorFinding(
                capability=required.capability,
                connector_name=required.connector_name,
                verdict="blocked",
                classification=BLOCKED,
                policy_name=_policy_name(policy),
                detail=detail,
            )
        if classification is None and indeterminate is None:
            indeterminate = _indeterminate(
                required,
                policy,
                "this policy governs the environment but carries neither the connector "
                "nor a default group, so its classification could not be read",
            )
    if indeterminate is not None:
        return indeterminate
    return ConnectorFinding(
        capability=required.capability,
        connector_name=required.connector_name,
        verdict="unblocked",
        classification=None,
        policy_name=None,
        detail=_no_block_detail(governing),
    )


def _indeterminate(required, policy, detail):
    return ConnectorFinding(
        capability=required.capability,
        connector_name=required.connector_name,
        verdict="indeterminate",
        classification=None,
        policy_name=_policy_name(policy),
        detail=detail,
    )


def _no_block_detail(governing):
    """Say whether the check found policies, not merely that none blocked."""
    if not governing:
        return "no data policy governs this environment"
    return f"none of the {len(governing)} governing data policies block it"


def _policy_name(policy):
    return policy.get("displayName") or policy.get("policyName")


def _explicit_classification(policy, required):
    wanted = _normalise(required.connector_name)
    for group in policy.get("connectorGroups") or ():
        for entry in group.get("connectors") or ():
            if wanted in {_normalise(value) for value in _strings(entry)}:
                return group.get("classification")
    return None


def _strings(entry):
    return [value for value in entry.values() if isinstance(value, str)]


def _normalise(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _environment_names(policy):
    return {
        environment.get("name")
        for environment in policy.get("environments") or ()
        if isinstance(environment, dict)
    }


@dataclass(frozen=True)
class Endpoint:
    """One row of the Copilot Studio required-services table.

    ``domain`` is the published entry, which may be a wildcard; ``probe_host``
    is the concrete host dialled to stand in for it.
    """

    domain: str
    probe_host: str
    path: str
    protocol: str
    required: bool
    uses: str


@dataclass(frozen=True)
class ProbeResult:
    """The outcome of one egress probe.

    ``reachable`` says the service answered. ``confirmed`` says the protocol the
    demo actually uses got through, which for a WebSocket row means a genuine
    ``101 Switching Protocols`` — a proxy can strip the upgrade headers and
    forward the request as ordinary HTTPS, and the origin then answers exactly
    as it answers a plain GET.
    """

    endpoint: Endpoint
    reachable: bool
    status: int | None
    detail: str
    confirmed: bool


def probe(endpoint, timeout=10.0, port=443, use_tls=True):
    """Dial an endpoint and report whether the service itself answered.

    A WebSocket probe sends a real ``Upgrade`` handshake, because a proxy that
    permits HTTPS to a host and silently drops its WebSocket upgrade is exactly
    the failure this preflight exists to catch.
    """
    key = base64.b64encode(os.urandom(16)).decode()
    request = _request_bytes(endpoint, key)
    try:
        with _connect(endpoint.probe_host, port, timeout, use_tls) as connection:
            connection.sendall(request)
            response = _read_response(connection)
    except OSError as error:
        return ProbeResult(endpoint, False, None, f"{type(error).__name__}: {error}", False)

    head, _, body = response.partition("\r\n\r\n")
    status_line = head.split("\r\n", 1)[0]
    status = _status_code(status_line)
    if status is None:
        return ProbeResult(endpoint, False, None, f"not an HTTP response: {status_line!r}", False)
    confirmed = _handshake_completed(status, head, key) if endpoint.protocol == "WS" else True
    return ProbeResult(endpoint, True, status, _detail(status, status_line, body), confirmed)


def _detail(status, status_line, body):
    """The status line, plus — on a refusal — enough reply to identify the sender."""
    if status < 400:
        return status_line
    excerpt = " ".join(body.split())[:160]
    return f"{status_line} — {excerpt}" if excerpt else status_line


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _handshake_completed(status, head, key):
    """Whether the peer actually completed the WebSocket handshake.

    A 101 status line alone can be produced by anything; only an accept token
    derived from the key this probe generated shows the peer spoke WebSocket.
    """
    if status != 101:
        return False
    headers = _headers(head)
    if headers.get("upgrade", "").lower() != "websocket":
        return False
    if "upgrade" not in headers.get("connection", "").lower():
        return False
    expected = base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode()).digest()).decode()
    return headers.get("sec-websocket-accept") == expected


def _headers(head):
    parsed = {}
    for line in head.split("\r\n")[1:]:
        name, separator, value = line.partition(":")
        if separator:
            parsed[name.strip().lower()] = value.strip()
    return parsed


def _request_bytes(endpoint, key):
    lines = [
        f"GET {endpoint.path} HTTP/1.1",
        f"Host: {endpoint.probe_host}",
        "User-Agent: copilot-studio-preflight",
        "Connection: close",
    ]
    if endpoint.protocol == "WS":
        lines[-1] = "Connection: Upgrade"
        lines += [
            "Upgrade: websocket",
            "Sec-WebSocket-Version: 13",
            f"Sec-WebSocket-Key: {key}",
            f"Origin: https://{endpoint.probe_host}",
        ]
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def _connect(host, port, timeout, use_tls):
    connection = socket.create_connection((host, port), timeout=timeout)
    if not use_tls:
        return connection
    context = ssl.create_default_context()
    return context.wrap_socket(connection, server_hostname=host)


def _read_response(connection, limit=2048):
    """Headers plus a bounded slice of the body.

    Stops as soon as the reply is complete rather than on the first body byte,
    because a reply split across TCP segments would otherwise be recorded as
    its first character. A successful upgrade never closes the connection and
    carries no body, so 101 returns on the headers alone.
    """
    buffered = b""
    while True:
        head, separator, body = buffered.partition(b"\r\n\r\n")
        if separator and _is_complete(head, body, limit):
            break
        if len(buffered) >= limit:
            break
        try:
            chunk = connection.recv(512)
        except (TimeoutError, socket.timeout):
            break
        if not chunk:
            break
        buffered += chunk
    return buffered.decode("latin-1")


def _is_complete(head, body, limit):
    if _status_code(head.split(b"\r\n", 1)[0]) == 101:
        return True
    promised = _content_length(head)
    if promised is None:
        # No length and not an upgrade: only the peer closing ends the reply,
        # which the recv loop handles. Chunked bodies fall here too and are
        # deliberately read as a bounded, best-effort excerpt.
        return False
    return len(body) >= min(promised, limit)


def _content_length(head):
    match = re.search(rb"(?im)^content-length:\s*(\d+)", head)
    return int(match.group(1)) if match else None


def _status_code(status_line):
    if isinstance(status_line, bytes):
        status_line = status_line.decode("latin-1")
    match = re.match(r"HTTP/\d\.\d (\d{3})", status_line)
    return int(match.group(1)) if match else None


def exit_code(connector_findings, violations, probe_results):
    """0 clear, 1 something is blocked or unreachable, 2 undetermined.

    Fails closed on both axes. A blocked or unreachable result outranks an
    undetermined one, because only the first is actionable; but an undetermined
    result never reports as clear, or the check would let an unproven path read
    as verified.
    """
    if any(finding.verdict == "blocked" for finding in connector_findings):
        return 1
    if violations:
        return 1
    if any(result.endpoint.required and not result.reachable for result in probe_results):
        return 1
    if any(finding.verdict != "unblocked" for finding in connector_findings):
        return UNDETERMINED
    if any(result.endpoint.required and not result.confirmed for result in probe_results):
        return UNDETERMINED
    return 0


REMEDIATION = (
    "Agent data-policy exemption was withdrawn in early 2025, so there is no exemption route: "
    "the owner of the named policy has to move the connector out of the Blocked group in the "
    "Power Platform admin center (Security > Data and privacy > Data policy). Tenant-scoped "
    "policies can only be edited by a Power Platform administrator; an environment admin "
    "cannot edit a policy a tenant admin created."
)


DIRECT_LINE_CONVERSATIONS_URL = (
    "https://unitedstates.directline.botframework.com/v3/directline/conversations"
)


SECURE_STREAM_SCHEMES = ("wss", "https")
INSECURE_STREAM_SCHEMES = ("ws", "http")


def stream_transport(stream_url):
    """The (port, TLS) a Direct Line stream URL should be dialled on.

    Direct Line returns the stream URL as ``https`` as well as ``wss``; reading
    ``https`` as insecure would send the handshake to port 80 in clear text and
    a confirmable row would read as a failure.
    """
    parsed = urllib.parse.urlparse(stream_url)
    if parsed.scheme in SECURE_STREAM_SCHEMES:
        return parsed.port or 443, True
    if parsed.scheme in INSECURE_STREAM_SCHEMES:
        return parsed.port or 80, False
    raise ValueError(f"unsupported Direct Line stream scheme: {parsed.scheme!r}")


def confirm_direct_line_websocket(secret, base_url=DIRECT_LINE_CONVERSATIONS_URL, timeout=10.0):
    """Start a Direct Line conversation and dial the stream URL it hands back.

    This is the only way to turn the WebSocket row from "the service answered"
    into "the upgrade completed": a proxy that strips the upgrade headers can
    reproduce every error status, but it cannot produce a 101. Needs a Direct
    Line secret, so it becomes runnable once the SOP agent is published.

    The stream URL is read from the service's reply rather than composed here,
    which is also how the endpoint stays correct outside the default region.
    """
    request = urllib.request.Request(
        base_url, data=b"", headers={"Authorization": f"Bearer {secret}"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        conversation = json.loads(response.read().decode("utf-8"))

    stream_url = conversation.get("streamUrl")
    if not stream_url:
        raise ValueError("Direct Line started a conversation without a streamUrl")

    parsed = urllib.parse.urlparse(stream_url)
    port, secure = stream_transport(stream_url)
    endpoint = Endpoint(
        domain="*.directline.botframework.com",
        probe_host=parsed.hostname,
        path=parsed.path + (f"?{parsed.query}" if parsed.query else ""),
        protocol="WS",
        required=True,
        uses="Web socket connection to support Chat",
    )
    return probe(endpoint, timeout=timeout, port=port, use_tls=secure)


def _probe_mark(result):
    if not result.reachable:
        return "FAIL"
    return "OK  " if result.confirmed else "UNCONFIRMED"


def blocked_group_inventory(policies, environment_id):
    """Every connector each governing policy blocks, by policy.

    Matching a required connector by name is this check's weakest link: policy
    entries keep whatever name they were written with, so a renamed connector
    is matched by nobody. Printing the Blocked groups verbatim lets a reader
    catch what the matcher missed.
    """
    inventory = {}
    for policy in applicable_policies(policies, environment_id):
        blocked = set()
        for group in policy.get("connectorGroups") or ():
            if group.get("classification") != BLOCKED:
                continue
            for entry in group.get("connectors") or ():
                blocked.add(_connector_label(entry))
        if blocked:
            inventory[_policy_name(policy)] = sorted(blocked)
    return inventory


def _connector_label(entry):
    return entry.get("displayName") or entry.get("name") or entry.get("id") or repr(entry)


def format_report(connector_findings, violations, probe_results, blocked_inventory=None):
    lines = ["Copilot Studio data policy — required connectors", ""]
    for finding in connector_findings:
        lines.append(f"  {finding.verdict.upper():<10} {finding.capability}")
        lines.append(f"             connector: {finding.connector_name}")
        lines.append(f"             {finding.detail}")
        if finding.policy_name:
            lines.append(f"             policy: {finding.policy_name}")
        lines.append("")

    if violations:
        lines.append("Data-group split — unblocked, but the connectors cannot share data")
        for violation in violations:
            lines.append(f"  policy: {violation.policy_name}")
            for classification, connectors in violation.groups.items():
                lines.append(f"    {classification}: {', '.join(connectors)}")
        lines.append("")

    if blocked_inventory:
        lines.append("Connectors each governing policy blocks, as the policy names them")
        for policy_name, connectors in blocked_inventory.items():
            lines.append(f"  {policy_name}:")
            lines += [f"    {name}" for name in connectors]
        lines.append("")

    if any(finding.verdict != "unblocked" for finding in connector_findings) or violations:
        lines += ["Remediation", f"  {REMEDIATION}", ""]

    if probe_results:
        lines.append("Network egress from this machine")
        for result in probe_results:
            mark = _probe_mark(result)
            requirement = "required" if result.endpoint.required else "optional"
            lines.append(
                f"  {mark} {result.endpoint.protocol:<5} {result.endpoint.domain} "
                f"({requirement}) — {result.detail}"
            )
        lines.append("")

    return "\n".join(lines)


# The Copilot Studio required-services table (Learn: requirements-quotas#required-services).
# Wildcard rows are probed at a concrete regional host that the wildcard covers.
REQUIRED_ENDPOINTS = (
    Endpoint(
        domain="*.directline.botframework.com",
        probe_host="unitedstates.directline.botframework.com",
        path="/v3/directline/conversations",
        protocol="HTTPS",
        required=True,
        uses="Access to Bot Framework Web Chat",
    ),
    Endpoint(
        domain="*.directline.botframework.com",
        probe_host="unitedstates.directline.botframework.com",
        path="/v3/directline/conversations/preflight/stream",
        protocol="WS",
        required=True,
        uses="Web socket connection to support Chat",
    ),
    Endpoint(
        domain="*.powerva.microsoft.com",
        probe_host="web.powerva.microsoft.com",
        path="/",
        protocol="HTTPS",
        required=True,
        uses="Copilot Studio authoring experience and APIs",
    ),
    Endpoint(
        domain="*.analysis.windows.net",
        probe_host="api.analysis.windows.net",
        path="/",
        protocol="HTTPS",
        required=True,
        uses="Analytics reports shown in Copilot Studio (through Power BI)",
    ),
    Endpoint(
        domain="bot-framework.azureedge.net",
        probe_host="bot-framework.azureedge.net",
        path="/",
        protocol="HTTPS",
        required=True,
        uses="Bot Framework resources (CDN)",
    ),
    Endpoint(
        domain="cci-prod-botdesigner.azureedge.net",
        probe_host="cci-prod-botdesigner.azureedge.net",
        path="/",
        protocol="HTTPS",
        required=True,
        uses="Copilot Studio authoring experience (CDN)",
    ),
    # Optional rows: the demo publishes with no authentication and does not need
    # the Bot Framework OAuth redirect, and telemetry and in-product guidance are
    # recommendations rather than requirements.
    Endpoint(
        domain="token.botframework.com",
        probe_host="token.botframework.com",
        path="/",
        protocol="HTTPS",
        required=False,
        uses="Bot Framework OAuth redirect — manual authentication only",
    ),
    Endpoint(
        domain="cdn.botframework.com",
        probe_host="cdn.botframework.com",
        path="/botframework-webchat/latest/webchat.js",
        protocol="HTTPS",
        required=False,
        uses="Web Chat bundle — only if it is loaded from the CDN rather than bundled",
    ),
    Endpoint(
        domain="pipe.aria.microsoft.com",
        probe_host="pipe.aria.microsoft.com",
        path="/",
        protocol="HTTPS",
        required=False,
        uses="Client-side telemetry gathered by Microsoft",
    ),
    Endpoint(
        domain="pa-guided.azureedge.net",
        probe_host="pa-guided.azureedge.net",
        path="/",
        protocol="HTTPS",
        required=False,
        uses="In-product guidance (CDN)",
    ),
)

DEFAULT_ENVIRONMENT = "Default-0f87abfb-0840-4199-96b7-1882c01a998b"
POLICIES_URL = "https://api.bap.microsoft.com/providers/PowerPlatform.Governance/v2/policies?api-version=2016-11-01"
ENVIRONMENTS_URL = (
    "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform"
    "/scopes/admin/environments?api-version=2016-11-01"
)
BAP_RESOURCE = "https://api.bap.microsoft.com/"

# Exit codes: 0 clear, 1 something is blocked or unreachable, 2 undetermined.
UNDETERMINED = 2


def admin_visibility_error(environments, environment_id):
    """Why an empty policy list from this identity cannot be trusted, or None.

    A caller without tenant administrative scope is served an empty policy list
    rather than a denial, so "no policies" has to be corroborated by the same
    token being able to see the target environment through the admin scope.
    """
    names = {e.get("name") for e in environments if isinstance(e, dict)}
    if not names:
        return "the signed-in identity sees no environments through the admin scope"
    if environment_id not in names:
        return (
            f"the signed-in identity does not see {environment_id} through the admin scope "
            f"(it sees {', '.join(sorted(n for n in names if n))})"
        )
    return None


def fetch_json(token, url, timeout=30.0):
    """A BAP collection, following the service's paging links."""
    values = []
    while url:
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        values.extend(payload.get("value", []))
        url = payload.get("nextLink") or payload.get("@odata.nextLink")
    return values


def fetch_policies(token, url=POLICIES_URL, timeout=30.0):
    return fetch_json(token, url, timeout)


def fetch_admin_environments(token, timeout=30.0):
    return fetch_json(token, ENVIRONMENTS_URL, timeout)


def acquire_token(resource=BAP_RESOURCE):
    """A Power Platform admin token from the signed-in Azure CLI, or None."""
    completed = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        print(f"::error::could not acquire a Power Platform token: {completed.stderr.strip()}", file=sys.stderr)
        return None
    return completed.stdout.strip()


def _read_policies_file(path):
    """A saved data-policy payload, or None if the file is not one."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("value")
    if not isinstance(payload, list):
        print(
            f"{path} is not a data-policy payload: expected a list of policies or an "
            "object with a 'value' list",
            file=sys.stderr,
        )
        return None
    return payload


def _with_confirmed_stream(probe_results, args):
    """Replace the argued WebSocket row with the one a real 101 confirms."""
    try:
        confirmed = confirm_direct_line_websocket(
            args.direct_line_secret, timeout=args.timeout
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"could not confirm the Direct Line stream: {error}", file=sys.stderr)
        return probe_results
    return [confirmed if r.endpoint.protocol == "WS" else r for r in probe_results]


def _acquire_policies(args):
    """The policies to classify, or None when the question stays unanswered.

    Raises OSError or ValueError when the source itself failed; main turns
    those into UNDETERMINED rather than letting a traceback exit as a failure.
    """
    if args.policies_file:
        return _read_policies_file(args.policies_file)
    token = acquire_token()
    if not token:
        print(
            "Data-policy half undetermined. Re-run after `az login --tenant "
            f"{DEFAULT_ENVIRONMENT.removeprefix('Default-')}`, or pass --egress-only.",
            file=sys.stderr,
        )
        return None
    unseen = admin_visibility_error(fetch_admin_environments(token), args.environment)
    if unseen:
        print(f"Data-policy half undetermined: {unseen}.", file=sys.stderr)
        return None
    return fetch_policies(token)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument(
        "--policies-file",
        help="a saved data-policy payload, so a finding can be re-checked without a token",
    )
    parser.add_argument("--egress-only", action="store_true", help="skip the data-policy half")
    parser.add_argument("--skip-egress", action="store_true", help="skip the network-egress half")
    parser.add_argument(
        "--direct-line-secret",
        help=(
            "confirm the WebSocket row with a real 101 by starting a Direct Line "
            "conversation and dialling the stream URL the service returns"
        ),
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    if args.egress_only and args.skip_egress:
        print("--egress-only and --skip-egress together check nothing", file=sys.stderr)
        return UNDETERMINED

    findings, violations, inventory = [], [], {}
    if not args.egress_only:
        try:
            policies = _acquire_policies(args)
        except (OSError, ValueError) as error:
            print(
                f"Data-policy half undetermined: the policies could not be read "
                f"({type(error).__name__}: {error}).",
                file=sys.stderr,
            )
            return UNDETERMINED
        if policies is None:
            return UNDETERMINED
        findings = classify_connectors(policies, args.environment)
        violations = split_group_violations(policies, args.environment)
        inventory = blocked_group_inventory(policies, args.environment)

    probe_results = []
    if not args.skip_egress:
        probe_results = [probe(e, timeout=args.timeout) for e in REQUIRED_ENDPOINTS]
        if args.direct_line_secret:
            probe_results = _with_confirmed_stream(probe_results, args)

    print(format_report(findings, violations, probe_results, blocked_inventory=inventory))
    return exit_code(findings, violations, probe_results)


if __name__ == "__main__":
    sys.exit(main())
