import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import TokenMeterPanel from './TokenMeterPanel';
import {
    emptyMeter,
    recordPolicyBlock,
    recordSourceUsed,
    recordTokenUsage,
    GUARDRAIL_ROW_KEY,
} from '../../models/meter';
import { parseSourceUsed, parseTokenUsage } from '../../models/transparency';
import { allRulesIncludingMediaQueries } from '@/testing/stylesheets';

/** Every selector the stylesheets forbid a line break in, read out of them. */
const COLUMNS = 5;

const nowrapSelectors = (): string[] =>
    allRulesIncludingMediaQueries()
        .filter((rule) => /white-space:\s*nowrap/.test(rule.body))
        .map((rule) => rule.selector);

const wraps = (cell: HTMLElement): boolean =>
    !nowrapSelectors().some((selector) => cell.matches(selector));

const usage = (executorId: string, agentName: string, input: number, output: number) =>
    parseTokenUsage({
        agent_name: agentName,
        executor_id: executorId,
        input_tokens: input,
        output_tokens: output,
        total_tokens: input + output,
    })!;

const sopAnswer = parseSourceUsed({
    platform: 'Copilot Studio',
    source: 'Dataverse',
    agent_name: 'Store SOP Assistant',
    citations: [],
})!;

const models = { shift_tasks_agent: 'gpt-4.1-mini', orchestrator: 'o4-mini' };

describe('the Token meter', () => {
    it('gives every column a share of the rail rather than its content width', () => {
        // Wrapping the names is only half of it. Left to size themselves, the
        // three numeric columns still take whatever their content asks for and
        // the name columns absorb the shortfall, so a five-figure token count
        // squeezes `Agent` to one character a line. `table-layout: fixed` plus
        // a declared share per column is what makes the table's width the
        // rail's rather than its content's — read out of the stylesheet,
        // because nothing in jsdom lays a table out.
        const meter = allRulesIncludingMediaQueries().filter((rule) =>
            rule.selector.split(',').some((part) => part.trim().startsWith('.token-meter')),
        );

        const table = meter.find((rule) => /table-layout:\s*fixed/.test(rule.body));
        expect(table, 'no rule fixes the token meter\u2019s table layout').toBeDefined();

        const shares = meter
            .filter((rule) => /nth-child\(\d+\)/.test(rule.selector))
            .map((rule) => /width:\s*([\d.]+)%/.exec(rule.body)?.[1])
            .filter((share): share is string => share !== undefined)
            .map(Number);

        expect(shares, 'every column needs a declared share').toHaveLength(COLUMNS);
        expect(shares.reduce((total, share) => total + share, 0)).toBe(100);
    });

    it('breaks the names rather than the credits column', () => {
        // Five columns that could not wrap made the table 448px wide inside a
        // 320px rail, so its right-hand end — the estimated Copilot Credits,
        // the number the two-billing-models point is made with — sat outside
        // the box at every width the surface has. The numbers keep their
        // nowrap, because a wrapped figure breaks the side-by-side reading; the
        // agent and model names give the room up instead.
        let meter = recordTokenUsage(emptyMeter(), usage('shift_tasks_agent', 'Shift Tasks Agent', 900, 100));
        meter = recordSourceUsed(meter, sopAnswer);

        render(<TokenMeterPanel meter={meter} models={models} />);

        const row = screen.getByTestId('meter-row-shift_tasks_agent');
        expect(wraps(within(row).getByTestId('meter-agent')), 'the agent name cannot wrap').toBe(true);
        expect(wraps(within(row).getByTestId('meter-model')), 'the model name cannot wrap').toBe(true);
        expect(wraps(within(row).getByTestId('meter-tokens')), 'the token count may wrap').toBe(false);
        expect(wraps(within(row).getByTestId('meter-credits')), 'the credits count may wrap').toBe(false);
        expect(
            wraps(screen.getByTestId('meter-credits-heading')),
            'the credits heading cannot wrap, so it sets the column width on its own',
        ).toBe(true);
    });

    it('shows a row per agent with its call count and tokens', () => {
        let meter = emptyMeter();
        meter = recordTokenUsage(meter, usage('shift_tasks_agent', 'Shift Tasks Agent', 900, 100));
        meter = recordTokenUsage(meter, usage('shift_tasks_agent', 'Shift Tasks Agent', 100, 20));

        render(<TokenMeterPanel meter={meter} models={models} />);

        const row = screen.getByTestId('meter-row-shift_tasks_agent');
        expect(row).toHaveTextContent('Shift Tasks Agent');
        expect(within(row).getByTestId('meter-calls')).toHaveTextContent('2');
        expect(within(row).getByTestId('meter-tokens')).toHaveTextContent('1,120');
    });

    it('puts tokens and estimated Copilot Credits side by side on every row', () => {
        let meter = recordTokenUsage(emptyMeter(), usage('orchestrator', 'Orchestrator', 10, 5));
        meter = recordSourceUsed(meter, sopAnswer);

        render(<TokenMeterPanel meter={meter} models={models} />);

        // Two billing models, visibly not uniform: the Foundry row has tokens
        // and no credits, the Copilot Studio row has credits and no tokens.
        const foundry = screen.getByTestId('meter-row-orchestrator');
        expect(within(foundry).getByTestId('meter-tokens')).toHaveTextContent('15');
        expect(within(foundry).getByTestId('meter-credits')).toHaveTextContent('—');

        const copilot = screen.getByTestId('meter-row-Copilot Studio:Store SOP Assistant');
        expect(within(copilot).getByTestId('meter-credits')).toHaveTextContent('2');
        expect(within(copilot).getByTestId('meter-tokens')).toHaveTextContent('—');
    });

    it('renders an unreported count as a dash and never as a zero', () => {
        const meter = recordSourceUsed(emptyMeter(), sopAnswer);

        render(<TokenMeterPanel meter={meter} models={models} />);

        const row = screen.getByTestId('meter-row-Copilot Studio:Store SOP Assistant');
        expect(within(row).getByTestId('meter-tokens')).toHaveTextContent('—');
        expect(within(row).getByTestId('meter-tokens')).not.toHaveTextContent('0');
    });

    it('renders the refusal as a real zero, which is the row that proves the guardrail is free', () => {
        const meter = recordPolicyBlock(emptyMeter(), {
            kind: 'policy_block',
            code: 'identity_boundary',
            message: 'refused',
        });

        render(<TokenMeterPanel meter={meter} models={models} />);

        const row = screen.getByTestId(`meter-row-${GUARDRAIL_ROW_KEY}`);
        expect(within(row).getByTestId('meter-tokens')).toHaveTextContent('0');
        expect(within(row).getByTestId('meter-credits')).toHaveTextContent('0');
        expect(row).toHaveAttribute('data-billing', 'refused');
    });

    it('shows the model each agent was assigned, so cheap models on cheap work are visible', () => {
        let meter = recordTokenUsage(emptyMeter(), usage('orchestrator', 'Orchestrator', 10, 5));
        meter = recordTokenUsage(meter, usage('shift_tasks_agent', 'Shift Tasks Agent', 10, 5));

        render(<TokenMeterPanel meter={meter} models={models} />);

        expect(
            within(screen.getByTestId('meter-row-orchestrator')).getByTestId('meter-model'),
        ).toHaveTextContent('o4-mini');
        expect(
            within(screen.getByTestId('meter-row-shift_tasks_agent')).getByTestId('meter-model'),
        ).toHaveTextContent('gpt-4.1-mini');
    });

    it('leaves the model column blank rather than inventing an assignment', () => {
        const meter = recordTokenUsage(emptyMeter(), usage('mystery_agent', 'Mystery', 10, 5));

        render(<TokenMeterPanel meter={meter} models={models} />);

        expect(
            within(screen.getByTestId('meter-row-mystery_agent')).getByTestId('meter-model'),
        ).toHaveTextContent('—');
    });

    it('says the credits are an estimate, because they are', () => {
        const meter = recordSourceUsed(emptyMeter(), sopAnswer);

        render(<TokenMeterPanel meter={meter} models={models} />);

        expect(screen.getByTestId('meter-credits-heading')).toHaveTextContent(/est/i);
    });

    it('shows nothing but an explanation before anything has been spent', () => {
        render(<TokenMeterPanel meter={emptyMeter()} models={models} />);

        expect(screen.queryByTestId('meter-table')).not.toBeInTheDocument();
        expect(screen.getByTestId('meter-empty')).toBeInTheDocument();
    });
});
