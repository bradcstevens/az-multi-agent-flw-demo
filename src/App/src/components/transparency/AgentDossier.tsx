import React from 'react';
import {
    Button,
    Dialog,
    DialogBody,
    DialogContent,
    DialogSurface,
    DialogTitle,
} from '@fluentui/react-components';
import { Dismiss20Regular } from '@fluentui/react-icons';

import { Agent } from '../../models/Team';
import { AGENT_DOSSIER_COPY } from '../../models/agentDossier';
import { getAgentDisplayNameWithSuffix } from '../../utils/agentIconUtils';

export interface AgentDossierProps {
    agent: Agent;
    onClose: () => void;
}

const AgentDossier: React.FC<AgentDossierProps> = ({ agent, onClose }) => (
    <Dialog open onOpenChange={(_, data) => !data.open && onClose()}>
        <DialogSurface aria-label={AGENT_DOSSIER_COPY.accessibleName} className="agent-dossier">
            <DialogBody>
                <div className="agent-dossier__header">
                    <DialogTitle as="div">{getAgentDisplayNameWithSuffix(agent.name)}</DialogTitle>
                    <Button
                        appearance="subtle"
                        aria-label={AGENT_DOSSIER_COPY.closeLabel}
                        icon={<Dismiss20Regular />}
                        onClick={onClose}
                    />
                </div>
                <DialogContent className="agent-dossier__content">
                    {agent.deployment_name && (
                        <dl className="agent-dossier__model">
                            <dt>{AGENT_DOSSIER_COPY.modelLabel}</dt>
                            <dd>{agent.deployment_name}</dd>
                        </dl>
                    )}
                    {agent.description && <p className="agent-dossier__description">{agent.description}</p>}
                    {agent.system_message && (
                        <>
                            <p className="agent-dossier__preamble">
                                {AGENT_DOSSIER_COPY.systemMessagePreamble}
                            </p>
                            <pre className="agent-dossier__prompt" data-testid="agent-dossier-prompt">
                                {agent.system_message}
                            </pre>
                        </>
                    )}
                </DialogContent>
            </DialogBody>
        </DialogSurface>
    </Dialog>
);

export default AgentDossier;
