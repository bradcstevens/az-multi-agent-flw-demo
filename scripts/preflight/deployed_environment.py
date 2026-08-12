#!/usr/bin/env python3
"""Preflight: does the deployed environment match what the vanilla flavour promises?

The first deploy (#12) settled a handful of facts that every downstream ticket
leans on — the embedding deployment the Identity boundary gate needs is present
and finished, Azure AI Search provisioned in its own region, the application
hosts run exactly one replica, and nothing anywhere fell back to key auth. Those
are point-in-time facts about a subscription, so they are recorded as a preflight
and re-checked rather than re-derived; see docs/preflight/deployed-environment.md.

`evaluate` is pure: it takes the resource group as ARM returns it and returns a
`Verdict`. The live `az` reads are in `main`.
"""

import argparse
import json
import subprocess
import sys

RESOURCE_GROUP = "rg-macae-flw-v1"
OPENAI_API_VERSION = "2024-10-21"

# Container Apps boot on one of the accelerator's placeholder images before any
# application image exists. A container app still serving one is a workload that
# never deployed, which is precisely what an empty registry leaves behind.
PLACEHOLDER_IMAGES = (
    "k8se/quickstart",
    "containerapps-helloworld",
)

# The one tag the templates apply themselves. `SecurityControl=Ignore` is
# appended by the subscription's own policy assignment, so its presence is not
# evidence that the templates asked for the MCAPS exemption (ADR-010).
COMMON_TAG = "azd-env-name"


class Expected:
    """What the vanilla flavour promises for this environment."""

    def __init__(
        self,
        location,
        search_location,
        search_sku,
        models,
        registry,
        resource_group,
        container_apps,
    ):
        self.location = location
        self.search_location = search_location
        self.search_sku = search_sku
        self.models = tuple(models)
        self.registry = registry
        self.resource_group = resource_group
        self.container_apps = tuple(container_apps)


class Check:
    """One named expectation and whether the observed deployment meets it."""

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


def evaluate(observed, expected):
    """Return the `Verdict` for an observed resource group. Pure."""
    container_apps = observed.get("containerApps") or []
    return Verdict(
        [
            _primary_location_check(observed.get("location"), expected),
            _model_roster_check(observed.get("models"), expected),
            _search_check(observed.get("search"), expected),
            _application_hosts_check(container_apps, expected),
            _single_replica_check(container_apps),
            _keyless_check(observed),
            _application_images_check(container_apps, expected),
            _own_foundry_project_check(observed.get("project"), expected),
            _foundry_tags_check(observed.get("foundry")),
        ]
    )


def _primary_location_check(location, expected):
    """ADR-009: the accelerator enforces two region allowlists whose
    intersection is four regions, and `eastus2` is the only one of them
    carrying the whole model roster. A group somewhere else is a different
    environment, not this one."""
    if normalised_location(location) != normalised_location(expected.location):
        return Check(
            "primary-location",
            False,
            f"the resource group is in {location!r}, not {expected.location!r}",
        )
    return Check("primary-location", True, f"the resource group is in {location}")


def _application_hosts_check(container_apps, expected):
    """Every application host exists, provisioned, with ingress. Pure.

    Separate from the image check because they fail differently: an app can
    carry the right image and the right scale and still have no revision, which
    is exactly the state the MCP app sat in for nine days. And an app that was
    never created cannot fail any per-app check at all — it has to be missed by
    name.
    """
    by_name = {app.get("name"): app for app in container_apps}
    problems = [
        f"{name} does not exist"
        for name in expected.container_apps
        if name not in by_name
    ]
    for name in expected.container_apps:
        app = by_name.get(name)
        if app is None:
            continue
        if app.get("provisioningState") != "Succeeded":
            problems.append(f"{name} is {app.get('provisioningState')}")
        elif not app.get("fqdn"):
            problems.append(f"{name} has no ingress FQDN")
    if problems:
        return Check("application-hosts", False, "; ".join(problems))
    return Check(
        "application-hosts",
        True,
        f"all of {', '.join(expected.container_apps)} are Succeeded with ingress",
    )


def image_is_placeholder(image):
    """True when the image is one of the accelerator's bootstrap defaults. Pure."""
    return any(marker in (image or "") for marker in PLACEHOLDER_IMAGES)


def normalised_location(location):
    """Fold an Azure region onto its region name. Pure.

    ARM answers with the display name ("Central US") on some resource providers
    and the region name ("centralus") on others, and the templates only ever
    speak the latter. Comparing them raw would fail a resource that is exactly
    where it belongs.
    """
    return (location or "").replace(" ", "").lower()


def reachability_check(probes):
    """Return the `Check` for a data-plane probe of the model roster. Pure.

    `Succeeded` on a model deployment is a control-plane fact. Whether the
    deployment answers a request is a different one, and it is the one the
    guardrail corpus (#13) and the Identity boundary gate (#14) actually need.
    An unprobed roster is reported as unprobed rather than as a reachable one.
    """
    if not probes:
        return Check(
            "model-reachability",
            False,
            "the model roster was not probed — an unprobed roster is not a "
            "reachable one (drop --no-probe)",
        )
    refused = [
        f"{name} answered {status}"
        for name, status in sorted(probes.items())
        if status != 200
    ]
    if refused:
        return Check("model-reachability", False, "; ".join(refused))
    return Check(
        "model-reachability",
        True,
        f"all of {', '.join(sorted(probes))} answered a live request",
    )


def _model_roster_check(models, expected):
    if models is None:
        return Check(
            "model-roster",
            False,
            "the Foundry account's model deployments were not read — an unread "
            "roster is not an empty one",
        )
    by_name = {model.get("name"): model for model in models}
    missing = [name for name in expected.models if name not in by_name]
    # A deployment row appears well before the model answers a request, so
    # presence alone is not the fact the guardrail corpus (#13) depends on.
    unfinished = [
        f"{name} is {by_name[name].get('provisioningState')}"
        for name in expected.models
        if name in by_name and by_name[name].get("provisioningState") != "Succeeded"
    ]
    problems = [f"{name} is absent" for name in missing] + unfinished
    if problems:
        return Check("model-roster", False, "; ".join(problems))
    return Check(
        "model-roster",
        True,
        f"all of {', '.join(expected.models)} are deployed and Succeeded",
    )


def _search_check(search, expected):
    if not search:
        return Check(
            "search-service",
            False,
            "no Azure AI Search service — the Foundry IQ Knowledge Base path "
            "has nothing to resolve against",
        )
    location = search.get("location")
    state = (search.get("provisioningState") or "").lower()
    if normalised_location(location) != normalised_location(expected.search_location):
        return Check(
            "search-service",
            False,
            f"{search.get('name')} is in {location}, not "
            f"{expected.search_location} — the region decoupling (ADR-008) was lost",
        )
    if state != "succeeded":
        return Check(
            "search-service",
            False,
            f"{search.get('name')} is {search.get('provisioningState')}",
        )
    if (search.get("sku") or "").lower() != expected.search_sku.lower():
        # The free tier carries no semantic reranking and a hard index cap, so
        # the tier is part of the fact rather than decoration on it.
        return Check(
            "search-service",
            False,
            f"{search.get('name')} is on the {search.get('sku')} tier, not "
            f"{expected.search_sku}",
        )
    return Check(
        "search-service",
        True,
        f"{search.get('name')} is {search.get('sku')} in {location}",
    )


def _single_replica_check(container_apps):
    scaled = [
        f"{app.get('name')} scales {app.get('minReplicas')}-{app.get('maxReplicas')}"
        for app in container_apps
        if app.get("minReplicas") != 1 or app.get("maxReplicas") != 1
    ]
    if scaled:
        return Check(
            "single-replica",
            False,
            "; ".join(scaled)
            + " — orchestrations are held in a process-local dictionary, so a "
            "second replica is non-deterministic mid-demo",
        )
    return Check(
        "single-replica",
        True,
        f"all {len(container_apps)} container apps are pinned to one replica",
    )


def _keyless_check(observed):
    """Every place the deployment could have fallen back to key auth. Pure.

    Reported as one check because the claim is a single one — nothing
    authenticates with a key — and a per-resource split would let a partial pass
    read as progress.
    """
    failures = []
    if not ((observed.get("foundry") or {}).get("disableLocalAuth")):
        failures.append("Foundry local auth is enabled")
    if not ((observed.get("cosmos") or {}).get("disableLocalAuth")):
        failures.append("Cosmos local auth is enabled")
    search = observed.get("search")
    if search and not search.get("disableLocalAuth"):
        failures.append("Search local auth is enabled")
    if (observed.get("storage") or {}).get("allowSharedKeyAccess") is not False:
        failures.append("storage shared key access is enabled")
    if (observed.get("registry") or {}).get("adminUserEnabled") is not False:
        failures.append("registry admin user is enabled")
    if failures:
        return Check("keyless", False, "; ".join(failures))
    return Check(
        "keyless",
        True,
        "local auth is disabled on Foundry, Cosmos and Search; storage shared "
        "key and the registry admin user are off",
    )


def _application_images_check(container_apps, expected):
    if not container_apps:
        return Check("application-images", False, "no container apps are deployed")
    problems = []
    for app in container_apps:
        image = app.get("image")
        if image_is_placeholder(image):
            problems.append(f"{app.get('name')} still runs the placeholder {image}")
        elif not (image or "").startswith(expected.registry):
            problems.append(f"{app.get('name')} runs {image}, not an image from "
                            f"{expected.registry}")
    if problems:
        return Check("application-images", False, "; ".join(problems))
    return Check(
        "application-images",
        True,
        f"all {len(container_apps)} container apps run images from {expected.registry}",
    )


def _own_foundry_project_check(project, expected):
    """The reuse path's deployer role grants are commented out upstream, so a
    deployment that took it is silently short of role assignments."""
    resource_group = (project or {}).get("resourceGroup")
    if resource_group != expected.resource_group:
        return Check(
            "own-foundry-project",
            False,
            f"the Foundry project lives in {resource_group!r}, not "
            f"{expected.resource_group!r} — the reuse-an-existing-project path "
            "was taken and its deployer role grants are commented out",
        )
    return Check(
        "own-foundry-project",
        True,
        f"{(project or {}).get('name')} was deployed by this template",
    )


def _foundry_tags_check(foundry):
    tags = (foundry or {}).get("tags") or {}
    if COMMON_TAG not in tags:
        return Check(
            "foundry-tags",
            False,
            f"the Foundry account carries {sorted(tags)} — the common tag set "
            "did not reach the AI Foundry project module",
        )
    return Check(
        "foundry-tags",
        True,
        f"the Foundry account carries the common tag set ({sorted(tags)})",
    )


def format_report(verdict):
    """Return the human-readable report for a `Verdict`. Pure.

    The consequence line is derived, not asserted. "Feature work is unblocked"
    is a claim about the models *answering*, so a control-plane-only run — every
    resource shaped correctly, nothing asked a question — reports that the
    roster is unproven rather than that the environment is ready.
    """
    checks = list(verdict.checks)
    if not any(check.name == "model-reachability" for check in checks):
        checks.append(reachability_check({}))
    lines = [
        f"  {'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}" for c in checks
    ]
    ready = all(check.ok for check in checks)
    lines.append(
        "  ----  feature work (#13, #14, #20): "
        + ("unblocked" if ready else "blocked on the failures above")
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Live reads. Everything above this line is pure.
# ---------------------------------------------------------------------------


def _az(*args):
    """Run an `az` command and return its parsed JSON output."""
    result = subprocess.run(
        ["az", *args, "-o", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"az {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "null")


def read_deployment(resource_group, foundry, registry_name):
    """Read the resource group into the shape `evaluate` expects."""
    project = _az(
        "resource", "list",
        "-g", resource_group,
        "--resource-type", "Microsoft.CognitiveServices/accounts/projects",
        "--query", "[0]",
    )
    searches = _az(
        "resource", "list",
        "-g", resource_group,
        "--resource-type", "Microsoft.Search/searchServices",
    )
    search = None
    if searches:
        search = _az(
            "search", "service", "show",
            "-g", resource_group,
            "-n", searches[0]["name"],
            "--query",
            "{name:name,location:location,sku:sku.name,"
            "disableLocalAuth:disableLocalAuth,provisioningState:provisioningState}",
        )
    return {
        "location": _az("group", "show", "-n", resource_group, "--query", "location"),
        "foundry": _az(
            "cognitiveservices", "account", "show",
            "-g", resource_group, "-n", foundry,
            "--query",
            "{name:name,disableLocalAuth:properties.disableLocalAuth,tags:tags}",
        ),
        "project": {
            "name": (project or {}).get("name", "").split("/")[-1],
            "resourceGroup": (project or {}).get("resourceGroup"),
        },
        "models": _az(
            "cognitiveservices", "account", "deployment", "list",
            "-g", resource_group, "-n", foundry,
            "--query",
            "[].{name:name,provisioningState:properties.provisioningState}",
        ),
        "search": search,
        "storage": _az(
            "storage", "account", "list", "-g", resource_group,
            "--query", "[0].{allowSharedKeyAccess:allowSharedKeyAccess}",
        ),
        "cosmos": _az(
            "cosmosdb", "list", "-g", resource_group,
            "--query", "[0].{disableLocalAuth:disableLocalAuth}",
        ),
        "registry": _az(
            "acr", "show", "-n", registry_name, "-g", resource_group,
            "--query", "{adminUserEnabled:adminUserEnabled}",
        ),
        "containerApps": _az(
            "containerapp", "list", "-g", resource_group,
            "--query",
            "[].{name:name,image:properties.template.containers[0].image,"
            "minReplicas:properties.template.scale.minReplicas,"
            "maxReplicas:properties.template.scale.maxReplicas,"
            "fqdn:properties.configuration.ingress.fqdn,"
            "provisioningState:properties.provisioningState}",
        ),
    }


def probe_models(foundry, models):
    """Send one real request to each model deployment; return {name: status}.

    Chat and embedding deployments take different request shapes, so the probe
    is chosen by deployment name — the roster is small and named by us, and a
    wrong-shaped body would report an unreachable model that is merely being
    asked the wrong question.
    """
    import urllib.error
    import urllib.request

    token = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", "https://cognitiveservices.azure.com",
            "--query", "accessToken", "-o", "tsv",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    statuses = {}
    for name in models:
        embedding = "embedding" in name
        path = "embeddings" if embedding else "chat/completions"
        body = (
            {"input": "preflight"}
            if embedding
            else {
                "messages": [{"role": "user", "content": "reply with: ok"}],
                "max_completion_tokens": 16,
            }
        )
        request = urllib.request.Request(
            f"https://{foundry}.openai.azure.com/openai/deployments/"
            f"{name}/{path}?api-version={OPENAI_API_VERSION}",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                statuses[name] = response.status
        except urllib.error.HTTPError as error:
            statuses[name] = error.code
    return statuses


def main(argv=None, read=None, probe=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-group", default=RESOURCE_GROUP)
    parser.add_argument("--foundry", default="aif-macaeflwv1flrpd")
    parser.add_argument("--registry", default="crmacaeflwv1flrpd")
    parser.add_argument("--location", default="eastus2")
    parser.add_argument("--search-location", default="centralus")
    parser.add_argument("--search-sku", default="basic")
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="skip the live request to each model deployment. The roster is "
             "then reported as unproven, not as reachable — the probe spends a "
             "handful of tokens and proves the fact #13 and #14 depend on.",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help="expected model deployment name; repeatable",
    )
    parser.add_argument(
        "--container-app",
        action="append",
        default=None,
        help="expected container app name; repeatable",
    )
    args = parser.parse_args(argv)

    expected = Expected(
        location=args.location,
        search_location=args.search_location,
        search_sku=args.search_sku,
        models=args.model
        or ("gpt-5.4-mini", "gpt-5.4", "text-embedding-3-small"),
        registry=f"{args.registry}.azurecr.io",
        resource_group=args.resource_group,
        container_apps=args.container_app
        or (
            "ca-macaeflwv1flrpd",
            "ca-mcp-macaeflwv1flrpd",
            "app-macaeflwv1flrpd",
        ),
    )
    reader = read or read_deployment
    observed = reader(args.resource_group, args.foundry, args.registry)
    verdict = evaluate(observed, expected)
    if not args.no_probe:
        prober = probe or probe_models
        verdict.checks.append(
            reachability_check(prober(args.foundry, expected.models))
        )
    else:
        verdict.checks.append(reachability_check({}))

    print(f"Deployed environment: {args.resource_group}")
    print(format_report(verdict))
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
