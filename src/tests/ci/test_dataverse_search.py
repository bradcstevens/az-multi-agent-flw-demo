"""Tests for the Dataverse search preflight check (issue #3).

Dataverse search is not on by default in a Default environment, and it is the
longest lead-time item in the build: enabling it is a toggle, but the index
sync behind it takes minutes to over an hour. So the question this check
answers is not "is the toggle on?" but "has a document uploaded to Dataverse
actually come back from a search?" — the toggle and the sync are different
facts, read from different APIs, and only the second one unblocks #17.

The seam under test is the pure evaluation: given the organisation row, the
search-status payload, the result of a marker probe and the tenant's capacity,
`evaluate` decides whether Dataverse-based knowledge is usable. The live HTTP
calls sit outside it, in `main`.
"""

from preflight.dataverse_admin_role import (
    DEFAULT_ENVIRONMENT_ID,
)
from preflight.dataverse_search import (
    Probe,
    capacity_of,
    created_entity_id,
    document_hit,
    evaluate,
    format_report,
    index_status,
    main,
)


ORGANIZATION_ID = "d3c93f69-ac94-f011-8706-000d3a106522"
MARKER = "flwpreflight7a3f9c2e"

# The licensing API's tenant capacity, in the shape it returns.
CAPACITY = [
    {
        "capacityType": "File",
        "capacityUnits": "MB",
        "totalCapacity": 20480.0,
        "consumption": {"actual": 1915.291},
        "status": "Available",
    },
    {
        "capacityType": "Database",
        "capacityUnits": "MB",
        "totalCapacity": 5120.0,
        "consumption": {"actual": 148.125},
        "status": "Available",
    },
]
ANNOTATION_ID = "939ce1bb-e096-f111-8076-0022482abf62"


def search_response(highlights=None, entity="annotation"):
    """A `POST /api/search/v1.0/query` response shaped like the live one."""
    return {
        "querycontext": None,
        "facets": {},
        "totalrecordcount": -1,
        "value": [
            {
                "@search.score": 22.226927,
                "@search.entityname": entity,
                "@search.objectid": ANNOTATION_ID,
                "@search.highlights": (
                    {
                        "filename": [f"{{crmhit}}{MARKER}{{/crmhit}}.txt"],
                        "subject": [f"preflight {{crmhit}}{MARKER}{{/crmhit}}"],
                        "notetext": [f"Marker {{crmhit}}{MARKER}{{/crmhit}}"],
                        "documentbody": [f"Marker {{crmhit}}{MARKER}{{/crmhit}}."],
                    }
                    if highlights is None
                    else highlights
                ),
            }
        ],
    }


def environment(name=DEFAULT_ENVIRONMENT_ID, sku="Default"):
    """A Power Platform environment as the BAP admin API returns it."""
    return {
        "name": name,
        "properties": {
            "displayName": "Contoso (default)",
            "isDefault": sku == "Default",
            "environmentSku": sku,
            "linkedEnvironmentMetadata": {
                "instanceUrl": "https://org5dadb450.crm.dynamics.com/",
                "instanceState": "Ready",
            },
        },
    }


def organization(**overrides):
    """An `organizations` row shaped like the Dataverse Web API's."""
    row = {
        "organizationid": ORGANIZATION_ID,
        "name": "org5dadb450",
        "isexternalsearchindexenabled": True,
    }
    row.update(overrides)
    return row


def test_search_disabled_fails_the_enabled_check():
    verdict = evaluate(
        environment(),
        organization(isexternalsearchindexenabled=False),
        status=None,
        probe=None,
        capacity=None,
    )

    assert not verdict.ok
    assert not verdict.check("dataverse-search-enabled").ok


def test_a_hit_highlighting_the_file_content_is_a_document_hit():
    hit = document_hit(search_response(), MARKER)

    assert hit is not None
    assert hit.object_id == ANNOTATION_ID
    assert hit.entity == "annotation"
    assert hit.content_indexed


def test_a_hit_highlighting_only_metadata_is_not_content_indexed():
    """The toggle can be on and the record found by its subject while the file
    body is still unindexed. Knowledge sources retrieve against content, so that
    state is a half-synced index, not a pass."""
    metadata_only = search_response(
        highlights={
            "subject": [f"preflight {{crmhit}}{MARKER}{{/crmhit}}"],
            "filename": [f"{{crmhit}}{MARKER}{{/crmhit}}.txt"],
        }
    )

    hit = document_hit(metadata_only, MARKER)

    assert hit is not None
    assert not hit.content_indexed


def test_no_results_is_no_hit():
    assert document_hit({"value": []}, MARKER) is None


PROVISIONED_PAYLOAD = {
    "value": {
        "status": "provisioned",
        "lockboxstatus": "Disabled",
        "cmkstatus": "Disabled",
        "totalTimeToGenerateStatusInMs": 0,
    }
}


def test_index_status_reads_the_v1_shape():
    assert index_status(PROVISIONED_PAYLOAD) == "provisioned"


def test_index_status_reads_the_v2_shape_whose_payload_is_a_json_string():
    """v2.0 answers the same question with the payload double-encoded under
    `response`. Reading it as a mapping yields None and would report a
    provisioned index as unprovisioned."""
    import json

    v2 = {
        "@odata.context": "https://org.crm.dynamics.com/api/data/v9.0/$metadata",
        "response": json.dumps(PROVISIONED_PAYLOAD),
    }

    assert index_status(v2) == "provisioned"


def test_index_status_of_an_unparseable_payload_is_none():
    assert index_status({"response": "not json"}) is None
    assert index_status(None) is None


def probe(response=None, elapsed_seconds=181):
    """A completed marker probe, as `main` builds it from the live query."""
    if response is None:
        response = search_response()
    return Probe(MARKER, document_hit(response, MARKER), elapsed_seconds)


def test_an_enabled_provisioned_index_returning_the_document_passes():
    verdict = evaluate(
        environment(),
        organization(),
        status="provisioned",
        probe=probe(),
        capacity=CAPACITY,
    )

    assert verdict.ok, verdict.check("indexed-document-hit").detail


def test_the_toggle_alone_does_not_pass_when_the_document_is_not_found_yet():
    """The whole reason this check probes: `isexternalsearchindexenabled` is
    true the instant the PATCH returns, and the index sync behind it is what
    #17 actually waits on."""
    verdict = evaluate(
        environment(),
        organization(),
        status="provisioned",
        probe=probe(response={"value": []}),
        capacity=CAPACITY,
    )

    assert not verdict.ok
    assert verdict.check("dataverse-search-enabled").ok
    assert not verdict.check("indexed-document-hit").ok


def test_a_metadata_only_hit_does_not_pass_the_document_check():
    verdict = evaluate(
        environment(),
        organization(),
        status="provisioned",
        probe=probe(
            response=search_response(
                highlights={"subject": [f"x {{crmhit}}{MARKER}{{/crmhit}}"]}
            )
        ),
        capacity=CAPACITY,
    )

    assert not verdict.check("indexed-document-hit").ok


def test_an_unprovisioned_index_fails_the_provisioned_check():
    verdict = evaluate(
        environment(),
        organization(),
        status="notprovisioned",
        probe=probe(),
        capacity=CAPACITY,
    )

    assert not verdict.ok
    assert not verdict.check("search-index-provisioned").ok


def test_file_capacity_is_read_in_megabytes_with_its_headroom():
    file_capacity = capacity_of(CAPACITY, "File")

    assert file_capacity.total_mb == 20480.0
    assert file_capacity.used_mb == 1915.291
    assert round(file_capacity.headroom_mb) == 18565


def test_capacity_ignores_entries_that_are_not_denominated_in_megabytes():
    """The same list carries unit-denominated quotas. Reading
    `M365EnvironmentCount`'s total of 5 as 5 MB would report an exhausted pool
    and fail a healthy tenant."""
    unit_denominated = [
        {
            "capacityType": "File",
            "capacityUnits": "Unit",
            "totalCapacity": 5.0,
            "consumption": {"actual": 0.0},
        }
    ]

    assert capacity_of(unit_denominated, "File") is None


def test_an_exhausted_file_pool_fails_even_with_a_synced_index():
    """File capacity is pooled tenant-wide, so another environment can exhaust
    it. Search still works; the document upload is what gets refused."""
    exhausted = [
        {
            "capacityType": "File",
            "capacityUnits": "MB",
            "totalCapacity": 20480.0,
            "consumption": {"actual": 20470.0},
        }
    ]

    verdict = evaluate(
        environment(),
        organization(), status="provisioned", probe=probe(), capacity=exhausted
    )

    assert not verdict.ok
    assert verdict.check("indexed-document-hit").ok
    assert not verdict.check("file-capacity-headroom").ok


def test_the_report_names_every_check_and_the_consequence_for_the_sop_agent():
    report = format_report(
        evaluate(environment(), organization(), "provisioned", probe(), CAPACITY)
    )

    assert "PASS  dataverse-search-enabled" in report
    assert "PASS  search-index-provisioned" in report
    assert "PASS  indexed-document-hit" in report
    assert "PASS  file-capacity-headroom" in report
    assert "#17" in report


def test_a_failing_report_carries_the_remedy_for_the_check_that_failed():
    """A run during the sync window is the common failure, and its remedy is to
    wait and re-run — not to re-flip a toggle that is already on."""
    report = format_report(
        evaluate(
            environment(),
            organization(),
            "provisioned",
            probe(response={"value": []}),
            CAPACITY,
        )
    )

    assert "FAIL  indexed-document-hit" in report
    assert "Remedy" in report
    assert "--probe" in report


def test_a_disabled_toggle_is_remedied_by_enabling_it_not_by_waiting():
    report = format_report(
        evaluate(
            environment(),
            organization(isexternalsearchindexenabled=False),
            None,
            probe(response={"value": []}),
            CAPACITY,
        )
    )

    assert "--enable" in report


class FakeTenant:
    """The live reads and writes `main` makes, recorded rather than performed."""

    def __init__(self, enabled=True, response=None, capacity=None,
                 env=None):
        self.environment = env if env is not None else environment()
        self.enabled = enabled
        self.response = search_response() if response is None else response
        self.capacity = CAPACITY if capacity is None else capacity
        self.enabled_calls = 0
        self.probe_calls = 0

    def read(self, environment_id=None):
        return (
            self.environment,
            organization(isexternalsearchindexenabled=self.enabled),
            "provisioned",
            self.capacity,
        )

    def enable(self, organization_row):
        self.enabled_calls += 1
        self.enabled = True

    def run_probe(self, organization_row, marker=None):
        self.probe_calls += 1
        return Probe(MARKER, document_hit(self.response, MARKER), 181)


def test_main_exits_zero_when_the_index_returns_the_document():
    tenant = FakeTenant()

    assert (
        main(
            ["--probe"],
            read=tenant.read,
            enable=tenant.enable,
            run_probe=tenant.run_probe,
        )
        == 0
    )


def test_main_exits_non_zero_while_the_sync_is_still_running():
    tenant = FakeTenant(response={"value": []})

    assert (
        main(
            ["--probe"],
            read=tenant.read,
            enable=tenant.enable,
            run_probe=tenant.run_probe,
        )
        == 1
    )


def test_main_does_not_probe_unless_asked():
    """A probe writes a document into Dataverse. A bare check is a read, so it
    stays a read — an operator asking "is it on?" should not leave litter."""
    tenant = FakeTenant()

    main([], read=tenant.read, enable=tenant.enable, run_probe=tenant.run_probe)

    assert tenant.probe_calls == 0


def test_enable_flips_the_toggle_and_then_re_reads_rather_than_assuming():
    tenant = FakeTenant(enabled=False)

    exit_code = main(
        ["--enable", "--probe"],
        read=tenant.read,
        enable=tenant.enable,
        run_probe=tenant.run_probe,
    )

    assert tenant.enabled_calls == 1
    assert exit_code == 0


def test_enable_is_a_no_op_when_search_is_already_on():
    """Re-flipping a setting that is already on is not free — it is a write
    against the organisation row, and on a Default environment that cannot be
    restored, needless writes are the thing to avoid."""
    tenant = FakeTenant(enabled=True)

    main(
        ["--enable", "--probe"],
        read=tenant.read,
        enable=tenant.enable,
        run_probe=tenant.run_probe,
    )

    assert tenant.enabled_calls == 0


def test_a_run_that_did_not_probe_says_so_rather_than_reporting_a_bad_index():
    """A bare run gathers no evidence, and "no evidence" is not "broken". It
    still fails — the toggle is not the evidence, which is this check's whole
    thesis — but an operator must not read it as a stalled sync and go waiting
    for something that was never started."""
    verdict = evaluate(environment(), organization(), "provisioned", probe=None, capacity=CAPACITY)

    document = verdict.check("indexed-document-hit")
    assert not document.ok
    assert "not probed" in document.detail
    assert "None" not in document.detail
    assert "--probe" in format_report(verdict)


def test_the_probe_timing_is_reported_from_the_write_not_from_enabling():
    """The two numbers differ by the whole cold-start sync. A re-run on a warm
    index measures seconds from writing the document; only the very first run
    after the toggle measures the sync itself. Labelling the warm number "after
    enabling" would understate the lead time this ticket exists to record."""
    detail = evaluate(
        environment(),
        organization(), "provisioned", probe(), CAPACITY
    ).check("indexed-document-hit").detail

    assert "36s after enabling" not in detail.replace("181", "36")
    assert "181s after the document was written" in detail


def test_not_probing_is_remedied_by_probing_not_by_waiting():
    """"Wait, do not fix" is the right advice for a sync in progress and the
    wrong advice for a run that never gathered evidence — it sends the operator
    away to wait for something that was never started."""
    report = format_report(
        evaluate(environment(), organization(), "provisioned", probe=None, capacity=CAPACITY)
    )

    assert "--probe" in report
    assert "a wait, not a fix" not in report


def test_a_probe_that_found_nothing_is_remedied_by_waiting():
    report = format_report(
        evaluate(
            environment(),
            organization(), "provisioned", probe(response={"value": []}), CAPACITY
        )
    )

    assert "a wait, not a fix" in report


def test_the_created_id_is_read_from_the_odata_entity_id_header():
    """Dataverse answers a create with 204 and no body. Reading the id from the
    body alone yields None, and a None id makes the probe's cleanup a silent
    no-op — which leaves a document behind in the tenant-wide file pool this
    same check reports headroom for. Observed live, not hypothesised."""
    headers = {
        "OData-EntityId": (
            "https://org5dadb450.crm.dynamics.com/api/data/v9.2/"
            f"annotations({ANNOTATION_ID})"
        )
    }

    assert created_entity_id(headers, {}) == ANNOTATION_ID


def test_the_created_id_falls_back_to_the_body_when_one_is_returned():
    assert created_entity_id({}, {"annotationid": ANNOTATION_ID}) == ANNOTATION_ID


def test_no_id_anywhere_is_none_rather_than_a_crash():
    assert created_entity_id({}, {}) is None


def test_the_two_preflights_agree_on_which_environment_is_the_default_one():
    """Both checks act on the Default environment and each carries the
    identifier. If they ever disagree, one of them is enabling search in a
    place the other refuses to grant a role in."""
    from preflight import dataverse_search

    assert dataverse_search.DEFAULT_ENVIRONMENT_ID == DEFAULT_ENVIRONMENT_ID


def test_a_developer_environment_does_not_pass_however_healthy_its_index_is():
    """Default-environment routing can silently land a maker in a personal
    Developer environment. Enabling search there and reporting a pass would
    green-light #17 against an environment the demo never runs in."""
    verdict = evaluate(
        environment(name="Default-99999999-0000-0000-0000-000000000000",
                    sku="Developer"),
        organization(),
        "provisioned",
        probe(),
        CAPACITY,
    )

    assert not verdict.ok
    assert not verdict.check("default-environment-identity").ok
    assert verdict.check("indexed-document-hit").ok


def test_a_probe_that_could_not_delete_its_document_does_not_pass():
    """Leaving a document behind on every run silently fills the tenant-wide
    file pool this same check reports headroom for. A warning on stdout is not
    enough — an unattended loop reads the exit code."""
    left_behind = Probe(
        MARKER,
        document_hit(search_response(), MARKER),
        181,
        cleanup_error="DELETE ... → 403",
    )

    verdict = evaluate(
        environment(), organization(), "provisioned", left_behind, CAPACITY
    )

    assert not verdict.ok
    assert verdict.check("indexed-document-hit").ok
    assert not verdict.check("probe-document-removed").ok


def test_the_wrong_environment_is_a_verdict_not_a_traceback():
    """An operator who passed the identifier their Copilot Studio URL showed
    them needs the report that says it is the wrong environment. A traceback
    loses every other check and reads as a broken tool."""
    report = format_report(
        evaluate(
            environment(name="Default-99999999-0000-0000-0000-000000000000",
                        sku="Developer"),
            {},
            None,
            None,
            CAPACITY,
        )
    )

    assert "FAIL  default-environment-identity" in report
    assert "wrong environment" in report
    assert "--enable" not in report


def test_an_environment_without_dataverse_still_reports_rather_than_raising():
    """A named environment that has no Dataverse instance is a fact to report,
    not an exception: it is exactly the state an operator who mistyped an
    identifier is in."""
    tenant = FakeTenant(env=environment(name="Default-99999999-0000-0000-0000-000000000000",
                                        sku="Developer"))

    assert (
        main(
            ["--enable", "--probe"],
            read=tenant.read,
            enable=tenant.enable,
            run_probe=tenant.run_probe,
        )
        == 1
    )
    assert tenant.enabled_calls == 0
    assert tenant.probe_calls == 0
