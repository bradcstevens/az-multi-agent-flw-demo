"""`main` deploys itself, and the three load-bearing details survive editing.

Issue #48's neighbour, [ADR-020](../../../docs/ADR/020-deploy-main-on-every-commit.md).

These are CI-tooling tests, the same shape as `test_e2e_wiring.py` and for the
same reason: the workflow itself cannot run here — it needs a tenant, a
registry and twenty minutes — so the part of it that *can* be asserted without
one is asserted here.

What they defend is narrow, and every item is a failure this repository has
already paid for once:

- **The registry is filled before provisioning.** The accelerator's documented
  order updates Container Apps that provisioning never created. The Placeholder
  image listens on 80 against ingress ports of 8000, 9000 and 3000, never
  produces a ready revision, and stalls the `mcp -> backend -> frontend` chain
  for twenty minutes before ARM gives up with `latestRevisionName: null`.
  Commit `6a7199a5`.
- **The tag is the commit, not `latest`.** `azd provision` only makes a new
  revision where the template changed, so a re-pushed `latest` rolls whichever
  app's template happened to change and leaves the others serving what they
  cached — one app in three deployed, and a green run saying so.
- **`MACAE_USE_CASE=none`.** Unset, `post_deploy.sh` prompts and an unattended
  run hangs. Answered wrongly it restores the six stock content packs that #25
  deliberately suppressed.
- **Every no-default parameter has a value in the repository.** A runner starts
  with an empty azd environment. `AZURE_ENV_BACKEND_IMAGE_NAME` and its two
  siblings default to the Placeholder image, so a parameter added without a
  default and without a value here does not fail loudly — it reinstates the
  placeholder.
- **The token endpoint is a secret, and its absence stops the deploy.** It was
  missing from this deployment for four weeks while thirteen checks stayed
  green, and unset the SOP tool answers with its fixed failure message: the
  centrepiece cross-platform beat cannot work and nothing says so.
"""

from pathlib import Path
import json
import re

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-main.yml"
BASELINE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "azure-dev.yml"
INPUTS = REPO_ROOT / "infra" / "environments" / "macae-flw-v1.env"
PARAMETERS = REPO_ROOT / "infra" / "main.parameters.json"
POST_DEPLOY = REPO_ROOT / "infra" / "scripts" / "post-provision" / "post_deploy.sh"

#: The two the workflow supplies itself rather than reading out of the inputs
#: file: one is the commit being deployed, the other is a capability URL that
#: issues Direct Line tokens for an agent whose authentication mode is None.
SUPPLIED_BY_THE_WORKFLOW = {
    "AZURE_ENV_IMAGE_TAG",
    "COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _uncommented(path: Path) -> str:
    """The file's instructions, with its prose removed.

    The same move `test_e2e_wiring.py` makes on TypeScript comments, for the
    same reason: this workflow's own comments discuss `latest`, the Placeholder
    image and `MACAE_USE_CASE`, so a rule named only in a comment would
    otherwise satisfy a check that nothing executable satisfies.
    """
    return re.sub(r"^\s*#.*$", "", _text(path), flags=re.MULTILINE)


def _step_order(source: str) -> list[str]:
    return re.findall(r"^\s*- name: (.+)$", source, flags=re.MULTILINE)


def _index_of(source: str, needle: str) -> int:
    where = source.find(needle)
    assert where != -1, f"{needle!r} is not in the workflow at all"
    return where


def _substitutions_without_defaults() -> set[str]:
    """Parameters `main.parameters.json` reads from the azd environment.

    `${FOO}` is read with no fallback; `${FOO=bar}` carries its own default and
    survives an empty environment.
    """
    raw = json.dumps(json.loads(_text(PARAMETERS)))
    return {
        name
        for name in re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", raw)
    }


def _inputs_keys() -> set[str]:
    keys = set()
    for line in _text(INPUTS).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0])
    return keys


def test_the_deploy_can_also_be_asked_for_by_hand():
    """The way out of a red build gate that no push can reach (#54).

    The gate the Demo validator opens with compares the **deployed build** to
    `HEAD`, and a commit that touches only the harness, the loops or the docs
    moves `HEAD` without matching a single path above. So the gate goes red,
    correctly, and the only sanctioned answer — *"merge to `main` and let
    `Deploy main` run"* — is one the repository has no way to ask for: there is
    no deployable path left to touch. Measured on 2026-08-14, when the SOP
    rehearsal's own fix was what put the deployment behind.

    `workflow_dispatch` is the same manual trigger `azure-dev.yml` has kept
    since it was inherited. It is a re-stamp, not a new order of operations:
    the job below is unchanged and the concurrency group still queues it behind
    anything in flight.
    """
    source = _uncommented(WORKFLOW)

    assert "workflow_dispatch" in source, (
        "the deploy can only be triggered by a push touching a deployable "
        "path, so a harness-only commit leaves the build gate red with no way "
        "to clear it"
    )


def test_the_workflow_exists_and_fires_on_push_to_main():
    assert WORKFLOW.is_file(), "nothing deploys `main`"
    source = _uncommented(WORKFLOW)

    assert re.search(r"on:\s*\n\s*push:", source), "the deploy is not triggered by a push"
    assert re.search(r"branches:\s*\n\s*- main", source), "the deploy does not watch `main`"


def test_the_registry_is_filled_before_provisioning():
    # Not a stylistic preference. The other order updates Container Apps that
    # provisioning never created.
    source = _uncommented(WORKFLOW)
    steps = _step_order(source)

    build = next((i for i, s in enumerate(steps) if "registry" in s.lower()), None)
    provision = next((i for i, s in enumerate(steps) if s.strip() == "Provision"), None)

    assert build is not None, "no step fills the registry"
    assert provision is not None, "no step provisions"
    assert build < provision, (
        "provisioning runs before the registry is filled: the Placeholder image "
        "stalls the mcp -> backend -> frontend chain (commit 6a7199a5)"
    )
    assert "az acr build" in source, (
        "the images are not built server-side; a local docker build needs "
        "registry credentials the template keeps disabled"
    )


def test_the_image_tag_is_the_commit():
    source = _uncommented(WORKFLOW)

    assert "git rev-parse --short=12 HEAD" in source, (
        "the workflow does not derive a commit-shaped tag"
    )
    assert not re.search(
        r"azd env set AZURE_ENV_IMAGE_TAG\s+(latest|['\"]latest)", source
    ), (
        "the image tag is pinned to `latest`: azd provision would roll only the "
        "apps whose template changed and leave the rest on a cached image"
    )
    assert re.search(r'azd env set AZURE_ENV_IMAGE_TAG "\$IMAGE_TAG"', source), (
        "the commit is computed but never becomes the image tag"
    )


def test_no_stock_content_pack_is_seeded():
    source = _uncommented(WORKFLOW)

    assert "MACAE_USE_CASE none" in source or "MACAE_USE_CASE: none" in source, (
        "the use case is not pinned; post_deploy.sh prompts, and an unattended "
        "run has nobody to answer it"
    )
    assert _index_of(source, "MACAE_USE_CASE") < _index_of(source, "post_deploy.sh"), (
        "the use case is pinned after post_deploy.sh has already run"
    )


def test_a_deploy_in_flight_is_never_cancelled():
    # Cancelling midway through an ARM deployment leaves the environment in a
    # state no commit describes.
    source = _uncommented(WORKFLOW)

    assert "concurrency:" in source, "two pushes can deploy over each other"
    assert re.search(r"cancel-in-progress:\s*false", source), (
        "a queued push cancels a deploy already talking to ARM"
    )


def test_every_parameter_without_a_default_has_a_value_in_the_repository():
    # The Placeholder-image guard. A parameter added without a default and
    # without a value here does not fail loudly; it reinstates the placeholder.
    missing = _substitutions_without_defaults() - _inputs_keys() - SUPPLIED_BY_THE_WORKFLOW

    assert not missing, (
        "main.parameters.json reads these from the azd environment, but nothing "
        f"in the repository supplies them: {sorted(missing)}. A runner starts "
        "with an empty environment, and the three image-name parameters default "
        "to the Placeholder image."
    )


def test_the_three_image_names_are_never_left_to_their_default():
    keys = _inputs_keys()

    for key in (
        "AZURE_ENV_BACKEND_IMAGE_NAME",
        "AZURE_ENV_FRONTEND_IMAGE_NAME",
        "AZURE_ENV_MCP_IMAGE_NAME",
    ):
        assert key in keys, f"{key} is unset; it defaults to the Placeholder image"

    assert "containerapps-helloworld" not in _uncommented(INPUTS), (
        "the Placeholder image is named as a value in the inputs"
    )


def test_the_token_endpoint_is_a_secret_and_its_absence_stops_the_deploy():
    source = _uncommented(WORKFLOW)

    assert "COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT" not in _inputs_keys(), (
        "a URL that issues Direct Line tokens for an anonymous agent is checked "
        "into the repository"
    )
    assert "secrets.COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT" in _text(WORKFLOW), (
        "the token endpoint is not read from repository secrets"
    )
    assert re.search(
        r'if \[ -z "\$DIRECT_LINE_TOKEN_ENDPOINT" \]', source
    ), (
        "an absent token endpoint deploys anyway: the SOP tool would answer "
        "with its fixed failure message and the cross-platform beat could not work"
    )


def test_the_deploy_proves_its_own_result():
    # `azd` exiting zero is not the deployment working. Both checks read the
    # running deployment, and both exist because a green repository sat on top
    # of a deployment that could not have run its own centrepiece beat.
    source = _uncommented(WORKFLOW)
    steps = _step_order(source)

    assert "check-deployed-surface.sh" in source, (
        "nothing observes the surface after deploying it"
    )
    assert "check-deployed-environment.sh" in source, (
        "nothing re-checks the environment after deploying it"
    )
    assert _index_of(source, "azd provision") < _index_of(
        source, "check-deployed-surface.sh"
    ), "the surface is checked before it is deployed"
    assert steps, "the workflow has no named steps to order"


def test_the_job_declares_no_environment():
    # The federated credential's subject is `repo:<owner>/<repo>:ref:refs/heads/main`.
    # A GitHub Environment changes the OIDC subject to `...:environment:<name>`
    # and the token exchange silently stops matching — a failure that only
    # appears on a real push.
    source = _uncommented(WORKFLOW)

    assert not re.search(r"^\s{4}environment:", source, flags=re.MULTILINE), (
        "the job declares a GitHub Environment; the federated credential's "
        "subject no longer matches the token this job would present"
    )


def test_post_deploy_resolves_a_principal_without_a_signed_in_user():
    # `az ad signed-in-user show` is a Graph `/me` call and fails outright under
    # a service principal. Without the fallback the script reaches `fatal`
    # before it seeds anything, so the whole unattended path is dead.
    source = _text(POST_DEPLOY)

    assert "resolve_principal_id()" in source, (
        "post_deploy.sh has no principal-id fallback; under a service principal "
        "it stops at `fatal` before seeding"
    )
    assert "az ad sp show" in source, (
        "the fallback never asks for the service principal's own object id"
    )


def test_the_login_is_refreshed_before_the_data_plane():
    # A GitHub OIDC assertion is short-lived and `azure/login` does not refresh
    # it. The first run of this workflow reached `post_deploy.sh` ten minutes
    # after logging in, could no longer acquire a *new* Microsoft Graph token,
    # and stopped before seeding anything — while its cached ARM token was still
    # perfectly valid, which is why the provision had just succeeded.
    source = _uncommented(WORKFLOW)

    assert source.count("uses: azure/login@v3") >= 2, (
        "the workflow logs in once and then runs for ten minutes; the seeding "
        "step will not be able to acquire tokens for Storage, Search or Foundry"
    )
    assert _index_of(source, "azd provision") < source.rfind("uses: azure/login@v3"), (
        "the login is not refreshed *after* the slow steps, so it refreshes nothing"
    )
    assert source.rfind("uses: azure/login@v3") < _index_of(source, "post_deploy.sh"), (
        "the refreshed login comes after the step that needs it"
    )


def test_the_principal_is_resolved_while_the_assertion_is_fresh():
    # Handed to `post_deploy.sh` rather than looked up by it, so the one Graph
    # call the deploy needs happens at a moment the token is known to work.
    source = _uncommented(WORKFLOW)

    assert "MACAE_PRINCIPAL_ID=" in source, (
        "the deploying principal is never resolved for post_deploy.sh"
    )
    assert "MACAE_PRINCIPAL_ID" in _text(POST_DEPLOY), (
        "post_deploy.sh ignores the principal the workflow resolved for it"
    )
    assert _index_of(source, "MACAE_PRINCIPAL_ID=") < _index_of(source, "post_deploy.sh"), (
        "the principal is resolved after the script that needs it has run"
    )


def test_the_workflow_and_the_inputs_name_the_same_environment():
    # The env name appears twice — as the job's `AZURE_ENV_NAME`, which the
    # workflow needs before it has read anything, and as a value in the inputs.
    # Disagreeing, the workflow would create a second, empty azd environment
    # and provision a whole parallel deployment beside the real one.
    workflow = _uncommented(WORKFLOW)
    declared = re.search(r"AZURE_ENV_NAME:\s*(\S+)", workflow)

    assert declared, "the job does not name the environment it deploys"

    from_inputs = dict(
        line.split("=", 1)
        for line in _uncommented(INPUTS).splitlines()
        if line.strip() and not line.startswith("#") and "=" in line
    )

    assert declared.group(1) == from_inputs.get("AZURE_ENV_NAME"), (
        f"the workflow deploys {declared.group(1)!r} but the inputs describe "
        f"{from_inputs.get('AZURE_ENV_NAME')!r}"
    )


def test_the_inherited_template_validation_workflow_is_left_alone():
    # `azure-dev.yml` provisions a *fresh timestamped* environment to prove the
    # template deploys. It is inherited baseline (ADR-006) and is not the thing
    # that redeploys the demonstration; wiring it to `push` would create a new
    # environment, and a new bill, on every commit.
    source = _uncommented(BASELINE_WORKFLOW)

    assert "workflow_dispatch" in source, "azure-dev.yml lost its manual trigger"
    assert not re.search(r"^on:\s*\n(?:.*\n)*?\s*push:", source, flags=re.MULTILINE), (
        "azure-dev.yml now fires on push: it provisions a brand new timestamped "
        "environment each run"
    )
