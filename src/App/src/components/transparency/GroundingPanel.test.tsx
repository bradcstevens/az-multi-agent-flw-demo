import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import GroundingPanel, {
    COPILOT_STUDIO_PLATFORM,
    DIRECT_LINE_ROUTE_SEGMENT,
    ROUTE_ORIGIN,
    SOP_ASK_ROUTE_SEGMENT,
    SOP_TOOL_ROUTE_SEGMENT,
} from './GroundingPanel';
import { parseSourceUsed } from '../../models/transparency';

const FRONTEND_SOURCE = join(__dirname, '..', '..');

function sourceFiles(directory: string): string[] {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const path = join(directory, entry.name);
        return entry.isDirectory()
            ? sourceFiles(path)
            : entry.isFile()
              ? [path]
              : [];
    });
}

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

const otherPlatform = parseSourceUsed({
    platform: 'Another platform',
    source: 'Another source',
    citations: [],
});

describe('the Grounding panel', () => {
    it('names the platform that answered, so the hop is visible as a hop', () => {
        render(<GroundingPanel source={cited} />);

        expect(screen.getByTestId('grounding-platform')).toHaveTextContent('Copilot Studio');
    });

    it('names every observed hop to the Dataverse source rather than SharePoint', () => {
        render(<GroundingPanel source={cited} />);

        const route = screen.getByTestId('grounding-route');
        expect(route).toHaveTextContent(
            'Foundry orchestratorsearch_store_procedures (MCP tool, plain HTTP)POST /sop/askDirect LineCopilot StudioDataverse',
        );
        expect(route).not.toHaveTextContent(/SharePoint/i);
    });

    it('exports the observed Copilot Studio route segments for the runbook contract', () => {
        expect(ROUTE_ORIGIN).toBe('Foundry orchestrator');
        expect(SOP_TOOL_ROUTE_SEGMENT).toBe('search_store_procedures (MCP tool, plain HTTP)');
        expect(SOP_ASK_ROUTE_SEGMENT).toBe('POST /sop/ask');
        expect(DIRECT_LINE_ROUTE_SEGMENT).toBe('Direct Line');
        expect(COPILOT_STUDIO_PLATFORM).toBe('Copilot Studio');
    });

    it('does not claim the Copilot Studio transport for another platform', () => {
        render(<GroundingPanel source={otherPlatform} />);

        const route = screen.getByTestId('grounding-route');
        expect(route).toHaveTextContent('Foundry orchestratorAnother platformAnother source');
        expect(route).not.toHaveTextContent('search_store_procedures');
        expect(route).not.toHaveTextContent('POST /sop/ask');
        expect(route).not.toHaveTextContent('Direct Line');
    });

    it('never names the nonexistent Direct Line MCP component anywhere in frontend source', () => {
        // Searched rather than enumerated: a list of the files it might appear
        // in goes stale the first time somebody adds a file. Case-insensitively,
        // because the component does not exist in any casing, and this is the
        // one panel whose whole purpose is that its claims are checkable.
        const forbiddenName = ['Direct', ' Line', ' MCP', ' server'].join('');
        const pattern = new RegExp(forbiddenName, 'i');
        const offenders = sourceFiles(FRONTEND_SOURCE).filter((path) =>
            pattern.test(readFileSync(path, 'utf8')),
        );

        expect(offenders).toEqual([]);
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
