import { describe, it, expect } from 'vitest';

import {
    parsePresenterAlert,
    parseSourceUsed,
    parseTokenUsage,
} from './transparency';

/**
 * The WebSocket message contract, from the frontend side.
 *
 * Every payload here is the shape `src/backend/transparency/payloads.py`
 * actually puts on the wire — `asdict()` of the three dataclasses, wrapped by
 * `send_status_update_async` as `{type, data}`. These parsers are given the
 * `data`.
 */
describe('parseSourceUsed', () => {
    it('reads the platform, the source and the citations off the wire', () => {
        const source = parseSourceUsed({
            platform: 'Copilot Studio',
            source: 'Dataverse',
            agent_name: 'Store SOP Assistant',
            conversation_id: 'abc123',
            citations: [
                {
                    position: 1,
                    name: 'SOP-102 Store Closing Procedure.docx',
                    snippet: 'Close the tills, then…',
                    url: null,
                },
            ],
        });

        expect(source).not.toBeNull();
        expect(source!.platform).toBe('Copilot Studio');
        expect(source!.source).toBe('Dataverse');
        expect(source!.agentName).toBe('Store SOP Assistant');
        expect(source!.conversationId).toBe('abc123');
        expect(source!.citations).toHaveLength(1);
        expect(source!.citations[0].name).toBe('SOP-102 Store Closing Procedure.docx');
        expect(source!.citations[0].snippet).toBe('Close the tills, then…');
        expect(source!.citations[0].url).toBeNull();
    });

    it('keeps an answer that cited nothing — the honest miss is a beat, not a bug', () => {
        const source = parseSourceUsed({
            platform: 'Copilot Studio',
            source: 'Dataverse',
            agent_name: 'Store SOP Assistant',
            citations: [],
        });

        expect(source).not.toBeNull();
        expect(source!.citations).toEqual([]);
    });

    it('refuses a payload that names no platform', () => {
        expect(
            parseSourceUsed({ source: 'Dataverse', agent_name: 'Store SOP Assistant' }),
        ).toBeNull();
    });

    it('refuses anything that is not a payload at all', () => {
        expect(parseSourceUsed(null)).toBeNull();
        expect(parseSourceUsed(undefined)).toBeNull();
        expect(parseSourceUsed('Copilot Studio')).toBeNull();
        expect(parseSourceUsed(42)).toBeNull();
    });
});

describe('parseTokenUsage', () => {
    it('reads the counts and the executor they are attributed to', () => {
        const usage = parseTokenUsage({
            agent_name: 'Troubleshooting Agent',
            executor_id: 'troubleshooting_agent',
            input_tokens: 1200,
            output_tokens: 340,
            total_tokens: 1540,
        });

        expect(usage).not.toBeNull();
        expect(usage!.agentName).toBe('Troubleshooting Agent');
        expect(usage!.executorId).toBe('troubleshooting_agent');
        expect(usage!.inputTokens).toBe(1200);
        expect(usage!.outputTokens).toBe(340);
        expect(usage!.totalTokens).toBe(1540);
    });

    it('refuses a payload with no executor to attribute the cost to', () => {
        expect(
            parseTokenUsage({ agent_name: 'Troubleshooting Agent', total_tokens: 10 }),
        ).toBeNull();
    });

    it('refuses counts that are not numbers rather than reading them as zero', () => {
        expect(
            parseTokenUsage({
                agent_name: 'Troubleshooting Agent',
                executor_id: 'troubleshooting_agent',
                input_tokens: 'lots',
                output_tokens: null,
                total_tokens: undefined,
            }),
        ).toBeNull();
    });
});

describe('parsePresenterAlert', () => {
    it('reads the title and the content the server chose', () => {
        const alert = parsePresenterAlert({
            title: 'Shift task due',
            content: 'The coffee station deep clean is due before the 15:00 handover.',
            timestamp: '2026-08-13T09:00:00+00:00',
        });

        expect(alert).not.toBeNull();
        expect(alert!.title).toBe('Shift task due');
        expect(alert!.content).toContain('coffee station');
        expect(alert!.timestamp).toBe('2026-08-13T09:00:00+00:00');
    });

    it('refuses an alert with nothing to say', () => {
        expect(parsePresenterAlert({ title: 'Shift task due', content: '' })).toBeNull();
        expect(parsePresenterAlert({ content: 'something happened' })).toBeNull();
    });
});
