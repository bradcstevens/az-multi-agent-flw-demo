"""The Agent dossier's MCP tool mirror agrees with the backend (issue #147).

The dossier states which MCP tools an agent holds before a question is asked, so
the browser must resolve its ``toolbox_filter`` itself. The backend independently
filters that same domain with ``DOMAIN_ALLOWED_TOOLS``. Nothing on the wire
reconciles those two copies; a drift is a dossier that tells the room an agent
can use a tool it never received, or hides one it did.
"""

import ast
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_CONFIG = REPO_ROOT / "src" / "backend" / "config" / "mcp_config.py"
DOSSIER_COPY = REPO_ROOT / "src" / "App" / "src" / "models" / "agentDossier.ts"
STORE_PACK = (
    REPO_ROOT
    / "content_packs"
    / "store_assistant"
    / "agent_teams"
    / "store_assistant.json"
)


def _backend_allowed_tools() -> dict[str, list[str]]:
    """Read the backend's actual allowlist without importing its app configuration."""
    module = ast.parse(MCP_CONFIG.read_text(encoding="utf-8"))
    assignment = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DOMAIN_ALLOWED_TOOLS"
        ),
        None,
    )
    assert assignment and assignment.value, "mcp_config.py no longer declares DOMAIN_ALLOWED_TOOLS"
    return ast.literal_eval(assignment.value)


def _browser_tools_for(domain: str) -> list[str]:
    """Read the mirror's literal tool names from its frontend copy module."""
    source = DOSSIER_COPY.read_text(encoding="utf-8")
    block = re.search(
        rf"^    {re.escape(domain)}:\s*\[(.*?)^    \],",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert block, f"agentDossier.ts has no tool mirror for {domain!r}"
    return re.findall(r"name:\s*'([^']+)'", block.group(1))


def _store_pack_domains() -> set[str]:
    team = json.loads(STORE_PACK.read_text(encoding="utf-8"))
    return {
        agent["toolbox_filter"]
        for agent in team["agents"]
        if agent.get("toolbox_filter")
    }


def test_the_agent_dossier_mirrors_every_toolbox_domain_the_store_pack_names():
    allowed_tools = _backend_allowed_tools()

    for domain in _store_pack_domains():
        assert _browser_tools_for(domain) == allowed_tools[domain]
