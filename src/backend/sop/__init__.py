"""The Copilot Studio SOP agent, reached over Direct Line (issue #18, ADR-011).

The client lives here rather than in the MCP container because the container
ships only its own directory and `httpx`; `BaseAPIService` — the seam this
repository tests outbound HTTP at — is a backend module. The MCP tool therefore
calls back to the backend over HTTP, the pattern `ask_user` already uses.
"""

from sop.citation import SCHEMA_ORG_MESSAGE, Citation, citations_from_activity
from sop.provenance import SOP_PLATFORM, SOP_SOURCE

__all__ = [
    "SCHEMA_ORG_MESSAGE",
    "SOP_PLATFORM",
    "SOP_SOURCE",
    "Citation",
    "citations_from_activity",
]
