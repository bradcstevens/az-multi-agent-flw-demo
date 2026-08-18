"""Tests for the worktree sweep's collection ladder (issue #161, ADR-044).

Thirteen worktrees of this repository accumulated as flat siblings in the
developer's projects folder because nothing said where a worktree belongs, and
nothing collected one afterwards. ADR-044 answers both halves — *inside
``<repo>.worktrees/``, collected once every commit is reachable from
``origin/main``* — and this file guards the answer.

The seam under test is the pure decision. Given a ``Worktree`` record of what
git observed, :func:`classify` returns what happens to it. Every git call sits
outside that function, so the ladder that decides **whether uncommitted work
survives** is testable with no repository, no remote and no disk.

The invariants defended hardest are the ones that cost something to get wrong:

- **A live worktree is stood down from first.** One was observed changing from
  three uncommitted files to clean four minutes before the grilling session that
  produced this ADR started. If that check is not the first branch, a running
  session can be stashed under.
- **Nothing is ever force-removed.** ``git worktree remove`` refuses a dirty
  worktree, and that refusal is the last thing standing between a sweep and
  somebody's afternoon.
- **The base ref is remote.** Local ``main`` was two commits behind when this was
  written. A sweep that reads it is wrong in a way that grows quietly.
"""

from pathlib import Path

import ast

import pytest

from worktree_hygiene import (
    BASE_REF,
    Branch,
    COLLECT,
    CONTAINER_SUFFIX,
    DEFER,
    ESCALATE,
    KEEP,
    SKIP_ACTIVE,
    STASH_THEN_COLLECT,
    Worktree,
    classify_branch,
    classify,
    container_for,
    exit_code,
    is_externally_owned,
    is_sanctioned,
    liveness_observation,
    owner_run_id_for_worktree,
    parse_live_run_ids,
    plan,
    plan_branches,
    render,
    render_remote_branches,
    stash_message,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "worktree.sh"
MODULE = REPO_ROOT / "scripts" / "worktree_hygiene.py"
AGENTS = REPO_ROOT / "AGENTS.md"
ADR = REPO_ROOT / "docs" / "ADR" / "044-an-agent-worktree-lives-in-the-containing-folder.md"

PRIMARY = Path("/code/az-multi-agent-flw-demo")
CONTAINER = Path("/code/az-multi-agent-flw-demo.worktrees")


def make(**overrides) -> Worktree:
    """An idle, clean, fully-landed worktree — the boring case every test bends."""
    defaults = dict(
        path=CONTAINER / "issue-123",
        head="a" * 40,
        branch="issue-123",
        is_primary=False,
        sanctioned=True,
        externally_owned=False,
        owner_run_id=None,
        dirty=False,
        locked=False,
        idle_seconds=10_000.0,
        reachable_from_base=True,
        commits_absent_from_remote=0,
    )
    defaults.update(overrides)
    return Worktree(**defaults)


# --------------------------------------------------------------------------
# Location
# --------------------------------------------------------------------------


def test_the_container_is_a_sibling_of_the_repository_not_a_child():
    """Inside the repo it would be committed; the container is beside it."""
    container = container_for(PRIMARY)

    assert container == CONTAINER
    assert container.parent == PRIMARY.parent
    assert PRIMARY not in container.parents


def test_the_container_is_named_for_the_repository_it_belongs_to():
    """Two repositories in one folder must not share a container."""
    assert container_for(Path("/code/other-repo")).name == f"other-repo{CONTAINER_SUFFIX}"
    assert container_for(PRIMARY) != container_for(Path("/code/other-repo"))


@pytest.mark.parametrize(
    "path",
    [
        CONTAINER / "issue-123",
        CONTAINER / "01M06AG4CAAKZVEE35Y1QTPXQQ" / "issue-103",
        CONTAINER / "a" / "b" / "c",
    ],
)
def test_anything_below_the_container_is_sanctioned(path):
    """git-loopy files lanes under ``<run-id>/<lane>`` and stays correct.

    ADR-044 governs the containing folder, not a naming scheme — disturbing
    tooling that already puts its worktrees in the right place would buy
    nothing.
    """
    assert is_sanctioned(path, PRIMARY)


@pytest.mark.parametrize(
    "path",
    [
        Path("/code/az-mafd-issue-101"),
        Path("/code/az-mafd-grill-92"),
        PRIMARY.parent,
        PRIMARY / "nested-inside-the-repo",
        Path("/code/other-repo.worktrees/issue-1"),
        CONTAINER,
    ],
)
def test_the_parent_directory_is_never_sanctioned(path):
    """The exact shape of the defect: ``git worktree add ../<slug>``."""
    assert not is_sanctioned(path, PRIMARY)


# --------------------------------------------------------------------------
# The ladder
# --------------------------------------------------------------------------


def test_the_primary_checkout_is_never_collected():
    assert classify(make(is_primary=True, reachable_from_base=True)).action == KEEP


def test_a_landed_clean_worktree_is_collected():
    verdict = classify(make())

    assert verdict.action == COLLECT
    assert BASE_REF in verdict.reason


def test_a_landed_dirty_worktree_is_stashed_before_it_is_removed():
    """The only destructible thing a sweep can reach is working-tree edits."""
    verdict = classify(make(dirty=True))

    assert verdict.action == STASH_THEN_COLLECT
    assert "stash" in verdict.reason


def test_a_lock_stands_the_sweep_down_before_anything_else_is_asked():
    """Order is the safety property, so assert it on the case that would
    otherwise be destructive: dirty, landed, and therefore in scope."""
    verdict = classify(make(locked=True, dirty=True, reachable_from_base=True))

    assert verdict.action == SKIP_ACTIVE


def test_a_recently_touched_worktree_is_left_alone():
    verdict = classify(make(idle_seconds=60.0, dirty=True))

    assert verdict.action == SKIP_ACTIVE
    assert "60s ago" in verdict.reason


def test_the_idle_threshold_is_the_boundary_not_a_suggestion():
    assert classify(make(idle_seconds=899.0), idle_seconds=900).action == SKIP_ACTIVE
    assert classify(make(idle_seconds=900.0), idle_seconds=900).action == COLLECT


def test_commits_on_no_remote_escalate_rather_than_being_collected():
    verdict = classify(make(reachable_from_base=False, commits_absent_from_remote=3))

    assert verdict.action == ESCALATE
    assert "only copy" in verdict.reason
    assert "3 commits" in verdict.reason


def test_the_escalation_counts_a_single_commit_in_the_singular():
    assert "1 commit exist" in classify(
        make(reachable_from_base=False, commits_absent_from_remote=1)
    ).reason


def test_pushed_but_unlanded_work_is_kept_not_escalated():
    """``issue-102`` and ``issue-110``: on ``origin`` at their exact tips, but
    not yet in ``origin/main``. Nothing is at risk and nothing is finished, so
    the answer is neither removal nor an alarm."""
    verdict = classify(make(reachable_from_base=False, commits_absent_from_remote=0))

    assert verdict.action == KEEP
    assert verdict.retained


def test_a_detached_head_needs_no_special_case():
    """``az-mafd-review-101`` had no branch, so "merged" was undefined for it —
    reachability is defined for everything."""
    verdict = classify(make(branch=None, reachable_from_base=True))

    assert verdict.action == COLLECT


def test_a_misplaced_worktree_is_judged_by_the_same_ladder():
    """Location governs creation; lifetime governs collection. A worktree in
    the wrong place is not thereby more or less safe to remove."""
    misplaced = make(path=Path("/code/az-mafd-issue-101"), sanctioned=False)

    assert classify(misplaced).action == classify(make()).action
    assert classify(misplaced).as_dict()["misplaced"] is True


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


def test_a_worktree_one_level_below_the_container_is_ours():
    """``worktree.sh add <slug>`` creates exactly one level down."""
    assert not is_externally_owned(CONTAINER / "issue-123", PRIMARY, "issue-123")


def test_a_run_scoped_lane_belongs_to_the_run_that_made_it():
    """git-loopy files lanes under ``<run-id>/<lane>``. Structure identifies
    the owner without sniffing branch names — which is necessary, because a
    run's lane is not always on a branch in the run's namespace."""
    lane = CONTAINER / "01M06AG4CAAKZVEE35Y1QTPXQQ" / "issue-103"

    assert is_externally_owned(lane, PRIMARY, "issue-102-remediation")


def test_a_run_scoped_lane_records_the_run_that_owns_it():
    lane = CONTAINER / "01M06AG4CAAKZVEE35Y1QTPXQQ" / "issue-103"

    assert owner_run_id_for_worktree(lane, PRIMARY, "issue-102-remediation") == (
        "01M06AG4CAAKZVEE35Y1QTPXQQ"
    )


def test_an_owned_branch_namespace_is_enough_on_its_own():
    assert is_externally_owned(
        CONTAINER / "issue-50", PRIMARY, "git-loopy/01KZZ89E/integrate/issue-50"
    )


def test_a_deferred_worktree_is_reported_and_never_collected():
    """A run that is paused, blocked, or waiting on a gate looks exactly like
    an abandoned worktree by idleness alone. Deferring costs a folder entry;
    collecting costs the run."""
    verdict = classify(make(externally_owned=True, reachable_from_base=True, dirty=True))

    assert verdict.action == DEFER
    assert verdict.retained


def test_ownership_outranks_every_state_the_sweep_could_act_on():
    """Including the state that would otherwise escalate."""
    for overrides in (
        {"reachable_from_base": True},
        {"reachable_from_base": False, "commits_absent_from_remote": 4},
        {"locked": True},
        {"idle_seconds": 1.0},
    ):
        assert classify(make(externally_owned=True, **overrides)).action == DEFER


def test_deferring_never_makes_the_sweep_exit_non_zero():
    """It is not a problem, and it is not yours to fix."""
    assert exit_code(plan([make(externally_owned=True, commits_absent_from_remote=9)])) == 0


def test_a_dead_run_owner_falls_through_to_collection_but_a_live_one_defers():
    run_id = "01M06AG4CAAKZVEE35Y1QTPXQQ"
    lane = make(externally_owned=True, owner_run_id=run_id)

    assert classify(lane, live_run_ids=frozenset({run_id})).action == DEFER
    assert classify(lane, live_run_ids=frozenset()).action == COLLECT


def test_a_dead_run_owner_with_the_only_copy_escalates():
    lane = make(
        externally_owned=True,
        owner_run_id="01M06AG4CAAKZVEE35Y1QTPXQQ",
        reachable_from_base=False,
        commits_absent_from_remote=1,
    )

    assert classify(lane, live_run_ids=frozenset()).action == ESCALATE


def test_undeterminable_owner_liveness_defers_without_escalating():
    lane = make(
        externally_owned=True,
        owner_run_id="01M06AG4CAAKZVEE35Y1QTPXQQ",
        reachable_from_base=False,
        commits_absent_from_remote=1,
    )
    verdicts = plan([lane], live_run_ids=None)

    assert verdicts[0].action == DEFER
    assert exit_code(verdicts) == 0


def test_an_empty_successful_liveness_probe_means_no_run_is_live():
    assert liveness_observation(returncode=0, stdout="", stderr="") == frozenset()


def test_an_undeterminable_liveness_probe_remains_distinct_from_an_empty_one():
    assert liveness_observation(returncode=2, stdout="", stderr="permission denied") is None


def test_liveness_parser_reads_the_run_id_from_an_open_log_path():
    output = (
        "p47514\n"
        "n/code/az-multi-agent-flw-demo/.git-loopy/logs/"
        "2026-08-17T19-20-30Z-01M08JP4GPHSKED91XXPRX8AGZ.log\n"
    )

    assert parse_live_run_ids(output) == frozenset({"01M08JP4GPHSKED91XXPRX8AGZ"})


# --------------------------------------------------------------------------
# Branches
# --------------------------------------------------------------------------


def make_branch(**overrides) -> Branch:
    defaults = dict(
        name="issue-123",
        checked_out=False,
        is_main=False,
        is_current=False,
        reachable_from_base=True,
        commits_absent_from_remote=0,
        owner_run_id=None,
    )
    defaults.update(overrides)
    return Branch(**defaults)


def test_a_checked_out_branch_is_kept_until_its_worktree_is_collected():
    branch = make_branch(checked_out=True)

    assert classify_branch(branch, live_run_ids=frozenset()).action == KEEP
    assert classify_branch(
        make_branch(checked_out=False), live_run_ids=frozenset()
    ).action == COLLECT


@pytest.mark.parametrize("overrides", [{"is_main": True}, {"is_current": True}])
def test_main_and_the_current_branch_are_never_candidates(overrides):
    assert classify_branch(make_branch(**overrides), live_run_ids=frozenset()).action == KEEP


def test_a_dead_run_branch_with_the_only_copy_escalates():
    branch = make_branch(
        owner_run_id="01M06AG4CAAKZVEE35Y1QTPXQQ",
        reachable_from_base=False,
        commits_absent_from_remote=2,
    )

    assert classify_branch(branch, live_run_ids=frozenset()).action == ESCALATE


def test_remote_reporting_prints_deletion_commands_without_deleting_anything():
    report = render_remote_branches(["closed-pr", "already-landed"])

    assert "git push origin --delete closed-pr" in report
    assert "git push origin --delete already-landed" in report


def test_branch_collection_uses_proven_reachability_not_git_branch_ds_oracle():
    literals = _argv_literals()

    assert "-D" in literals
    assert "-d" not in literals
    assert "merge-base" in literals and "--is-ancestor" in literals


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_only_an_escalation_makes_the_sweep_exit_non_zero():
    """A kept or skipped worktree is the rule working, not the rule failing."""
    assert exit_code(plan([make(), make(dirty=True)])) == 0
    assert exit_code(plan([make(reachable_from_base=False)])) == 0
    assert exit_code(plan([make(locked=True)])) == 0
    assert (
        exit_code(plan([make(), make(reachable_from_base=False, commits_absent_from_remote=1)]))
        == 1
    )


def test_the_stash_message_names_the_worktree_its_branch_and_the_date():
    """A stash nobody can identify is a stash nobody will ever pop."""
    message = stash_message(make(), now="2026-08-16T23:00:00")

    assert "issue-123" in message
    assert "2026-08-16" in message
    assert "worktree-hygiene" in message


def test_a_detached_worktrees_stash_is_still_identifiable():
    message = stash_message(make(branch=None, head="deadbeef" + "0" * 32), now="2026-08-16")

    assert "deadbeef" in message


def test_the_report_flags_a_retained_worktree_that_is_also_misplaced():
    """Three folders left behind with no explanation is the state this replaces."""
    report = render(
        plan([make(path=Path("/code/az-mafd-issue-102"), sanctioned=False, dirty=False,
                   reachable_from_base=False)])
    )

    assert "az-mafd-issue-102" in report
    assert "[misplaced]" in report
    assert KEEP in report


def test_the_report_distinguishes_lanes_that_share_a_name():
    """Three live runs produce three worktrees called ``issue-103``. A report
    — and above all an escalation — naming one of them ``issue-103`` says
    nothing about which one."""
    runs = ["01M06AG4CAAKZVEE35Y1QTPXQQ", "01M06AVSJBEADYYHD78S1DV0P6"]
    verdicts = plan(
        [make(path=CONTAINER / run / "issue-103", externally_owned=True) for run in runs]
    )

    labels = {verdict.worktree.label for verdict in verdicts}
    assert labels == {f"{run}/issue-103" for run in runs}
    for label in labels:
        assert label in render(verdicts)


def test_an_ad_hoc_worktree_is_labelled_by_its_slug_alone():
    assert make(path=CONTAINER / "issue-123").label == "issue-123"


def test_a_misplaced_worktree_outside_the_container_is_labelled_by_name():
    assert make(path=Path("/code/az-mafd-issue-101"), sanctioned=False).label == "az-mafd-issue-101"


# --------------------------------------------------------------------------
# The rule, the script and the documentation say the same thing
# --------------------------------------------------------------------------


def test_the_base_ref_is_remote():
    """Local ``main`` was two commits behind when ADR-044 was written."""
    assert BASE_REF == "origin/main"


def _argv_literals() -> set[str]:
    """Every exact string literal in the module.

    A command-line flag is always its own argv element, so an exact match finds
    a real ``--force`` and never a docstring that merely promises not to use
    one — which is precisely the distinction these two tests exist to make.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_the_sweep_never_force_removes():
    """``git worktree remove`` refuses a dirty worktree, and that refusal is
    the guarantee ADR-044 makes about uncommitted work. Assert it on the
    source, because a single added flag would silently retract it."""
    assert "--force" not in _argv_literals()
    assert "-f" not in _argv_literals()


def test_the_removal_is_reachability_not_merge():
    """``git branch --merged`` cannot tell a landed branch from a stale one."""
    literals = _argv_literals()

    assert "merge-base" in literals and "--is-ancestor" in literals
    assert "--merged" not in literals


def test_the_shell_entry_point_only_fixes_the_entry_point():
    """The logic stays importable, or this suite cannot reach it."""
    script = SCRIPT.read_text(encoding="utf-8")

    assert "worktree_hygiene.py" in script
    assert script.startswith("#!/usr/bin/env bash")


def test_agents_md_forbids_the_parent_directory_and_names_the_paved_road():
    agents = AGENTS.read_text(encoding="utf-8")

    assert "## Worktrees and branches" in agents
    assert "git worktree add ../" in agents, "the forbidden form is not named"
    assert "scripts/worktree.sh add" in agents
    assert "044-an-agent-worktree-lives-in-the-containing-folder.md" in agents
    assert "047-ownership-defers-collection-only-while-the-owner-lives.md" in agents


def test_agents_md_and_the_adr_agree_on_the_base_ref():
    """The documented rule and the implemented rule drift silently otherwise."""
    for document in (AGENTS, ADR):
        assert BASE_REF in document.read_text(encoding="utf-8"), document.name
