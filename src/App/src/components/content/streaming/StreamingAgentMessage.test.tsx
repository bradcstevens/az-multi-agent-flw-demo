import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import renderAgentMessages from './StreamingAgentMessage';
import { AgentMessageType } from '@/models';

const reply = (agent: string) => [
    {
        agent,
        agent_type: AgentMessageType.AI_AGENT,
        content: 'Cash up the tills before the shutters come down.',
    } as any,
];

const Harness: React.FC<{ agent: string }> = ({ agent }) => (
    <>{renderAgentMessages(reply(agent))}</>
);

describe('a reply names the specialist that produced it', () => {
    it('shows the agent that answered, so the assistant is not one black box', () => {
        // The stakeholder's question is whether this is several specialists or
        // a single model wearing hats. The answer has to be on the reply
        // itself: the Agent Team panel lists who *could* have answered, and
        // only this says who did.
        render(<Harness agent="TroubleshootingAgent" />);

        expect(screen.getByText('Troubleshooting')).toBeInTheDocument();
    });

    it('names the SOP specialist on a procedure answer, not the orchestrator', () => {
        render(<Harness agent="StoreSOPAgent" />);

        expect(screen.getByText(/Store SOP/i)).toBeInTheDocument();
    });

    it('omits the agent header when the executor was unnamed', () => {
        render(<Harness agent="" />);

        expect(screen.queryByText('Assistant')).not.toBeInTheDocument();
    });
});
