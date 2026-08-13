#!/usr/bin/env python3
"""Preflight: is Dataverse search enabled and synced in the Default environment?

Dataverse search is off by default in a Default environment and gates the
"documents" knowledge source the Copilot Studio SOP agent is grounded on (#17).
It is the build's longest lead-time item, and the reason is that flipping the
toggle and having a document come back from a search are *different facts*: the
setting is one PATCH on the `organizations` row, and the index sync behind it
runs afterwards on its own clock.

So the check does not trust the toggle. It probes: it writes a document into
Dataverse carrying a unique marker, queries the search index for that marker,
and only passes once the document comes back — with the marker highlighted in
the **file content**, not merely in the record's metadata, because content is
what a knowledge source retrieves against.

`evaluate` is pure: it takes the organisation row, the search-status payload,
the probe result and the tenant's capacity, and returns a `Verdict`. The live
calls are in `main`.
"""

import json

SEARCH_SETTING = "isexternalsearchindexenabled"

# Duplicated from dataverse_admin_role rather than imported: this module is
# executed directly by its shell entry point, where the `preflight` package is
# not importable. `test_dataverse_search.py` asserts the two never drift — if
# they did, one check would enable search somewhere the other refuses to grant
# a role.
DEFAULT_ENVIRONMENT_ID = "Default-0f87abfb-0840-4199-96b7-1882c01a998b"

# A maker who follows a Copilot Studio URL without an explicit environment can
# be routed into their personal Developer environment, which is rate-capped and
# invisible to the demo. Enabling search there and reporting a pass would
# green-light #17 against an environment nothing else in this build touches.
DEVELOPER_REDIRECT_HAZARD = (
    "a personal Developer environment is not the environment this build "
    "provisions, and work done there is invisible to the demo"
)

PROVISIONED = "provisioned"

# Dataverse wraps each matched term in the highlight fragments it returns.
HIGHLIGHT_OPEN = "{crmhit}"

# The tables that hold an uploaded file's bytes. A marker found in one of these
# fields is the file's own content coming back out of the index; a marker found
# in `subject` or `filename` is only the record's metadata, which Dataverse
# indexes on a different clock. Documents-based knowledge retrieves against
# content, so the distinction decides the verdict.
CONTENT_FIELDS = ("documentbody", "body", "content")

FILE_CAPACITY = "File"

# Enough headroom to upload the SOP corpus and the troubleshooting knowledge
# base several times over. The point of the floor is to catch an *exhausted*
# pool before it refuses an upload, not to police normal use.
MINIMUM_FILE_HEADROOM_MB = 100

# Measured on 2026-08-13 (issue #3): 181 seconds from flipping the toggle to the
# first successful search on this environment. Recorded so the remedy can quote a
# number rather than an impression — but it is a *floor*, not a promise: this
# environment holds 148 MB of data, and Microsoft documents 15 minutes minimum
# with a full sync exceeding an hour on a populated one.
MEASURED_SYNC_SECONDS = 181

# A Default environment cannot be backed up, restored or deleted, so its
# customisations exist only in a solution export. This is the unmanaged solution
# that holds them — not `Default` ("Default Solution"), which is the system
# catalogue of every component in the org.
DEFAULT_SOLUTION = "Cr688e5"

# The document check's "no evidence" detail, matched by the remedy so the two
# cannot drift into contradicting each other.
NOT_PROBED = "not probed"


class Capacity:
    """One capacity type as the licensing API reports it, in megabytes."""

    def __init__(self, capacity_type, total_mb, used_mb, status=None):
        self.capacity_type = capacity_type
        self.total_mb = total_mb
        self.used_mb = used_mb
        self.status = status

    @property
    def headroom_mb(self):
        return self.total_mb - self.used_mb


def capacity_of(capacities, capacity_type):
    """Return the named `Capacity`, or None. Pure.

    Only megabyte-denominated entries are read: the same list carries unit-
    denominated quotas (environment counts, API calls) whose numbers would be
    nonsense if compared against a megabyte floor.
    """
    for entry in capacities or []:
        if entry.get("capacityType") != capacity_type:
            continue
        if entry.get("capacityUnits") != "MB":
            continue
        consumption = entry.get("consumption") or {}
        return Capacity(
            capacity_type,
            float(entry.get("totalCapacity") or 0.0),
            float(consumption.get("actual") or 0.0),
            entry.get("status"),
        )
    return None


class SearchHit:
    """One record the search index returned for the probe's marker."""

    def __init__(self, entity, object_id, highlights):
        self.entity = entity
        self.object_id = object_id
        self.highlights = highlights

    @property
    def content_indexed(self):
        """True when the marker came back out of the file's own content."""
        return any(
            _highlighted(self.highlights.get(field))
            for field in CONTENT_FIELDS
        )

    @property
    def fields(self):
        return sorted(self.highlights)


def _highlighted(fragments):
    return any(HIGHLIGHT_OPEN in fragment for fragment in fragments or [])


class Probe:
    """A marker written into Dataverse and looked for in the search index.

    `elapsed_seconds` is how long the marker took to become findable, measured
    from whichever moment the caller started the clock. It is the number the
    build schedules against, so it is carried on the result rather than logged
    and thrown away.
    """

    def __init__(self, marker, hit, elapsed_seconds=None, cleanup_error=None):
        self.marker = marker
        self.hit = hit
        self.elapsed_seconds = elapsed_seconds
        self.cleanup_error = cleanup_error

    @property
    def found(self):
        return self.hit is not None

    @property
    def content_indexed(self):
        return bool(self.hit and self.hit.content_indexed)


class Check:
    """One named precondition and whether the observed tenant state meets it."""

    def __init__(self, name, ok, detail):
        self.name = name
        self.ok = ok
        self.detail = detail


class Verdict:
    """The outcome of every check, and whether they all passed."""

    def __init__(self, checks):
        self.checks = checks

    @property
    def ok(self):
        return all(check.ok for check in self.checks)

    def check(self, name):
        """Return the named `Check`."""
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)


def created_entity_id(headers, payload):
    """Return the id of a just-created Dataverse record, or None. Pure.

    A create answers `204 No Content` unless `Prefer: return=representation`
    was asked for, so the id arrives in the `OData-EntityId` response header as
    a full URL — `.../annotations(<guid>)`. Reading the body alone yields None,
    and a None id turns the probe's cleanup into a silent no-op.
    """
    location = (headers or {}).get("OData-EntityId")
    if location and location.endswith(")") and "(" in location:
        return location.rsplit("(", 1)[1][:-1]
    for key, value in (payload or {}).items():
        if key.endswith("id") and isinstance(value, str):
            return value
    return None


def index_status(payload):
    """Return the search index's status string, or None. Pure.

    The two API versions answer the same question in different shapes: v1.0
    returns the status as a mapping under `value`, while v2.0 returns the whole
    v1.0 payload **double-encoded as a JSON string** under `response`. Reading
    the v2.0 shape as a mapping yields nothing, which would report a healthy
    index as unprovisioned, so both are decoded here.
    """
    if not isinstance(payload, dict):
        return None
    if "response" in payload:
        try:
            payload = json.loads(payload["response"])
        except (TypeError, ValueError):
            return None
    value = payload.get("value")
    if not isinstance(value, dict):
        return None
    return value.get("status")


def document_hit(response, marker):
    """Return the `SearchHit` for `marker`, or None. Pure.

    The marker has to appear in the *highlights* rather than merely in a
    response that came back non-empty: a search for a nonsense token that
    returns unrelated records is a miss, not a hit.
    """
    for result in (response or {}).get("value") or []:
        highlights = result.get("@search.highlights") or {}
        if any(
            marker in fragment
            for fragments in highlights.values()
            for fragment in fragments or []
        ):
            return SearchHit(
                result.get("@search.entityname"),
                result.get("@search.objectid"),
                highlights,
            )
    return None


def evaluate(environment, organization, status, probe, capacity):
    """Return the `Verdict` for Dataverse search in an environment. Pure."""
    return Verdict(
        [
            _identity_check(environment),
            _enabled_check(organization),
            _provisioned_check(status),
            _document_check(probe),
            _cleanup_check(probe),
            _capacity_check(capacity),
        ]
    )


def _identity_check(environment):
    """Whether the environment under check is the tenant's Default one.

    Checked *before* anything is enabled, for the same reason the admin-role
    preflight refuses to elevate into the wrong environment: a write to a
    Developer environment a maker was silently routed into is worse than no
    write at all, because it reports success somewhere the demo never runs.
    """
    observed = (environment or {}).get("name")
    if observed == DEFAULT_ENVIRONMENT_ID:
        return Check(
            "default-environment-identity",
            True,
            f"the environment under check is {observed!r}",
        )
    sku = ((environment or {}).get("properties") or {}).get("environmentSku")
    return Check(
        "default-environment-identity",
        False,
        f"the environment under check is {observed!r} (SKU {sku!r}), not the "
        f"expected {DEFAULT_ENVIRONMENT_ID!r} — {DEVELOPER_REDIRECT_HAZARD}",
    )


def _cleanup_check(probe):
    """Whether the probe removed the document it wrote.

    Its own check rather than a warning on stdout, because the caller that
    matters is an unattended loop that reads the exit code. A probe that leaves
    a document behind on every run fills the tenant-wide file pool this same
    check reports headroom for.
    """
    if probe is None:
        return Check("probe-document-removed", True, "nothing was written")
    if probe.cleanup_error:
        return Check(
            "probe-document-removed",
            False,
            f"the probe document {probe.marker!r} could not be deleted and is "
            f"still in the environment: {probe.cleanup_error}",
        )
    return Check(
        "probe-document-removed",
        True,
        "the probe deleted the document it wrote",
    )


def _provisioned_check(status):
    if status == PROVISIONED:
        return Check(
            "search-index-provisioned",
            True,
            f"the search index reports {PROVISIONED!r}",
        )
    return Check(
        "search-index-provisioned",
        False,
        f"the search index reports {status!r}, not {PROVISIONED!r}",
    )


def _document_check(probe):
    """Whether a document written to Dataverse came back out of the index.

    Three outcomes, deliberately distinguished: not found at all (the sync is
    still running, which is the expected state for the first minutes), found by
    its metadata only (a half-synced index — the record is searchable but the
    file's bytes are not, and a knowledge source retrieves against the bytes),
    and found by its content, which is the only pass.
    """
    if probe is None:
        return Check(
            "indexed-document-hit",
            False,
            f"{NOT_PROBED} — the toggle alone is not evidence that the index "
            "has synced, and only a document coming back out of it is",
        )
    if not probe.found:
        return Check(
            "indexed-document-hit",
            False,
            f"no document carrying marker {probe.marker!r} came back from the "
            "search index — the toggle is not the sync, and the sync is what "
            "#17 waits on",
        )
    if not probe.content_indexed:
        return Check(
            "indexed-document-hit",
            False,
            f"the test document was found by {probe.hit.fields} but not by its "
            f"file content ({', '.join(CONTENT_FIELDS)}) — the index is only "
            "half synced and documents-based knowledge retrieves against content",
        )
    return Check(
        "indexed-document-hit",
        True,
        f"a test document uploaded to {probe.hit.entity} came back from the "
        f"search index by its file content{_timing(probe)}",
    )


def _timing(probe):
    """How long the marker took to become findable, and from when.

    From the *write*, not from enabling. On a warm index that is seconds; the
    number this ticket records — the sync itself — is only measurable on the
    first probe after the toggle, and conflating them would understate the lead
    time by the whole cold start.
    """
    if probe.elapsed_seconds is None:
        return ""
    return f", {probe.elapsed_seconds}s after the document was written"


def _capacity_check(capacity):
    """Whether there is Dataverse **file** capacity left to upload documents into.

    Dataverse-based knowledge is files in Dataverse, and file capacity is
    pooled tenant-wide rather than held per environment, so a different
    environment can exhaust it. Exhausted capacity does not disable search — it
    refuses the upload, which surfaces much later and looks like a Copilot
    Studio fault.
    """
    file_capacity = capacity_of(capacity, FILE_CAPACITY)
    if file_capacity is None:
        return Check(
            "file-capacity-headroom",
            False,
            "the tenant's file capacity could not be read, so headroom for "
            "uploading documents is unknown",
        )
    if file_capacity.headroom_mb < MINIMUM_FILE_HEADROOM_MB:
        return Check(
            "file-capacity-headroom",
            False,
            f"only {file_capacity.headroom_mb:.0f} MB of file capacity is left "
            f"(of {file_capacity.total_mb:.0f} MB, shared tenant-wide) — "
            "document upload will be refused",
        )
    return Check(
        "file-capacity-headroom",
        True,
        f"{file_capacity.headroom_mb:.0f} MB of file capacity is free "
        f"({file_capacity.used_mb:.0f} MB used of {file_capacity.total_mb:.0f} "
        "MB, shared tenant-wide)",
    )


def format_report(verdict, remedy=None):
    """Return the human-readable report for a `Verdict`. Pure.

    The consequence — whether the Copilot Studio SOP agent (#17) can be
    grounded on documents — is derived from the verdict rather than stated
    unconditionally, because it is a consequence of the index being synced and
    not an independent fact.
    """
    lines = [
        f"  {'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}"
        for c in verdict.checks
    ]
    consequence = (
        "documents-based knowledge is selectable and returns hits"
        if verdict.ok
        else "documents-based knowledge is not usable yet"
    )
    lines.append(f"  ----  Copilot Studio SOP agent (#17): {consequence}")
    if not verdict.ok:
        lines.append(remedy if remedy is not None else _remedy(verdict))
    return "\n".join(lines)


def _remedy(verdict):
    """Return the operator's next step for a failing verdict. Pure.

    Ordered by what has to be true first. The distinction that matters is
    between a toggle that was never flipped and an index still syncing behind a
    toggle that was: the first is fixed by a PATCH, the second only by waiting,
    and re-flipping a setting that is already on fixes nothing while looking
    like action.
    """
    if not verdict.check("default-environment-identity").ok:
        return (
            "\nRemedy: wrong environment — do not enable search here. Re-run "
            f"against the tenant's Default environment "
            f"({DEFAULT_ENVIRONMENT_ID}), or pass --environment with the "
            "identifier the Copilot Studio URL actually shows."
        )
    if not verdict.check("dataverse-search-enabled").ok:
        return (
            "\nRemedy: Dataverse search is off in this environment. Turn it on "
            "and start the sync clock:\n"
            "  scripts/preflight/check-dataverse-search.sh --enable --probe"
        )
    if not verdict.check("file-capacity-headroom").ok:
        return (
            "\nRemedy: free tenant-wide Dataverse file capacity, or add "
            "capacity. Search is unaffected; the document upload is what is "
            "refused."
        )
    if not verdict.check("search-index-provisioned").ok:
        return (
            "\nRemedy: the index is not provisioned yet. This is a wait, not a "
            "fix. Re-run the check.\n"
            "  scripts/preflight/check-dataverse-search.sh --probe"
        )
    if NOT_PROBED in verdict.check("indexed-document-hit").detail:
        return (
            "\nRemedy: nothing is known to be wrong — this run simply gathered "
            "no evidence. Probe for it:\n"
            "  scripts/preflight/check-dataverse-search.sh --probe"
        )
    return (
        "\nRemedy: the toggle is on and the index is provisioned, so this is "
        "the sync window — a wait, not a fix. Re-run the probe until the "
        f"document comes back (measured at {MEASURED_SYNC_SECONDS}s on a nearly "
        "empty environment; a populated one takes considerably longer):\n"
        "  scripts/preflight/check-dataverse-search.sh --probe"
    )


def _enabled_check(organization):
    enabled = (organization or {}).get(SEARCH_SETTING)
    if enabled:
        return Check(
            "dataverse-search-enabled",
            True,
            f"{SEARCH_SETTING} is true on the organisation",
        )
    return Check(
        "dataverse-search-enabled",
        False,
        f"{SEARCH_SETTING} is {enabled!r} — documents-based knowledge is not "
        "selectable in this environment",
    )


# ---------------------------------------------------------------------------
# Live calls. Everything above this line is pure and unit-tested.
# ---------------------------------------------------------------------------

BAP_API = "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform"
BAP_RESOURCE = "https://api.bap.microsoft.com/"
BAP_API_VERSION = "2020-10-01"

# Tenant-wide storage capacity is not on the BAP admin API at all — neither
# `scopes/admin/tenant/capacity` (404) nor `$expand=capacity` on the environment
# (null). It is on the licensing service, which is a separate resource and so a
# separate token.
LICENSING_API = "https://licensing.powerplatform.microsoft.com"
LICENSING_RESOURCE = "https://licensing.powerplatform.microsoft.com/"

DATAVERSE_API_VERSION = "v9.2"

# The probe polls rather than waiting a fixed time: the sync is minutes on an
# empty environment and can exceed an hour on a populated one, so a fixed sleep
# would either fail a healthy tenant or waste an hour on a broken one.
PROBE_ATTEMPTS = 60
PROBE_DELAY_SECONDS = 15

PROBE_PREFIX = "flwpreflight"


def _token(resource):
    """Return an access token for `resource` from the signed-in Azure CLI."""
    import subprocess

    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"could not get a token for {resource}; run:\n"
            f"  az login --scope \"{resource}/.default\"\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _request(url, resource, method="GET", body=None, token=None,
             with_headers=False):
    import urllib.error
    import urllib.request

    headers = {"Authorization": "Bearer " + (token or _token(resource))}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method,
                                     headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read().decode()
            decoded = json.loads(payload) if payload.strip() else {}
            if with_headers:
                return decoded, dict(response.headers)
            return decoded
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"{method} {url} → {error.code}: {error.read().decode()[:400]}"
        ) from error


def read_live(environment_id=None):
    """Return (the environment, its organisation row, the index status, capacity)."""
    environment = _environment(environment_id)
    url = (
        ((environment.get("properties") or {}).get("linkedEnvironmentMetadata")
         or {}).get("instanceUrl")
    )
    if not url:
        # A named environment with no Dataverse instance is a fact to report,
        # not an exception — it is exactly the state an operator who mistyped an
        # identifier is in, and the identity check already says so precisely.
        return environment, {}, None, read_capacity_live()
    resource = f"{url.rstrip('/')}/"
    base = f"{url.rstrip('/')}/api/data/{DATAVERSE_API_VERSION}"
    token = _token(resource)

    organization = _request(
        f"{base}/organizations?$select=organizationid,name,{SEARCH_SETTING}",
        resource, token=token,
    )["value"][0]
    organization["_base"] = base
    organization["_resource"] = resource

    status = None
    if organization.get(SEARCH_SETTING):
        # Asking an environment with the setting off answers 'notprovisioned',
        # which is true but reads as a fault; the enabled check already said so.
        status = index_status(
            _request(f"{url.rstrip('/')}/api/search/v1.0/status", resource,
                     token=token)
        )
    return environment, organization, status, read_capacity_live()


def _environment(environment_id=None):
    """Return the environment under check, as the BAP admin API returns it.

    An identifier the tenant does not have is reported by name rather than
    silently falling back to the Default environment — the caller passed it
    because that is what the Copilot Studio URL showed them.
    """
    environments = _request(
        f"{BAP_API}/scopes/admin/environments?api-version={BAP_API_VERSION}",
        BAP_RESOURCE,
    )["value"]
    for environment in environments:
        if environment_id:
            if environment.get("name") == environment_id:
                return environment
        elif (environment.get("properties") or {}).get("isDefault"):
            return environment
    if environment_id:
        return {"name": environment_id, "properties": {}}
    raise RuntimeError("the tenant has no Default environment")


def read_capacity_live():
    """Return the tenant's storage capacity entries, or None if unreadable.

    Capacity is a note, not a gate on the search itself, so a licensing service
    that cannot be reached must not fail the run with a traceback — it fails its
    own check, which says the headroom is unknown.
    """
    import subprocess

    try:
        tenant_id = subprocess.run(
            ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return _request(
            f"{LICENSING_API}/v0.1-alpha/tenants/{tenant_id}/TenantCapacity",
            LICENSING_RESOURCE,
        ).get("tenantCapacities")
    except Exception:  # noqa: BLE001 — reported as an unknown-headroom check
        return None


def enable_live(organization):
    """Turn Dataverse search on for the environment."""
    _request(
        f"{organization['_base']}/organizations({organization['organizationid']})",
        organization["_resource"],
        method="PATCH",
        body={SEARCH_SETTING: True},
    )


def probe_live(organization, marker=None):
    """Write a marked document into Dataverse and wait for search to return it.

    The document is deleted afterwards whatever happens: this check is
    re-runnable, and a check that leaves a record behind on every run silently
    fills the tenant-wide file pool it also reports on.
    """
    import time
    import uuid

    marker = marker or f"{PROBE_PREFIX}{uuid.uuid4().hex[:12]}"
    base = organization["_base"]
    resource = organization["_resource"]
    started = time.monotonic()

    annotation_id = _create_probe_document(base, resource, marker)
    hit = None
    try:
        for attempt in range(PROBE_ATTEMPTS):
            hit = document_hit(_query_live(base, resource, marker), marker)
            if hit is not None and hit.content_indexed:
                break
            if attempt < PROBE_ATTEMPTS - 1:
                time.sleep(PROBE_DELAY_SECONDS)
    finally:
        cleanup_error = _delete_probe_document(base, resource, annotation_id,
                                               marker)
    return Probe(marker, hit, round(time.monotonic() - started), cleanup_error)


def _create_probe_document(base, resource, marker):
    import base64

    body = base64.b64encode(
        f"Dataverse search preflight. Marker {marker}. This document exists "
        "only to prove the search index finished its initial sync.".encode()
    ).decode()
    payload, headers = _request(
        f"{base}/annotations", resource, method="POST",
        body={
            "subject": f"Dataverse search preflight {marker}",
            "notetext": f"Marker {marker}",
            "filename": f"{marker}.txt",
            "mimetype": "text/plain",
            "documentbody": body,
        },
        with_headers=True,
    )
    # None is survivable rather than fatal: the document carries its marker in
    # its subject, so cleanup can find it again. Raising here would orphan the
    # very document it was trying not to leave behind — the create has already
    # happened by this point.
    return created_entity_id(headers, payload)


def _query_live(base, resource, marker):
    search = base.rsplit("/api/data/", 1)[0] + "/api/search/v1.0/query"
    return _request(search, resource, method="POST",
                    body={"search": marker, "top": 5})


def _delete_probe_document(base, resource, annotation_id, marker):
    """Delete the probe document. Return None, or why it could not be deleted.

    Reported rather than raised, so a cleanup failure does not mask the search
    result the probe just established — but returned rather than printed, so it
    reaches the verdict and therefore the exit code.
    """
    annotation_id = annotation_id or _find_probe_document(base, resource, marker)
    if not annotation_id:
        return f"the document could not be found again by marker {marker!r}"
    try:
        _request(f"{base}/annotations({annotation_id})", resource,
                 method="DELETE")
    except Exception as error:  # noqa: BLE001 — reported through the verdict
        return str(error)
    return None


def _find_probe_document(base, resource, marker):
    """Find the probe document by its marker, for when its id was never read."""
    try:
        results = _request(
            f"{base}/annotations?$select=annotationid"
            f"&$filter=contains(subject,'{marker}')",
            resource,
        )["value"]
    except Exception:  # noqa: BLE001 — the caller reports "could not be found"
        return None
    return results[0]["annotationid"] if results else None


def export_solution_live(base, resource, solution_name, directory):
    """Export `solution_name` as an unmanaged solution zip into `directory`.

    A Default environment cannot be backed up, restored or deleted, so the
    solution export is the only copy of its customisations that exists.
    """
    import base64
    import datetime
    import os

    payload = _request(
        f"{base}/ExportSolution", resource, method="POST",
        body={
            "SolutionName": solution_name,
            "Managed": False,
            "ExportAutoNumberingSettings": False,
            "ExportCalendarSettings": False,
            "ExportCustomizationSettings": False,
            "ExportEmailTrackingSettings": False,
            "ExportGeneralSettings": False,
            "ExportIsvConfig": False,
            "ExportMarketingSettings": False,
            "ExportOutlookSynchronizationSettings": False,
            "ExportRelationshipRoles": False,
            "ExportSales": False,
        },
    )
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{solution_name}-{stamp}.zip")
    with open(path, "wb") as handle:
        handle.write(base64.b64decode(payload["ExportSolutionFile"]))
    return path


def main(argv=None, read=read_live, enable=enable_live, run_probe=probe_live):
    import sys

    argv = sys.argv[1:] if argv is None else argv
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    environment_id = _argument(argv, "--environment")

    environment, organization, status, capacity = read(environment_id)

    # Nothing is written into an environment whose identity does not check out.
    wrong_environment = not _identity_check(environment).ok
    if "--enable" in argv and not wrong_environment and not organization.get(
        SEARCH_SETTING
    ):
        enable(organization)
        print(f"enabled Dataverse search on {environment.get('name')!r}")
        environment, organization, status, capacity = read(environment_id)

    probe = (
        run_probe(organization)
        if "--probe" in argv and not wrong_environment
        else None
    )
    verdict = evaluate(environment, organization, status, probe, capacity)

    export = _argument(argv, "--export")
    if export:
        path = export_solution_live(
            organization["_base"], organization["_resource"],
            _argument(argv, "--solution") or DEFAULT_SOLUTION, export,
        )
        print(f"exported solution to {path}")

    print(f"\nDataverse search — {environment.get('name', 'unknown environment')}")
    print(format_report(verdict))
    return 0 if verdict.ok else 1


def _argument(argv, name):
    """Return the value following `name` in `argv`, or None."""
    if name in argv:
        position = argv.index(name) + 1
        if position < len(argv):
            return argv[position]
    return None


if __name__ == "__main__":
    raise SystemExit(main())
