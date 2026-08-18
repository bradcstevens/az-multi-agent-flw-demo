/**
 * The authored framing for an Agent dossier (issues #144, #145).
 *
 * The roster supplies the configuration it was given. These are the surface's
 * words about that configuration, kept together so the dossier makes each
 * claim one way — including the plain-English reading of `user_responses`,
 * which the room is not reading as a config file. The tool map mirrors the
 * backend's allowlist for the store pack's domains; each gloss is surface copy.
 */
export interface AgentDossierTool {
    name: string;
    gloss: string;
}

export const AGENT_DOSSIER_TOOLS: Readonly<Record<string, readonly AgentDossierTool[]>> = {
    sop: [
        {
            name: 'search_store_procedures',
            gloss: 'Searches store procedures',
        },
    ],
    troubleshooting: [
        {
            name: 'list_attempted_steps',
            gloss: 'Lists steps already tried in this shift',
        },
        {
            name: 'record_attempted_steps',
            gloss: 'Records a step tried in this shift',
        },
    ],
    escalation: [
        {
            name: 'draft_service_ticket',
            gloss: 'Drafts a service ticket',
        },
        {
            name: 'get_ticket_status',
            gloss: 'Gets the service ticket status',
        },
    ],
    workforce: [
        {
            name: 'list_workforce_procedures',
            gloss: 'Lists workforce procedures',
        },
        {
            name: 'get_workforce_procedure',
            gloss: 'Gets a workforce procedure',
        },
    ],
};

export const AGENT_DOSSIER_COPY = {
    accessibleName: 'Agent dossier',
    closeLabel: 'Close Agent dossier',
    modelLabel: 'Model',
    available: 'Available',
    spokeInThisAnswer: 'Spoke in this answer',
    availableHasNotSpoken: 'Available, has not spoken',
    systemMessagePreamble: 'System message, verbatim',
    knowledgeBaseLabel: 'Knowledge base',
    followUpQuestionsLabel: 'Follow-up questions',
    followUpQuestionsEnabled: 'Can ask you follow-up questions',
    followUpQuestionsDisabled: 'Will not ask you follow-up questions',
    temperatureLabel: 'Temperature',
    mcpToolsLabel: 'MCP tools',
} as const;
