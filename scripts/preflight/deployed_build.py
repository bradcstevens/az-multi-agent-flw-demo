#!/usr/bin/env python3
"""Preflight: is the deployed build the build we think it is?

**Deployment drift** is the distance between the images the Container Apps are
running and the commit they were built from. Nothing measured it until this
check, and the reasons are structural rather than careless. Every declared
feedback loop runs against fakes, so all of them stay green while the deployment
is arbitrarily old. `check-deployed-environment.sh` grades an image's
*provenance* — not the **Placeholder image**, and from the expected registry —
and both were true of an image forty-two commits out of date.
`check-deployed-surface.sh` catches drift that has already changed something
visible, which is a symptom rather than a measurement: it cannot tell a
deployment one commit behind from a current one.

So this check reads the tag off every Container App's image and asks `git` how
far it is from `HEAD`. See docs/preflight/deployed-build.md and
[ADR-018](../../docs/ADR/018-deployed-build-provenance-check.md).

Three things here are the point rather than implementation detail:

- **Unknown is not a pass.** An image whose tag names no commit, or a commit
  this checkout has never heard of, is reported `UNKN` and exits non-zero.
  ADR-018: treating that as a pass would rebuild the exact hole this closes.
- **The comparison base is reported.** The verdict is a claim about `HEAD`, so
  a detached or dirty checkout is named rather than left to be assumed.
- **The hosts are checked against each other, not only against `HEAD`.** Three
  hosts on two commits is ADR-020's second failure mode seen from outside: a
  deploy that looked successful and rolled one app in three.

`evaluate` is pure: it takes what `az` and `git` answered and returns a
`Verdict`. The live reads are in `read_build`.
"""

import argparse
import json
import re
import subprocess
import sys

RESOURCE_GROUP = "rg-macae-flw-v1"

#: The three states a check can be in. `UNKNOWN` exists because the honest
#: answer to "is this build current" is often "nothing here can say", and the
#: only wrong thing to do with that answer is round it to `PASS`.
PASS = "pass"
UNKNOWN = "unknown"
FAIL = "fail"

#: What `deploy-main.yml` stamps: `git rev-parse --short=12 HEAD`. Accepted
#: wider than twelve so a hand-run `az acr build` with a full or a short SHA
#: still reads as a commit — and narrower than seven would match `latest` on a
#: bad day, and does match nothing else this registry is ever tagged with.
COMMIT_TAG = re.compile(r"^[0-9a-f]{7,40}$")


class Check:
    """One named expectation, its three-state outcome, and why."""

    def __init__(self, name, status, detail):
        self.name = name
        self.status = status
        self.detail = detail

    @property
    def ok(self):
        """True only for `PASS`. An unproved check is not a passing one."""
        return self.status == PASS


class Verdict:
    """The outcome of every check, and whether the deployment is proved current."""

    def __init__(self, checks):
        self.checks = checks

    @property
    def ok(self):
        return all(check.ok for check in self.checks)

    @property
    def failed(self):
        """True when something is definitely wrong, as against merely unproved."""
        return any(check.status == FAIL for check in self.checks)

    def check(self, name):
        """Return the named `Check`."""
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)


def evaluate(observed):
    """Return the `Verdict` for a deployment's images against `HEAD`. Pure."""
    container_apps = observed.get("containerApps") or []
    commits = observed.get("commits") or {}
    return Verdict(
        [
            _comparison_base_check(observed),
            _build_stamp_check(container_apps),
            _build_currency_check(container_apps, commits, observed),
            _build_agreement_check(container_apps),
        ]
    )


def commit_from_image(image):
    """Return the commit an image reference names, or None. Pure.

    The tag is the stamp. `deploy-main.yml` builds `<image>:<sha>` from
    `git rev-parse --short=12 HEAD`, and ADR-020 records why it is the commit
    and not `latest`: `azd provision` only rolls a revision where the template
    changed, so a re-pushed `latest` deploys one app in three.

    A tag is a *claim* rather than a stamp inside the image — anyone may push
    any tag — and that is the honest limit of this first version, stated in
    `docs/preflight/deployed-build.md` rather than papered over. What it is not
    is a guess: a reference that names no commit returns None and is reported
    `UNKN`, never `PASS`.
    """
    reference = image or ""
    # A digest-pinned reference carries no tag at all, and its 64 hex characters
    # would otherwise read as a very long commit.
    if "@" in reference:
        return None
    # The last path segment, so a registry host's port (`localhost:5000/x`) is
    # not mistaken for a tag.
    name = reference.rsplit("/", 1)[-1]
    if ":" not in name:
        return None
    tag = name.rsplit(":", 1)[-1]
    return tag if COMMIT_TAG.match(tag) else None


def deployed_build(observed):
    """Return the one commit every application host runs, or None. Pure.

    The verdict grades a deployment and then throws away *which* deployment it
    graded. That was enough while the only reader was a presenter reading the
    report — and it is not enough for the **rehearsal** (#54), whose claim is
    ten consecutive runs of the centrepiece beat against **one** build. A run
    that cannot name the build it observed cannot be told apart from a run
    somebody got past the gate with `E2E_SKIP_BUILD_CHECK`, and ten of those
    read as a proof.

    `None` whenever the hosts do not agree on one datable commit, which is
    ADR-018's rule seen from the other side: a build that cannot be named has
    not been proved, and the name is what the ledger records.
    """
    container_apps = observed.get("containerApps") or []
    if not container_apps:
        return None
    commits = {commit_from_image(app.get("image")) for app in container_apps}
    if len(commits) != 1:
        return None
    return commits.pop()


def _comparison_base_check(observed):
    """Which commit this run compared against.

    ADR-018's second negative consequence, made visible: the check couples a
    preflight to `git` state, so it is meaningless run from a detached or stale
    checkout. Naming the base costs one line and turns "the deployment is nine
    commits behind" into a statement the reader can check.
    """
    head = observed.get("head")
    if not head:
        return Check(
            "comparison-base",
            UNKNOWN,
            "this run could not read a commit from git, so it has no base to "
            "compare the deployment against — nothing below is a measurement",
        )
    branch = observed.get("branch")
    where = f"branch {branch}" if branch else "a detached HEAD"
    detail = f"compared against {head[:12]} on {where}"
    if observed.get("dirty"):
        detail += ", with uncommitted changes in the worktree"
    return Check("comparison-base", PASS, detail)


def _build_stamp_check(container_apps):
    """Every application host's image names the commit it was built from."""
    if not container_apps:
        return Check(
            "build-stamp",
            UNKNOWN,
            "no container apps were read, so no image could be dated",
        )
    unstamped = [
        f"{app.get('name')} runs {app.get('image')}"
        for app in container_apps
        if commit_from_image(app.get("image")) is None
    ]
    if unstamped:
        return Check(
            "build-stamp",
            UNKNOWN,
            "; ".join(unstamped)
            + " — an image whose tag names no commit cannot be dated, so this "
            "is unproved rather than current",
        )
    return Check(
        "build-stamp",
        PASS,
        f"all {len(container_apps)} container apps run a commit-tagged image",
    )


def _build_currency_check(container_apps, commits, observed):
    """The commit every host runs is `HEAD`, or the distance is reported."""
    if not observed.get("head"):
        return Check(
            "build-currency",
            UNKNOWN,
            "there is no HEAD to compare against",
        )
    deployed = {}
    for app in container_apps:
        commit = commit_from_image(app.get("image"))
        if commit is not None:
            deployed.setdefault(commit, []).append(app.get("name"))
    if not deployed:
        return Check(
            "build-currency",
            UNKNOWN,
            "no image named a commit, so no distance is computable",
        )

    unknown, problems, undeployed = [], [], []
    for commit, names in sorted(deployed.items()):
        known = commits.get(commit) or {}
        if not known.get("known"):
            unknown.append(
                f"{commit} ({', '.join(names)}) is not a commit this checkout "
                "knows — a shallow clone, or an image built from a branch that "
                "never landed"
            )
            continue
        behind = known.get("behind") or 0
        ahead = known.get("ahead") or 0
        if ahead:
            problems.append(
                f"{commit} ({', '.join(names)}) is {ahead} commit(s) ahead of "
                "this checkout — the deployment is newer than what is being "
                "read here, so this checkout is the stale one"
            )
        if behind:
            problems.append(
                f"{commit} ({', '.join(names)}) is {behind} commit(s) behind "
                "HEAD"
            )
            undeployed.extend(known.get("undeployed") or [])

    if problems:
        detail = "; ".join(problems)
        if undeployed:
            detail += ". Not deployed: " + "; ".join(
                f"{subject!r}" for subject in _first(undeployed)
            )
        return Check("build-currency", FAIL, detail)
    if unknown:
        return Check("build-currency", UNKNOWN, "; ".join(unknown))
    return Check(
        "build-currency",
        PASS,
        f"every container app runs {observed['head'][:12]}, which is HEAD",
    )


#: How many undeployed commit subjects a failing report names before it stops.
#: The number is a reading limit, not a truncation of the verdict: the count is
#: already in the sentence above it, and forty subjects buries it.
UNDEPLOYED_SHOWN = 10


def _first(subjects):
    shown = subjects[:UNDEPLOYED_SHOWN]
    if len(subjects) > UNDEPLOYED_SHOWN:
        shown = shown + [f"and {len(subjects) - UNDEPLOYED_SHOWN} more"]
    return shown


def _build_agreement_check(container_apps):
    """All the application hosts run the same build.

    ADR-020's second load-bearing rule, observed from outside the deploy: a
    re-pushed `latest` rolls whichever app's template changed and leaves the
    others serving what they cached. Three hosts on two commits is a deploy
    that looked successful and updated one app in three — and every one of
    those hosts would pass a currency check written per-app if the newest one
    happened to be `HEAD`.
    """
    deployed = {}
    for app in container_apps:
        commit = commit_from_image(app.get("image"))
        if commit is not None:
            deployed.setdefault(commit, []).append(app.get("name"))
    if len(deployed) <= 1:
        return Check(
            "build-agreement",
            PASS,
            "every container app runs the same build"
            if deployed
            else "no dated image to disagree with",
        )
    spread = "; ".join(
        f"{', '.join(sorted(names))} on {commit}"
        for commit, names in sorted(deployed.items())
    )
    return Check(
        "build-agreement",
        FAIL,
        f"the application hosts run {len(deployed)} different builds ({spread})"
        " — a partial deploy leaves a surface whose halves were never tested "
        "together",
    )


def format_report(verdict):
    """Return the human-readable report for a `Verdict`. Pure.

    `UNKN` is four characters for the same reason it is a status: it must not
    be skimmable as `PASS`. A reader scanning a column of verdicts on the
    morning of a demonstration reads shape before words.
    """
    label = {PASS: "PASS", FAIL: "FAIL", UNKNOWN: "UNKN"}
    return "\n".join(
        f"  {label[check.status]}  {check.name}: {check.detail}"
        for check in verdict.checks
    )


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


def _git(*args):
    """Run a `git` command, returning its stdout or None if it did not answer.

    Read-only by construction: every caller passes a query. A preflight that
    could move a ref would be a preflight nobody runs before a demonstration.
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def read_build(resource_group=RESOURCE_GROUP):
    """Read the running images and what `git` knows about them."""
    apps = _az("containerapp", "list", "-g", resource_group) or []
    container_apps = [
        {
            "name": app.get("name"),
            "image": (
                ((app.get("properties") or {}).get("template") or {}).get(
                    "containers") or [{}]
            )[0].get("image"),
        }
        for app in apps
    ]
    head = _git("rev-parse", "HEAD")
    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD")
    commits = {}
    for app in container_apps:
        commit = commit_from_image(app["image"])
        if commit is None or commit in commits:
            continue
        commits[commit] = _distance(commit, head)
    return {
        "head": head,
        "branch": branch or None,
        "dirty": bool(_git("status", "--porcelain")),
        "containerApps": container_apps,
        "commits": commits,
    }


def _distance(commit, head):
    """How far `commit` is from `head`, and the subjects in between."""
    if not head or _git("cat-file", "-e", f"{commit}^{{commit}}") is None:
        return {"known": False}
    counts = _git("rev-list", "--left-right", "--count", f"{commit}...{head}")
    if counts is None:
        return {"known": False}
    ahead, behind = (int(part) for part in counts.split())
    subjects = _git("log", "--format=%s", f"{commit}..{head}") if behind else ""
    return {
        "known": True,
        "ahead": ahead,
        "behind": behind,
        "undeployed": [line for line in (subjects or "").splitlines() if line],
    }


def main(argv=None, read=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-group", default=RESOURCE_GROUP)
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the verdict as JSON, for the Demo validator's first "
             "assertion rather than for a reader.",
    )
    args = parser.parse_args(argv)

    reader = read or read_build
    read_state = reader(args.resource_group)
    verdict = evaluate(read_state)

    if args.json:
        print(json.dumps({
            "ok": verdict.ok,
            "failed": verdict.failed,
            "resourceGroup": args.resource_group,
            "deployedBuild": deployed_build(read_state),
            # The rendered report travels with the verdict so its one reader —
            # the Demo validator's global setup — gets the human text and the
            # commit from a single `az` read, and never renders a second
            # opinion of `format_report` in another language.
            "report": format_report(verdict),
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail}
                for c in verdict.checks
            ],
        }, indent=2))
    else:
        print(f"Deployed build: {args.resource_group}")
        print(format_report(verdict))

    if verdict.failed:
        return 1
    # Nothing failed, but something could not be proved. Deliberately not zero:
    # "we could not tell" and "it is nine commits old" send the reader to
    # different places, and only one of them is fixed by re-running the deploy.
    return 0 if verdict.ok else 3


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
