/**
 * The authored framing for an Agent dossier (issue #144).
 *
 * The roster supplies the configuration it was given. These are the surface's
 * words about that configuration, kept together so the dossier makes each
 * claim one way.
 */
export const AGENT_DOSSIER_COPY = {
    accessibleName: 'Agent dossier',
    closeLabel: 'Close Agent dossier',
    modelLabel: 'Model',
    systemMessagePreamble: 'System message, verbatim',
} as const;
