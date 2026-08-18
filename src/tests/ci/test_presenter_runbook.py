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

import provenance
from escalation.ticket import SIMULATED_NOTICE, TICKET_ID_PREFIX
from sop.provenance import SOP_SOURCE

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
RESUME_MODULE = REPO_ROOT / "src" / "App" / "src" / "models" / "resume.ts"
AGENT_AVAILABILITY = (
    REPO_ROOT / "src" / "App" / "src" / "models" / "agentAvailability.ts"
)
GROUNDING_PANEL = (
    REPO_ROOT
    / "src"
    / "App"
    / "src"
    / "components"
    / "transparency"
    / "GroundingPanel.tsx"
)
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


def _unwrapped(text: str) -> str:
    """Text with its line wrapping collapsed.

    A sentence is one sentence whether the file it lives in broke it across
    two lines or not, so a check about wording must not become a check about
    line width.
    """
    return re.sub(r"\s+", " ", text)


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


def test_the_runbook_quotes_the_grounding_route_the_panel_exports():
    """A presenter's route names every observed hop, not a parallel story.

    The surface owns the known Copilot Studio transport segments and the backend
    owns the source the hop lands in, so every word of the quoted route is read
    out of the repository rather than restated here. Dataverse stays supplied by
    `source_used` at run time, which is why the panel can still refuse to claim
    this route for a platform it did not observe.
    """
    names = (
        "ROUTE_ORIGIN",
        "SOP_TOOL_ROUTE_SEGMENT",
        "SOP_ASK_ROUTE_SEGMENT",
        "DIRECT_LINE_ROUTE_SEGMENT",
        "COPILOT_STUDIO_PLATFORM",
    )
    segments = [_exported_string(GROUNDING_PANEL, name) for name in names]
    segments.append(SOP_SOURCE)
    route = " → ".join(segments)

    assert route in _rendered(), (
        f"the runbook does not quote the Grounding panel's observed route: {route}"
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


def test_the_boundary_unlock_and_shift_swap_beats_name_the_same_associate():
    """The personal-record boundary and the workforce process are one contrast."""
    runbook = _rendered()

    for heading in (
        "### 5. How much PTO do I have? — the boundary",
        "### 6. Sign in to continue — the door in the wall",
        "### 8. Swap a shift — the fourth specialist",
    ):
        start = runbook.index(heading)
        following = runbook[start + len(heading) :]
        next_heading = re.search(r" ### \d+\.", following)
        beat = following[: next_heading.start()] if next_heading else following
        assert "Clara Workman" in beat


def test_every_follow_on_edge_is_quoted_in_the_presenter_runbook():
    """A Follow-on task is an authored transition the presenter has to rehearse.

    The general prompt test protects each Quick Task in isolation. This seam
    protects the graph transition: the runbook quotes the exact source-to-target
    edge the presenter is expected to tap.
    """
    tasks = {task["id"]: task for task in _quick_tasks()}
    edges = [
        (task["id"], target_id)
        for task in tasks.values()
        for target_id in task.get("follow_on", [])
    ]
    runbook = _rendered()

    assert edges, "the store pack authors no Follow-on edges to rehearse"
    unresolved = [target_id for _, target_id in edges if target_id not in tasks]
    assert not unresolved, f"Follow-on edges name unknown Quick Tasks: {unresolved}"
    missing = [
        f"`{tasks[source_id]['prompt']}` -> `{tasks[target_id]['prompt']}`"
        for source_id, target_id in edges
        if f"`{tasks[source_id]['prompt']}` -> `{tasks[target_id]['prompt']}`"
        not in runbook
    ]
    assert not missing, f"the runbook does not quote Follow-on edges: {missing}"


def test_the_shift_swap_beat_quotes_its_authored_people_and_order():
    """The Reviewable plan names its people in the pack, not in presenter prose."""
    task = next(
        task for task in _quick_tasks() if task["id"] == "task-223-shift-swap"
    )
    rendered = _rendered()
    beat = rendered[rendered.index(task["prompt"]) :][:1800]

    assert "Deliberate" in beat
    person_steps = [
        step
        for step in task["plan_steps"]
        if step["assignee"]["kind"] == "person"
    ]
    for step in person_steps:
        assert step["assignee"]["name"] in beat
    for step in person_steps:
        assert step["action"] in beat
    assert "waitsOn" in beat


def test_the_walkthrough_never_walks_a_decline():
    """A colleague can say no, and the demonstration never asks one to.

    ADR-042 decision 6: the decline path is expressible and specified, and
    deliberately not rehearsed. A named peer who might refuse on the customer
    run is unpresentable, and a beat whose outcome the presenter cannot predict
    is one this runbook cannot script — so every person the walked plan asks is
    authored to approve, and the beat offers no decline to attempt.
    """
    task = next(
        task for task in _quick_tasks() if task["id"] == "task-223-shift-swap"
    )
    asked = {
        step["assignee"]["name"]: step.get("outcome")
        for step in task["plan_steps"]
        if step["assignee"]["kind"] == "person"
        and step["assignee"].get("relation") != "associate"
    }

    assert asked, "the shift-swap plan asks nobody for a verdict"
    assert set(asked.values()) == {"approved"}, (
        f"the walkthrough authors a decline it cannot rehearse: {asked}"
    )

    rendered = _rendered()
    beat = rendered[rendered.index(task["prompt"]) :][:1800]
    assert "declin" not in beat.lower(), (
        "the runbook scripts a decline the walkthrough does not walk"
    )


def test_the_runbook_says_approval_completes_a_ticket_and_starts_a_swap():
    """The two workflows share an approval shape but have opposite next steps."""
    assert (
        "Approving the ticket completes it; approving this plan starts the swap"
        in _rendered()
    )


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


def test_the_ticket_beat_quotes_the_persisted_ticket_read_back():
    """Beat 4 proves persistence by rendering the submitted record again."""
    task = next(task for task in _quick_tasks() if task.get("ticket_on_approval") is True)
    prompt = task["ticket_status_reply"]["prompt"]
    runbook = _rendered()
    beat = runbook[runbook.index("### 4.") : runbook.index("### 5.")]

    assert prompt in beat, (
        "the ticket beat does not name the authored status inquiry that reads "
        "the ticket back"
    )
    assert TICKET_ID_PREFIX in beat, (
        "the ticket beat does not point out the record's ticket number"
    )
    assert SIMULATED_NOTICE in beat, (
        "the ticket beat does not quote the Simulated ticket's own notice"
    )


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


def test_the_mocked_unlock_describes_named_address_without_promising_model_prose():
    """The governance beat proves the manager learned a name, not a phrase.

    The browser may assert the deterministic handoff but never wording a model
    chose, so the runbook must say both halves without promising a greeting it
    cannot guarantee.
    """
    runbook = _rendered()
    unlock = runbook[runbook.index("Sign in to continue") : runbook.index("### 7.")]

    assert "before sign-in it cannot know your name; after it, the manager does" in unlock
    assert "Do not promise an exact greeting or browser-test its wording" in unlock


def test_every_provenance_line_is_in_the_simulation_register():
    """Every source-owned Provenance line has a presenter-owned register row.

    The source module is deliberately enumerated rather than sampled. Adding a
    record's line without documenting it here leaves the record honest in a
    screenshot but strands the presenter who must explain it conversationally.
    """
    runbook = _runbook()
    start = runbook.index("## Simulation register")
    register = runbook[start : runbook.find("\n## ", start + 1)]
    lines = {
        name: value
        for name, value in vars(provenance).items()
        if name.isupper() and isinstance(value, str)
    }

    assert lines, "provenance.py no longer exposes any Provenance line constants"
    missing = {name: value for name, value in lines.items() if value not in register}
    assert not missing, (
        "the Simulation register is missing Provenance line constants: "
        f"{missing}"
    )


def test_no_component_composes_a_provenance_line():
    """The Provenance line module owns the wording; the surface renders what
    the record already carried.

    A component that spells a line out is a second copy of a sentence the
    presenter reads verbatim off the register, and only one of the two moves
    when the register does. #137 removed the copies by hand; this keeps them
    gone, including for the records added since.
    """
    lines = {
        name: value
        for name, value in vars(provenance).items()
        if name.isupper() and isinstance(value, str)
    }
    surface = REPO_ROOT / "src" / "App" / "src"
    composed = {
        f"{path.relative_to(REPO_ROOT)}:{name}"
        for path in surface.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        for name, value in lines.items()
        if _unwrapped(value) in _unwrapped(path.read_text(encoding="utf-8"))
    }

    assert not composed, (
        "a Provenance line belongs to src/backend/provenance.py and reaches "
        f"the surface on the record, not composed in a component: {sorted(composed)}"
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


def test_the_runbook_states_the_availability_the_rail_actually_states():
    """The count on the rail before a question is typed (#79).

    The rail states how many specialists are **available** once the roster has
    resolved and before any question is sent — the count needs no request of its
    own — and the runbook tells the presenter to point at it while the home
    surface is still empty. Both halves are read out of the
    repository rather than written here: the sentence's shape from
    `availabilityHeading`, and the number from the store pack's own roster. A
    fifth agent added to the pack changes what the rail says, and a runbook
    carrying its own copy of the old number sends the presenter to point at a
    panel that disagrees with them.
    """
    heading = AGENT_AVAILABILITY.read_text(encoding="utf-8")
    match = re.search(
        r"return `\$\{count\} (specialist)\$\{count === 1 \? '' : 's'\} (available)`",
        heading,
    )
    assert match, "agentAvailability.ts no longer builds the heading this way"

    roster = len(json.loads(STORE_PACK.read_text(encoding="utf-8"))["agents"])
    stated = f"{roster} {match.group(1)}{'' if roster == 1 else 's'} {match.group(2)}"
    assert stated in _rendered(), (
        f"the runbook does not quote what the rail states before a question is "
        f"typed ({stated}), so the presenter opens the demonstration pointing at "
        "a number nobody checked"
    )


def test_the_runbook_does_not_turn_availability_into_participation():
    """**Available vs participating**, in the presenter's own words.

    The Agent Team panel says who *could* answer. The **Identity boundary gate**
    refuses the boundary probe above the **Lane router**, so on beat 5 the number
    that participate is zero and the meter renders a measured `0` two panels
    below the roster. A runbook that tells the presenter the panel shows "who
    answered" hands them a sentence the screen contradicts on the one beat the
    whole governance argument rests on.
    """
    row = next(
        line
        for line in _runbook().splitlines()
        if line.startswith("| **Agent Team**")
    )
    assert "available" in row.lower(), (
        "the runbook's Agent Team row does not say the panel states availability"
    )
    for forbidden in ("who answered", "who took", "identified", "assigned"):
        assert forbidden not in row.lower(), (
            f"the runbook's Agent Team row claims participation: {forbidden!r}"
        )
