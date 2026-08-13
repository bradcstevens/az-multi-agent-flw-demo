"""The stock content packs, suppressed at the deploy path (issue #25).

R1 is a **single-assistant** surface, and the spec puts suppressing the
accelerator's stock content packs inside it: an environment seeded with HR
Onboarding, RFP Evaluation and four more is an environment where one of them
can end up answering under the Circle K header.

The surface suppresses them structurally — ``selectStoreAssistant`` recognises
the store assistant rather than taking whatever the backend listed first — but
a pack that was never uploaded cannot be reached by anything at all, and it is
also six agent teams of Foundry agents that this demo pays for and never uses.

These tests **source the real script** and call its real predicate, rather than
reading the menu text and agreeing with themselves about what it means. The
predicate is the one place the six upload guards go through, so a guard that
stops using it turns one of these red.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
POST_DEPLOY_SH = REPO_ROOT / "infra" / "scripts" / "post-provision" / "post_deploy.sh"
POST_DEPLOY_PS1 = REPO_ROOT / "infra" / "scripts" / "post-provision" / "post_deploy.ps1"

#: Every stock pack, and the use-case number it is installed under.
STOCK_PACKS = {
    "RFP Evaluation": "1",
    "Retail Customer Satisfaction": "2",
    "HR Employee Onboarding": "3",
    "Marketing Press Release": "4",
    "Contract Compliance Review": "5",
    "Content Generation": "6",
}


def _run(script: str) -> subprocess.CompletedProcess:
    """Source post_deploy.sh as a library and run a fragment against it."""
    return subprocess.run(
        [
            "bash",
            "-c",
            f'MACAE_POST_DEPLOY_LIB_ONLY=1 source "{POST_DEPLOY_SH}"\n{script}',
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _selection_for(value: str) -> str:
    result = _run(
        f'MACAE_USE_CASE="{value}" select_use_case >/dev/null\n'
        'echo "$selected_use_case"'
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("use_case", sorted(set(STOCK_PACKS.values())))
def test_the_none_selection_installs_no_stock_pack(use_case: str):
    # Through `select_use_case`, not by assigning `selected_use_case` here:
    # the claim is that *the selection an operator makes* installs nothing, and
    # a `none` that quietly resolved to `7` would satisfy a test that set the
    # variable itself while seeding all six packs on the deployment.
    result = _run(
        'MACAE_USE_CASE="none" select_use_case >/dev/null\n'
        f"if installs_use_case {use_case}; then echo INSTALLS; else echo SKIPS; fi"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SKIPS"


def test_the_predicate_still_installs_the_pack_it_was_asked_for():
    # The suppression must not be a predicate that says no to everything — the
    # accelerator's own use cases have to keep working for anyone who wants
    # one, or this is a deletion wearing a flag's clothes.
    result = _run(
        'selected_use_case="3"\n'
        "if installs_use_case 3; then echo INSTALLS; else echo SKIPS; fi\n"
        "if installs_use_case 5; then echo INSTALLS; else echo SKIPS; fi"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["INSTALLS", "SKIPS"]


def test_all_still_means_all():
    result = _run(
        'selected_use_case="7"\n'
        "if installs_use_case 6; then echo INSTALLS; else echo SKIPS; fi"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "INSTALLS"


def test_the_selection_can_be_made_without_a_prompt():
    # `azd hooks run postdeploy` on the rehearsal machine must not stop on a
    # `read -rp` nobody is watching, and the walkthrough's own seeding is the
    # store assistant's pack alone.
    assert _selection_for("none") == "none"
    assert _selection_for("3") == "3"


def test_an_unreadable_override_is_refused_rather_than_guessed():
    # Falling back to a default here would silently seed six stock packs
    # because somebody typed `MACAE_USE_CASE=None`.
    result = _run('MACAE_USE_CASE="banana" select_use_case')
    assert result.returncode != 0
    assert "banana" in (result.stdout + result.stderr)


def test_the_six_upload_guards_all_go_through_the_predicate():
    # The predicate is only load-bearing while every guard uses it. A guard
    # that reverts to `[[ "$selected_use_case" == "3" ... ]]` would keep the
    # tests above green while uploading a stock pack anyway.
    source = POST_DEPLOY_SH.read_text(encoding="utf-8")
    assert source.count("if installs_use_case ") == len(STOCK_PACKS)
    # Once, in the predicate's own body, and nowhere else.
    assert source.count('"$selected_use_case" == "7"') == 1


def test_powershell_offers_the_same_escape():
    # The two entry points are separate files and a presenter on Windows gets
    # the PowerShell one. One platform seeding six stock packs while the other
    # seeds none is the same defect, discovered later.
    source = POST_DEPLOY_PS1.read_text(encoding="utf-8")
    assert "MACAE_USE_CASE" in source
    assert '"none"' in source


def test_the_two_entry_points_agree_about_the_shape_of_the_word():
    # PowerShell's `switch` is case-insensitive, so `MACAE_USE_CASE=None`
    # selects "none" on Windows. If bash rejected it, the same rehearsal
    # setting would seed nothing on one machine and abort on the other —
    # and the difference would be found on the machine that is on stage.
    for spelling in ("none", "None", "NONE"):
        assert _selection_for(spelling) == "none", spelling
    assert _selection_for("ALL") == "7"


def test_a_change_to_the_deploy_path_runs_these_tests():
    # This suite reads `post_deploy.sh`, and `test.yml` triggers on Python
    # paths — so the one change that can break it, an edit to the deploy
    # script, would not have run it. The trigger is asserted rather than
    # assumed, the same way #24 asserted the transparency contract's.
    text = (
        Path(__file__).resolve().parents[3] / ".github" / "workflows" / "test.yml"
    ).read_text(encoding="utf-8")

    for path in (
        "infra/scripts/post-provision/post_deploy.sh",
        "infra/scripts/post-provision/post_deploy.ps1",
    ):
        assert text.count(f"'{path}'") >= 2, (
            f"a change to {path} does not run the CI-tooling tests on both "
            "push and pull_request"
        )

    assert "'infra/**'" not in text, (
        "test.yml triggers on the whole of infra — a Bicep edit now runs the "
        "backend suite"
    )
