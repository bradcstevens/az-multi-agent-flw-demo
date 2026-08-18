/**
 * The authored framing for an Agent dossier (issues #144, #145).
 *
 * The roster supplies the configuration it was given. These are the surface's
 * words about that configuration, kept together so the dossier makes each
 * claim one way — including the plain-English reading of `user_responses`,
 * which the room is not reading as a config file.
 */
export const AGENT_DOSSIER_COPY = {
    accessibleName: 'Agent dossier',
    closeLabel: 'Close Agent dossier',
    modelLabel: 'Model',
    available: 'Available',
    spokeInThisAnswer: 'Spoke in this answer',
    availableHasNotSpoken: 'Available, has not spoken',
    systemMessagePreamble: 'System message, verbatim',
    mcpToolsLabel: 'MCP tools',
    mcpToolGlosses: {
        search_store_procedures: 'Searches store procedures',
        list_attempted_steps: 'Lists troubleshooting steps already tried',
        record_attempted_steps: 'Records a troubleshooting step',
        draft_service_ticket: 'Drafts a simulated service ticket',
        get_ticket_status: 'Gets a simulated ticket status',
        list_workforce_procedures: 'Lists workforce procedures',
        get_workforce_procedure: 'Gets a workforce procedure',
    },
    knowledgeBaseLabel: 'Knowledge base',
    followUpQuestionsLabel: 'Follow-up questions',
    followUpQuestionsEnabled: 'Can ask you follow-up questions',
    followUpQuestionsDisabled: 'Will not ask you follow-up questions',
    temperatureLabel: 'Temperature',
} as const;
