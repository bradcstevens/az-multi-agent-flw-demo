import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';

import renderAgentMessages from './StreamingAgentMessage';
import StreamingBufferMessage from './StreamingBufferMessage';
import { AgentMessageType } from '@/models';
import { sourceFiles } from '@/testing/stylesheets';

/**
 * A reply's Markdown headings stay out of the surface's outline (#57).
 *
 * The words come from a language model, and `react-markdown` renders `#` as a
 * real `<h1>`. Left alone, one reply puts a second top-level heading on the
 * plan surface — above the panels that explain where that reply came from and
 * what it cost.
 */

const MARKDOWN = [
    '# Closing the store',
    '',
    'Cash up the tills before the shutters come down.',
    '',
    '## Tills',
    '',
    '### Safe drop',
].join('\n');

const AgentReply: React.FC = () => (
    <>
        {renderAgentMessages([
            {
                agent: 'ShiftTasksAgent',
                agent_type: AgentMessageType.AI_AGENT,
                content: MARKDOWN,
            } as any,
        ])}
    </>
);

describe('a reply may not head the surface', () => {
    it('renders no heading at all from a finalised reply', () => {
        render(<AgentReply />);

        expect(screen.getByText('Closing the store')).toBeInTheDocument();
        expect(screen.queryAllByRole('heading')).toEqual([]);
    });

    it('renders no heading at all from the streaming buffer', () => {
        // The buffer shows the same words a moment earlier and rendered them
        // with react-markdown's defaults, so the `h1` arrived there first.
        render(<StreamingBufferMessage streamingMessageBuffer={MARKDOWN} />);

        expect(screen.queryAllByRole('heading')).toEqual([]);
    });

    it('is asked of every Markdown reply on the surface, not of the two that broke', () => {
        // Read out of the source: the failure this guards is the *next*
        // `ReactMarkdown`, and two of the three that exist today shipped with
        // react-markdown's default headings precisely because nothing asked.
        const unpoliced = sourceFiles()
            .filter((path) => readFileSync(path, 'utf8').includes('<ReactMarkdown'))
            .filter((path) => !readFileSync(path, 'utf8').includes('replyHeadings'));

        expect(unpoliced, 'renders a model\'s Markdown without the heading policy').toEqual([]);
    });
});
