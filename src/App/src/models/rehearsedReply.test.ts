import { describe, it, expect } from 'vitest';
import { rehearsedRepliesFor } from './rehearsedReply';
import { TeamConfig } from './Team';

const task = (overrides: Partial<TeamConfig['starting_tasks'][number]> = {}) => ({
    id: 'task-223-troubleshooting',
    name: 'The coffee brewer is down',
    prompt: 'The coffee brewer is down. It is not brewing on the left head.',
    created: '',
    creator: '',
    logo: 'Wrench',
    lane: 'fast',
    rehearsed_replies: ['I switched it off at the wall and back on again.'],
    ...overrides,
});

const team = (tasks = [task()]) =>
    ({ starting_tasks: tasks } as unknown as TeamConfig);

describe('resolving the rehearsed replies for a plan', () => {
    it('gives the replies of the Quick Task the plan was started from', () => {
        expect(
            rehearsedRepliesFor(
                team(),
                'The coffee brewer is down. It is not brewing on the left head.',
            ),
        ).toEqual(['I switched it off at the wall and back on again.']);
    });

    it('gives nothing for a goal no Quick Task declares', () => {
        // Free-typed input, which is the same thing an edited prompt is. The
        // declaration does not survive an edit (#26), and neither do the
        // rehearsed answers to it: replies written for one question, offered
        // under another, are a tap that answers something nobody asked.
        expect(rehearsedRepliesFor(team(), 'the walk-in cooler is warm')).toEqual([]);
    });

    it('gives nothing for a Quick Task that authored none', () => {
        // Only one beat asks a question back. Every other tap is answered, and
        // a chip under it would be a second way to start a turn.
        expect(
            rehearsedRepliesFor(team([task({ rehearsed_replies: undefined })]), task().prompt),
        ).toEqual([]);
    });

    it('gives nothing when there is no team and nothing when there is no goal', () => {
        // The surface may say nothing. Both are real states: the assistant is
        // absent on a deployment that never got the pack (#25), and a plan
        // reloaded before its data arrives has no goal yet.
        expect(rehearsedRepliesFor(undefined, task().prompt)).toEqual([]);
        expect(rehearsedRepliesFor(team(), undefined)).toEqual([]);
    });

    it('ignores the whitespace and casing a prompt picks up in a text box', () => {
        // The prompt makes a round trip through a textarea and back off the
        // wire as the plan's initial goal. A trailing newline is not an edit.
        expect(
            rehearsedRepliesFor(team(), `  ${task().prompt.toUpperCase()}\n`),
        ).toEqual(['I switched it off at the wall and back on again.']);
    });

    it('reads only strings, so an unreadable reply cannot reach the surface', () => {
        // The field arrives from an uploaded team definition and is
        // deliberately unvalidated on the backend, as `lane` is.
        expect(
            rehearsedRepliesFor(
                team([task({ rehearsed_replies: ['ok', 7, null, ' '] as unknown as string[] })]),
                task().prompt,
            ),
        ).toEqual(['ok']);
    });
});
