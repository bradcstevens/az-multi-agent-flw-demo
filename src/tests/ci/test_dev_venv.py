"""Tests for the feedback loops' own virtualenv bootstrap.

Every loop in AGENTS.md sources `scripts/dev-venv.sh`, so this decision — where
the virtualenv lives, and whether it is already warm — is upstream of every
other check in the repository. ADR-005 accepted that a cold worktree pays a
one-off dependency install; what it did not anticipate is that the integration
gate runs each loop in a *fresh* worktree, so that one-off install sat between
every merged lane and a green gate, and a package index that blinked turned a
perfectly good lane red. Issue #117's integration burned four consecutive
auto-resolution attempts on exactly that, and issue #115's post-merge gate
failed the same way with all six loops passing against a warm environment.

Two properties close it, and both are asserted here:

- A stamp-identical virtualenv already built anywhere on this machine is
  **reused**, so the second worktree to ask for a given dependency set never
  touches the network.
- A bootstrap that genuinely cannot provision **says so with its own exit
  code**, so a gate never again reports a network outage as a lint failure.
"""

import os
import shutil
import subprocess
from pathlib import Path

from dev_venv import EXIT_CANNOT_PROVISION, resolve, stamp_value

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOTSTRAP = REPO_ROOT / "scripts" / "dev-venv.sh"
RESOLVER = REPO_ROOT / "scripts" / "dev_venv.py"


def make_venv(path, stamp):
    """Build the parts of a virtualenv that the bootstrap's warmth test reads."""
    (path / "bin").mkdir(parents=True, exist_ok=True)
    python = path / "bin" / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    if stamp is not None:
        (path / ".dev-venv-stamp").write_text(stamp, encoding="utf-8")
    return path


def run_bootstrap(cwd, env, timeout):
    """Source the bootstrap and call it exactly as every loop script does.

    Each loop is `set -euo pipefail`, `source dev-venv.sh`, `dev_venv_ensure`,
    so what the gate reads is this script's exit code — which is the whole
    point of the bootstrap having one of its own.
    """
    bootstrap = Path(cwd) / "scripts" / "dev-venv.sh"
    script = f'set -euo pipefail\nsource "{bootstrap}"\ndev_venv_ensure\n'
    return subprocess.run(
        ["bash", "-c", script],
        cwd=str(cwd),
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def make_checkout(tmp_path, requirements="example-package==1.0\n"):
    """A throwaway checkout carrying only what the bootstrap reads.

    The bootstrap derives REPO_ROOT from its own location, so copying the two
    scripts and a requirements file is a whole repository as far as it is
    concerned — and keeps the test off this worktree's real `.venv`.
    """
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(BOOTSTRAP, root / "scripts" / "dev-venv.sh")
    shutil.copy(RESOLVER, root / "scripts" / "dev_venv.py")
    (root / ".github").mkdir()
    (root / ".github" / "requirements.txt").write_text(requirements, encoding="utf-8")
    return root


def bootstrap_extra_tools(checkout):
    """The pinned tools the shell adds to the stamp, read from the shell itself."""
    bootstrap = Path(checkout) / "scripts" / "dev-venv.sh"
    result = subprocess.run(
        ["bash", "-c", f'source "{bootstrap}"; printf "%s\\n" "${{DEV_VENV_EXTRA_TOOLS[@]}}"'],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


class TestReusingAWarmEnvironmentAcrossWorktrees:
    def test_given_a_stamp_identical_shared_venv_when_resolving_a_cold_worktree_then_it_is_reused(
        self, tmp_path
    ):
        repo_root = tmp_path / "worktrees" / "issue-115"
        repo_root.mkdir(parents=True)
        cache = tmp_path / "cache"
        stamp = "a" * 64
        shared = make_venv(cache / "az-multi-agent-flw-demo" / f"venv-{stamp[:12]}", stamp)

        resolution = resolve(repo_root, stamp, env={}, cache_home=cache)

        assert resolution.path == shared
        assert resolution.warm is True

    def test_given_no_warm_venv_anywhere_when_resolving_then_it_is_created_in_the_shared_cache(
        self, tmp_path
    ):
        repo_root = tmp_path / "worktrees" / "issue-115"
        repo_root.mkdir(parents=True)
        cache = tmp_path / "cache"
        stamp = "b" * 64

        resolution = resolve(repo_root, stamp, env={}, cache_home=cache)

        assert resolution.warm is False
        assert resolution.path == cache / "az-multi-agent-flw-demo" / f"venv-{stamp[:12]}"

    def test_given_a_shared_venv_built_for_other_requirements_when_resolving_then_it_is_not_reused(
        self, tmp_path
    ):
        repo_root = tmp_path / "worktrees" / "issue-115"
        repo_root.mkdir(parents=True)
        cache = tmp_path / "cache"
        make_venv(cache / "az-multi-agent-flw-demo" / "venv-oldoldoldold", "c" * 64)
        wanted = "d" * 64

        resolution = resolve(repo_root, wanted, env={}, cache_home=cache)

        assert resolution.warm is False
        assert resolution.path.name == f"venv-{wanted[:12]}"


class TestReusingTheMainCheckoutsEnvironment:
    """The warm environment on this machine is usually the main checkout's.

    `git worktree` puts every lane in its own directory beside the checkout a
    developer actually works in, and that checkout has had a provisioned
    `.venv` since ADR-005. A lane worktree that ignores it and builds its own
    is asking the network for something it already has.
    """

    def test_given_the_main_checkout_is_warm_when_resolving_a_lane_worktree_then_it_is_reused(
        self, tmp_path
    ):
        main = tmp_path / "checkout"
        main.mkdir()
        lane = tmp_path / "worktrees" / "issue-115"
        lane.mkdir(parents=True)
        stamp = "2" * 64
        warm = make_venv(main / ".venv", stamp)

        resolution = resolve(
            lane, stamp, env={}, cache_home=tmp_path / "cache", main_worktree=main
        )

        assert resolution.path == warm
        assert resolution.warm is True

    def test_given_the_main_checkout_is_stale_when_resolving_then_the_shared_store_is_used(
        self, tmp_path
    ):
        main = tmp_path / "checkout"
        main.mkdir()
        lane = tmp_path / "worktrees" / "issue-115"
        lane.mkdir(parents=True)
        make_venv(main / ".venv", "8" * 64)
        stamp = "3" * 64

        resolution = resolve(
            lane, stamp, env={}, cache_home=tmp_path / "cache", main_worktree=main
        )

        assert resolution.warm is False
        assert resolution.path.name == f"venv-{stamp[:12]}"

    def test_given_no_main_checkout_is_known_when_resolving_then_resolution_still_succeeds(
        self, tmp_path
    ):
        lane = tmp_path / "lane"
        lane.mkdir()
        stamp = "4" * 64

        resolution = resolve(lane, stamp, env={}, cache_home=tmp_path / "cache", main_worktree=None)

        assert resolution.warm is False

    def test_given_the_worktree_venv_link_dangles_when_resolving_then_a_warm_one_is_found(
        self, tmp_path
    ):
        """A link left pointing at a deleted store entry must not look warm.

        Store entries are disposable — `~/.cache` gets cleared, a machine gets
        tidied — and the link in the worktree outlives them. Reading a dangling
        link as an answer hands the loops an interpreter that is not there.
        """
        main = tmp_path / "checkout"
        main.mkdir()
        lane = tmp_path / "worktrees" / "issue-115"
        lane.mkdir(parents=True)
        stamp = "6" * 64
        warm = make_venv(main / ".venv", stamp)
        (lane / ".venv").symlink_to(tmp_path / "deleted-store-entry", target_is_directory=True)

        resolution = resolve(
            lane, stamp, env={}, cache_home=tmp_path / "cache", main_worktree=main
        )

        assert resolution.path == warm
        assert resolution.warm is True

    def test_given_a_venv_with_no_stamp_when_resolving_then_it_is_not_warm(self, tmp_path):
        """A build interrupted before it was stamped is not a usable environment."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        make_venv(repo_root / ".venv", None)

        resolution = resolve(
            repo_root, "7" * 64, env={}, cache_home=tmp_path / "cache", main_worktree=None
        )

        assert resolution.warm is False

    def test_given_the_worktree_venv_is_a_link_into_the_store_then_the_real_path_is_returned(
        self, tmp_path
    ):
        """Resolve the link, or the second run links `.venv` to itself.

        The first run leaves `.venv` as a link to the warm environment. If the
        second run then reports the *link* as the answer, the bootstrap is
        handed a target and a link that name the same directory by two
        different strings — one logical, one physical — and `ln -sfn` turns
        `.venv` into a symlink to itself. That worktree is then unusable until
        someone deletes it by hand, and the error it gives ("Too many levels of
        symbolic links") names nothing that would lead them there.
        """
        main = tmp_path / "checkout"
        main.mkdir()
        lane = tmp_path / "worktrees" / "issue-115"
        lane.mkdir(parents=True)
        stamp = "5" * 64
        warm = make_venv(main / ".venv", stamp)
        (lane / ".venv").symlink_to(warm, target_is_directory=True)

        resolution = resolve(
            lane, stamp, env={}, cache_home=tmp_path / "cache", main_worktree=main
        )

        assert resolution.warm is True
        assert resolution.path == warm.resolve()
        assert not resolution.path.is_symlink()


class TestHonouringTheLocationsAlreadyDocumented:
    def test_given_dev_venv_is_set_when_resolving_then_that_location_wins(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        cache = tmp_path / "cache"
        stamp = "e" * 64
        make_venv(cache / "az-multi-agent-flw-demo" / f"venv-{stamp[:12]}", stamp)
        chosen = make_venv(tmp_path / "explicit", stamp)

        resolution = resolve(repo_root, stamp, env={"DEV_VENV": str(chosen)}, cache_home=cache)

        assert resolution.path == chosen
        assert resolution.warm is True

    def test_given_a_warm_venv_in_the_worktree_when_resolving_then_it_is_used_untouched(
        self, tmp_path
    ):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        cache = tmp_path / "cache"
        stamp = "f" * 64
        local = make_venv(repo_root / ".venv", stamp)

        resolution = resolve(repo_root, stamp, env={}, cache_home=cache)

        assert resolution.path == local
        assert resolution.warm is True

    def test_given_a_stale_venv_in_the_worktree_when_resolving_then_the_shared_cache_is_preferred(
        self, tmp_path
    ):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        cache = tmp_path / "cache"
        stamp = "1" * 64
        make_venv(repo_root / ".venv", "9" * 64)
        shared = make_venv(cache / "az-multi-agent-flw-demo" / f"venv-{stamp[:12]}", stamp)

        resolution = resolve(repo_root, stamp, env={}, cache_home=cache)

        assert resolution.path == shared
        assert resolution.warm is True


class TestTheStamp:
    def test_given_the_same_inputs_when_stamped_twice_then_the_value_is_stable(self):
        assert stamp_value("fastapi==0.137.1\n", ["flake8==7.1.1"]) == stamp_value(
            "fastapi==0.137.1\n", ["flake8==7.1.1"]
        )

    def test_given_a_changed_requirement_when_stamped_then_the_value_moves(self):
        before = stamp_value("fastapi==0.137.1\n", ["flake8==7.1.1"])
        after = stamp_value("fastapi==0.138.0\n", ["flake8==7.1.1"])

        assert before != after

    def test_given_the_shell_bootstraps_inputs_when_stamped_then_python_agrees_with_the_shell(self):
        """The shell hashed `printf tools; cat requirements` — keep that exact value.

        A different hash here is not a bug in itself, but it would silently
        orphan every virtualenv already stamped on every machine, so the
        equivalence is worth pinning.
        """
        requirements = "fastapi==0.137.1\nuvicorn==0.31.0\n"
        tools = ["flake8==7.1.1"]

        import hashlib

        expected = hashlib.sha256(
            ("flake8==7.1.1\n" + requirements).encode("utf-8")
        ).hexdigest()

        assert stamp_value(requirements, tools) == expected


class TestFailingHonestly:
    def test_given_provisioning_is_impossible_then_its_exit_code_is_not_the_loops_failure_code(
        self,
    ):
        """A network outage must not look like a flake8 violation.

        The gate reads an exit code. flake8 and pytest both signal a real
        finding with 1, so the bootstrap must not also exit 1 when it simply
        could not build an environment to run them in.
        """
        assert EXIT_CANNOT_PROVISION != 0
        assert EXIT_CANNOT_PROVISION != 1


class TestTheShellCarriesTheVerdict:
    """The exit code only helps if the shell every loop sources actually uses it.

    `dev_venv.py` decides; `dev-venv.sh` is what the loops run. A constant that
    differs from 1 in the module while the shell still aborts with 1 buys
    nothing, so both shell-only properties are exercised here — without a
    package index, because the whole point is behaviour when there isn't one.
    """

    def test_given_the_environment_cannot_be_built_then_the_loop_exits_three_not_one(
        self, tmp_path
    ):
        """Unbuildable is exit 3, and promptly.

        `DEV_VENV` points below a plain file, so nothing can be created there —
        an offline stand-in for the unreachable index that turned two lanes red.
        The timeout is part of the assertion: the build lock lives beside the
        environment, so a lock that cannot tell "held by another worktree" from
        "there is nowhere to put it" waits ten minutes for nobody.
        """
        checkout = make_checkout(tmp_path)
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("", encoding="utf-8")

        result = run_bootstrap(
            checkout, {"DEV_VENV": str(blocker / "venv"), "XDG_CACHE_HOME": str(tmp_path / "cache")},
            timeout=90,
        )

        assert result.returncode == EXIT_CANNOT_PROVISION, result.stderr
        assert "environment failure" in result.stderr

    def test_given_a_warm_shared_environment_then_the_loop_uses_it_and_dot_venv_points_at_it(
        self, tmp_path
    ):
        """A cold worktree beside a warm store entry provisions nothing.

        This is the property that keeps the gate off the network, and the link
        is how AGENTS.md's documented `.venv/bin/python` invocations — the
        guardrail corpus, the fast-lane measurement — keep working in a
        worktree that never built a virtualenv of its own.
        """
        requirements = "example-package==1.0\n"
        checkout = make_checkout(tmp_path, requirements)
        cache = tmp_path / "cache"
        stamp = stamp_value(requirements, bootstrap_extra_tools(checkout))
        store_entry = make_venv(
            cache / "az-multi-agent-flw-demo" / f"venv-{stamp[:12]}", stamp
        )

        result = run_bootstrap(checkout, {"XDG_CACHE_HOME": str(cache)}, timeout=90)

        assert result.returncode == 0, result.stderr
        assert "installing pinned dependencies" not in result.stdout
        link = checkout / ".venv"
        assert link.is_symlink()
        assert link.resolve() == store_entry.resolve()

    def test_given_a_hand_built_venv_in_the_worktree_then_it_survives_and_the_mismatch_is_said(
        self, tmp_path
    ):
        """A real `.venv` is never deleted, and never silently bypassed.

        Replacing a directory somebody built themselves would be data loss, so
        the bootstrap leaves it and runs the loops elsewhere — which is exactly
        the situation in which AGENTS.md's documented `.venv/bin/python`
        invocations stop agreeing with the loops. Saying so is what keeps the
        divergence from being silent.
        """
        requirements = "example-package==1.0\n"
        checkout = make_checkout(tmp_path, requirements)
        cache = tmp_path / "cache"
        stamp = stamp_value(requirements, bootstrap_extra_tools(checkout))
        make_venv(cache / "az-multi-agent-flw-demo" / f"venv-{stamp[:12]}", stamp)
        stale = make_venv(checkout / ".venv", "0" * 64)

        result = run_bootstrap(checkout, {"XDG_CACHE_HOME": str(cache)}, timeout=90)

        assert result.returncode == 0, result.stderr
        assert not stale.is_symlink()
        assert (stale / ".dev-venv-stamp").read_text(encoding="utf-8") == "0" * 64
        assert "different pinned inputs" in result.stderr
