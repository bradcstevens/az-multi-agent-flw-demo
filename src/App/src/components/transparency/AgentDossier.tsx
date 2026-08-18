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
import { AGENT_DOSSIER_COPY, AGENT_DOSSIER_TOOLS } from '../../models/agentDossier';
import { getAgentDisplayNameWithSuffix } from '../../utils/agentIconUtils';

export interface AgentDossierProps {
    agent: Agent;
    /** Undefined means the home surface, which has no conversation to claim about. */
    participation?: boolean;
    onClose: () => void;
}

const ConfiguredFact: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
    <div className="agent-dossier__fact">
        <dt>{label}</dt>
        <dd>{value}</dd>
    </div>
);

const AgentDossier: React.FC<AgentDossierProps> = ({ agent, participation, onClose }) => {
    /**
     * The knowledge base the agent actually reads: the backend attaches one
     * only where the pack both names it and switches it on, so a name behind
     * `use_knowledge_base: false` is no knowledge base at all.
     */
    const knowledgeBase = agent.use_knowledge_base ? agent.knowledge_base_name || null : null;
    /** A configured `false` is a choice the pack made; an omitted field is not. */
    const followUpQuestions = agent.user_responses ?? null;
    const temperature = agent.temperature ?? null;
    const domain = agent.toolbox_filter;
    const tools =
        agent.use_toolbox &&
        domain &&
        Object.prototype.hasOwnProperty.call(AGENT_DOSSIER_TOOLS, domain)
            ? AGENT_DOSSIER_TOOLS[domain]
            : [];
    const hasConfiguredFacts =
        knowledgeBase !== null || followUpQuestions !== null || temperature !== null;

    return (
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
                        <p className="agent-dossier__participation">
                            {participation === undefined
                                ? AGENT_DOSSIER_COPY.available
                                : participation
                                  ? AGENT_DOSSIER_COPY.spokeInThisAnswer
                                  : AGENT_DOSSIER_COPY.availableHasNotSpoken}
                        </p>
                        {agent.description && (
                            <p className="agent-dossier__description">{agent.description}</p>
                        )}
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
                        {tools.length > 0 && (
                            <>
                                <p className="agent-dossier__tools-label">
                                    {AGENT_DOSSIER_COPY.mcpToolsLabel}
                                </p>
                                <dl className="agent-dossier__tools" data-testid="agent-dossier-tools">
                                    {tools.map((tool) => (
                                        <ConfiguredFact
                                            key={tool.name}
                                            label={tool.name}
                                            value={tool.gloss}
                                        />
                                    ))}
                                </dl>
                            </>
                        )}
                        {hasConfiguredFacts && (
                            <dl
                                className="agent-dossier__configuration"
                                data-testid="agent-dossier-configuration"
                            >
                                {knowledgeBase !== null && (
                                    <ConfiguredFact
                                        label={AGENT_DOSSIER_COPY.knowledgeBaseLabel}
                                        value={knowledgeBase}
                                    />
                                )}
                                {followUpQuestions !== null && (
                                    <ConfiguredFact
                                        label={AGENT_DOSSIER_COPY.followUpQuestionsLabel}
                                        value={
                                            followUpQuestions
                                                ? AGENT_DOSSIER_COPY.followUpQuestionsEnabled
                                                : AGENT_DOSSIER_COPY.followUpQuestionsDisabled
                                        }
                                    />
                                )}
                                {temperature !== null && (
                                    <ConfiguredFact
                                        label={AGENT_DOSSIER_COPY.temperatureLabel}
                                        value={temperature}
                                    />
                                )}
                            </dl>
                        )}
                    </DialogContent>
                </DialogBody>
            </DialogSurface>
        </Dialog>
    );
};

export default AgentDossier;
