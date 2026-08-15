import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import {
    AN_AGENT_RESPONDING,
    LOADING_PLAN,
    PLAN_ARRIVING,
    REQUEST_PHASES,
    RequestPhase,
    SENDING,
    advancesTo,
    narrate,
} from './progressNarration';

describe('the phases a request passes through', () => {
    it('runs from nothing said to nothing left to say', () => {
        expect(REQUEST_PHASES).toEqual([
            'idle',
            'sent',
            'routed',
            'connected',
            'working',
            'done',
        ]);
    });

    it('advances to a later phase', () => {
        expect(advancesTo('sent', 'working')).toBe(true);
    });

    it('does not advance to an earlier one, so the story never runs backwards', () => {
        expect(advancesTo('working', 'routed')).toBe(false);
    });

    it('does not advance to the phase it is already in', () => {
        expect(advancesTo('working', 'working')).toBe(false);
    });
});

describe('availability is not a phase of the narration (#79)', () => {
    // The rail states how many specialists are **available** before a question
    // is typed. That is a standing fact about the roster, not a step a request
    // passes through, and folding it in here would make it a claim the phase
    // machine advances *past* — which on the boundary-probe beat would read as
    // the three having taken a question the gate refused above the Lane router.
    it('has no phase for who is available', () => {
        expect(REQUEST_PHASES).not.toContain('available');
    });

    it('never narrates availability in any phase', () => {
        const said = REQUEST_PHASES.flatMap((phase) => [
            narrate({ phase, lane: 'fast', executor: 'TroubleshootingAgent' }) ?? '',
            narrate({ phase }) ?? '',
        ]).join(' ');

        expect(said).not.toMatch(/available|specialists/i);
    });
});

describe('what the surface says in each phase', () => {
    it('says nothing before a question has been asked', () => {
        expect(narrate({ phase: 'idle' })).toBeNull();
    });

    it('says the question is on its way while the POST is in flight', () => {
        expect(narrate({ phase: 'sent' })).toBe('Sending your question...');
    });

    it('names the lane the router decided, in the Lane badge\'s own words', () => {
        expect(narrate({ phase: 'routed', lane: 'fast' })).toBe('Routed — Fast lane');
        expect(narrate({ phase: 'routed', lane: 'deliberate' })).toBe(
            'Routed — Needs approval',
        );
    });

    it('holds the last true statement when a phase reports nothing', () => {
        // `connection_status` is plumbing. A surface that invented the next
        // stage here would be back to narrating stages the system does not have.
        expect(narrate({ phase: 'connected', lane: 'fast' })).toBe('Routed — Fast lane');
    });

    it('names the executor that is actually responding', () => {
        expect(narrate({ phase: 'working', executor: 'Troubleshooting Agent' })).toBe(
            'Troubleshooting Agent is responding...',
        );
    });

    it('resolves an executor spelled the way the wire spells it', () => {
        expect(narrate({ phase: 'working', executor: 'shift_tasks_agent' })).toBe(
            'Shift Tasks Agent is responding...',
        );
    });

    it('falls back to generic wording when the name cannot be resolved', () => {
        // Not "Assistant Agent", which is what the display-name helper returns
        // for an empty string — a name nobody configured, on screen.
        expect(narrate({ phase: 'working', executor: '' })).toBe('An agent is responding...');
        expect(narrate({ phase: 'working' })).toBe('An agent is responding...');
    });

    it('falls back rather than naming the stand-ins the parsers invent', () => {
        // `UnknownAgent` is `parseAgentMessageStreaming`'s own placeholder and
        // `unknown` is the orchestrator's. Rendered as "Unknown Agent" they
        // read as an agent the roster has, which is the surface saying
        // something that is not so.
        expect(narrate({ phase: 'working', executor: 'UnknownAgent' })).toBe(
            'An agent is responding...',
        );
        expect(narrate({ phase: 'working', executor: 'unknown' })).toBe(
            'An agent is responding...',
        );
    });

    it('says nothing once the answer or the plan has arrived', () => {
        expect(narrate({ phase: 'done', lane: 'fast', executor: 'Shift Tasks Agent' })).toBeNull();
    });

    it('holds the lane rather than reverting to the question being sent', () => {
        const phases: RequestPhase[] = ['routed', 'connected'];
        for (const phase of phases) {
            expect(narrate({ phase, lane: 'deliberate' })).toBe('Routed — Needs approval');
        }
    });

    it('says the question is on its way when the router has not reported a lane', () => {
        expect(narrate({ phase: 'routed' })).toBe('Sending your question...');
    });
});

/**
 * One module owns every string shown while a request is in flight (ADR-023).
 *
 * Read off the source tree, because this is a claim about the *repository* and
 * not about any one render: the defect was six components each carrying their
 * own copy, which no component test can see. A component reading these words
 * from anywhere but here is the same fault coming back, and the four rotated
 * ones name stages the system does not have at all.
 */
describe('nowhere else says any of it', () => {
    const sourceFiles = (): string[] => {
        const found: string[] = [];
        const walk = (dir: string) => {
            for (const entry of readdirSync(dir, { withFileTypes: true })) {
                const path = join(dir, entry.name);
                if (entry.isDirectory()) {
                    if (entry.name === 'node_modules') continue;
                    walk(path);
                } else if (/\.(ts|tsx)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
                    found.push(path);
                }
            }
        };
        walk(join(__dirname, '..'));
        return found;
    };

    /**
     * Comments stripped, on `HomeInput.test.tsx`'s finding: a comment naming a
     * string it deleted is not a component carrying it, and a guard that
     * cannot tell them apart makes explaining the change impossible.
     */
    const codeOf = (file: string): string =>
        readFileSync(file, 'utf8')
            .replace(/\/\*[\s\S]*?\*\//g, '')
            .replace(/(^|[^:])\/\/.*$/gm, '$1');

    const carriedBy = (phrase: string): string[] =>
        sourceFiles().filter(
            (file) => !file.endsWith('progressNarration.ts') && codeOf(file).includes(phrase),
        );

    it.each([
        'Initializing AI agents',
        'Generating plan scaffolds',
        'Optimizing task steps',
        'Applying finishing touches',
        'Assigning tasks to specialized agents',
        'Agents are analyzing and researching',
        'Compiling results from agents',
        'Finalizing responses',
    ])('has deleted the authored stage "%s", which nothing emits', (phrase) => {
        expect(carriedBy(phrase)).toEqual([]);
    });

    it.each([
        'Creating a plan',
        'Creating your plan',
        'Creating plan...',
        'Processing your plan and coordinating',
    ])('has removed the component copy "%s"', (phrase) => {
        expect(carriedBy(phrase)).toEqual([]);
    });

    it.each([SENDING, LOADING_PLAN, PLAN_ARRIVING, AN_AGENT_RESPONDING])(
        'is the only place "%s" is written',
        (phrase) => {
            expect(carriedBy(phrase)).toEqual([]);
        },
    );

    it('rotates nothing on a timer', () => {
        // The rotation was a progress bar with no progress behind it. A
        // `setInterval` on the chat page is how it came back last time.
        const page = readFileSync(join(__dirname, '..', 'pages', 'ChatPage.tsx'), 'utf8');
        expect(page).not.toContain('loadingMessages');
        expect(page.match(/setInterval/g) ?? []).toHaveLength(1);
    });
});
