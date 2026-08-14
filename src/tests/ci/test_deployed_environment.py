"""Tests for the deployed-environment preflight check (issue #12).

Every downstream ticket assumes the same handful of facts about
`macae-flw-v1`: that the embedding deployment the Identity boundary gate needs
is actually there (#13, #14), that Azure AI Search provisioned in its own
region, that the application hosts run one replica so the process-local Workflow
cache stays deterministic, and that nothing anywhere fell back to key auth. The
first deploy proved them once; this check re-proves them on demand.

The seam under test is the pure evaluation: given the resource group as ARM
returns it, `evaluate` decides whether the deployment matches what the vanilla
flavour promises. The live `az` reads sit outside it.
"""

import pytest

from preflight.deployed_environment import (
    Expected,
    evaluate,
    format_report,
    image_is_placeholder,
    main,
    normalised_location,
    project_endpoint,
    reachability_check,
    retrieval_check,
    retrieval_topics,
    search_endpoint,
    summarise_retrieval,
)

EXPECTED = Expected(
    location="eastus2",
    search_location="centralus",
    search_sku="basic",
    models=("gpt-5.4-mini", "gpt-5.4", "text-embedding-3-small"),
    registry="crmacaeflwv1flrpd.azurecr.io",
    resource_group="rg-macae-flw-v1",
    container_apps=(
        "ca-macaeflwv1flrpd",
        "ca-mcp-macaeflwv1flrpd",
        "app-macaeflwv1flrpd",
    ),
    knowledge_bases=("store-troubleshooting-kb", "store-operations-kb"),
)


_DEFAULT = object()


def knowledge_base(name, source=None, index=_DEFAULT, documents=1, sample=_DEFAULT):
    stem = name[: -len("-kb")] if name.endswith("-kb") else name
    return {
        "name": name,
        "sources": [
            {
                "name": source or f"{stem}-ks",
                "index": f"{stem}-index" if index is _DEFAULT else index,
                "documents": documents,
                "sample": f"{stem} sample document" if sample is _DEFAULT else sample,
            }
        ],
    }


def kb_connection(kb, **overrides):
    connection = {
        "name": f"{kb}-mcp",
        "category": "RemoteTool",
        "authType": "ProjectManagedIdentity",
        "target": (
            "https://srch-macaeflwv1flrpd.search.windows.net/knowledgebases/"
            f"{kb}/mcp?api-version=2025-11-01-preview"
        ),
    }
    connection.update(overrides)
    return connection


def model(name, state="Succeeded"):
    return {"name": name, "provisioningState": state}


def container_app(name, image=None, min_replicas=1, max_replicas=1, fqdn=None):
    return {
        "name": name,
        "image": image or f"{EXPECTED.registry}/{name}:latest",
        "minReplicas": min_replicas,
        "maxReplicas": max_replicas,
        "fqdn": fqdn or f"{name}.eastus2.azurecontainerapps.io",
        "provisioningState": "Succeeded",
    }


def deployment(**overrides):
    """The resource group as the live reads assemble it, all green."""
    observed = {
        "location": "eastus2",
        "foundry": {
            "name": "aif-macaeflwv1flrpd",
            "disableLocalAuth": True,
            "tags": {"azd-env-name": "macae-flw-v1"},
        },
        "project": {"name": "proj-macaeflwv1flrpd", "resourceGroup": "rg-macae-flw-v1"},
        "models": [
            model("gpt-5.4-mini"),
            model("gpt-5.4"),
            model("text-embedding-3-small"),
        ],
        "search": {
            "name": "srch-macaeflwv1flrpd",
            "location": "centralus",
            "sku": "basic",
            "disableLocalAuth": True,
            "provisioningState": "succeeded",
        },
        "storage": {"allowSharedKeyAccess": False},
        "cosmos": {"disableLocalAuth": True},
        "registry": {"adminUserEnabled": False},
        "containerApps": [
            container_app("ca-macaeflwv1flrpd"),
            container_app("ca-mcp-macaeflwv1flrpd"),
            container_app("app-macaeflwv1flrpd"),
        ],
        "knowledgeBases": [
            knowledge_base(name) for name in EXPECTED.knowledge_bases
        ],
        "kbConnections": [
            kb_connection(name) for name in EXPECTED.knowledge_bases
        ],
    }
    observed.update(overrides)
    return observed


def test_given_a_fully_converged_deployment_when_evaluated_then_verdict_passes():
    verdict = evaluate(deployment(), EXPECTED)

    assert verdict.ok, format_report(verdict)


def test_given_a_missing_embedding_deployment_when_evaluated_then_roster_fails():
    without_embedding = deployment(
        models=[model("gpt-5.4-mini"), model("gpt-5.4")],
    )

    verdict = evaluate(without_embedding, EXPECTED)

    assert not verdict.ok
    assert not verdict.check("model-roster").ok
    assert "text-embedding-3-small" in verdict.check("model-roster").detail


def test_given_a_model_that_did_not_finish_provisioning_then_roster_fails():
    """A deployment row exists long before the model answers a request, so
    presence alone is not the fact the guardrail corpus depends on."""
    half_done = deployment(
        models=[
            model("gpt-5.4-mini"),
            model("gpt-5.4"),
            model("text-embedding-3-small", state="Creating"),
        ],
    )

    verdict = evaluate(half_done, EXPECTED)

    assert not verdict.check("model-roster").ok
    assert "Creating" in verdict.check("model-roster").detail


def test_given_no_search_service_when_evaluated_then_search_fails():
    verdict = evaluate(deployment(search=None), EXPECTED)

    assert not verdict.check("search-service").ok


def test_given_search_in_the_primary_region_when_evaluated_then_search_fails():
    """ADR-008: Search has its own region because East US 2 could not allocate
    it. A Search service that came back in eastus2 means the decoupling was
    lost, not that capacity appeared."""
    colocated = deployment(
        search={
            "name": "srch-macaeflwv1flrpd",
            "location": "eastus2",
            "sku": "basic",
            "disableLocalAuth": True,
            "provisioningState": "succeeded",
        },
    )

    verdict = evaluate(colocated, EXPECTED)

    assert not verdict.check("search-service").ok
    assert "eastus2" in verdict.check("search-service").detail


def test_given_search_reported_by_display_name_when_evaluated_then_search_passes():
    """`az search service show` answers with the region's display name ("Central
    US") while the template names it `centralus`. Comparing them raw would fail
    a Search service that is exactly where ADR-008 puts it."""
    display_name = deployment(
        search={
            "name": "srch-macaeflwv1flrpd",
            "location": "Central US",
            "sku": "basic",
            "disableLocalAuth": True,
            "provisioningState": "succeeded",
        },
    )

    verdict = evaluate(display_name, EXPECTED)

    assert verdict.check("search-service").ok


@pytest.mark.parametrize(
    "location,normalised",
    [
        ("Central US", "centralus"),
        ("centralus", "centralus"),
        ("East US 2", "eastus2"),
        (None, ""),
    ],
)
def test_normalised_location_folds_display_names_onto_region_names(
    location, normalised
):
    assert normalised_location(location) == normalised


def test_given_a_container_app_that_can_scale_out_then_single_replica_fails():
    """Orchestrations live in a process-local dictionary and checkpoint state is
    in-memory, so a second replica is non-deterministic behaviour mid-demo."""
    scaled = deployment(
        containerApps=[
            container_app("ca-macaeflwv1flrpd", max_replicas=10),
            container_app("ca-mcp-macaeflwv1flrpd"),
            container_app("app-macaeflwv1flrpd"),
        ],
    )

    verdict = evaluate(scaled, EXPECTED)

    assert not verdict.check("single-replica").ok
    assert "ca-macaeflwv1flrpd" in verdict.check("single-replica").detail


@pytest.mark.parametrize(
    "observed,failing",
    [
        ({"storage": {"allowSharedKeyAccess": True}}, "storage shared key"),
        ({"cosmos": {"disableLocalAuth": False}}, "Cosmos"),
        ({"registry": {"adminUserEnabled": True}}, "registry admin user"),
        (
            {
                "foundry": {
                    "name": "aif-macaeflwv1flrpd",
                    "disableLocalAuth": False,
                    "tags": {},
                }
            },
            "Foundry",
        ),
    ],
)
def test_given_key_auth_anywhere_when_evaluated_then_keyless_fails(observed, failing):
    verdict = evaluate(deployment(**observed), EXPECTED)

    assert not verdict.check("keyless").ok
    assert failing in verdict.check("keyless").detail


def test_given_the_bootstrap_placeholder_image_then_application_images_fails():
    """The accelerator boots every container app on the hello-world image. A
    container app still running it is a workload that never deployed, which the
    empty registry after the first pass is exactly what produced."""
    placeholder = deployment(
        containerApps=[
            container_app("ca-macaeflwv1flrpd"),
            container_app(
                "ca-mcp-macaeflwv1flrpd",
                image="mcr.microsoft.com/k8se/quickstart:latest",
            ),
            container_app("app-macaeflwv1flrpd"),
        ],
    )

    verdict = evaluate(placeholder, EXPECTED)

    assert not verdict.check("application-images").ok
    assert "ca-mcp-macaeflwv1flrpd" in verdict.check("application-images").detail


@pytest.mark.parametrize(
    "image,placeholder",
    [
        ("mcr.microsoft.com/k8se/quickstart:latest", True),
        ("mcr.microsoft.com/azuredocs/containerapps-helloworld:latest", True),
        ("crmacaeflwv1flrpd.azurecr.io/macaebackend:latest", False),
    ],
)
def test_image_is_placeholder_classifies_the_bootstrap_defaults(image, placeholder):
    assert image_is_placeholder(image) is placeholder


def test_given_a_reused_foundry_project_when_evaluated_then_foundry_path_fails():
    """The reuse path's deployer role grants are commented out upstream, so a
    deployment that took it is silently short of permissions."""
    reused = deployment(
        project={"name": "proj-elsewhere", "resourceGroup": "rg-someone-else"},
    )

    verdict = evaluate(reused, EXPECTED)

    assert not verdict.check("own-foundry-project").ok


def test_given_the_policys_security_control_tag_when_evaluated_then_tags_pass():
    """`SecurityControl=Ignore` arrives from the subscription policy assignment,
    not from the templates. The check is that we did not ask for it, so its
    presence alongside the common tag set is not a failure."""
    tagged = deployment(
        foundry={
            "name": "aif-macaeflwv1flrpd",
            "disableLocalAuth": True,
            "tags": {"azd-env-name": "macae-flw-v1", "SecurityControl": "Ignore"},
        },
    )

    verdict = evaluate(tagged, EXPECTED)

    assert verdict.check("foundry-tags").ok


def test_given_an_untagged_foundry_account_when_evaluated_then_tags_fail():
    """The Foundry project module deployed completely untagged upstream."""
    untagged = deployment(
        foundry={"name": "aif-macaeflwv1flrpd", "disableLocalAuth": True, "tags": {}},
    )

    verdict = evaluate(untagged, EXPECTED)

    assert not verdict.check("foundry-tags").ok


def test_format_report_names_every_check_and_its_verdict():
    report = format_report(evaluate(deployment(search=None), EXPECTED))

    assert "FAIL  search-service" in report
    assert "PASS  model-roster" in report


def test_given_every_model_answering_when_probed_then_reachability_passes():
    """`Succeeded` is a control-plane fact. Whether the deployment answers a
    request is a data-plane one, and the guardrail corpus (#13) needs the
    second."""
    check = reachability_check(
        {"gpt-5.4-mini": 200, "gpt-5.4": 200, "text-embedding-3-small": 200}
    )

    assert check.ok
    assert check.name == "model-reachability"


def test_given_a_model_refusing_the_request_when_probed_then_reachability_fails():
    check = reachability_check(
        {"gpt-5.4-mini": 200, "gpt-5.4": 200, "text-embedding-3-small": 404}
    )

    assert not check.ok
    assert "text-embedding-3-small" in check.detail
    assert "404" in check.detail


def test_given_no_probes_when_asked_then_reachability_is_reported_unprobed():
    """An unprobed roster is not a reachable one — the check must not pass by
    saying nothing."""
    check = reachability_check({})

    assert not check.ok
    assert "not probed" in check.detail


def test_given_a_converged_deployment_when_main_runs_without_probing_then_it_says_so(
    capsys,
):
    """`--no-probe` is a control-plane-only run: it must still report the
    unproven reachability rather than quietly omitting it."""
    exit_code = main(argv=["--no-probe"], read=lambda *_: deployment())

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL  model-reachability" in out
    assert "not probed" in out


def test_given_probe_is_the_default_when_main_runs_then_the_roster_is_probed(capsys):
    """The roster is probed unless the operator opts out, because #12's fact is
    that the models are *reachable*, not merely deployed."""
    probed = {}

    def probe(foundry, models):
        probed["models"] = models
        return {name: 200 for name in models}

    # `retrieve` is stubbed even though this test is about the roster: left to
    # its default, `main` runs a real agent against the live project, so the
    # CI-tooling loop would dial a tenant and go red on a transient empty
    # retrieval. A unit test that needs a subscription is not a unit test.
    exit_code = main(
        argv=[],
        read=lambda *_: deployment(),
        probe=probe,
        retrieve=lambda project, endpoint, topics: {
            name: grounded() for name in topics
        },
    )

    assert exit_code == 0
    assert "text-embedding-3-small" in probed["models"]
    assert "PASS  model-reachability" in capsys.readouterr().out


def test_given_a_model_that_will_not_answer_when_main_probes_then_it_exits_nonzero(
    capsys,
):
    exit_code = main(
        argv=[],
        read=lambda *_: deployment(),
        probe=lambda foundry, models: {name: 404 for name in models},
        retrieve=lambda project, endpoint, topics: {
            name: grounded() for name in topics
        },
    )

    assert exit_code == 1
    assert "FAIL  model-reachability" in capsys.readouterr().out


# --- the review's four findings ------------------------------------------------


def test_given_a_failed_container_app_when_evaluated_then_hosts_fails():
    """`Failed` is exactly the state the MCP app sat in for nine days. An app
    can carry the right image and the right scale and still have no revision."""
    failed = deployment(
        containerApps=[
            container_app("ca-macaeflwv1flrpd"),
            dict(container_app("ca-mcp-macaeflwv1flrpd"),
                 provisioningState="Failed", fqdn=None),
            container_app("app-macaeflwv1flrpd"),
        ],
    )

    verdict = evaluate(failed, EXPECTED)

    assert not verdict.ok
    assert not verdict.check("application-hosts").ok
    assert "ca-mcp-macaeflwv1flrpd" in verdict.check("application-hosts").detail


def test_given_a_container_app_that_was_never_created_then_hosts_fails():
    """The backend and frontend did not fail on 2026-08-03 — they did not
    exist, because the app at the head of the chain failed first."""
    missing = deployment(
        containerApps=[container_app("ca-mcp-macaeflwv1flrpd")],
    )

    verdict = evaluate(missing, EXPECTED)

    assert not verdict.check("application-hosts").ok
    assert "ca-macaeflwv1flrpd" in verdict.check("application-hosts").detail


def test_given_a_container_app_with_no_ingress_then_hosts_fails():
    no_ingress = deployment(
        containerApps=[
            container_app("ca-macaeflwv1flrpd"),
            container_app("ca-mcp-macaeflwv1flrpd"),
            dict(container_app("app-macaeflwv1flrpd"), fqdn=None),
        ],
    )

    verdict = evaluate(no_ingress, EXPECTED)

    assert not verdict.check("application-hosts").ok
    assert "app-macaeflwv1flrpd" in verdict.check("application-hosts").detail


def test_given_the_wrong_primary_region_when_evaluated_then_location_fails():
    """ADR-009: the two region allowlists the accelerator enforces intersect on
    four regions, and eastus2 is the only one carrying the whole model roster."""
    verdict = evaluate(deployment(location="westus"), EXPECTED)

    assert not verdict.check("primary-location").ok
    assert "westus" in verdict.check("primary-location").detail


def test_given_a_free_tier_search_service_when_evaluated_then_search_fails():
    """The free tier carries no semantic reranking and a hard index cap, so the
    tier is part of the fact, not decoration on it."""
    free = deployment(
        search={
            "name": "srch-macaeflwv1flrpd",
            "location": "centralus",
            "sku": "free",
            "disableLocalAuth": True,
            "provisioningState": "succeeded",
        },
    )

    verdict = evaluate(free, EXPECTED)

    assert not verdict.check("search-service").ok
    assert "free" in verdict.check("search-service").detail


def test_given_another_resource_group_when_asked_for_then_foundry_path_passes():
    """The expected resource group is the one the operator asked for. Pinning it
    to a constant would fail every environment but the one it names."""
    elsewhere = Expected(
        location="eastus2",
        search_location="centralus",
        search_sku="basic",
        models=EXPECTED.models,
        registry=EXPECTED.registry,
        resource_group="rg-other",
        container_apps=EXPECTED.container_apps,
        knowledge_bases=EXPECTED.knowledge_bases,
    )

    verdict = evaluate(
        deployment(project={"name": "proj-other", "resourceGroup": "rg-other"}),
        elsewhere,
    )

    assert verdict.check("own-foundry-project").ok


def test_given_a_passing_verdict_without_a_probe_then_the_report_does_not_claim_unblocked():
    """`Succeeded` on a model deployment is not the same fact as the deployment
    answering, so a control-plane-only run must not say feature work is ready."""
    report = format_report(evaluate(deployment(), EXPECTED))

    assert "unblocked" not in report
    assert "not probed" in report


def test_given_a_passing_verdict_with_a_passing_probe_then_the_report_claims_unblocked():
    verdict = evaluate(deployment(), EXPECTED)
    verdict.checks.append(
        reachability_check({name: 200 for name in EXPECTED.models})
    )
    verdict.checks.append(
        retrieval_check({name: grounded() for name in EXPECTED.knowledge_bases})
    )

    assert "unblocked" in format_report(verdict)


# --- the knowledge-base path (#30) --------------------------------------------
#
# A Search service can be in the right region, on the right tier and keyless
# while holding nothing at all — which is exactly what it held when the other
# ten checks first went green. So `search-service` is not evidence that anything
# resolves against it, and the facts below each had to be proven separately.


def grounded(retrieved=1, **overrides):
    """One knowledge-base probe that called the tool and got documents back."""
    probe = {"status": "completed", "called": True, "error": None,
             "retrieved": retrieved}
    probe.update(overrides)
    return probe


def test_given_a_search_service_with_no_knowledge_bases_then_the_kb_check_fails():
    """The state the environment sat in while all ten earlier checks passed:
    Search provisioned, Basic, in Central US, and empty."""
    verdict = evaluate(deployment(knowledgeBases=[]), EXPECTED)

    assert not verdict.ok
    assert not verdict.check("knowledge-bases").ok
    assert "store-troubleshooting-kb" in verdict.check("knowledge-bases").detail


def test_given_an_unread_knowledge_base_list_then_the_kb_check_fails():
    """An unread list is not an empty one, and neither is a reason to pass."""
    verdict = evaluate(deployment(knowledgeBases=None), EXPECTED)

    assert not verdict.check("knowledge-bases").ok
    assert "not read" in verdict.check("knowledge-bases").detail


def test_given_a_knowledge_base_with_no_sources_then_the_kb_check_fails():
    """`PUT /knowledgebases/{kb}` succeeds with an empty `knowledgeSources`, so
    the KB can exist and resolve to nothing."""
    sourceless = deployment(
        knowledgeBases=[
            dict(knowledge_base("store-troubleshooting-kb"), sources=[]),
            knowledge_base("store-operations-kb"),
        ],
    )

    verdict = evaluate(sourceless, EXPECTED)

    assert not verdict.check("knowledge-bases").ok
    assert "no knowledge source" in verdict.check("knowledge-bases").detail


def test_given_a_knowledge_source_whose_index_is_missing_then_the_kb_check_fails():
    """The knowledge source names its index by string. `index_datasets.py` not
    having run leaves the source pointing at nothing, and the KB still exists."""
    dangling = deployment(
        knowledgeBases=[
            knowledge_base("store-troubleshooting-kb", index=None),
            knowledge_base("store-operations-kb"),
        ],
    )

    verdict = evaluate(dangling, EXPECTED)

    assert not verdict.check("knowledge-bases").ok
    assert "store-troubleshooting-ks" in verdict.check("knowledge-bases").detail


def test_given_an_index_with_no_documents_then_the_kb_check_fails():
    """An empty index retrieves nothing, and an agent that retrieves nothing
    answers from the model without saying so. That is the failure this whole
    demonstration cannot afford, so an empty index is a failed check."""
    empty = deployment(
        knowledgeBases=[
            knowledge_base("store-troubleshooting-kb", documents=0),
            knowledge_base("store-operations-kb"),
        ],
    )

    verdict = evaluate(empty, EXPECTED)

    assert not verdict.check("knowledge-bases").ok
    assert "store-troubleshooting-index" in verdict.check("knowledge-bases").detail


def test_given_every_knowledge_base_seeded_then_the_kb_check_passes():
    verdict = evaluate(deployment(), EXPECTED)

    assert verdict.check("knowledge-bases").ok


def test_given_a_missing_kb_connection_then_the_connection_check_fails():
    """Without the per-KB `RemoteTool` connection the KB is perfect and still
    unreachable: the agent has no identity to present at the MCP endpoint."""
    verdict = evaluate(
        deployment(kbConnections=[kb_connection("store-operations-kb")]),
        EXPECTED,
    )

    assert not verdict.check("knowledge-base-connections").ok
    assert (
        "store-troubleshooting-kb-mcp"
        in verdict.check("knowledge-base-connections").detail
    )


def test_given_a_kb_connection_authenticating_with_a_key_then_it_fails():
    """`ProjectManagedIdentity` is the only auth mode this deployment has —
    Search local auth is disabled, so an `ApiKey` connection cannot work and is
    a keyless regression besides."""
    keyed = deployment(
        kbConnections=[
            kb_connection("store-troubleshooting-kb", authType="ApiKey"),
            kb_connection("store-operations-kb"),
        ],
    )

    verdict = evaluate(keyed, EXPECTED)

    assert not verdict.check("knowledge-base-connections").ok
    assert "ApiKey" in verdict.check("knowledge-base-connections").detail


def test_given_a_kb_connection_pointing_at_another_kb_then_it_fails():
    """The connections are seeded in a loop over KB names and differ only in
    that name, so a connection aimed at the wrong knowledge base is the most
    likely way to get a confidently wrong answer rather than an error."""
    crossed = deployment(
        kbConnections=[
            kb_connection(
                "store-troubleshooting-kb",
                target=(
                    "https://srch-macaeflwv1flrpd.search.windows.net/"
                    "knowledgebases/store-operations-kb/mcp"
                ),
            ),
            kb_connection("store-operations-kb"),
        ],
    )

    verdict = evaluate(crossed, EXPECTED)

    assert not verdict.check("knowledge-base-connections").ok
    assert "store-troubleshooting-kb" in verdict.check(
        "knowledge-base-connections"
    ).detail


def test_given_a_non_remote_tool_connection_then_it_fails():
    """The project already carries a `CognitiveSearch` connection to the same
    service. It is not an MCP tool and matching on name alone would accept it."""
    wrong_category = deployment(
        kbConnections=[
            kb_connection("store-troubleshooting-kb", category="CognitiveSearch"),
            kb_connection("store-operations-kb"),
        ],
    )

    verdict = evaluate(wrong_category, EXPECTED)

    assert not verdict.check("knowledge-base-connections").ok
    assert "CognitiveSearch" in verdict.check("knowledge-base-connections").detail


def test_given_every_knowledge_base_retrieving_when_probed_then_retrieval_passes():
    check = retrieval_check({name: grounded() for name in EXPECTED.knowledge_bases})

    assert check.ok
    assert check.name == "knowledge-base-retrieval"


def test_given_no_retrieval_probes_when_asked_then_it_is_reported_unprobed():
    """The cross-region hop is the whole claim of ADR-008's topology. An
    unprobed hop is not a working one."""
    check = retrieval_check({})

    assert not check.ok
    assert "not probed" in check.detail


def test_given_an_agent_that_never_called_the_tool_then_retrieval_fails():
    """This is the failure the check exists for. The run completes, the agent
    answers fluently, and nothing was retrieved — the model answered from its
    own weights and the Search service was never consulted at all."""
    check = retrieval_check(
        {"store-troubleshooting-kb": grounded(called=False, retrieved=0)}
    )

    assert not check.ok
    assert "did not call" in check.detail
    assert "store-troubleshooting-kb" in check.detail


def test_given_a_tool_call_that_errored_then_retrieval_fails():
    check = retrieval_check(
        {"store-troubleshooting-kb": grounded(error="connection not found")}
    )

    assert not check.ok
    assert "connection not found" in check.detail


def test_given_a_tool_call_that_retrieved_nothing_then_retrieval_fails():
    """A tool call that returns zero documents grounds nothing, so the answer
    that follows it is the model's, not the store's."""
    check = retrieval_check({"store-troubleshooting-kb": grounded(retrieved=0)})

    assert not check.ok
    assert "no documents" in check.detail


def test_given_a_run_that_did_not_complete_then_retrieval_fails():
    check = retrieval_check(
        {"store-troubleshooting-kb": grounded(status="incomplete")}
    )

    assert not check.ok
    assert "incomplete" in check.detail


def test_summarise_retrieval_reads_a_grounded_agent_run():
    """The shape the Foundry Responses API actually returns for the run
    recorded in the preflight: a tool listing, the retrieval, then the answer."""
    probe = summarise_retrieval(
        {
            "status": "completed",
            "output": [
                {"type": "mcp_list_tools", "tools": [{"name": "knowledge_base_retrieve"}]},
                {
                    "type": "mcp_call",
                    "name": "knowledge_base_retrieve",
                    "error": None,
                    "output": "Retrieved 1 documents.\n\n【4:0†source】",
                },
                {
                    "type": "message",
                    "content": [{"text": "Check that the brew basket is seated."}],
                },
            ],
        }
    )

    assert probe == {
        "status": "completed",
        "called": True,
        "error": None,
        "retrieved": 1,
    }


def test_summarise_retrieval_reports_an_ungrounded_run_as_uncalled():
    """No `mcp_call` in the output means the model answered by itself. The
    payload looks entirely healthy, which is precisely the danger."""
    probe = summarise_retrieval(
        {
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"text": "Try turning it off."}]},
            ],
        }
    )

    assert probe["called"] is False
    assert probe["retrieved"] == 0


def test_summarise_retrieval_carries_the_tool_error_through():
    probe = summarise_retrieval(
        {
            "status": "completed",
            "output": [
                {
                    "type": "mcp_call",
                    "name": "knowledge_base_retrieve",
                    "error": "Forbidden",
                    "output": None,
                },
            ],
        }
    )

    assert probe["called"] is True
    assert probe["error"] == "Forbidden"


def test_summarise_retrieval_reports_a_transport_failure_as_the_status():
    """An HTTP failure has no `output` at all, and must not read as a run that
    completed without retrieving."""
    probe = summarise_retrieval({"status": "403", "output": []})

    assert probe["status"] == "403"
    assert probe["called"] is False


def test_summarise_retrieval_counts_documents_across_several_calls():
    """The agent batches queries and may call the tool more than once; the
    grounded fact is that documents came back overall."""
    probe = summarise_retrieval(
        {
            "status": "completed",
            "output": [
                {"type": "mcp_call", "error": None, "output": "Retrieved 0 documents."},
                {"type": "mcp_call", "error": None, "output": "Retrieved 3 documents."},
            ],
        }
    )

    assert probe["retrieved"] == 3


def test_given_a_converged_deployment_without_probing_then_retrieval_is_unproven(
    capsys,
):
    exit_code = main(argv=["--no-probe"], read=lambda *_: deployment())

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL  knowledge-base-retrieval" in out
    assert "not probed" in out


def test_given_probe_is_the_default_when_main_runs_then_the_knowledge_bases_probe(
    capsys,
):
    asked = {}

    def retrieve(project, search_endpoint, topics):
        asked["topics"] = topics
        return {name: grounded() for name in topics}

    exit_code = main(
        argv=[],
        read=lambda *_: deployment(),
        probe=lambda foundry, models: {name: 200 for name in models},
        retrieve=retrieve,
    )

    assert exit_code == 0
    assert "store-troubleshooting-kb" in asked["topics"]
    assert "PASS  knowledge-base-retrieval" in capsys.readouterr().out


def test_retrieval_topics_asks_about_a_document_the_corpus_actually_holds():
    """An open question leaves the model to invent search terms, and an
    invented term matches nothing often enough to fail a healthy deployment.
    The question is derived from a title the read already found instead."""
    topics = retrieval_topics(deployment()["knowledgeBases"], EXPECTED)

    assert topics["store-troubleshooting-kb"] == "store-troubleshooting sample document"
    assert topics["store-operations-kb"] == "store-operations sample document"


def test_retrieval_topics_still_names_a_knowledge_base_it_found_nothing_for():
    """A knowledge base with no title to offer has already failed
    `knowledge-bases`. The probe must still run against it rather than skip it,
    because a skipped probe would leave the retrieval check passing."""
    topics = retrieval_topics(
        [knowledge_base("store-troubleshooting-kb", sample=None)], EXPECTED
    )

    assert topics == {
        "store-troubleshooting-kb": None,
        "store-operations-kb": None,
    }


def test_given_an_agent_that_answers_ungrounded_when_main_runs_then_it_exits_nonzero(
    capsys,
):
    exit_code = main(
        argv=[],
        read=lambda *_: deployment(),
        probe=lambda foundry, models: {name: 200 for name in models},
        retrieve=lambda project, endpoint, topics: {
            name: grounded(called=False, retrieved=0) for name in topics
        },
    )

    assert exit_code == 1
    assert "FAIL  knowledge-base-retrieval" in capsys.readouterr().out


def test_given_no_search_service_when_main_probes_then_retrieval_is_not_attempted(
    capsys,
):
    """With no Search service there is no endpoint to probe. Inventing one
    would report a transport error where the real finding — no Search service
    at all — is already stated by `search-service`."""
    attempted = []

    exit_code = main(
        argv=[],
        read=lambda *_: deployment(search=None),
        probe=lambda foundry, models: {name: 200 for name in models},
        retrieve=lambda *args: attempted.append(args) or {},
    )

    out = capsys.readouterr().out
    assert exit_code == 1
    assert attempted == []
    assert "FAIL  search-service" in out
    assert "not probed" in out


def test_project_endpoint_and_search_endpoint_are_derived_from_the_read():
    observed = deployment()

    assert project_endpoint("aif-x", observed) == (
        "https://aif-x.services.ai.azure.com/api/projects/proj-macaeflwv1flrpd"
    )
    assert search_endpoint(observed) == (
        "https://srch-macaeflwv1flrpd.search.windows.net"
    )
    assert search_endpoint(deployment(search=None)) is None
    assert project_endpoint("aif-x", deployment(project={})) is None
