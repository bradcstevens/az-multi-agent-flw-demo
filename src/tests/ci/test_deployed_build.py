"""Tests for the deployed-build check (issue #48, ADR-018).

**Deployment drift** is the distance between the images the Container Apps are
running and the commit they were built from, and until this check existed
nothing measured it. `check-deployed-environment.sh` grades an image's
*provenance* — not the **Placeholder image**, from our own registry — and both
were true of an image forty-two commits out of date.
`check-deployed-surface.sh` catches drift that has already changed something
visible, which is a symptom rather than a measurement: it cannot tell a
deployment one commit behind from a current one.

The seam under test is the pure evaluation. Given the image references
`az containerapp list` returned and what `git` knows about the commits in them,
`evaluate` decides whether the deployed build is this commit. The live reads sit
outside it, so the whole verdict is testable with no tenant and no clone.

The distinction the tests defend hardest is **unknown is not a pass**. ADR-018:
"treating that as a pass would rebuild the exact hole this closes."
"""

import os
from pathlib import Path

from preflight.deployed_build import (
    FAIL,
    PASS,
    UNKNOWN,
    commit_from_image,
    evaluate,
    format_report,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "scripts" / "preflight" / "deployed_build.py"
SCRIPT = REPO_ROOT / "scripts" / "preflight" / "check-deployed-build.sh"
AGENTS = REPO_ROOT / "AGENTS.md"

HEAD = "231eeeecfce69725a6e830aa293ccf84a599ea66"
REGISTRY = "crmacaeflwv1flrpd.azurecr.io"

#: The three application hosts, as `az containerapp list` names them.
HOSTS = ("ca-macaeflwv1flrpd", "app-macaeflwv1flrpd", "mcp-macaeflwv1flrpd")


def observed(commit=HEAD[:12], **overrides):
    """What a current deployment answers, as the live reads return it."""
    base = {
        "head": HEAD,
        "branch": "main",
        "dirty": False,
        "containerApps": [
            {"name": name, "image": f"{REGISTRY}/macaebackend:{commit}"}
            for name in HOSTS
        ],
        "commits": {commit: {"known": True, "behind": 0, "undeployed": []}},
    }
    base.update(overrides)
    return base


def drifted(commit="a96b44815f80", behind=9, undeployed=()):
    """The state found on 2026-08-14: nine commits of frontend work undeployed."""
    return observed(
        commit=commit,
        commits={
            commit: {
                "known": True,
                "behind": behind,
                "undeployed": list(undeployed),
            }
        },
    )


class TestTheCommitInTheImage:
    """A commit-shaped tag is the stamp; anything else is not a claim at all."""

    def test_a_commit_shaped_tag_is_the_commit(self):
        assert (
            commit_from_image(f"{REGISTRY}/macaefrontend:a96b44815f80")
            == "a96b44815f80"
        )

    def test_latest_names_no_commit(self):
        # `deploy-main.yml` pushes `:latest` beside the commit tag, and ADR-020
        # records why a deployment *on* `latest` is the failure it is: azd rolls
        # only the app whose template changed. A deployment there cannot say
        # what it is running, which is unknown rather than drifted.
        assert commit_from_image(f"{REGISTRY}/macaefrontend:latest") is None

    def test_an_untagged_image_names_no_commit(self):
        assert commit_from_image(f"{REGISTRY}/macaefrontend") is None

    def test_a_digest_is_not_a_commit(self):
        # `name@sha256:...` is 64 hex characters and would otherwise read as a
        # very long commit — one git has never heard of, so the check would
        # report *unknown* for the right reason by accident. Named here so the
        # detail says "pinned by digest" rather than "git does not know it".
        assert (
            commit_from_image(f"{REGISTRY}/macaefrontend@sha256:{'a' * 64}")
            is None
        )

    def test_a_registry_port_is_not_a_tag(self):
        # The last colon is not the tag separator when the host carries a port.
        assert commit_from_image("localhost:5000/macaefrontend") is None

    def test_the_placeholder_image_names_no_commit(self):
        assert commit_from_image(
            "mcr.microsoft.com/k8se/quickstart:latest") is None

    def test_nothing_names_no_commit(self):
        assert commit_from_image(None) is None


class TestTheComparisonBase:
    """Which commit this run compared against, so a stale checkout is visible."""

    def test_the_head_commit_and_branch_are_named(self):
        check = evaluate(observed()).check("comparison-base")

        assert check.status == PASS
        assert HEAD[:12] in check.detail
        assert "main" in check.detail

    def test_a_detached_checkout_says_so(self):
        # ADR-018's second negative consequence: the check is meaningless run
        # from a detached or stale checkout, so it reports which commit it
        # compared against rather than leaving the reader to assume `main`.
        check = evaluate(observed(branch=None)).check("comparison-base")

        assert "detached" in check.detail

    def test_uncommitted_work_says_so(self):
        check = evaluate(observed(dirty=True)).check("comparison-base")

        assert "uncommitted" in check.detail

    def test_no_git_at_all_is_unknown_rather_than_a_pass(self):
        verdict = evaluate(observed(head=None))

        assert verdict.check("comparison-base").status == UNKNOWN
        assert not verdict.ok


class TestTheBuildStamp:
    """Every host's image names a commit, or the answer is unknown."""

    def test_commit_tagged_images_pass(self):
        assert evaluate(observed()).check("build-stamp").status == PASS

    def test_an_image_on_latest_is_unknown_not_a_pass(self):
        # The whole of ADR-018's "report unknown rather than pass". An image
        # that cannot say what it was built from has not been proved current,
        # and a check that shrugs and passes is the hole this closes.
        verdict = evaluate(
            observed(
                containerApps=[
                    {"name": HOSTS[0], "image": f"{REGISTRY}/macaebackend:latest"},
                ],
                commits={},
            )
        )
        check = verdict.check("build-stamp")

        assert check.status == UNKNOWN
        assert check.status != PASS
        assert not verdict.ok
        assert HOSTS[0] in check.detail

    def test_no_container_apps_at_all_is_unknown(self):
        verdict = evaluate(observed(containerApps=[], commits={}))

        assert verdict.check("build-stamp").status == UNKNOWN


class TestTheBuildCurrency:
    """The stamped commit is HEAD, or the report names the distance."""

    def test_a_deployment_of_head_passes(self):
        verdict = evaluate(observed())

        assert verdict.check("build-currency").status == PASS
        assert verdict.ok

    def test_a_deployment_behind_head_fails_and_reports_the_distance(self):
        # The measured case: `macaefrontend:a96b44815f80`, nine commits behind,
        # while the Demo validator's troubleshooting beat went red for the
        # image and the red was indistinguishable from a regression.
        check = evaluate(drifted(behind=9)).check("build-currency")

        assert check.status == FAIL
        assert "9 commit" in check.detail

    def test_the_failure_names_what_is_not_deployed(self):
        check = evaluate(
            drifted(undeployed=["Give the surface an outline",
                                "Make the rail fit its own box"])
        ).check("build-currency")

        assert "Give the surface an outline" in check.detail

    def test_a_commit_this_checkout_does_not_know_is_unknown(self):
        # A detached or shallow clone, or an image built from a branch that
        # never landed. Distance is not computable, so nothing about currency
        # has been proved — and *unproved* is not *current*.
        verdict = evaluate(
            observed(
                commit="deadbeefcafe",
                commits={"deadbeefcafe": {"known": False}},
            )
        )
        check = verdict.check("build-currency")

        assert check.status == UNKNOWN
        assert not verdict.ok

    def test_an_image_ahead_of_head_fails_rather_than_passing_quietly(self):
        # A stale checkout, which is the reader's mistake rather than the
        # deployment's — and reads as "everything is fine" unless it is said.
        check = evaluate(
            observed(
                commit="0f0f0f0f0f0f",
                commits={
                    "0f0f0f0f0f0f": {"known": True, "behind": 0, "ahead": 4,
                                     "undeployed": []},
                },
            )
        ).check("build-currency")

        assert check.status == FAIL
        assert "ahead" in check.detail


class TestTheHostsAgree:
    """All three application hosts run the same build."""

    def test_one_commit_across_every_host_passes(self):
        assert evaluate(observed()).check("build-agreement").status == PASS

    def test_a_partial_deploy_fails_and_names_the_host_left_behind(self):
        # ADR-020's second load-bearing rule, observed from the outside: a
        # re-pushed `latest` rolls whichever app's template changed and leaves
        # the others serving what they cached. Three hosts on two commits is a
        # run that looked successful and deployed one app in three.
        verdict = evaluate(
            observed(
                containerApps=[
                    {"name": HOSTS[0], "image": f"{REGISTRY}/macaebackend:{HEAD[:12]}"},
                    {"name": HOSTS[1], "image": f"{REGISTRY}/macaefrontend:a96b44815f80"},
                    {"name": HOSTS[2], "image": f"{REGISTRY}/macaemcp:{HEAD[:12]}"},
                ],
                commits={
                    HEAD[:12]: {"known": True, "behind": 0, "undeployed": []},
                    "a96b44815f80": {"known": True, "behind": 9, "undeployed": []},
                },
            )
        )
        check = verdict.check("build-agreement")

        assert check.status == FAIL
        assert HOSTS[1] in check.detail
        assert not verdict.ok


class TestTheReport:
    """What the presenter reads, and what the exit code says."""

    def test_a_current_deployment_reports_the_commit_it_matched(self):
        report = format_report(evaluate(observed()))

        assert "PASS" in report
        assert "UNKN" not in report

    def test_an_unknown_is_never_printed_as_a_pass(self):
        report = format_report(evaluate(observed(head=None)))

        assert "UNKN" in report

    def test_a_current_deployment_exits_zero(self):
        assert main([], read=lambda group: observed()) == 0

    def test_a_drifted_deployment_exits_one(self):
        assert main([], read=lambda group: drifted()) == 1

    def test_an_unprovable_deployment_exits_three_not_zero(self):
        # Distinct from drift on purpose. "We could not tell" and "it is nine
        # commits old" send the reader to different places, and only one of
        # them is fixed by re-running the deploy.
        assert main([], read=lambda group: observed(head=None)) == 3


class TestTheCheckIsPartOfTheRecord:
    """A check nobody can find is a check nobody runs.

    Every other preflight in this repository is a pair — a record under
    `docs/preflight/` and a re-runnable script beside it, both named in
    `AGENTS.md`. A check that exists only as a Python module is one an agent
    re-derives by hand, which is the failure `AGENTS.md`'s preflight table
    exists to prevent.
    """

    def test_the_script_exists_and_runs(self):
        assert SCRIPT.exists(), "nothing runs the deployed-build check"
        assert os.access(SCRIPT, os.X_OK), f"{SCRIPT.name} is not executable"

    def test_the_record_and_its_check_are_both_declared(self):
        agents = AGENTS.read_text(encoding="utf-8")

        assert "docs/preflight/deployed-build.md" in agents, (
            "the deployed-build record is not in the preflight table"
        )
        assert "scripts/preflight/check-deployed-build.sh" in agents, (
            "the record names no re-runnable check"
        )

    def test_the_check_only_ever_reads(self):
        # ADR-018: "The check is read-only." It is run before a demonstration,
        # against the demonstration's own environment, by someone who cannot
        # recover from it having changed something.
        source = MODULE.read_text(encoding="utf-8")

        for mutation in ('"az", "containerapp", "update"', "az_write",
                         '_git("checkout"', '_git("fetch"', '_git("reset"'):
            assert mutation not in source, f"the check writes: {mutation}"
        for verb in ("update", "create", "delete", "restart"):
            assert f'"{verb}"' not in source, (
                f"an `az {verb}` reached the check; it must only read"
            )
