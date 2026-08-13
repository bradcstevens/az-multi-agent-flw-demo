"""Where a SOP answer came from (issue #18).

Two facts, kept in one place because they are the demo's central claim and the
Grounding panel (R6) is an assertion about both: the answer was produced by
**Copilot Studio**, a different platform from every other agent in the roster,
and it was grounded in **Dataverse** documents — never SharePoint, which
[ADR-012](../../../docs/adr/012-grounding-option-a-dataverse-documents-only.md)
deleted rather than deferred.
"""

SOP_PLATFORM = "Copilot Studio"
SOP_SOURCE = "Dataverse"
