"""What the Grounding panel is allowed to claim (issue #23).

The replies here are the shape ``/sop/ask`` returns, which is the shape #18
pinned against the live Copilot Studio agent: no citation ``url``, a ``name``
that is the uploaded filename, and a ``snippet`` truncated out of the whole
document.
"""

from transparency.source import source_used

SOP_102 = "SOP-102 Store Closing Procedure.docx"

ANSWERED = {
    "text": "1. Count the drawer.",
    "failed": False,
    "conversation_id": "conv-7",
    "platform": "Copilot Studio",
    "source": "Dataverse",
    "agent": "Store SOP Assistant",
    "citations": [
        {"position": 1, "name": SOP_102, "snippet": "Store Closing Procedure", "url": None}
    ],
}


class TestSourceUsed:
    def test_an_answer_names_the_platform_that_produced_it(self):
        """Not merely the source: "Dataverse" alone does not distinguish this
        answer's path from any other retrieval. The claim is that it left
        Foundry."""
        signal = source_used(ANSWERED)

        assert signal.platform == "Copilot Studio"
        assert signal.source == "Dataverse"
        assert signal.agent_name == "Store SOP Assistant"

    def test_the_documents_travel_with_the_signal(self):
        (citation,) = source_used(ANSWERED).citations

        assert citation["name"] == SOP_102
        assert citation["url"] is None

    def test_the_conversation_is_carried_so_the_hop_is_traceable(self):
        assert source_used(ANSWERED).conversation_id == "conv-7"

    def test_a_failed_reply_lights_nothing(self):
        """#18's fixed failure message is written by the backend, not by
        Copilot Studio. A panel lit over it would claim the cross-platform hop
        happened on the one occasion it did not."""
        assert source_used({**ANSWERED, "failed": True}) is None

    def test_an_answer_with_no_documents_still_shows_the_hop(self):
        """The rehearsed out-of-corpus probe (#26): the agent was reached, the
        corpus was searched, nothing matched. An empty document list is what
        makes the honest miss legible as a miss rather than as a silence."""
        signal = source_used({**ANSWERED, "citations": []})

        assert signal.platform == "Copilot Studio"
        assert signal.citations == []

    def test_a_reply_naming_no_platform_claims_nothing(self):
        assert source_used({**ANSWERED, "platform": ""}) is None

    def test_an_empty_reply_claims_nothing(self):
        assert source_used({}) is None
        assert source_used(None) is None
