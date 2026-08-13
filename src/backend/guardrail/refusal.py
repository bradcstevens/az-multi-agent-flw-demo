"""What the Identity boundary gate says when it refuses (issue #14, ADR-014).

The refusal is a **fixed, well-written string**, and the shape it travels in is
labelled as a **Policy block** so the UI can render it distinctly from a
**retrieval miss**. Conflating those two makes a governed refusal look like a
bug, which would cost the demo the exact point it is making.

Four constraints on the wording, all from R5:

- it explains that the assistant is scoped to the store, not to an individual;
- it says plainly that on a shared device it cannot tell who is asking;
- it deflects to a manager or the HR line, so the associate is not stranded;
- it neither over-apologises nor reads as an error. This is policy working, and
  it should sound like it.

It also ends on an invitation rather than a full stop: #27 hangs a "Sign in to
continue" affordance beside this refusal, and the boundary is meant to read as
a door rather than a wall.
"""

from typing import Any, Dict

# The discriminators the frontend switches on. `kind` separates a policy block
# from every other failure shape; `code` says which policy blocked it, so a
# second gate could never be mistaken for this one.
POLICY_BLOCK_KIND = "policy_block"
POLICY_BLOCK_CODE = "identity_boundary"

# The HR line is fictional, like everything else in the demo content.
IDENTITY_BOUNDARY_REFUSAL = (
    "This assistant is set up for Store 223 rather than for individual "
    "associates. It works from store procedures and store records, it holds "
    "nothing about any one person's pay, hours or benefits, and on a shared "
    "device it has no way to tell who is asking. For anything personal, your "
    "store manager can help, or the HR line on 1-800-555-0142 can take it "
    "directly. Ask me anything about running the store and I will pick it up "
    "from here."
)


def policy_block_detail() -> Dict[str, Any]:
    """The refusal as the payload the request path returns.

    A fresh dictionary each call, so a caller that annotates one response does
    not quietly edit the constant behind every other one.
    """
    return {
        "kind": POLICY_BLOCK_KIND,
        "code": POLICY_BLOCK_CODE,
        "message": IDENTITY_BOUNDARY_REFUSAL,
    }
