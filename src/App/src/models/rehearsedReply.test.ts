import { describe, it, expect } from 'vitest';
import {
    followOnTaskFor,
    rehearsedRepliesFor,
    ticketStatusReplyFor,
} from './rehearsedReply';
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

    describe('resolving the follow-on task for a plan', () => {
        it('finds the task authored as the matching task follow-on', () => {
            const escalation = task({
                id: 'task-223-escalation',
                name: "I can't fix it",
                follow_on: undefined,
            });

            expect(
                followOnTaskFor(
                    team([task({ follow_on: escalation.id }), escalation]),
                    task().prompt,
                ),
            ).toEqual(escalation);
        });

        it('gives nothing when the plan did not start from a task with a follow-on', () => {
            expect(followOnTaskFor(team(), task().prompt)).toBeUndefined();
            expect(followOnTaskFor(team([task({ follow_on: 'missing-task' })]), task().prompt)).toBeUndefined();
        });
    });

    it('gives the escalation task authored ticket-status reply to its own Chat', () => {
        const escalation = {
            ...task({
                id: 'task-223-escalation',
                name: "I can't fix it",
                prompt: 'I have tried everything and I need someone to come out.',
            }),
            ticket_status_reply: {
                prompt: "What's happening with my ticket?",
                lane: 'fast',
            },
        };

        expect(ticketStatusReplyFor(team([escalation]), escalation.prompt)).toEqual(
            escalation.ticket_status_reply,
        );
    });

    it('finds the ticketing reply after its status turn became the latest plan', () => {
        const escalation = {
            ...task({
                id: 'task-223-escalation',
                name: "I can't fix it",
                prompt: 'I have tried everything and I need someone to come out.',
                ticket_on_approval: true,
            }),
            ticket_status_reply: {
                prompt: "What's happening with my ticket?",
                lane: 'fast',
            },
        };

        expect(ticketStatusReplyFor(team([escalation]), escalation.ticket_status_reply.prompt)).toEqual(
            escalation.ticket_status_reply,
        );
    });

    it('keeps ticketing continuations separate when a team has more than one', () => {
        const coffeeTicket = {
            ...task({
                id: 'task-223-coffee',
                ticket_on_approval: true,
            }),
            ticket_status_reply: {
                prompt: 'What is happening with the coffee ticket?',
                lane: 'fast',
            },
        };
        const coolerTicket = {
            ...task({
                id: 'task-223-cooler',
                ticket_on_approval: true,
            }),
            ticket_status_reply: {
                prompt: 'What is happening with the cooler ticket?',
                lane: 'fast',
            },
        };

        expect(
            ticketStatusReplyFor(team([coffeeTicket, coolerTicket]), coolerTicket.ticket_status_reply.prompt),
        ).toEqual(coolerTicket.ticket_status_reply);
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
