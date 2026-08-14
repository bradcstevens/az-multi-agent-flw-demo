import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import GroundingPanel from './GroundingPanel';
import { parseSourceUsed } from '../../models/transparency';

const cited = parseSourceUsed({
    platform: 'Copilot Studio',
    source: 'Dataverse',
    agent_name: 'Store SOP Assistant',
    conversation_id: 'abc123',
    tool_query: 'What are the steps for closing the store tonight?',
    retrieval_query: 'How do I close the store?',
    citations: [
        {
            position: 1,
            name: 'SOP-102 Store Closing Procedure.docx',
            snippet: 'Cash up the tills before the shutters come down…',
            url: null,
        },
    ],
});

const uncited = parseSourceUsed({
    platform: 'Copilot Studio',
    source: 'Dataverse',
    agent_name: 'Store SOP Assistant',
    citations: [],
});

describe('the Grounding panel', () => {
    it('names the platform that answered, so the hop is visible as a hop', () => {
        render(<GroundingPanel source={cited} />);

        expect(screen.getByTestId('grounding-platform')).toHaveTextContent('Copilot Studio');
    });

    it('shows the route the answer took, ending at Dataverse rather than SharePoint', () => {
        render(<GroundingPanel source={cited} />);

        const route = screen.getByTestId('grounding-route');
        expect(route).toHaveTextContent('Foundry orchestrator');
        expect(route).toHaveTextContent('Copilot Studio');
        expect(route).toHaveTextContent('Dataverse');
        expect(route).not.toHaveTextContent(/SharePoint/i);
    });

    it('carries both SOP queries so a retrieval miss can be attributed', () => {
        render(<GroundingPanel source={cited} />);

        const panel = screen.getByTestId('grounding-panel');
        expect(panel).toHaveAttribute(
            'data-tool-query',
            'What are the steps for closing the store tonight?',
        );
        expect(panel).toHaveAttribute('data-retrieval-query', 'How do I close the store?');
    });

    it('shows the document detail — the second half of the pair of signals', () => {
        render(<GroundingPanel source={cited} />);

        expect(screen.getByText('SOP-102 Store Closing Procedure.docx')).toBeInTheDocument();
        expect(screen.getByText(/Cash up the tills/)).toBeInTheDocument();
    });

    it('shows the route with nothing retrieved when the answer cited nothing', () => {
        render(<GroundingPanel source={uncited} />);

        // The rehearsed out-of-corpus probe: the hop happened, and nothing came
        // back. The route still renders — suppressing it would delete the beat.
        expect(screen.getByTestId('grounding-route')).toBeInTheDocument();
        expect(screen.getByTestId('grounding-miss')).toBeInTheDocument();
    });

    it('is a retrieval miss and not a policy block — the two must never be confused', () => {
        render(<GroundingPanel source={uncited} />);

        expect(screen.queryByTestId('policy-block')).not.toBeInTheDocument();
        expect(screen.getByTestId('grounding-miss')).toHaveTextContent(/no matching/i);
    });

    it('renders a document the backend could not name without calling it a miss', () => {
        const unnamed = parseSourceUsed({
            platform: 'Copilot Studio',
            source: 'Dataverse',
            agent_name: 'Store SOP Assistant',
            citations: [{ position: 1, name: '', snippet: 'Cash up the tills…', url: null }],
        });

        render(<GroundingPanel source={unnamed} />);

        // A document came back. Saying "no matching procedure" here would be
        // the panel reporting an honest miss that never happened.
        expect(screen.queryByTestId('grounding-miss')).not.toBeInTheDocument();
        expect(screen.getByText(/Cash up the tills/)).toBeInTheDocument();
        expect(screen.getByTestId('grounding-citations')).toHaveTextContent(/unnamed document/i);
    });

    it('claims nothing at all before a signal arrives', () => {
        render(<GroundingPanel source={null} />);

        expect(screen.queryByTestId('grounding-platform')).not.toBeInTheDocument();
        expect(screen.queryByTestId('grounding-route')).not.toBeInTheDocument();
        expect(screen.getByTestId('grounding-empty')).toBeInTheDocument();
    });
});
