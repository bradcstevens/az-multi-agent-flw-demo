import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import AgentTeamPanel from './AgentTeamPanel';
import { modelsByExecutor } from '../../models/roster';
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

    it('omits an agent the roster assigned no model', () => {
        expect(modelsByExecutor(roster).EscalationAgent).toBeUndefined();
    });

    it('is empty rather than undefined when there is no roster', () => {
        expect(modelsByExecutor(null)).toEqual({});
    });
});
