#!/usr/bin/env python3
"""The Copilot Studio SOP agent: author it, publish it, prove it over Direct Line.

The agent is the build's entire cross-platform proof (#17) — a low-code agent,
owned by business users, grounded on the SOP corpus uploaded as Dataverse
documents, reachable anonymously from outside Copilot Studio.

It is authored through the **Dataverse Web API** rather than the portal or the
Power Platform CLI: `pac` cannot authenticate unattended, while every preflight
check in this repo already drives Dataverse with an `az` token. A Copilot Studio
agent is a `bot` row plus `botcomponent` rows, and publishing, the Direct Line
endpoint and the publish status are all bound actions on that row.

`evaluate` is pure: it takes the bot row, its components and the transcript of a
live Direct Line conversation, and returns a `Verdict`. The live calls are below
the line, in `main`.
"""

import json
import re

# Duplicated from the preflight checks rather than imported: this module is
# executed directly by its shell entry point, where the `preflight` package is
# not importable. `test_sop_agent.py` asserts the three never drift — if they
# did, the agent would be authored in an environment where the preflight checks
# refuse to grant a role or enable search.
DEFAULT_ENVIRONMENT_ID = "Default-0f87abfb-0840-4199-96b7-1882c01a998b"

# The unmanaged solution that holds a Default environment's customisations. A
# Default environment cannot be backed up, restored or deleted, so its export is
# the only copy of this agent that exists outside the tenant.
DEFAULT_SOLUTION = "Cr688e5"

# The schema prefix belongs to that solution's publisher. A component whose
# prefix does not match it cannot be created in the solution, so the agent's
# schema name and the solution are one decision, not two.
AGENT_SCHEMA_NAME = "cr48b_StoreSopAssistant"
AGENT_NAME = "Store SOP Assistant"

# `bot.authenticationmode`: 1 is "None". The demo front end is a shared store
# device with no individual sign-in, and Copilot Studio will not serve
# authenticated knowledge into an unidentified session (ADR-012), so anything
# other than None makes the agent answer nothing at all over Direct Line.
NO_AUTHENTICATION = 1

# `bot.accesscontrolpolicy`: 0 is "Any".
ACCESS_CONTROL_ANY = 0

# The default agent template the portal itself stamps onto a new agent.
BOT_TEMPLATE = "default-2.1.0"

FILE_ATTACHMENT = 14
CUSTOM_GPT = 15
TOPIC = 9

LANGUAGE_EN_US = 1033


class Component:
    """One `botcomponent` row, in the shape the Web API takes it."""

    def __init__(self, schemaname, name, componenttype, data=None,
                 description=None, filename=None):
        self.schemaname = schemaname
        self.name = name
        self.componenttype = componenttype
        self.data = data
        self.description = description
        self.filename = filename

    def record(self, bot_id):
        """Return the POST body for this component under `bot_id`."""
        body = {
            "name": self.name,
            "schemaname": self.schemaname,
            "componenttype": self.componenttype,
            "parentbotid@odata.bind": f"/bots({bot_id})",
        }
        if self.data is not None:
            body["data"] = self.data
        if self.description is not None:
            body["description"] = self.description
        if self.filename is not None:
            body["filedata_name"] = self.filename
        return body

    def __repr__(self):  # pragma: no cover - diagnostics only
        return f"Component({self.schemaname!r})"


def upload_reason(row, filename, local_bytes, remote_bytes):
    """Why `filename` has to be uploaded to `row`, or None if it is already there.

    Decided on the document's **content**, not on its name. The filename is the
    citation the associate reads, so a document is rewritten far more often than
    it is renamed — the Circle K rebrand (ADR-019) rewrote all ten and renamed
    none. A provision that skips a file whose `filedata_name` already matches
    therefore reports the whole corpus present, uploads nothing, and leaves the
    agent answering out of the previous corpus with nothing red anywhere.

    `remote_bytes` is None when nothing is attached or the attachment could not
    be read back, and both mean upload: unknown is not current.
    """
    if row is None:
        return "the component does not exist yet"
    attached = (row or {}).get("filedata_name")
    if attached != filename:
        return (f"the attached file is {attached!r}" if attached
                else "no file is attached")
    if remote_bytes is None:
        return "the attached file could not be read back"
    if remote_bytes != local_bytes:
        return "the attached file's content is not the built document"
    return None


def document_key(filename):
    """Return the stable component key for a corpus filename.

    Derived from the document identifier ("SOP-102 Store Closing.docx" →
    "sop102") rather than from the whole filename, so the component name is
    stable if a document is retitled and so re-running the provision is
    idempotent instead of uploading a second copy beside the first.
    """
    return filename.split()[0].replace("-", "").lower()


def file_components(filenames):
    """Return the file-attachment components for the SOP corpus.

    An uploaded document is exactly one `botcomponent` of type 14 carrying the
    file's bytes — there is no separate knowledge-source row for individually
    uploaded files. The component's `name` is the filename, and the filename is
    what comes back as the citation the associate reads, so the corpus is built
    to be quotable by filename alone.
    """
    return [
        Component(
            schemaname=f"{AGENT_SCHEMA_NAME}.file.{document_key(filename)}",
            name=filename,
            componenttype=FILE_ATTACHMENT,
            description=(
                "This knowledge source searches information contained in "
                f"{filename}"
            ),
            filename=filename,
        )
        for filename in filenames
    ]


# A step ordinal is a number at the start of a line followed by ". ". Anything
# looser matches "$1.50" and "1 hour", and a false positive here would let a
# paragraph answer satisfy the criterion the agent's instructions exist to
# enforce.
STEP = re.compile(r"^\s*(\d+)\.\s+\S", re.MULTILINE)

# Copilot Studio returns citations in the activity's entities collection, under
# the schema.org Message type. The markdown reference-style form in the text is
# a parallel representation, not the source of truth (ADR-011).
CITATION_ENTITY = "https://schema.org/Message"


def numbered_steps(text):
    """Return the step ordinals a reply is written as, in order."""
    return [int(match.group(1)) for match in STEP.finditer(text or "")]


def cited_documents(activity):
    """Return the names of the documents an activity cites, in position order.

    Read out of the entities collection: `appearance.name` is the uploaded
    file's name, which is the citation the associate sees. There is no citation
    URL for a document uploaded to Dataverse, and there is no need for one.
    """
    citations = []
    for entity in (activity or {}).get("entities") or []:
        if entity.get("type") != CITATION_ENTITY:
            continue
        for citation in entity.get("citation") or []:
            appearance = citation.get("appearance") or {}
            citations.append((citation.get("position", 0),
                              appearance.get("name")))
    return [name for _, name in sorted(citations) if name]


class Check:
    """One named fact about the agent, and why it does or does not hold."""

    def __init__(self, name, ok, detail):
        self.name = name
        self.ok = ok
        self.detail = detail


class Verdict:
    """The checks together. Fails if any one of them fails."""

    def __init__(self, checks):
        self.checks = checks

    @property
    def ok(self):
        return all(check.ok for check in self.checks)

    def check(self, name):
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)


def evaluate(bot, components, probe, corpus, banner=None):
    """Return the `Verdict` for the SOP agent. Pure."""
    return Verdict([
        _exists_check(bot),
        _authentication_check(bot),
        _corpus_check(components, corpus),
        _authored_check(components, corpus),
        _published_check(bot),
        _greeting_check(probe),
        _procedure_check(probe, corpus),
        _repeats_check(probe, corpus),
        _honest_miss_check(probe),
        _branding_check(probe, banner),
    ])


def _exists_check(bot):
    if not bot:
        return Check(
            "agent-exists",
            False,
            f"an agent named {AGENT_SCHEMA_NAME} does not exist in this "
            "environment",
        )
    return Check(
        "agent-exists",
        True,
        f"{bot.get('name')} ({bot.get('schemaname')}) exists",
    )


def publish_state(bot):
    """Return the bot's synchronisation record, decoded. Pure.

    Dataverse carries it as a JSON string in a column, so every reader would
    otherwise decode it — including the ones that would rather not think about
    a row that has never been published.
    """
    raw = (bot or {}).get("synchronizationstatus")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def _authentication_check(bot):
    """Whether the agent serves an anonymous session.

    Two facts, and the second is the one that matters: the row's mode is what a
    future publish would go out with, while `lastPublishedDetails` is what the
    publish currently answering Direct Line went out with. An agent edited to
    None but published as Integrated still refuses every anonymous question.
    """
    if not bot:
        return Check("no-authentication", False,
                     "there is no agent to read an authentication mode from")
    mode = bot.get("authenticationmode")
    published = ((publish_state(bot).get("lastPublishedDetails") or {})
                 .get("authenticationMode"))
    if mode != NO_AUTHENTICATION:
        return Check(
            "no-authentication", False,
            f"authenticationmode is {mode!r}, not {NO_AUTHENTICATION} (None) — "
            "the agent will not retrieve knowledge for an anonymous session",
        )
    if published is None:
        return Check(
            "no-authentication", False,
            "the agent has never been published, so no authentication mode is "
            "serving Direct Line yet",
        )
    if published != "None":
        return Check(
            "no-authentication", False,
            f"the last publish went out as {published!r} — the row says None, "
            "but the published agent is what answers",
        )
    return Check("no-authentication", True,
                 "the agent is published with no authentication")


def _corpus_check(components, corpus):
    """Whether every document in the SOP corpus is uploaded to the agent."""
    uploaded = {
        component.get("name")
        for component in components or []
        if component.get("componenttype") == FILE_ATTACHMENT
    }
    missing = [name for name in corpus if name not in uploaded]
    if missing:
        return Check(
            "corpus-uploaded", False,
            f"{len(missing)} of {len(corpus)} SOP documents are not uploaded: "
            + ", ".join(missing),
        )
    return Check(
        "corpus-uploaded", True,
        f"all {len(corpus)} SOP documents are uploaded as Dataverse files",
    )


def _published_check(bot):
    """Whether a successful publish is what Direct Line is serving.

    Uploading a document changes the authoring copy. Direct Line serves the
    published one, and the two are different facts — an agent can hold the whole
    corpus and answer nothing.
    """
    if not (bot or {}).get("publishedon"):
        return Check("published-to-direct-line", False,
                     "the agent has never been published, so Direct Line has "
                     "no content to serve")
    operation = publish_state(bot).get("lastFinishedPublishOperation") or {}
    status = operation.get("status")
    if status != "Succeeded":
        return Check(
            "published-to-direct-line", False,
            f"the last publish finished as {status!r} — Direct Line is still "
            "serving whatever was published before it",
        )
    return Check(
        "published-to-direct-line", True,
        f"published successfully on {bot['publishedon']}",
    )


# The document check's "no evidence" detail, matched by the remedy so the two
# cannot drift into contradicting each other. Borrowed deliberately from the
# Dataverse search preflight: "nothing was asked" and "the answer was wrong"
# are different failures with different remedies, and conflating them sends an
# operator to fix an agent that was never questioned.
NOT_PROBED = "not probed"

# The wording an out-of-corpus question is refused with. It is spoken by the
# Fallback topic and repeated in the agent's instructions, and the verdict looks
# for it, so the beat cannot drift from the check that proves it.
#
# What issue #54 spent six deploys chasing through the orchestrator turned out
# to end here. Measured 2026-08-14 over 69 fresh Direct Line conversations
# asking the **rehearsed** question, with no orchestrator in front of them:
# three came back as this sentence alone, uncited, and one came back as the
# cited closing procedure with this sentence 30 ms behind it. The Fallback topic
# spoke it on turns the generative planner had not answered — without anything
# having searched the corpus, because the topic's only action was to say it.
#
# So the sentence is not the problem and it has not changed. Where it is spoken
# from has: `fallback_topic` now searches the corpus first and reaches this only
# if the search found nothing, which is what the sentence has always claimed.
HONEST_MISS = (
    "That procedure is not in the store's SOP library, so I can't give you the "
    "steps. Ask your shift lead, and let them know the procedure is missing so "
    "it can be added."
)

# The phrase the honest miss is recognised by. Shorter than the whole sentence
# so the beat can be reworded without silently turning the check off, but
# specific enough that a generative answer cannot stumble into it.
HONEST_MISS_PHRASE = "not in the store's SOP library"

# The greeting the Conversation Start topic answers an explicit
# conversation-start event with.
GREETING = "Hello, I'm {System.Bot.Name}. How can I help?"

# Fewer ordinals than this is a sentence that happens to start with "1.", not a
# procedure. Every SOP in the corpus has at least three steps.
MINIMUM_STEPS = 2


class Probe:
    """What a live Direct Line conversation answered, by beat.

    Four beats, because they are four different claims: the agent greets an
    explicit conversation-start event, answers a procedure question in numbered
    steps from a named source, refuses an out-of-corpus question plainly, and
    reads back a line of the document's own branding.

    `repeats` is the procedure question asked again, each in its own fresh
    conversation. One sample answers *can it*; the fault this check exists to
    catch since #54 answers *does it every time*, and at 6% that is invisible
    below about thirty.
    """

    def __init__(self, greeting=(), procedure=(), miss=(), branding=(),
                 repeats=()):
        self.greeting = list(greeting)
        self.procedure = list(procedure)
        self.miss = list(miss)
        self.branding = list(branding)
        self.repeats = [list(turn) for turn in repeats]

    @property
    def procedure_turns(self):
        """Every conversation the procedure question was asked in."""
        return [self.procedure] + self.repeats


# How many consecutive polls must add nothing before a beat counts as over.
# The same rule the Direct Line client in the backend drains by, for the same
# reason: an agent answers in however many activities it chose to send, and a
# poll landing between two of them is quiet without the turn being finished.
PROBE_SETTLE_POLLS = 2


def settled(replies, quiet_polls, settle_polls=PROBE_SETTLE_POLLS):
    """Whether a beat has finished arriving. Pure.

    Stopping at the *first* activity is what this replaced, and it made the
    probe blind to the fault it exists to catch: the turn that answers the
    rehearsed question correctly and then says the procedure is not in the
    library. One reply is the beginning of a turn, not the end of it.
    """
    return bool(replies) and quiet_polls >= settle_polls


def _spoken(activities):
    """Return the text of the message activities in a beat, joined."""
    return "\n".join(
        activity.get("text") or ""
        for activity in activities or []
        if activity.get("type") == "message" and (activity.get("text") or "")
    )


def _greeting_check(probe):
    if probe is None:
        return Check("greeting-on-conversation-start", False,
                     f"{NOT_PROBED}: no conversation was started")
    text = _spoken(probe.greeting)
    if not text.strip():
        return Check(
            "greeting-on-conversation-start", False,
            "the agent said nothing in response to a conversation-start event",
        )
    return Check("greeting-on-conversation-start", True,
                 f"the agent greets a new conversation: {text.strip()!r}")


def procedure_fault(turn, corpus):
    """Why one asking of the procedure question is not an answer from the corpus.

    `None` when it is one. This is the single grading rule, and both checks that
    read a procedure answer are held to it — `numbered-steps-with-source`, which
    grades the first asking, and `procedure-answers-every-time`, which grades all
    of them. Sharing it is the point: a repeat graded on a laxer bar than the
    first asking is a green row that means less than the row above it.

    The order of the two honest-miss branches carries the distinction #54 was
    about. The miss *beside* steps is a contradiction on screen — two things
    spoke. The miss *alone* is the failure the issue is named after.
    """
    text = _spoken(turn)
    steps = numbered_steps(text)
    documents = [name for activity in turn for name in cited_documents(activity)]
    if HONEST_MISS_PHRASE in text and steps:
        return (f"the answer says {HONEST_MISS_PHRASE!r} beside its steps — the "
                "honest miss arrived with the answer, and the presenter is left "
                "reading a contradiction")
    if HONEST_MISS_PHRASE in text:
        return ("a procedure the corpus holds came back as the honest miss: "
                f"{HONEST_MISS_PHRASE!r}")
    if len(steps) < MINIMUM_STEPS or steps[:1] != [1]:
        return (f"the answer is not numbered steps (found {steps or 'none'}) — "
                "an associate reads this one-handed, mid-shift")
    if not documents:
        return ("the answer cites no source document, so it is "
                "indistinguishable from an invention")
    unknown = [name for name in documents if name not in corpus]
    if unknown:
        return ("the answer cites a document that is not in the SOP corpus: "
                + ", ".join(unknown))
    return None


def _procedure_check(probe, corpus):
    """Whether a procedure question came back as numbered steps from a source.

    Both halves are load-bearing. The steps are what an associate can follow
    one-handed mid-shift; the citation is what proves the answer came out of
    Copilot Studio's Dataverse knowledge rather than out of the model.
    """
    if probe is None:
        return Check("numbered-steps-with-source", False,
                     f"{NOT_PROBED}: no procedure question was asked")
    fault = procedure_fault(probe.procedure, corpus)
    if fault:
        return Check("numbered-steps-with-source", False, fault)
    steps = numbered_steps(_spoken(probe.procedure))
    documents = [name for activity in probe.procedure
                 for name in cited_documents(activity)]
    return Check(
        "numbered-steps-with-source", True,
        f"{len(steps)} numbered steps, cited to " + ", ".join(documents),
    )


def _honest_miss_check(probe):
    """Whether the out-of-corpus question is refused rather than answered.

    Refusing is the demo beat; inventing loses the grounding claim entirely. So
    a reply that carries steps fails even if it also says the words.
    """
    if probe is None:
        return Check("honest-miss", False,
                     f"{NOT_PROBED}: the out-of-corpus question was not asked")
    text = _spoken(probe.miss)
    if numbered_steps(text):
        return Check(
            "honest-miss", False,
            "the agent answered the out-of-corpus question with steps — that "
            "is an invention, not a miss",
        )
    if HONEST_MISS_PHRASE not in text:
        return Check(
            "honest-miss", False,
            "the agent did not say the procedure is missing from the library; "
            f"it said {text.strip()[:120]!r}",
        )
    return Check("honest-miss", True,
                 "the out-of-corpus question is refused plainly")


def _repeats_check(probe, corpus):
    """Whether *every* asking of the procedure question answered from the corpus.

    `numbered-steps-with-source` grades one conversation, which answers "can
    it" and was the whole of this check's evidence until #54. The fault that
    issue turned out to be was intermittent at about 6%: ten samples come up
    clean about half the time, and one sample nineteen times in twenty, so a
    green row said nothing about the beat the presenter was about to stand in
    front of. This is the same grading — `procedure_fault`, the rule above —
    over as many fresh conversations as `--samples` asked for.

    A run in which *nothing* answered is reported as broken rather than
    intermittent. They want different next moves: intermittent is a rate to
    measure, broken is a state to fix, and the words are how the operator knows
    which one they are looking at.
    """
    if probe is None:
        return Check("procedure-answers-every-time", False,
                     f"{NOT_PROBED}: no procedure question was asked")
    turns = probe.procedure_turns
    faults = [procedure_fault(turn, corpus) for turn in turns]
    clean = [fault for fault in faults if fault is None]
    # Every *distinct* fault, not the first one. The first is usually the one
    # `numbered-steps-with-source` already reported, and printing it again here
    # is how a repeat that failed differently goes unread.
    spoken = "; ".join(dict.fromkeys(fault for fault in faults if fault))
    if turns and not clean:
        return Check(
            "procedure-answers-every-time", False,
            f"no asking of the procedure question answered from the corpus "
            f"({len(turns)} asked) — the rehearsed hit is broken rather than "
            f"intermittent: {spoken}",
        )
    if len(clean) < len(turns):
        return Check(
            "procedure-answers-every-time", False,
            f"only {len(clean)} of {len(turns)} askings of the procedure "
            "question answered from the corpus — the rehearsed hit is "
            f"intermittent, which is exactly what the walkthrough cannot be: "
            f"{spoken}",
        )
    if len(turns) == 1:
        return Check(
            "procedure-answers-every-time", True,
            "1 of 1 asking answered from the corpus — one sample, so this says "
            "the beat can work and not that it always does; --samples N asks "
            "N times in N fresh conversations",
        )
    return Check(
        "procedure-answers-every-time", True,
        f"{len(turns)} of {len(turns)} askings answered from the corpus, each "
        "in a fresh conversation",
    )


def _branding_check(probe, banner):
    """Whether the document that comes back out of the index is the built one.

    The corpus check reads filenames, and the rebrand (ADR-019) rewrote every
    document's body while renaming none of them — the filename is the citation
    the associate reads. So a stale index passes every other check in this
    verdict: ten documents present, published, answering in numbered steps, out
    of content weeks old. The banner is the one line of the document that a live
    conversation can read back, and the citation beside it is what separates
    reading it from knowing it: the model can name the customer's chain without
    opening a file, so an uncited answer is no evidence at all.
    """
    if banner is None:
        return Check("corpus-content-current", False,
                     f"{NOT_PROBED}: the corpus banner could not be read from "
                     "content/sop/corpus.toml, so there is nothing to compare "
                     "the answer against")
    if probe is None:
        return Check("corpus-content-current", False,
                     f"{NOT_PROBED}: the document's own branding was not asked "
                     "for")
    text = _spoken(probe.branding)
    documents = [name for activity in probe.branding
                 for name in cited_documents(activity)]
    if not documents:
        return Check(
            "corpus-content-current", False,
            "the answer cites no source document, so naming the banner proves "
            "the model knows the customer, not that the index holds the "
            "rebuilt corpus",
        )
    if banner.lower() not in text.lower():
        return Check(
            "corpus-content-current", False,
            f"the answer never says {banner!r} — the published index is "
            f"serving content this repository did not build; it said "
            f"{text.strip()[:160]!r}",
        )
    return Check(
        "corpus-content-current", True,
        f"the live answer reads {banner!r} back out of " + ", ".join(documents),
    )


INSTRUCTIONS = f"""You are the Store SOP Assistant for Circle K \
Store 223. You answer questions about store standard operating procedures using \
only the SOP documents in your knowledge.

Answer every procedure question as numbered steps - "1.", "2.", "3." - one \
action per step, in the order the procedure gives them. Never answer a \
procedure question as prose or as a paragraph.

Always name the source document the steps came from, using its document title, \
for example "SOP-102 Store Closing Procedure".

If, and only if, the procedure is not in the SOP library, reply with exactly \
this sentence and nothing else:

{HONEST_MISS}

Never invent steps, never guess, and never answer from general knowledge. Never \
say that sentence about a procedure you did find: if you are giving steps, you \
found it, so do not also say it is missing.

Keep answers short enough to read on a phone in the middle of a shift."""


def bot_record():
    """Return the POST body that creates the agent's `bot` row."""
    return {
        "name": AGENT_NAME,
        "schemaname": AGENT_SCHEMA_NAME,
        "language": LANGUAGE_EN_US,
        "authenticationmode": NO_AUTHENTICATION,
        "accesscontrolpolicy": ACCESS_CONTROL_ANY,
        "template": BOT_TEMPLATE,
    }


def bot_configuration():
    """Return the agent's `configuration`, as a mapping.

    `useModelKnowledge` is the decision in here. Left on, the model answers the
    question the corpus deliberately does not cover, and the honest miss — the
    beat the whole grounding claim rests on — becomes an invention nobody can
    tell apart from a real answer.
    """
    return {
        "$kind": "BotConfiguration",
        "settings": {"GenerativeActionsEnabled": True},
        "isAgentConnectable": True,
        "gPTSettings": {
            "$kind": "GPTSettings",
            "defaultSchemaName": f"{AGENT_SCHEMA_NAME}.gpt.default",
        },
        "aISettings": {
            "$kind": "AISettings",
            "useModelKnowledge": False,
            "isFileAnalysisEnabled": True,
            "isSemanticSearchEnabled": True,
            "contentModeration": "Low",
            "optInUseLatestModels": False,
        },
        "recognizer": {"$kind": "GenerativeAIRecognizer"},
    }


def gpt_component_data(instructions):
    """Return the Custom GPT component's `data` for `instructions`.

    A YAML block scalar, indented by hand rather than through a YAML library:
    this module is executed directly by a shell entry point with nothing but
    the standard library available, and the blank line between paragraphs is
    exactly what an unindented emitter would truncate the instructions at.
    """
    body = "\n".join(("  " + line).rstrip() for line in instructions.split("\n"))
    return f"kind: GptComponentMetadata\ninstructions: |-\n{body}\n"


def gpt_component():
    return Component(
        schemaname=f"{AGENT_SCHEMA_NAME}.gpt.default",
        name=AGENT_NAME,
        componenttype=CUSTOM_GPT,
        data=gpt_component_data(INSTRUCTIONS),
    )


def fallback_topic():
    """Return the Fallback topic: search the corpus, then miss honestly.

    A bare `SendActivity` here is what issue #54 spent six deploys chasing. This
    trigger fires on the turns the generative planner did not answer, and on
    those turns the old topic spoke the honest miss **without anything having
    searched** — measured 2026-08-14: three of sixty-nine fresh conversations
    asking the rehearsed question got the honest miss, and one got it beside the
    cited answer. Deleting the topic outright is worse: the platform's own
    "Sorry, I am not able to find a related topic" answers instead, on 40% of
    the same question, and that is not a beat, it is a stack trace.

    So the search happens **inside** the fallback. `SearchAndSummarizeContent`
    with no source list searches every knowledge source the agent has, and
    sends its own answer — which is what carries the citation entities the
    Grounding panel is a claim about, so the answer is never re-sent from a
    variable here. `Topic.Answer` is read only to decide whether anything was
    found. The honest miss is now what it says it is: the corpus was searched
    and holds nothing.

    The shape is Microsoft's own exported Conversational boosting topic
    (CopilotStudioSamples, `account-contact-lookup`); the `elseActions` branch
    is this repository's.
    """
    data = (
        "kind: AdaptiveDialog\n"
        "beginDialog:\n"
        "  kind: OnUnknownIntent\n"
        "  id: main\n"
        "  priority: -1\n"
        "  actions:\n"
        "    - kind: SearchAndSummarizeContent\n"
        "      id: search-content\n"
        "      userInput: =System.Activity.Text\n"
        "      variable: Topic.Answer\n"
        "    - kind: ConditionGroup\n"
        "      id: has-answer-conditions\n"
        "      conditions:\n"
        "        - id: has-answer\n"
        "          condition: =!IsBlank(Topic.Answer)\n"
        "          actions:\n"
        "            - kind: EndDialog\n"
        "              id: end-topic\n"
        "              clearTopicQueue: true\n"
        "      elseActions:\n"
        "        - kind: SendActivity\n"
        "          id: sendMessage_honestMiss\n"
        f"          activity: {HONEST_MISS}\n"
    )
    return Component(
        schemaname=f"{AGENT_SCHEMA_NAME}.topic.Fallback",
        name="Fallback",
        componenttype=TOPIC,
        data=data,
    )


def conversation_start_topic():
    """Return the Conversation Start topic.

    It fires on an explicit conversation-start event rather than on the first
    message, which is why the Direct Line client has to send one (ADR-011).
    """
    data = (
        "kind: AdaptiveDialog\n"
        "beginDialog:\n"
        "  kind: OnConversationStart\n"
        "  id: main\n"
        "  actions:\n"
        "    - kind: SendActivity\n"
        "      id: sendMessage_greeting\n"
        "      activity:\n"
        "        text:\n"
        f"          - {GREETING}\n"
    )
    return Component(
        schemaname=f"{AGENT_SCHEMA_NAME}.topic.ConversationStart",
        name="Conversation Start",
        componenttype=TOPIC,
        data=data,
    )


def authored_components(filenames):
    """Return every component the repository authors for the agent.

    The repository owns every word the agent says: its instructions, its
    greeting and the sentence it refuses an out-of-corpus question with. What
    it does not author, it does not create — an agent carrying topics nobody in
    this repository wrote is an agent whose behaviour is not reviewable here.

    The template a portal-created agent starts from copies thirteen system
    topics beside these. None of them is needed: generative orchestration
    answers from the uploaded documents with the three components below and
    nothing else, which was measured live rather than reasoned about.
    """
    return [gpt_component(), conversation_start_topic(),
            fallback_topic()] + file_components(filenames)


def _authored_check(components, corpus):
    """Whether every component the agent carries was written in this repository.

    The agent is editable in the Copilot Studio portal by anyone holding the
    environment, and a topic added there is matched before the corpus is
    searched. The demo's whole claim is that the answer came from the SOP
    documents, so a component this repository cannot show you the source of is
    a behaviour it cannot vouch for on stage.
    """
    ours = {component.schemaname for component in authored_components(corpus)}
    theirs = sorted(
        component.get("schemaname")
        for component in components or []
        if component.get("schemaname") not in ours
    )
    if theirs:
        return Check(
            "authored-here", False,
            f"{len(theirs)} component(s) were not authored by this "
            "repository — the agent has been edited elsewhere: "
            + ", ".join(theirs),
        )
    return Check(
        "authored-here", True,
        f"every component the agent carries is authored here "
        f"({len(ours)} of them)",
    )


def format_report(verdict, remedy=None):
    """Return the human-readable report for a `Verdict`. Pure."""
    lines = [
        f"  {'PASS' if check.ok else 'FAIL'}  {check.name}: {check.detail}"
        for check in verdict.checks
    ]
    consequence = (
        "the SOP agent is reachable over Direct Line and answers from the "
        "corpus"
        if verdict.ok
        else "the SOP agent is not reachable as a grounded tool yet"
    )
    lines.append(f"  ----  Foundry orchestrator (#18): {consequence}")
    if not verdict.ok:
        lines.append(remedy if remedy is not None else _remedy(verdict))
    return "\n".join(lines)


def _remedy(verdict):
    """Return the operator's next step for a failing verdict. Pure.

    Ordered by what has to be true first. Re-uploading the corpus into an agent
    that was never published fixes nothing while looking like action, and
    probing an agent that does not exist reports a conversation failure for a
    missing row.
    """
    if not verdict.check("agent-exists").ok:
        return (
            "\nRemedy: the agent does not exist. Author it, then publish and "
            "prove it:\n"
            "  scripts/copilot_studio/check-sop-agent.sh --provision --publish"
        )
    if not verdict.check("corpus-uploaded").ok:
        return (
            "\nRemedy: upload the missing SOP documents and publish again — "
            "Direct Line serves published content:\n"
            "  scripts/copilot_studio/check-sop-agent.sh --provision --publish"
        )
    if not verdict.check("no-authentication").ok:
        return (
            "\nRemedy: the agent is not serving anonymous sessions. Re-author "
            "it with no authentication and publish:\n"
            "  scripts/copilot_studio/check-sop-agent.sh --provision --publish"
        )
    if not verdict.check("published-to-direct-line").ok:
        return (
            "\nRemedy: publish. The authoring copy is not what Direct Line "
            "serves:\n"
            "  scripts/copilot_studio/check-sop-agent.sh --publish"
        )
    if not verdict.check("authored-here").ok:
        return (
            "\nRemedy: decide, per component named above, whether it belongs. "
            "Author it in scripts/copilot_studio/sop_agent.py so it is "
            "reviewed and re-created on a rebuild, or delete it from the "
            "environment. Provisioning converges what this repository "
            "authors; it never removes what it does not."
        )
    if any(NOT_PROBED in check.detail for check in verdict.checks
           if not check.ok):
        return (
            "\nRemedy: nothing is known to be wrong — this run gathered no "
            "evidence that the agent answers. Ask it:\n"
            "  scripts/copilot_studio/check-sop-agent.sh --probe"
        )
    return (
        "\nRemedy: the agent answered, but not the way the demo needs. Re-read "
        "the instructions above — they carry the honest miss verbatim — "
        "re-author and publish, then start a *fresh* conversation: a published "
        "change never reaches one already open:\n"
        "  scripts/copilot_studio/check-sop-agent.sh --provision --publish "
        "--probe"
    )


# ---------------------------------------------------------------------------
# Live calls. Everything above this line is pure and unit-tested.
# ---------------------------------------------------------------------------

BAP_API = "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform"
BAP_RESOURCE = "https://api.bap.microsoft.com/"
BAP_API_VERSION = "2020-10-01"

DATAVERSE_API_VERSION = "v9.2"

# The Direct Line 3.0 service the token from the channel settings endpoint is
# redeemed against. The *token* endpoint is never hardcoded — it is read from
# the environment's own regional channel settings service (ADR-011), which is
# what `PvaGetDirectLineEndpoint` returns.
DIRECT_LINE = "https://directline.botframework.com/v3/directline"

CORPUS_DIR = "content/sop/docx"

# The two questions the demo is rehearsed on. The second is deliberately not in
# the corpus (`content/sop/corpus.toml`), and the answer to it is the beat the
# grounding claim rests on.
PROCEDURE_QUESTION = "How do I close the store?"
OUT_OF_CORPUS_QUESTION = (
    "How do I restart the car wash after a vehicle stalls in the bay?"
)

# The third question is not a demo beat: it is the evidence that the published
# index holds the documents this repository built. It asks for the one line the
# rebrand (ADR-019) changed and the filename did not, so the answer is either
# the current corpus or the previous one, plainly.
BRANDING_QUESTION = (
    "In the store closing procedure document, who is listed as the owner and "
    "which store does it say it applies to? Quote the document."
)

# A publish is asynchronous: `PvaPublish` returns before the published content
# is what Direct Line serves. Measured at 17-85 seconds on this environment.
PUBLISH_ATTEMPTS = 40
PUBLISH_DELAY_SECONDS = 5

# How long to wait for the agent to finish answering one question. A generative
# answer over the corpus came back in 5-20 seconds live.
ANSWER_SECONDS = 45


def _token(resource):
    """Return an access token for `resource` from the signed-in Azure CLI."""
    import subprocess

    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"could not get a token for {resource}; run:\n"
            f"  az login --scope \"{resource}/.default\"\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _request(url, resource=None, method="GET", body=None, token=None,
             raw=None, content_type="application/json", headers=None):
    import urllib.error
    import urllib.parse
    import urllib.request

    url = urllib.parse.quote(url, safe="/?$=&,'()*+:%~")
    request_headers = {"Accept": "application/json"}
    if resource is not None or token is not None:
        request_headers["Authorization"] = "Bearer " + (token or _token(resource))
    request_headers.update(headers or {})
    data = None
    if raw is not None:
        data = raw
        request_headers["Content-Type"] = content_type
    elif body is not None:
        data = json.dumps(body).encode()
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method,
                                     headers=request_headers)
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read().decode()
            return json.loads(payload) if payload.strip() else {}
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"{method} {url} → {error.code}: {error.read().decode()[:400]}"
        ) from error


class Environment:
    """The Dataverse instance behind a Power Platform environment."""

    def __init__(self, environment_id, instance_url):
        self.environment_id = environment_id
        self.instance_url = instance_url
        self.resource = instance_url.rstrip("/") + "/"
        self.base = f"{instance_url.rstrip('/')}/api/data/{DATAVERSE_API_VERSION}"
        self._token = _token(self.resource)

    def call(self, path, method="GET", body=None, raw=None,
             content_type="application/json", headers=None):
        return _request(f"{self.base}/{path}", method=method, body=body,
                        token=self._token, raw=raw, content_type=content_type,
                        headers=headers)

    def download(self, path):
        """Return a file column's bytes, or None if they cannot be read back.

        None is what a component with nothing attached returns, and it is also
        what a read that failed returns. The caller treats both the same way —
        uploads — because the two are indistinguishable from here and guessing
        current is the failure this exists to prevent.
        """
        import urllib.error
        import urllib.parse
        import urllib.request

        url = urllib.parse.quote(f"{self.base}/{path}/$value",
                                 safe="/?$=&,'()*+:%~")
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self._token}"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.read()
        except urllib.error.HTTPError:
            return None


def resolve_environment(environment_id=None):
    """Return the Dataverse `Environment` for the tenant's Default environment.

    The identity check is the admin-role preflight's, for its reason: following
    a Copilot Studio URL without an explicit environment can land a maker in
    their personal Developer environment, and an agent authored there is
    invisible to the demo while every record looks correct.
    """
    wanted = environment_id or DEFAULT_ENVIRONMENT_ID
    url = (f"{BAP_API}/scopes/admin/environments/{wanted}"
           f"?api-version={BAP_API_VERSION}")
    environment = _request(url, BAP_RESOURCE)
    instance = (((environment.get("properties") or {})
                 .get("linkedEnvironmentMetadata")) or {}).get("instanceUrl")
    if not instance:
        raise RuntimeError(
            f"environment {wanted} has no Dataverse instance — Copilot Studio "
            "cannot host an agent there"
        )
    return Environment(wanted, instance)


def read_bot(environment):
    """Return the agent's `bot` row, or None."""
    rows = environment.call(
        "bots?$select=botid,name,schemaname,authenticationmode,"
        "accesscontrolpolicy,publishedon,synchronizationstatus,configuration"
        f"&$filter=schemaname eq '{AGENT_SCHEMA_NAME}'"
    )["value"]
    return rows[0] if rows else None


def read_components(environment, bot):
    """Return the agent's `botcomponent` rows."""
    if not bot:
        return []
    return environment.call(
        "botcomponents?$select=botcomponentid,name,schemaname,componenttype,"
        f"data,filedata_name&$filter=_parentbotid_value eq {bot['botid']}"
    )["value"]


def corpus_filenames(repo_root):
    """Return the SOP corpus's filenames, sorted."""
    import os

    directory = os.path.join(repo_root, CORPUS_DIR)
    return sorted(name for name in os.listdir(directory)
                  if name.endswith(".docx"))


def corpus_banner(repo_root):
    """Return the banner the SOP corpus is written under, or None.

    Read from the corpus manifest rather than pinned here, so the banner has one
    home: `content/sop/corpus.toml` is what the builder stamps into every
    document, and a check carrying its own copy would pass a rebrand it never
    saw. None if the manifest cannot be read — which the verdict reports as no
    evidence rather than as a pass.
    """
    import os
    import tomllib

    path = os.path.join(repo_root, "content", "sop", "corpus.toml")
    try:
        with open(path, "rb") as manifest:
            return tomllib.load(manifest).get("banner") or None
    except (OSError, tomllib.TOMLDecodeError):
        return None


def provision(environment, repo_root, solution=DEFAULT_SOLUTION):
    """Create or converge the agent, its components and the uploaded corpus.

    Idempotent by schema name: a second run patches what drifted rather than
    creating a second agent beside the first.
    """
    import os
    import time

    bot = read_bot(environment)
    if not bot:
        environment.call(
            "bots", "POST", bot_record(),
            headers={"Prefer": "return=representation",
                     "MSCRM.SolutionUniqueName": solution},
        )
        # Provisioning registers the agent with the runtime, and a component
        # cannot be attached until it has finished.
        for _ in range(PUBLISH_ATTEMPTS):
            bot = read_bot(environment)
            state = ((publish_state(bot).get("currentSynchronizationState")
                      or {}).get("provisioningStatus"))
            if state == "Provisioned":
                break
            time.sleep(PUBLISH_DELAY_SECONDS)
        else:
            raise RuntimeError("the agent did not finish provisioning")
        print(f"  created {AGENT_SCHEMA_NAME}")

    environment.call(f"bots({bot['botid']})", "PATCH", {
        "configuration": json.dumps(bot_configuration(), indent=2),
        "authenticationmode": NO_AUTHENTICATION,
        "accesscontrolpolicy": ACCESS_CONTROL_ANY,
    })

    existing = {row["schemaname"]: row
                for row in read_components(environment, bot)}
    for component in authored_components(corpus_filenames(repo_root)):
        row = existing.get(component.schemaname)
        if row is None:
            row = environment.call(
                "botcomponents", "POST", component.record(bot["botid"]),
                headers={"Prefer": "return=representation",
                         "MSCRM.SolutionUniqueName": solution},
            )
            print(f"  created {component.schemaname}")
        elif component.data is not None and row.get("data") != component.data:
            environment.call(f"botcomponents({row['botcomponentid']})",
                             "PATCH", {"data": component.data})
            print(f"  updated {component.schemaname}")
        if component.filename is None:
            continue
        path = os.path.join(repo_root, CORPUS_DIR, component.filename)
        local = open(path, "rb").read()
        reason = upload_reason(
            row, component.filename, local,
            environment.download(f"botcomponents({row['botcomponentid']})/filedata"),
        )
        if reason is None:
            continue
        environment.call(
            f"botcomponents({row['botcomponentid']})/filedata", "PATCH",
            raw=local,
            content_type="application/octet-stream",
            headers={"x-ms-file-name": component.filename},
        )
        print(f"  uploaded {component.filename} - {reason}")
    return read_bot(environment)


def publish(environment, bot):
    """Publish the agent and wait for the publish to finish. Returns seconds.

    `PvaPublish` returns before the published content is what Direct Line
    serves, so the wait is the point of this function: a probe run against an
    in-flight publish reads the previous content and calls it a regression.
    """
    import time

    started = time.time()
    before = bot.get("publishedon")
    environment.call(f"bots({bot['botid']})/Microsoft.Dynamics.CRM.PvaPublish",
                     "POST", {})
    for _ in range(PUBLISH_ATTEMPTS):
        current = read_bot(environment)
        if current.get("publishedon") != before:
            operation = (publish_state(current)
                         .get("lastFinishedPublishOperation") or {})
            return round(time.time() - started, 1), operation.get("status")
        time.sleep(PUBLISH_DELAY_SECONDS)
    raise RuntimeError("the publish did not finish")


def direct_line_token(environment, bot):
    """Return an anonymous Direct Line token for the published agent.

    The token endpoint is read from the environment's own regional channel
    settings service rather than assembled from the default Direct Line
    hostname (ADR-011). Tokens live 3600 seconds.
    """
    endpoint = environment.call(
        f"bots({bot['botid']})/Microsoft.Dynamics.CRM.PvaGetDirectLineEndpoint",
        "POST", {},
    )["Endpoint"]
    return endpoint, _request(endpoint)["token"]


def converse(token, questions, answer_seconds=ANSWER_SECONDS):
    """Drive one fresh Direct Line conversation and return what came back.

    A fresh conversation every time, deliberately: a published change never
    reaches a conversation that is already open, so reusing one is how a
    rehearsal convinces itself a fix did not work.
    """
    import time

    conversation = _request(f"{DIRECT_LINE}/conversations", method="POST",
                            body={}, token=token)
    identifier = conversation["conversationId"]
    token = conversation.get("token", token)
    watermark = None
    seen = set()

    def drain(seconds):
        nonlocal watermark
        replies = []
        quiet = 0
        deadline = time.time() + seconds
        while time.time() < deadline:
            url = f"{DIRECT_LINE}/conversations/{identifier}/activities"
            if watermark:
                url += f"?watermark={watermark}"
            payload = _request(url, token=token)
            watermark = payload.get("watermark") or watermark
            arrived = 0
            for activity in payload.get("activities", []):
                # Direct Line replaces the sender identifier with a
                # server-generated value, so the role is the only reliable way
                # to tell the agent's own activities from the echo of ours.
                if (activity.get("from") or {}).get("role") != "bot":
                    continue
                if activity["id"] in seen:
                    continue
                seen.add(activity["id"])
                replies.append(activity)
                arrived += 1
            quiet = 0 if arrived else quiet + 1
            if settled(replies, quiet):
                break
            time.sleep(2)
        return replies

    def send(activity):
        _request(f"{DIRECT_LINE}/conversations/{identifier}/activities",
                 method="POST", token=token,
                 body=dict(activity, **{"from": {"id": "probe", "role": "user"},
                                        "locale": "en-US"}))

    send({"type": "event", "name": "startConversation"})
    greeting = drain(20)
    answers = []
    for question in questions:
        send({"type": "message", "text": question})
        answers.append(drain(answer_seconds))
    return identifier, greeting, answers


def probe_live(environment, bot, samples=1):
    """Ask the agent the three rehearsed questions and return a `Probe`.

    `samples` is how many times the *procedure* question is asked, each in its
    own fresh conversation. More than one because the fault #54 turned out to
    be was intermittent at about 6%, and one sample cannot see that.
    """
    endpoint, token = direct_line_token(environment, bot)
    print(f"  Direct Line endpoint: {endpoint.split('?')[0]}")
    identifier, greeting, answers = converse(
        token, [PROCEDURE_QUESTION, OUT_OF_CORPUS_QUESTION, BRANDING_QUESTION])
    print(f"  conversation: {identifier}")
    repeats = []
    for _ in range(max(0, samples - 1)):
        # A fresh token as well as a fresh conversation: a Copilot Studio
        # Direct Line token carries a `conv` claim, so re-spending one rejoins
        # the conversation it was minted for and replays its transcript.
        _, again = direct_line_token(environment, bot)
        _, _, more = converse(again, [PROCEDURE_QUESTION])
        repeats.append(more[0])
    if repeats:
        print(f"  asked the procedure question {samples} times in "
              f"{samples} conversations")
    return Probe(greeting=greeting, procedure=answers[0], miss=answers[1],
                 branding=answers[2], repeats=repeats)


def export_solution(environment, directory, solution=DEFAULT_SOLUTION):
    """Write a solution export into `directory` and return the path.

    A Default environment cannot be backed up, restored or deleted, so this zip
    is the only copy of the agent that exists outside the tenant.
    """
    import base64
    import os

    payload = environment.call("ExportSolution", "POST", {
        "SolutionName": solution,
        "Managed": False,
        "ExportAutoNumberingSettings": False,
        "ExportCalendarSettings": False,
        "ExportCustomizationSettings": False,
        "ExportEmailTrackingSettings": False,
        "ExportGeneralSettings": False,
        "ExportIsvConfig": False,
        "ExportMarketingSettings": False,
        "ExportOutlookSynchronizationSettings": False,
        "ExportRelationshipRoles": False,
        "ExportSales": False,
    })
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{solution}.zip")
    with open(path, "wb") as handle:
        handle.write(base64.b64decode(payload["ExportSolutionFile"]))
    return path


def main(argv=None):
    """Read the agent's live state, act on the flags, and report. Returns 0/1."""
    import os
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    repo_root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))

    def option(name):
        if name in argv:
            index = argv.index(name)
            argv.pop(index)
            return argv.pop(index)
        return None

    environment_id = option("--environment")
    export_directory = option("--export")
    samples = int(option("--samples") or 1)
    should_provision = "--provision" in argv
    should_publish = "--publish" in argv
    should_probe = "--probe" in argv or not (should_provision or should_publish
                                             or export_directory)

    environment = resolve_environment(environment_id)
    print(f"Environment: {environment.environment_id} "
          f"({environment.instance_url})")

    if should_provision:
        provision(environment, repo_root)
    bot = read_bot(environment)
    if should_publish and bot:
        took, status = publish(environment, bot)
        print(f"  published in {took}s: {status}")
        bot = read_bot(environment)
    if export_directory:
        print(f"  exported {export_solution(environment, export_directory)}")

    probe = (probe_live(environment, bot, samples)
             if (should_probe and bot) else None)
    verdict = evaluate(bot, read_components(environment, bot), probe,
                       corpus_filenames(repo_root), corpus_banner(repo_root))
    print(format_report(verdict))
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover - entry point
    import sys

    sys.exit(main())
