"""Invariants of the presenter runbook (issue #53).

The runbook is the artefact the handoff depends on: a presenter who does not know
agent orchestration drives the whole demonstration from a URL, alone, in front of
the customer. Two of its instructions cannot be discovered on screen — the
**Presenter chord** and the **Rehearsed reply** chips — so the runbook is the only
place they exist for the person in the room.

These are CI-tooling tests, not application tests. What they assert is the rule the
rest of this repository's checks run on (ADR-019, and `e2e/authored.ts` one layer
out): **the expectation is read out of the repository.** A runbook carrying its own
copy of the words on screen survives a rebrand it never saw, and the presenter finds
out in front of the customer that the card is called something else now.
"""

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = REPO_ROOT / "docs" / "presenter-runbook.md"

STORE_PACK = (
    REPO_ROOT
    / "content_packs"
    / "store_assistant"
    / "agent_teams"
    / "store_assistant.json"
)
CHORD_MODULE = REPO_ROOT / "src" / "App" / "src" / "models" / "presenterChord.ts"
SURFACE_MODULE = REPO_ROOT / "src" / "App" / "src" / "models" / "storeSurface.ts"
HOME_INPUT = REPO_ROOT / "src" / "App" / "src" / "components" / "content" / "HomeInput.tsx"
RESUME_MODULE = REPO_ROOT / "src" / "App" / "src" / "models" / "resume.ts"
SOP_CORPUS = REPO_ROOT / "content" / "sop" / "corpus.toml"


def _runbook() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def _rendered() -> str:
    """The runbook as the presenter reads it, not as it is wrapped on disk.

    Markdown reflows, so a quoted prompt broken across two source lines is one
    line on screen. Asserting against the source would make the check a rule
    about line width rather than about what the presenter is told.
    """
    return re.sub(r"\s+", " ", RUNBOOK.read_text(encoding="utf-8"))


def _quick_tasks() -> list:
    pack = json.loads(STORE_PACK.read_text(encoding="utf-8"))
    return pack["starting_tasks"]


def _exported_string(module: Path, name: str) -> str:
    """One `export const NAME = '…'` read out of a TypeScript module."""
    match = re.search(
        rf"export const {name} = '([^']*)'", module.read_text(encoding="utf-8")
    )
    assert match, f"{module.name} no longer exports {name}"
    return match.group(1)


def _corpus_section(name: str) -> str:
    """One `[section]` of the corpus manifest.

    Scoped to the section rather than the file, for `e2e/authored.ts`'s reason:
    `question` is a key under both `[rehearsed_hit]` and `[honest_miss]`, and a
    whole-file match answers the opening beat with the question the corpus
    deliberately cannot answer.
    """
    source = SOP_CORPUS.read_text(encoding="utf-8")
    start = source.index(f"[{name}]")
    rest = source[start + len(name) + 2 :]
    end = re.search(r"^\[", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def _corpus_value(section: str, key: str) -> str:
    match = re.search(rf'^{key}\s*=\s*"([^"]*)"', section, re.MULTILINE)
    assert match, f"no {key} in the corpus section read"
    return match.group(1)


def test_the_runbook_is_tracked_by_git():
    """A runbook only this checkout holds is a runbook the presenter does not have.

    Their access is the repository on github.com and the URL they were sent, so
    untracked here is missing there.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--", str(RUNBOOK.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.returncode == 0, f"could not read git's index: {listed.stderr.strip()}"
    assert listed.stdout.split(), (
        f"{RUNBOOK.relative_to(REPO_ROOT)} is not tracked by git — `git add` it"
    )


def test_the_chord_is_the_chord_the_browser_listens_for():
    """The one instruction with no affordance anywhere on screen.

    `presenterChord.ts` exports the label precisely so that the place it is
    written down for the presenter and the place it is matched cannot drift. A
    runbook naming a different key leaves the R8 beat unreachable, with nothing
    on screen to recover it from.
    """
    label = _exported_string(CHORD_MODULE, "PRESENTER_CHORD_LABEL")
    assert label in _rendered(), (
        f"the runbook does not name the chord the browser listens for ({label})"
    )


def test_the_seven_taps_are_the_authored_taps_in_running_order():
    """Six Quick Tasks and the door in the wall, in the order the pack renders them.

    The cards are authored in `content_packs/`; the runbook is prose. A tap named
    out of order is a presenter looking for a card that is not there yet, and a
    tap named wrongly is a presenter reading out a card the surface does not show.
    """
    runbook = _rendered()
    taps = [task["name"] for task in _quick_tasks()]

    missing = [name for name in taps if name not in runbook]
    assert not missing, f"the runbook names no such tap: {missing}"

    positions = [runbook.index(name) for name in taps]
    assert positions == sorted(positions), (
        "the runbook's taps are out of the order the store pack renders them: "
        f"{taps}"
    )

    # The seventh tap. It is not a Quick Task — it is rendered inside the
    # refusal (#27) — and it falls between the boundary probe that provokes it
    # and the shift-task query that closes the walkthrough.
    door = runbook.index("Sign in to continue")
    assert positions[4] < door < positions[5], (
        "the sign-in tap is not between the boundary probe and the shift-task "
        "query, which is the only place in the walkthrough it exists"
    )


def test_every_prompt_is_quoted_from_the_pack():
    """What the presenter says out loud is what the card is about to send.

    The prompts are the questions the audience watches being asked, and three of
    them are themselves read out of the corpus and the Guardrail corpus. A
    paraphrase in the runbook is a presenter narrating a question the surface
    did not ask.
    """
    runbook = _rendered()
    missing = [
        task["prompt"] for task in _quick_tasks() if task["prompt"] not in runbook
    ]
    assert not missing, f"the runbook misquotes the prompts: {missing}"


def test_every_rehearsed_reply_chip_is_quoted_from_the_pack():
    """The other affordance nothing on screen reveals until it is too late.

    The chips appear only while a Clarification is pending. A presenter who types
    their own answer instead submits words the matcher may record no **Attempted
    steps** from, and the **Simulated ticket** then comes up short — falsifying,
    on stage, the strongest claim the demonstration makes.
    """
    runbook = _rendered()
    chips = [
        reply
        for task in _quick_tasks()
        for reply in task.get("rehearsed_replies", [])
    ]
    assert chips, "the store pack authors no rehearsed replies to document"

    missing = [reply for reply in chips if reply not in runbook]
    assert not missing, f"the runbook misquotes the rehearsed replies: {missing}"


def test_the_opening_beat_names_the_document_the_corpus_says_answers_it():
    """The centrepiece, and the one beat that decays silently.

    `[rehearsed_hit]` names the question *and* the `SOP-NNN` that answers it. A
    presenter who knows which document should be cited can tell the cross-platform
    hop from the honest miss wearing its clothes — which is exactly the failure
    #54 records happening one run in four.
    """
    hit = _corpus_section("rehearsed_hit")
    runbook = _rendered()

    assert _corpus_value(hit, "question") in runbook
    assert _corpus_value(hit, "doc_id") in runbook, (
        "the runbook does not say which document the opening answer must cite, "
        "so the presenter cannot tell the hop from a retrieval miss"
    )


def test_the_honest_miss_is_framed_as_deliberate():
    """The beat most easily mistaken on stage for a failure.

    Its question is rehearsed and the corpus keeps every term of it out, so the
    miss is authored. A presenter who reads it as a failure apologises for the
    demonstration's second-strongest claim.
    """
    miss = _corpus_section("honest_miss")
    runbook = _rendered()

    assert _corpus_value(miss, "question") in runbook
    assert re.search(
        r"deliberate", runbook[runbook.index(_corpus_value(miss, "question")) :][:1500],
        re.IGNORECASE,
    ), "the honest miss is not framed as deliberate where the presenter reads it"


def test_the_surface_names_itself_in_the_runbook_s_own_words():
    """Read from `storeSurface.ts`, which is where the surface reads them from.

    ADR-019's lesson: a runbook carrying its own copy of the header passes a
    rebrand it never saw, and the presenter opens a URL that calls itself
    something else.
    """
    runbook = _rendered()
    for name in ("ASSISTANT_NAME", "STORE_LABEL", "ANONYMOUS_IDENTITY_LABEL"):
        claim = _exported_string(SURFACE_MODULE, name)
        assert claim in runbook, f"the runbook does not quote the surface's {name}: {claim}"


def test_the_anonymous_opening_is_explained_rather_than_merely_stated():
    """The setup for the closing beat, and the licensing argument itself.

    *No user signed in* is the "before" of a before-and-after. A presenter who
    does not know why the demonstration opens anonymous cannot answer the
    question the header is there to provoke, and the sign-in beat lands as a
    feature rather than as the governance conversation.
    """
    runbook = _rendered()
    anonymous = _exported_string(SURFACE_MODULE, "ANONYMOUS_IDENTITY_LABEL")
    around = runbook[runbook.index(anonymous) - 1500 : runbook.index(anonymous) + 1500]
    assert re.search(r"shared", around, re.IGNORECASE), (
        "the runbook states the anonymous opening without the shared-device "
        "reason, which is the licensing argument it exists to set up"
    )


def test_the_simulated_sign_in_is_said_out_loud():
    """What the button says beside itself, said in the runbook too.

    A stakeholder who discovers afterwards that an identity provider was implied
    has stopped believing the rest of the demonstration, so the presenter must
    say it before they are asked.
    """
    note = re.search(
        r"(Simulated sign-in — no identity provider is involved\.)",
        HOME_INPUT.read_text(encoding="utf-8"),
    )
    assert note, "HomeInput no longer says the sign-in is simulated"
    assert note.group(1) in _rendered(), (
        "the runbook does not say out loud that the sign-in is mocked end to end"
    )


def test_every_beat_has_a_failure_playbook_row():
    """Every tap, and for each one: what it looks like, continue or not, what to say.

    A presenter alone in the room cannot diagnose. The only useful form of this
    is a decision already made for them, beat by beat.

    The taps are the Quick Tasks **plus the door in the wall** — the sign-in
    affordance is rendered inside the refusal rather than on a card, and it is
    a beat the presenter drives like any other. Counted rather than written
    down, so a card added to the pack without a row here is red.
    """
    runbook = _runbook()
    playbook = runbook[runbook.index("## If a beat fails") :]

    for index in range(1, len(_quick_tasks()) + 2):
        assert re.search(rf"^\| {index} \|", playbook, re.MULTILINE), (
            f"beat {index} has no row in the failure playbook"
        )
    assert re.search(r"^\|[^|]*\|[^|]*chord", playbook, re.MULTILINE | re.IGNORECASE), (
        "the shift-task alert — the beat with no affordance on screen — has no "
        "row in the failure playbook"
    )


def test_the_fallback_ladder_is_stated_in_order():
    """Deployed surface, then local, then the recording.

    Three rungs, and the order is the whole of the advice: each is a weaker
    claim than the one above it, and a presenter who drops to the recording
    first has given up the demonstration's only live evidence.
    """
    runbook = _rendered()
    ladder = runbook[runbook.index("## If the surface is down") :]
    rungs = [ladder.index(rung) for rung in ("deployed", "local", "recording")]
    assert rungs == sorted(rungs), (
        "the fallback ladder is out of order — the rungs run deployed surface, "
        "then local, then the recording"
    )


def test_the_invented_content_question_is_answered_in_the_presenter_s_words():
    """*Are these our procedures?* — asked in the room, every time.

    The corpus is invented and its README says so. An unprepared answer to this
    question is where a demonstration loses the audience it had convinced.
    """
    runbook = _rendered()
    asked = re.search(r"are these our procedures\?", runbook, re.IGNORECASE)
    assert asked, "the runbook does not put the invented-content question head-on"
    assert re.search(r"invented", runbook[asked.end() : asked.end() + 1200], re.IGNORECASE), (
        "the invented-content question is asked but not answered where the "
        "presenter reads it"
    )


def test_the_improvised_paraphrases_are_ones_the_corpus_measured():
    """The moment the demonstration answers *"you just hardcoded that"*.

    `IMPROVISED_PARAPHRASES` is the held-out set the **Guardrail corpus** scores
    the similarity tier against — phrasings the gate is *measured* to catch, kept
    out of the anchors on purpose (ADR-015). A runbook that invented its own
    examples would be sending the presenter to improvise with words nobody has
    ever run through the gate, in the one beat that has no fallback.

    Read in that direction: **every phrasing the runbook offers** must be one of
    the measured ones. The other direction — that some measured phrase appears
    somewhere in the document — is satisfied by a runbook whose beat 5 is
    entirely invented.
    """
    corpus = (REPO_ROOT / "src" / "backend" / "guardrail" / "corpus.py").read_text(
        encoding="utf-8"
    )
    block = corpus[corpus.index("IMPROVISED_PARAPHRASES") :]
    measured = set(re.findall(r'"([^"]+\?)"', block[: block.index(")")]))
    assert measured, "the guardrail corpus no longer holds improvised paraphrases"

    runbook = _rendered()
    start = runbook.index("**Then improvise.**")
    offered = re.findall(r'\*"([^"]+\?)"\*', runbook[start : start + 400])
    assert offered, (
        "beat 5 offers the presenter no paraphrase to improvise with — the "
        "answer to \"you just hardcoded that\" is the one thing this beat "
        "cannot be read off the cards"
    )

    invented = [phrase for phrase in offered if phrase not in measured]
    assert not invented, (
        f"the runbook sends the presenter to improvise with {invented}, which "
        "the guardrail corpus has never measured the gate against"
    )


def test_the_runbook_says_where_the_chord_works():
    """`usePresenterChord` is mounted on the chat page and nowhere else.

    So the chord is not merely hidden — on the home surface, where the six cards
    are and where the refusal and the personal answer render, there is no
    listener bound at all and the key does nothing. A presenter told only *press
    it whenever you like* fires it on the home screen, sees nothing, and reads a
    working demonstration as broken in the one beat that has no affordance to
    fall back on.

    If the hook is ever mounted globally this goes red, which is the point: the
    warning must go when the constraint does.
    """
    pages = REPO_ROOT / "src" / "App" / "src" / "pages"
    mounting = sorted(
        page.name
        for page in pages.glob("*.tsx")
        if "usePresenterChord()" in page.read_text(encoding="utf-8")
    )
    assert mounting == ["ChatPage.tsx"], (
        f"the chord is now mounted by {mounting}; the runbook's warning about "
        "where it works needs to change with it"
    )

    runbook = _rendered()
    label = _exported_string(CHORD_MODULE, "PRESENTER_CHORD_LABEL")
    assert re.search(r"while a chat is open", runbook[runbook.index(label) :][:900]), (
        "the runbook does not say that the chord only works while a chat "
        "is open, which is the difference between the beat landing and the key "
        "doing nothing at all"
    )


def test_resume_is_offered_in_the_words_the_box_itself_uses():
    """The recovery step, quoted from the module that renders it (#77, ADR-027).

    A presenter who taps **New chat** by mistake, or walks away and comes back,
    used to have no route back into the conversation at all: the box answered a
    **Clarification** and nothing else, and the escalation card was the only
    authored continuation. Reopening the chat and typing now continues *that*
    **Session**.

    The runbook quotes the placeholder rather than describing it, on ADR-019's
    rule: what the presenter is told to look for has to be what the surface
    actually says, or a reworded placeholder leaves them hunting for a box that
    is right in front of them.
    """
    invitation = _exported_string(RESUME_MODULE, "CONTINUE_THIS_CHAT")
    assert invitation in _rendered(), (
        "the runbook does not quote what the chat box invites when nothing is "
        f"waiting on a reply ({invitation}), so the presenter has no way to "
        "recognise the resume step on screen"
    )


def test_resume_does_not_promise_a_memory_it_has_not_got():
    """ADR-027's negative consequence, said where the presenter reads it.

    Resume carries what was **persisted** against the session — the attempted
    steps, the identity, the lane, the ticket. The transcript on screen is
    display-only and is never replayed into an agent's context, because the
    **Workflow cache** is process-local and keyed by user. A presenter who
    tells the room the assistant "remembers the whole conversation" has made a
    claim the next question can falsify in front of the customer, which is the
    failure mode every *Simulated* badge in this demonstration exists to avoid.
    """
    runbook = _rendered()
    invitation = _exported_string(RESUME_MODULE, "CONTINUE_THIS_CHAT")
    around = runbook[runbook.index(invitation) - 1200 : runbook.index(invitation) + 1200]
    assert re.search(r"transcript", around, re.IGNORECASE), (
        "the runbook offers resume without saying what it does not carry — "
        "the transcript on screen is not the assistant's memory, and a "
        "presenter told otherwise makes a claim the next turn can falsify"
    )
