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
    reachability_check,
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
)


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

    exit_code = main(argv=[], read=lambda *_: deployment(), probe=probe)

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

    assert "unblocked" in format_report(verdict)
