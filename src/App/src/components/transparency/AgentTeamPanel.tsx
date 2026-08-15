import React from 'react';
import { Body1Strong, Caption1, Caption1Strong } from '@fluentui/react-components';
import { PeopleTeam20Regular } from '@fluentui/react-icons';

import { TeamConfig } from '../../models/Team';
import {
    AVAILABILITY_NOTE,
    NO_ROSTER_MESSAGE,
    availabilityHeading,
    resolveAvailability,
} from '../../models/agentAvailability';
import { getAgentDisplayNameWithSuffix } from '../../utils/agentIconUtils';
import { SECTION_HEADING, SUBSECTION_HEADING } from '../../models/headingOutline';

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
 *
 * It states **availability**, never participation (issue #65). The roster says
 * who *could* answer and is known before the question is typed; who *did* is
 * named one at a time by the **Progress narration** as each specialist speaks.
 * Conflating them puts "3 agents identified" over the beat where the
 * **Identity boundary gate** refuses first and the **Token meter** below it
 * renders a measured `0`.
 *
 * Which is why it is on the **home surface**'s rail too (issue #79). There it
 * has only the one source — the roster — and states the one claim that is true
 * before anything has been sent. That beat is the boundary probe's: the refusal
 * happens on the home surface, so the panel and the meter's real `0` are two
 * panels apart on the one screen where a participation claim would be caught
 * out immediately.
 */
export interface AgentTeamPanelProps {
    /**
     * The workflow roster, from the plan-fetch response's `team`.
     *
     * Optional since #79: the **home surface** has no conversation to have a
     * roster of, and passing `null` for one there would be a null standing in
     * for a question that has not been asked.
     */
    team?: TeamConfig | null;
    /** The plan's flat list of member names, used only when there is no roster. */
    plan?: string[] | null;
    /**
     * The **store assistant roster** the app is already holding — `selectedTeam`,
     * in Redux since `HomePage`'s mount and needing nothing from the wire. It is
     * the chat surface's loading window and the home surface's *only* source.
     */
    available?: TeamConfig | null;
    /** Its size, from `selectTeamAgentCount`. Not recounted here. */
    availableCount?: number;
}

const AgentTeamPanel: React.FC<AgentTeamPanelProps> = ({
    team = null,
    plan = null,
    available = null,
    availableCount = 0,
}) => {
    const { agents, count } = resolveAvailability(team, plan, available, availableCount);

    return (
        <section className="transparency-panel" data-testid="agent-team-panel">
            <Body1Strong as={SECTION_HEADING} className="transparency-panel__title">
                <PeopleTeam20Regular aria-hidden="true" /> Agent Team
            </Body1Strong>

            {agents.length === 0 ? (
                <Caption1 data-testid="agent-team-empty" className="transparency-panel__empty">
                    {NO_ROSTER_MESSAGE}
                </Caption1>
            ) : (
                <>
                    <Caption1Strong
                        as={SUBSECTION_HEADING}
                        data-testid="agent-team-availability"
                        className="agent-team__availability"
                    >
                        {availabilityHeading(count)}
                    </Caption1Strong>
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
                    <Caption1 data-testid="agent-team-note" className="agent-team__note">
                        {AVAILABILITY_NOTE}
                    </Caption1>
                </>
            )}
        </section>
    );
};

export default AgentTeamPanel;
