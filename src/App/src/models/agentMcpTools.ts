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

    return MCP_TOOLS_BY_DOMAIN[domain] ?? [];
};
