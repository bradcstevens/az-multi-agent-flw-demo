"""The Agent dossier's MCP mirror agrees with the backend allowlist (#147).

The browser needs the standing tool attachment before a question is sent, but
the backend is the authority for which tools a domain can call. This contract
reads both implementations and the store pack that selects their domains so a
new or renamed tool cannot become an on-screen false claim.
"""

import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STORE_PACK = (
    REPO_ROOT
    / "content_packs"
    / "store_assistant"
    / "agent_teams"
    / "store_assistant.json"
)
BROWSER_MIRROR = REPO_ROOT / "src" / "App" / "src" / "models" / "agentMcpTools.ts"
BACKEND_CONFIG = REPO_ROOT / "src" / "backend" / "config" / "mcp_config.py"


def _store_pack_domains() -> set[str]:
    """The standing domains that the deployed store-assistant roster names."""
    pack = json.loads(STORE_PACK.read_text(encoding="utf-8"))
    return {agent["toolbox_filter"] for agent in pack["agents"]}


def _browser_mirror() -> dict[str, list[str]]:
    """Read the browser's domain-to-tool mirror without restating its values."""
    source = BROWSER_MIRROR.read_text(encoding="utf-8")
    declaration = re.search(
        r"export const MCP_TOOLS_BY_DOMAIN[^=]*=\s*\{(.*?)\n\};", source, re.S
    )
    assert declaration, "agentMcpTools.ts no longer declares MCP_TOOLS_BY_DOMAIN"

    return {
        domain: re.findall(r"'([^']+)'", tools)
        for domain, tools in re.findall(
            r"^\s*(\w+):\s*\[([^\]]*)\],?$", declaration.group(1), re.M
        )
    }


def _backend_allowlist() -> dict[str, list[str]]:
    """Read the backend's literal DOMAIN_ALLOWED_TOOLS without its live config."""
    module = ast.parse(BACKEND_CONFIG.read_text(encoding="utf-8"))
    declaration = next(
        (
            statement
            for statement in module.body
            if isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "DOMAIN_ALLOWED_TOOLS"
        ),
        None,
    )
    assert declaration, "mcp_config.py no longer declares DOMAIN_ALLOWED_TOOLS"
    return ast.literal_eval(declaration.value)


def test_the_agent_dossier_mirrors_each_domain_the_store_pack_uses():
    domains = _store_pack_domains()
    browser = _browser_mirror()
    backend = _backend_allowlist()

    assert set(browser) == domains
    assert {domain: browser[domain] for domain in domains} == {
        domain: backend[domain] for domain in domains
    }
