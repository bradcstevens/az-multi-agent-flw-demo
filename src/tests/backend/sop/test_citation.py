"""Citations parsed structurally out of a Direct Line activity (issue #18).

The payloads here are the ones recorded live against the Copilot Studio SOP
agent in `docs/copilot-studio/sop-agent.md`: the entity type is the schema.org
Message type, there is **no** `url`, `appearance.abstract` is the filename
rather than a snippet, and `appearance.text` carries the whole document.
"""

from sop.citation import SCHEMA_ORG_MESSAGE, citations_from_activity

SOP_102 = "SOP-102 Store Closing Procedure.docx"
SOP_104 = "SOP-104 Cash Handling.docx"

# The document body arrives as HTML under `appearance.text` — this is the
# opening of what SOP-102 returned live on 2026-08-13.
DOCUMENT_HTML = {
    SOP_102: "<h1>Store Closing Procedure</h1> Document ID: SOP-102",
    SOP_104: "<h1>Cash Handling</h1> Document ID: SOP-104",
}


def citation_entity(*names):
    """The entity shape Direct Line delivers, one claim per name."""
    return {
        "type": SCHEMA_ORG_MESSAGE,
        "citation": [
            {
                "@type": "Claim",
                "@id": f"turn13search{position}",
                "position": position + 1,
                "appearance": {
                    "@type": "DigitalDocument",
                    "name": name,
                    "abstract": name,
                    "text": DOCUMENT_HTML[name],
                },
            }
            for position, name in enumerate(names)
        ],
    }


class TestCitationsFromActivity:
    def test_reads_the_document_name_out_of_the_appearance(self):
        activity = {"type": "message", "entities": [citation_entity(SOP_102)]}

        assert [citation.name for citation in citations_from_activity(activity)] == [
            SOP_102
        ]

    def test_orders_the_citations_by_position(self):
        # Position is the number the answer's markdown refers to, so a citation
        # list in a different order would attribute the wrong step to the wrong
        # document in the Grounding panel.
        entity = citation_entity(SOP_102, SOP_104)
        entity["citation"].reverse()
        activity = {"type": "message", "entities": [entity]}

        assert [
            (citation.position, citation.name)
            for citation in citations_from_activity(activity)
        ] == [(1, SOP_102), (2, SOP_104)]

    def test_a_dataverse_uploaded_document_has_no_url(self):
        # ADR-011's central prediction, confirmed live in #17: the citation
        # carries no `url` key at all. Rendering must not require a link.
        activity = {"type": "message", "entities": [citation_entity(SOP_102)]}

        (citation,) = citations_from_activity(activity)

        assert citation.url is None

    def test_ignores_entities_that_are_not_the_schema_org_message_type(self):
        # Direct Line puts client capabilities and other entities in the same
        # collection; only the Message entity carries citations.
        activity = {
            "type": "message",
            "entities": [
                {"type": "ClientCapabilities", "requiresBotState": True},
                citation_entity(SOP_102),
            ],
        }

        assert [citation.name for citation in citations_from_activity(activity)] == [
            SOP_102
        ]

    def test_an_activity_with_no_entities_cites_nothing(self):
        assert citations_from_activity({"type": "message", "text": "hello"}) == []
        assert citations_from_activity(None) == []


class TestSnippet:
    def test_the_snippet_is_the_document_text_stripped_of_its_markup(self):
        # `appearance.text` is the whole document as HTML (3311 characters for
        # SOP-102 live), so it is the only snippet-shaped field there is.
        activity = {"type": "message", "entities": [citation_entity(SOP_102)]}

        (citation,) = citations_from_activity(activity)

        assert citation.snippet(limit=40) == "Store Closing Procedure Document ID: SOP"

    def test_the_abstract_is_not_the_snippet_because_it_is_the_filename(self):
        # ADR-011 was written expecting `abstract` to be a snippet. Live it is
        # identical to `name`, so a snippet taken from it prints the filename
        # twice. Corrected in CONTEXT.md under "Citation appearance".
        activity = {"type": "message", "entities": [citation_entity(SOP_102)]}

        (citation,) = citations_from_activity(activity)

        assert citation.abstract == citation.name
        assert citation.snippet() != citation.name

    def test_a_citation_with_no_text_has_no_snippet(self):
        entity = citation_entity(SOP_102)
        entity["citation"][0]["appearance"]["text"] = ""
        activity = {"type": "message", "entities": [entity]}

        (citation,) = citations_from_activity(activity)

        assert citation.snippet() == ""
