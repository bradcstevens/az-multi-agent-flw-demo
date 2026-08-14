import React from 'react';
import { Body1Strong, Caption1, Caption1Strong } from '@fluentui/react-components';
import { PeopleTeam20Regular } from '@fluentui/react-icons';

import { TeamConfig } from '../../models/Team';
import { rosterAgents } from '../../models/roster';
import { getAgentDisplayNameWithSuffix } from '../../utils/agentIconUtils';
import { SECTION_HEADING } from '../../models/headingOutline';

/**
 * The Agent Team panel (issue #24).
 *
 * Populated from the **workflow's agent roster**, not from the plan. With Plan
 * review off (ADR-013) the plan object is null, and a panel sourced from it
 * would be empty on the Fast lane — which is where most of the walkthrough
 * runs, so the audience would see "no agents assigned" throughout the part of
 * the demo that is meant to show several specialists at work.
 *
 * Each agent shows the model it was assigned. That is the point of the column:
 * the architecture claims it puts cheap models on cheap work, and this is where
 * the claim becomes checkable. An agent with no assignment shows `—` rather
 * than a default that nobody configured.
 */
export interface AgentTeamPanelProps {
    /** The workflow roster, from the plan-fetch response's `team`. */
    team: TeamConfig | null;
    /** The plan's flat list of member names, used only when there is no roster. */
    plan: string[] | null;
}

const AgentTeamPanel: React.FC<AgentTeamPanelProps> = ({ team, plan }) => {
    const agents = rosterAgents(team, plan);

    return (
        <section className="transparency-panel" data-testid="agent-team-panel">
            <Body1Strong as={SECTION_HEADING} className="transparency-panel__title">
                <PeopleTeam20Regular aria-hidden="true" /> Agent Team
            </Body1Strong>

            {agents.length === 0 ? (
                <Caption1 data-testid="agent-team-empty" className="transparency-panel__empty">
                    No agent roster loaded for this conversation.
                </Caption1>
            ) : (
                <ul className="agent-team">
                    {agents.map((agent) => (
                        <li
                            key={agent.name}
                            className="agent-team__member"
                            data-testid={`agent-team-member-${agent.name}`}
                        >
                            <Caption1Strong>
                                {getAgentDisplayNameWithSuffix(agent.name)}
                            </Caption1Strong>
                            <Caption1
                                data-testid="agent-team-model"
                                title="The model deployment this agent is assigned"
                            >
                                {agent.deployment_name || '—'}
                            </Caption1>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
};

export default AgentTeamPanel;
