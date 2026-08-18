import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import AgentTeamPanel from './AgentTeamPanel';
import { agentMatchesExecutor, modelsByExecutor } from '../../models/roster';
import { AVAILABILITY_NOTE, NO_ROSTER_MESSAGE } from '../../models/agentAvailability';
import { SUBSECTION_HEADING } from '../../models/headingOutline';
import { TeamConfig } from '../../models/Team';

const roster = {
    agents: [
        { input_key: '', type: '', name: 'TroubleshootingAgent', deployment_name: 'o4-mini' },
        { input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' },
        { input_key: '', type: '', name: 'EscalationAgent' },
    ],
} as unknown as TeamConfig;

describe('the Agent Team panel', () => {
    it('is populated from the workflow roster, so it is not empty with Plan review off', () => {
        // The fast lane produces no plan object at all. A panel reading the
        // plan's team would be empty for most of the walkthrough.
        render(<AgentTeamPanel team={roster} plan={null} />);

        expect(screen.getAllByTestId(/^agent-team-member/)).toHaveLength(3);
    });

    it('shows each agent with the model it was assigned', () => {
        render(<AgentTeamPanel team={roster} plan={null} />);

        const member = screen.getByTestId('agent-team-member-TroubleshootingAgent');
        expect(member).toHaveTextContent('Troubleshooting');
        expect(within(member).getByTestId('agent-team-model')).toHaveTextContent('o4-mini');
    });

    it('leaves the model blank rather than inventing one', () => {
        render(<AgentTeamPanel team={roster} plan={null} />);

        expect(
            within(screen.getByTestId('agent-team-member-EscalationAgent')).getByTestId(
                'agent-team-model',
            ),
        ).toHaveTextContent('—');
    });

    it('falls back to the plan roster when there is no team on the plan data', () => {
        render(<AgentTeamPanel team={null} plan={['TroubleshootingAgent']} />);

        expect(screen.getAllByTestId(/^agent-team-member/)).toHaveLength(1);
    });

    it('says so when it knows of no agents at all', () => {
        render(<AgentTeamPanel team={null} plan={null} />);

        expect(screen.getByTestId('agent-team-empty')).toBeInTheDocument();
    });
});

describe('the Agent Team panel during the loading window (issue #65)', () => {
    it('names the specialists standing by before the plan fetch returns', () => {
        // `planData` is null for the whole wait, so this panel used to render
        // "No agent roster loaded for this conversation." two inches from a
        // spinner claiming the agents were being initialised. The roster was
        // in Redux the whole time.
        render(<AgentTeamPanel team={null} plan={null} available={roster} availableCount={3} />);

        expect(screen.getAllByTestId(/^agent-team-member/)).toHaveLength(3);
        expect(screen.queryByTestId('agent-team-empty')).not.toBeInTheDocument();
    });

    it('counts them in a heading over the names, not instead of them', () => {
        render(<AgentTeamPanel team={null} plan={null} available={roster} availableCount={3} />);

        const heading = screen.getByTestId('agent-team-availability');
        expect(heading).toHaveTextContent('3 specialists available');
        expect(heading.tagName.toLowerCase()).toBe(SUBSECTION_HEADING);
        expect(screen.getByTestId('agent-team-member-ShiftTasksAgent')).toBeInTheDocument();
    });

    it('takes the count from the roster selector rather than from the rendered list', () => {
        // The two cannot disagree in practice — `selectTeamAgentCount` is
        // derived from the same team — but the panel must not be the place
        // that recounts, or there are two counts to keep in step.
        render(<AgentTeamPanel team={null} plan={null} available={roster} availableCount={7} />);

        expect(screen.getByTestId('agent-team-availability')).toHaveTextContent(
            '7 specialists available',
        );
    });

    it('says availability, never that these three took the question', () => {
        // The boundary probe is refused above the Lane router, so on that beat
        // the number that participate is zero and the Token meter says so.
        render(<AgentTeamPanel team={null} plan={null} available={roster} availableCount={3} />);

        expect(screen.getByTestId('agent-team-note')).toHaveTextContent(AVAILABILITY_NOTE);
        expect(screen.queryByText(/identified|assigned|selected|chosen/i)).not.toBeInTheDocument();
    });

    it('prefers this conversation\u2019s own roster once it has one', () => {
        const conversation = {
            agents: [{ input_key: '', type: '', name: 'EscalationAgent' }],
        } as unknown as TeamConfig;

        render(
            <AgentTeamPanel
                team={conversation}
                plan={null}
                available={roster}
                availableCount={3}
            />,
        );

        expect(screen.getAllByTestId(/^agent-team-member/)).toHaveLength(1);
        expect(screen.getByTestId('agent-team-availability')).toHaveTextContent(
            '1 specialist available',
        );
    });

    it('still says there is no roster when there genuinely is none', () => {
        // That state is real and the panel is right to say so. It just must
        // not say it about a team the app is already holding.
        render(<AgentTeamPanel team={null} plan={null} available={null} availableCount={0} />);

        expect(screen.getByTestId('agent-team-empty')).toHaveTextContent(NO_ROSTER_MESSAGE);
        expect(screen.queryByTestId('agent-team-availability')).not.toBeInTheDocument();
    });
});

describe('modelsByExecutor', () => {
    it('maps an executor id to the model the roster assigned it', () => {
        expect(modelsByExecutor(roster)).toMatchObject({
            TroubleshootingAgent: 'o4-mini',
            ShiftTasksAgent: 'gpt-4.1-mini',
        });
    });

    it('answers to the snake_case form the executor stream uses', () => {
        expect(modelsByExecutor(roster).troubleshooting_agent).toBe('o4-mini');
    });

    it('answers to the display, snake_case, and lower-cased executor spellings', () => {
        const agent = roster.agents[1];

        expect(agentMatchesExecutor(agent, 'Shift Tasks Agent')).toBe(true);
        expect(agentMatchesExecutor(agent, 'shift_tasks_agent')).toBe(true);
        expect(agentMatchesExecutor(agent, 'shifttasksagent')).toBe(true);
    });

    it('omits an agent the roster assigned no model', () => {
        expect(modelsByExecutor(roster).EscalationAgent).toBeUndefined();
    });

    it('is empty rather than undefined when there is no roster', () => {
        expect(modelsByExecutor(null)).toEqual({});
    });
});
