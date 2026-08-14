"""Tests for the Copilot Studio SOP agent (issue #17).

The agent is the whole cross-platform proof: a low-code agent, grounded on the
SOP corpus uploaded to Dataverse, reachable anonymously over Direct Line. The
seam under test is the pure one — the records the agent is built from and the
verdict over what a live Direct Line conversation answered. The HTTP calls that
create the records and drive the conversation sit outside it, in `main`.
"""

import json

from copilot_studio.sop_agent import (
    authored_components,
    cited_documents,
    evaluate,
    file_components,
    format_report,
    numbered_steps,
    bot_configuration,
    bot_record,
    conversation_start_topic,
    fallback_topic,
    gpt_component_data,
    DEFAULT_ENVIRONMENT_ID,
    GREETING,
    HONEST_MISS,
    HONEST_MISS_PHRASE,
    INSTRUCTIONS,
    NOT_PROBED,
    Probe,
    upload_reason,
)


CORPUS = [
    "SOP-101 Store Opening Procedure.docx",
    "SOP-102 Store Closing Procedure.docx",
]


def test_a_corpus_document_becomes_one_file_attachment_component():
    """Each .docx is one botcomponent the agent searches, named as the citation."""
    components = file_components(CORPUS)

    assert [c.name for c in components] == CORPUS
    assert [c.schemaname for c in components] == [
        "cr48b_StoreSopAssistant.file.sop101",
        "cr48b_StoreSopAssistant.file.sop102",
    ]


# A bot reply in the shape Direct Line delivered it live on 2026-08-13. The
# citation arrives structurally in the entities collection, not from the
# markdown reference in the text (ADR-011); `url` is absent, as it always is for
# a document uploaded to Dataverse.
def reply(text, citations=("SOP-102 Store Closing Procedure.docx",)):
    return {
        "type": "message",
        "id": "Db4YKvG8f2N8zGBZpNFlC3-us|0000004",
        "from": {"id": "cr48b_StoreSopAssistant", "role": "bot"},
        "text": text,
        "entities": [
            {
                "type": "https://schema.org/Message",
                "citation": [
                    {
                        "@type": "Claim",
                        "@id": str(position),
                        "position": position,
                        "appearance": {
                            "@type": "DigitalDocument",
                            "name": name,
                            "abstract": name,
                            "text": "<h1>Store Closing Procedure</h1> …",
                        },
                    }
                    for position, name in enumerate(citations, start=1)
                ],
            }
        ],
    }


ANSWER = (
    "**Store Closing Steps**  \n"
    "Source: SOP-102 Store Closing Procedure\n\n"
    "1. At 60 minutes before close, begin the coffee bar shutdown.\n"
    "2. At 30 minutes before close, clean and restock the restrooms.\n"
    "3. Lock the customer doors and switch the door sign to CLOSED.\n"
)


def test_numbered_steps_are_read_out_of_a_reply():
    """The answer's shape is a fact about the text, not about the model."""
    assert numbered_steps(ANSWER) == [1, 2, 3]


def test_prose_carrying_a_price_is_not_numbered_steps():
    """"$1.50" and "1 hour" are not step ordinals; a false pass here would let
    a paragraph answer satisfy the criterion the instructions exist to enforce.
    """
    assert numbered_steps(
        "Close the store at 11 p.m. The coffee bar takes 1 hour to shut down "
        "and the deposit bag holds $1.50 in coin."
    ) == []


def test_the_cited_source_is_read_structurally_not_from_the_markdown():
    """The markdown `[1]: cite:1` form is a parallel representation, not the
    source of truth — a reply whose text mentions no document at all still
    cites one.
    """
    assert cited_documents(reply("Numbered steps follow.\n\n[1]: cite:1")) == [
        "SOP-102 Store Closing Procedure.docx"
    ]


# The bot row and its publish state, as Dataverse returned them live after the
# first successful publish on 2026-08-13.
def bot_row(authenticationmode=1, published=True, publish_status="Succeeded",
            published_auth="None"):
    state = {
        "$kind": "BotSynchronizationDetails",
        "currentSynchronizationState": {"provisioningStatus": "Provisioned"},
    }
    if published:
        state["lastFinishedPublishOperation"] = {"status": publish_status}
        state["lastPublishedDetails"] = {"authenticationMode": published_auth}
    return {
        "botid": "c846cba0-e696-f111-8076-0022482abf62",
        "name": "Store SOP Assistant",
        "schemaname": "cr48b_StoreSopAssistant",
        "authenticationmode": authenticationmode,
        "publishedon": "2026-08-13T07:24:54Z" if published else None,
        "synchronizationstatus": json.dumps(state),
    }


def test_an_absent_agent_fails_before_anything_else_is_claimed():
    """No bot row means no agent — and no honest report of what it answered."""
    verdict = evaluate(None, [], probe=None, corpus=CORPUS)

    assert not verdict.ok
    assert not verdict.check("agent-exists").ok
    assert "not exist" in verdict.check("agent-exists").detail


def test_an_authenticated_agent_fails_because_it_answers_nothing_anonymously():
    """The demo front end is a shared store device with no sign-in. Copilot
    Studio will not retrieve knowledge on behalf of a user who does not exist
    (ADR-012), so an authenticated agent is not a degraded demo — it is a
    silent one.
    """
    verdict = evaluate(bot_row(authenticationmode=2), [], probe=None,
                       corpus=CORPUS)

    assert not verdict.check("no-authentication").ok
    assert verdict.check("agent-exists").ok


def test_the_publish_is_what_settles_authentication_not_the_row():
    """A row can be edited after the publish that is actually serving traffic,
    so the mode the last publish went out with is the one Direct Line answers
    under.
    """
    published_authenticated = evaluate(
        bot_row(published_auth="Integrated"), [], probe=None, corpus=CORPUS)

    assert not published_authenticated.check("no-authentication").ok
    assert evaluate(bot_row(), [], probe=None,
                    corpus=CORPUS).check("no-authentication").ok


def uploaded(filenames=CORPUS):
    return [
        {"schemaname": c.schemaname, "name": c.name,
         "componenttype": 14, "filedata_name": c.filename}
        for c in file_components(filenames)
    ]


def test_a_missing_document_is_named_rather_than_counted():
    """A corpus that is short one document still answers most questions, so the
    failure has to name the document or it reads as a healthy agent.
    """
    verdict = evaluate(bot_row(), uploaded(CORPUS[:1]), probe=None,
                       corpus=CORPUS)

    assert not verdict.check("corpus-uploaded").ok
    assert "SOP-102 Store Closing Procedure.docx" in (
        verdict.check("corpus-uploaded").detail)


def test_the_whole_corpus_uploaded_passes():
    assert evaluate(bot_row(), uploaded(), probe=None,
                    corpus=CORPUS).check("corpus-uploaded").ok


CLOSING = "SOP-102 Store Closing Procedure.docx"


def attached(filename=CLOSING):
    return {"botcomponentid": "b1", "schemaname": "cr48b_StoreSopAssistant.file.sop102",
            "name": filename, "componenttype": 14, "filedata_name": filename}


def test_a_document_whose_bytes_already_match_is_not_uploaded_again():
    assert upload_reason(attached(), CLOSING, b"built", b"built") is None


def test_a_rebranded_document_is_uploaded_even_though_its_filename_is_unchanged():
    """The rebrand (ADR-019) rewrites the body of all ten documents and renames none
    of them, because the filename is the citation the associate reads. A provision
    that decides on the filename alone therefore reports every document present and
    uploads nothing, and the agent goes on answering out of the old corpus.
    """
    reason = upload_reason(attached(), CLOSING, b"Circle K", b"Brightpath Convenience")

    assert reason is not None
    assert "content" in reason


def test_a_component_with_no_file_attached_is_uploaded():
    row = attached()
    row["filedata_name"] = None

    assert upload_reason(row, CLOSING, b"built", None) is not None


def test_a_file_that_cannot_be_read_back_is_uploaded_rather_than_assumed_current():
    """Unknown is not current. Skipping on a failed read is the same silent hole as
    skipping on the filename: nothing fails, and the old document keeps answering.
    """
    assert upload_reason(attached(), CLOSING, b"built", None) is not None


def test_a_file_attached_under_another_name_is_uploaded():
    assert upload_reason(attached("SOP-102 Store Closing.docx"), CLOSING,
                         b"built", b"built") is not None


def authored(filenames=CORPUS):
    """The agent exactly as this repository authors it."""
    return [{"schemaname": c.schemaname, "name": c.name,
             "componenttype": c.componenttype,
             "filedata_name": c.filename}
            for c in authored_components(filenames)]


def test_a_component_this_repository_never_wrote_is_named():
    """The agent is editable in the Copilot Studio portal by anyone with the
    environment, and a topic added there answers before the corpus does. The
    demo's claim is that every word comes from the SOP documents, so a
    component nobody in this repository wrote is a behaviour nobody here can
    review — and the report has to name it, because "something drifted" sends
    a reader to the portal to hunt.
    """
    portal_edit = authored() + [{
        "schemaname": "cr48b_StoreSopAssistant.topic.Escalate",
        "name": "Escalate", "componenttype": 9,
    }]

    check = evaluate(bot_row(), portal_edit, probe=None,
                     corpus=CORPUS).check("authored-here")

    assert not check.ok
    assert "topic.Escalate" in check.detail


def test_the_agent_as_this_repository_authors_it_passes():
    """Three components and the corpus — no copied system topics. Generative
    orchestration answers from the uploaded documents without them, which was
    measured live rather than assumed.
    """
    assert evaluate(bot_row(), authored(), probe=None,
                    corpus=CORPUS).check("authored-here").ok


def test_an_unpublished_agent_fails_even_with_the_corpus_in_place():
    """Uploading is not publishing: Direct Line serves published content, so an
    agent full of documents and never published answers nothing at all.
    """
    verdict = evaluate(bot_row(published=False), uploaded(), probe=None,
                       corpus=CORPUS)

    assert not verdict.check("published-to-direct-line").ok


def test_a_failed_publish_is_not_a_publish():
    verdict = evaluate(bot_row(publish_status="Failed"), uploaded(),
                       probe=None, corpus=CORPUS)

    assert not verdict.check("published-to-direct-line").ok
    assert "Failed" in verdict.check("published-to-direct-line").detail


GREETING_REPLY = reply("Hello, I'm Store SOP Assistant. How can I help?",
                       citations=())
MISS = reply(
    "That procedure is not in the store's SOP library, so I can't give you "
    "the steps. Ask your shift lead, and let them know the procedure is "
    "missing so it can be added.", citations=())


def probed(procedure=None, miss=MISS, greeting=GREETING_REPLY,
           branding=None):
    return Probe(
        greeting=[greeting] if greeting else [],
        procedure=[procedure if procedure is not None else reply(ANSWER)],
        miss=[miss] if miss else [],
        branding=[branding if branding is not None else reply(BRANDED_ANSWER)],
    )


BRANDED_ANSWER = (
    "SOP-102 Store Closing Procedure is owned by Circle K - Northgate District "
    "Operations and applies to the closing associate and the shift lead at "
    "Circle K Store 223."
)


def test_an_answer_that_quotes_the_banner_out_of_the_document_proves_the_content_is_live():
    """The rebrand (ADR-019) changed the documents' bytes and not their names, so
    the corpus check — which reads names — passes either way. Only the banner
    coming back out of a live conversation proves the index holds the rebuilt
    documents rather than the ones it held before.
    """
    check = evaluate(bot_row(), uploaded(), probe=probed(), corpus=CORPUS,
                     banner="Circle K").check("corpus-content-current")

    assert check.ok, check.detail


def test_an_answer_still_carrying_the_previous_banner_fails():
    stale = reply(
        "SOP-102 Store Closing Procedure is owned by Brightpath Convenience - "
        "Northgate District Operations and applies to Brightpath Convenience "
        "Store 223."
    )

    check = evaluate(bot_row(), uploaded(), probe=probed(branding=stale),
                     corpus=CORPUS, banner="Circle K").check(
                         "corpus-content-current")

    assert not check.ok
    assert "Circle K" in check.detail


def test_a_branding_answer_that_cites_nothing_fails_even_when_it_says_the_banner():
    """The model knows the customer's name without reading a document, so an
    uncited answer naming the banner is exactly what a stale index produces once
    the question has told it what to say.
    """
    uncited = reply(f"That procedure applies to Circle K Store 223.",
                    citations=())

    check = evaluate(bot_row(), uploaded(), probe=probed(branding=uncited),
                     corpus=CORPUS, banner="Circle K").check(
                         "corpus-content-current")

    assert not check.ok


def test_a_run_that_did_not_read_the_corpus_banner_reports_no_evidence():
    check = evaluate(bot_row(), uploaded(), probe=probed(), corpus=CORPUS,
                     banner=None).check("corpus-content-current")

    assert not check.ok
    assert NOT_PROBED in check.detail


def test_a_run_that_never_opened_a_conversation_reports_no_evidence():
    """The records being right is not the claim. The claim is that the agent
    answers, and a run that never asked has not tested it — so it fails, but
    with its own remedy: probe, rather than wait or fix.
    """
    verdict = evaluate(bot_row(), uploaded(), probe=None, corpus=CORPUS)

    assert not verdict.ok
    assert NOT_PROBED in verdict.check("numbered-steps-with-source").detail
    assert NOT_PROBED in verdict.check("honest-miss").detail
    assert NOT_PROBED in verdict.check("greeting-on-conversation-start").detail


def test_a_live_conversation_that_answers_in_numbered_steps_passes():
    verdict = evaluate(bot_row(), uploaded(), probe=probed(), corpus=CORPUS)

    assert verdict.ok, [c.detail for c in verdict.checks if not c.ok]
    assert "SOP-102 Store Closing Procedure.docx" in (
        verdict.check("numbered-steps-with-source").detail)


def test_a_prose_answer_fails_even_though_it_is_correct_and_cited():
    """Numbered steps are the requirement, not a preference: an associate
    reads this one-handed, mid-shift, on a phone.
    """
    verdict = evaluate(bot_row(), uploaded(), corpus=CORPUS, probe=probed(
        procedure=reply("Close the store by locking up and counting the "
                        "drawer, then arm the alarm.")))

    assert not verdict.check("numbered-steps-with-source").ok


def test_an_uncited_answer_fails_because_the_source_is_the_proof():
    """Numbered steps with no citation are indistinguishable from invention —
    and the citation is what proves the answer came from Copilot Studio's own
    Dataverse knowledge rather than from the model.
    """
    verdict = evaluate(bot_row(), uploaded(), corpus=CORPUS,
                       probe=probed(procedure=reply(ANSWER, citations=())))

    assert not verdict.check("numbered-steps-with-source").ok


def test_an_invented_answer_to_the_out_of_corpus_question_fails():
    """The honest miss is the beat the demo is built on. An agent that answers
    the car-wash question with confident steps has not missed honestly — it has
    invented, and the whole grounding claim goes with it.
    """
    verdict = evaluate(bot_row(), uploaded(), corpus=CORPUS, probe=probed(
        miss=reply("1. Press the reset button.\n2. Restart the conveyor.",
                   citations=())))

    assert not verdict.check("honest-miss").ok


def test_a_silent_conversation_start_fails():
    """The greeting is what tells an associate the assistant is listening, and
    it only fires on an explicit conversation-start event.
    """
    verdict = evaluate(bot_row(), uploaded(), corpus=CORPUS,
                       probe=probed(greeting=None))

    assert not verdict.check("greeting-on-conversation-start").ok


def test_the_agent_is_configured_not_to_answer_from_model_knowledge():
    """`useModelKnowledge` is the honest miss's off switch. Left on, the model
    fills the gap the corpus deliberately leaves and the demo's most-defended
    claim — that the answer came from the store's own documents — quietly stops
    being true.
    """
    assert bot_configuration()["aISettings"]["useModelKnowledge"] is False


def test_the_agent_uses_generative_orchestration_over_its_knowledge():
    configuration = bot_configuration()

    assert configuration["settings"]["GenerativeActionsEnabled"] is True
    assert configuration["gPTSettings"]["defaultSchemaName"] == (
        "cr48b_StoreSopAssistant.gpt.default")


def test_the_bot_row_is_created_with_no_authentication():
    assert bot_record()["authenticationmode"] == 1


def test_the_instructions_the_agent_is_authored_with_demand_the_answer_shape():
    """The three claims the acceptance criteria make about an answer are the
    three the instructions have to ask for, or the agent is being graded on
    something nobody told it to do.
    """
    instructions = gpt_component_data(INSTRUCTIONS)

    assert instructions.startswith("kind: GptComponentMetadata")
    assert "numbered steps" in instructions
    assert "name the source document" in instructions
    assert "not in the SOP library" in instructions


def test_the_instruction_block_survives_a_blank_line():
    """A block scalar's indentation is what holds a multi-paragraph
    instruction together; lose it and the YAML either truncates at the blank
    line or fails to parse, and the agent is published with no instructions at
    all.
    """
    data = gpt_component_data("first paragraph\n\nsecond paragraph")

    assert data.splitlines()[1] == "instructions: |-"
    assert "  first paragraph" in data
    assert "  second paragraph" in data


def test_the_fallback_topic_says_exactly_what_the_verdict_looks_for():
    """The honest miss is authored in one place and checked in another. If they
    drift, the check passes on wording the agent no longer says, or fails on
    wording it does.
    """
    assert HONEST_MISS in fallback_topic().data
    assert HONEST_MISS_PHRASE in HONEST_MISS


def test_the_conversation_start_topic_greets_an_explicit_event():
    topic = conversation_start_topic()

    assert "OnConversationStart" in topic.data
    assert GREETING in topic.data


def test_the_environment_the_agent_is_authored_in_is_the_one_preflight_checked():
    """Three modules name this environment because each is executed directly by
    its own shell entry point. If they drift, the agent is authored somewhere
    the preflight checks never looked — a personal Developer environment being
    the realistic way that happens.
    """
    from preflight.dataverse_admin_role import (
        DEFAULT_ENVIRONMENT_ID as admin_role_environment,
    )
    from preflight.dataverse_search import (
        DEFAULT_ENVIRONMENT_ID as search_environment,
    )

    assert DEFAULT_ENVIRONMENT_ID == admin_role_environment
    assert DEFAULT_ENVIRONMENT_ID == search_environment


def test_the_report_states_the_consequence_for_the_orchestrator():
    """#18 calls this agent as a tool. Whether that is possible yet is the one
    thing a reader of this report wants, and it is a consequence of the checks
    rather than an independent fact.
    """
    passing = format_report(evaluate(bot_row(), uploaded(), probe=probed(),
                                     corpus=CORPUS))
    failing = format_report(evaluate(None, [], probe=None, corpus=CORPUS))

    assert "reachable over Direct Line" in passing
    assert "not reachable" in failing


def test_the_remedy_for_an_unpublished_agent_is_to_publish_not_to_re_author():
    """Ordered by what has to be true first: re-uploading the corpus into an
    agent that was never published fixes nothing while looking like action.
    """
    verdict = evaluate(bot_row(published=False), uploaded(), probe=None,
                       corpus=CORPUS)

    assert "--publish" in format_report(verdict)


def test_the_remedy_for_a_portal_edit_is_not_to_re_provision():
    """`--provision` creates and converges; it never deletes. So the remedy for
    a component this repository did not write is a decision — author it here or
    remove it there — and telling the operator to re-run provision would send
    them to watch a no-op.
    """
    verdict = evaluate(bot_row(), authored() + [{
        "schemaname": "cr48b_StoreSopAssistant.topic.Escalate",
        "componenttype": 9,
    }], probe=probed(), corpus=CORPUS)
    report = format_report(verdict)

    assert "--provision" not in report
    assert "topic.Escalate" in report


def test_the_remedy_for_a_run_that_did_not_ask_is_to_ask():
    verdict = evaluate(bot_row(), uploaded(), probe=None, corpus=CORPUS)

    assert "--probe" in format_report(verdict)
