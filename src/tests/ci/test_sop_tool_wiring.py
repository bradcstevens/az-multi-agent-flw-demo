"""The two containers' agreement about the SOP tool (issue #18).

The orchestrator reaches the Copilot Studio agent through one MCP tool, and the
two halves of that hop are deployed as separate images: the backend decides
which tools an agent on the ``sop`` domain is allowed to call, and the MCP
container decides what that tool is called. Nothing at runtime reconciles them
— a rename on one side leaves an agent allowed a tool that does not exist,
which fails as the orchestrator quietly not having a procedure tool at all.

Read as text rather than imported: the backend module wants an AppConfig and
the MCP module wants its own container's import path, and neither is worth
standing up to compare two names.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_CONFIG = REPO_ROOT / "src" / "backend" / "config" / "mcp_config.py"
SOP_SERVICE = REPO_ROOT / "src" / "mcp_server" / "services" / "sop_service.py"
FACTORY = REPO_ROOT / "src" / "mcp_server" / "core" / "factory.py"


def _allowlisted_sop_tools() -> list[str]:
    block = re.search(
        r'"sop":\s*\[(.*?)\]', MCP_CONFIG.read_text(encoding="utf-8"), re.S
    )
    assert block, "the sop domain has no entry in DOMAIN_ALLOWED_TOOLS"
    return re.findall(r'"([^"]+)"', block.group(1))


def _registered_tools() -> list[str]:
    source = SOP_SERVICE.read_text(encoding="utf-8")
    return re.findall(r"async def (\w+)\(question: str\)", source)


def test_the_allowlisted_tool_is_the_tool_the_container_registers():
    assert _allowlisted_sop_tools() == _registered_tools()


def test_the_domain_the_allowlist_is_keyed_by_is_a_domain_the_server_mounts():
    """The allowlist's key is also the URL segment the agent connects to.

    ``MCPConfig.from_env(domain="sop")`` rewrites the endpoint to ``/sop/mcp``,
    which only answers because the MCP container mounts a server per ``Domain``
    member. A key with no member is a 404 at the moment the demo asks its
    procedure question.
    """
    assert 'SOP = "sop"' in FACTORY.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The same agreement, for the attempted-steps memory (issue #21)
# ---------------------------------------------------------------------------
TROUBLESHOOTING_SERVICE = (
    REPO_ROOT / "src" / "mcp_server" / "services" / "troubleshooting_service.py"
)


def _allowlisted_troubleshooting_tools() -> list[str]:
    block = re.search(
        r'"troubleshooting":\s*\[(.*?)\]',
        MCP_CONFIG.read_text(encoding="utf-8"),
        re.S,
    )
    assert block, "the troubleshooting domain has no entry in DOMAIN_ALLOWED_TOOLS"
    return re.findall(r'"([^"]+)"', block.group(1))


def _registered_troubleshooting_tools() -> list[str]:
    source = TROUBLESHOOTING_SERVICE.read_text(encoding="utf-8")
    return re.findall(r"async def (\w+)\(", source)


def test_the_allowlisted_memory_tools_are_the_ones_the_container_registers():
    assert sorted(_allowlisted_troubleshooting_tools()) == sorted(
        _registered_troubleshooting_tools()
    )


def test_the_memory_domain_is_one_the_server_mounts():
    assert 'TROUBLESHOOTING = "troubleshooting"' in FACTORY.read_text(encoding="utf-8")


def test_the_memory_allowlist_does_not_readmit_the_retired_proxy_tool():
    """``ask_user`` is registered on **every** domain server as a shared
    service, and it still asks a model to copy ``SESSION_USER_ID`` out of its
    instructions — a line nothing injects any more, since the approval-gated
    ``request_user_clarification`` replaced the proxy-agent approach. An empty
    allowlist is no filter at all, so the troubleshooting agent would be handed
    a tool that cannot work beside the clarification tool that does.
    """
    assert "ask_user" not in _allowlisted_troubleshooting_tools()
    assert _allowlisted_troubleshooting_tools(), (
        "an empty allowlist applies no filter — every shared tool comes through"
    )
