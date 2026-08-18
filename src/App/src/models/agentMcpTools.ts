import { AGENT_DOSSIER_COPY } from './agentDossier';

type McpToolName = keyof typeof AGENT_DOSSIER_COPY.mcpToolGlosses;

/**
 * The browser's standing-domain mirror. Unknown domains deliberately have no
 * entry, because guessing a tool would make the Agent dossier claim more than
 * the roster says.
 */
export const MCP_TOOLS_BY_DOMAIN: Readonly<Record<string, readonly McpToolName[]>> = {
    sop: ['search_store_procedures'],
    troubleshooting: ['list_attempted_steps', 'record_attempted_steps'],
    escalation: ['draft_service_ticket', 'get_ticket_status'],
    workforce: ['list_workforce_procedures', 'get_workforce_procedure'],
};

export const mcpToolsForDomain = (domain?: string): readonly McpToolName[] => {
    if (!domain) {
        return [];
    }

    // An own-property check, not a plain lookup: the mirror is an object
    // literal, so a bare `MCP_TOOLS_BY_DOMAIN[domain]` answers `Object` for
    // `constructor` and a function for `toString` — truthy values that survive
    // the `??` and reach the dossier as something it cannot render.
    return Object.prototype.hasOwnProperty.call(MCP_TOOLS_BY_DOMAIN, domain)
        ? MCP_TOOLS_BY_DOMAIN[domain]
        : [];
};
