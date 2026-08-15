import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import TokenMeterPanel from './TokenMeterPanel';
import {
    emptyMeter,
    recordPolicyBlock,
    recordSourceUsed,
    recordTokenUsage,
    GUARDRAIL_ROW_KEY,
    GUARDRAIL_ROW_NAME,
} from '../../models/meter';
import { parseSourceUsed, parseTokenUsage } from '../../models/transparency';
import { Rule, SRC, allRules, allRulesIncludingMediaQueries } from '@/testing/stylesheets';

/** Every selector the stylesheets forbid a line break in, read out of them. */
const COLUMNS = 5;

/** The store assistant roster, read out of the pack that authors it. */
const STORE_PACK = join(
    SRC,
    '..',
    '..',
    '..',
    'content_packs',
    'store_assistant',
    'agent_teams',
    'store_assistant.json',
);

/** The store assistant roster, read out of the pack that authors it. */
const roster = (): { name: string; deployment_name: string }[] => {
    const pack = JSON.parse(readFileSync(STORE_PACK, 'utf8'));
    const agents = pack.agents || [];
    expect(agents.length, 'the store pack authors no roster to render').toBeGreaterThan(0);
    return agents;
};

const rosterNames = (): string[] => roster().map((agent) => agent.name);

const rosterDeployments = (): string[] => roster().map((agent) => agent.deployment_name);

/**
 * How wide a word is in the meter's own type — 12px at weight 600, in Fluent's
 * Segoe UI stack — as a sum of per-character advances.
 *
 * jsdom lays nothing out, so a check about whether a word fits its column has
 * to model the font, and the model is the part that has to be honest. The one
 * this replaces was a single average of `6px` a character described as rounded
 * up. It was rounded *down*: `Workforce` measures 6.80px a character and
 * `boundary` 7.04, and `Troubleshooting` is 96.4px against the 90 that average
 * predicted. So the guard agreed with a column six pixels too narrow, and #70's
 * first fix shipped with every test green and the word still snapped after
 * eleven characters in a browser.
 *
 * These advances are measured — `measureText` in Chromium at `600 12px` in the
 * stack below — and each is rounded **up** to the nearest quarter-pixel, so a
 * sum is never less than the width a browser lays out. It over-states
 * `Troubleshooting` by 3.4px, which is the direction an assertion about fitting
 * should err in. A character nobody measured counts as the widest there is,
 * because a name in a script this table has never seen should fail loudly
 * rather than pass by omission.
 */
const ADVANCE_12PX_600: ReadonlyArray<readonly [number, string]> = [
    [3.25, ' '],
    [3.5, 'ijl'],
    [3.75, 'I'],
    [4, ".,'/"],
    [4.75, 'f'],
    [5, 't()'],
    [5.25, 'r'],
    [6, '1-'],
    [6.75, 'sxz'],
    [7, 'Jackvy'],
    [7.25, 'FLe7'],
    [7.5, 'Ehnou'],
    [7.75, 'bdgpq2'],
    [8, 'PST035'],
    [8.25, 'BRZ4689'],
    [8.5, 'KVY'],
    [8.75, 'AX'],
    [9, 'CD&'],
    [9.25, 'GHNU'],
    [9.5, 'OQ'],
    [10, 'w'],
    [10.75, 'M'],
    [11, 'm'],
    [12, 'W'],
];

const ADVANCE = new Map<string, number>(
    ADVANCE_12PX_600.flatMap(([px, chars]) => [...chars].map((char) => [char, px] as const)),
);

const WIDEST_ADVANCE = Math.max(...ADVANCE_12PX_600.map(([px]) => px));

const wordPx = (word: string): number =>
    [...word].reduce((total, char) => total + (ADVANCE.get(char) ?? WIDEST_ADVANCE), 0);

/**
 * The runs a browser may not break inside.
 *
 * Whitespace and a hyphen are wrap opportunities, so `Store SOP Assistant` is
 * three runs and a deployment like `gpt-5.4-mini` is three more. What has to
 * fit its column is the widest run, not the whole string — the roster's names
 * are *expected* to wrap, and #70 is about where.
 */
const unbreakableRuns = (text: string): string[] =>
    text
        .split(/\s+/)
        .filter(Boolean)
        .flatMap((word) => word.split(/(?<=-)/));

const topLevel = (selector: string): Rule => {
    const rule = allRules().find((candidate) => candidate.selector === selector);
    expect(rule, `no stylesheet declares ${selector}`).toBeDefined();
    return rule!;
};

/** One declaration's value in one rule, or nothing. Last one wins, as CSS has it. */
const declared = (rule: Rule, property: string): string | undefined =>
    Array.from(
        rule.body.matchAll(new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*([^;]+)`, 'g')),
    ).pop()?.[1].trim();

const declaration = (rule: Rule, property: string): string => {
    const found = declared(rule, property);
    expect(found, `${rule.selector} declares no ${property}`).toBeDefined();
    return found!;
};

/** A selector's weight, enough of CSS's arithmetic to order two rules. */
const specificity = (selector: string): number => {
    const ids = (selector.match(/#[\w-]+/g) || []).length;
    const classes = (
        selector.match(/\.[\w-]+|\[[^\]]+\]|:{1,2}[\w-]+(?:\([^)]*\))?/g) || []
    ).length;
    const elements = (selector.match(/(?:^|[\s>+~])([a-z][\w-]*)/gi) || []).length;
    return ids * 10_000 + classes * 100 + elements;
};

/**
 * What a rendered cell's declaration actually comes out as — the winning rule,
 * not the last one somebody wrote.
 *
 * The fault this exists for is one this suite shipped and a browser caught:
 * `.token-meter__name` is one class, `.token-meter th` is a class *and* an
 * element, so a padding declared on the first loses to the second and changes
 * nothing at all. A check that reads the declaration it expects to win agrees
 * with itself while the surface does something else.
 */
const effective = (cell: Element, property: string): string => {
    let winner: { weight: number; order: number; value: string } | undefined;

    allRules().forEach((rule, order) => {
        const value = declared(rule, property);
        if (value === undefined) return;
        rule.selector
            .split(',')
            .map((part) => part.trim())
            .filter((part) => part && cell.matches(part))
            .forEach((part) => {
                // Rules are walked in source order, so an equal weight later in
                // the stylesheet wins, exactly as the cascade has it.
                const weight = specificity(part);
                if (!winner || weight >= winner.weight) {
                    winner = { weight, order, value };
                }
            });
    });

    expect(winner, `nothing declares ${property} for the cell`).toBeDefined();
    return winner!.value;
};

const pxIn = (value: string, index = 0): number => {
    const lengths = Array.from(value.matchAll(/(-?[\d.]+)px/g)).map((match) => Number(match[1]));
    expect(lengths.length, `no length in ${JSON.stringify(value)}`).toBeGreaterThan(index);
    return lengths[index];
};

/** A shorthand's horizontal half: `14px` is 14, `6px 4px` is 4. */
const horizontal = (value: string): number => {
    const lengths = Array.from(value.matchAll(/(-?[\d.]+)px/g)).map((match) => Number(match[1]));
    return lengths.length > 1 ? lengths[1] : lengths[0];
};

/**
 * The pixels of text a rendered name cell's column actually has, read out of
 * the whole chain rather than assumed.
 *
 * #70's own arithmetic stopped at the rail (320px less its 32px of padding) and
 * came out 30px optimistic: the panel inside it is a card with 14px of padding
 * and a hairline border of its own, so the table is nearer 257px than 288. The
 * chain is read here — rail, panel, column share, and the padding the cascade
 * settles on — because every one of those numbers is a decision somebody may
 * revisit, and the column that stops fitting is not the one they were changing.
 *
 * The share is a share of the **table**, and the padding comes out of it. The
 * application's global reset makes every box a border-box (`:root` declares it
 * and `*` inherits it), so a percentage on a cell sizes the whole cell and its
 * padding is spent inside that, not added outside it. Measured against
 * Chromium with that reset in place, the five columns come out at exactly their
 * declared shares of 257px and the reading below is exact.
 *
 * Which box model this is has decided the answer twice. Read as content-box the
 * Agent column looks 4px narrower than it is and the Calls column 4px wider,
 * and it was a harness missing the reset — not the stylesheet — that made a
 * seven-point Calls column look wide enough for a two-digit count.
 */
const columnTextPx = (cell: Element, column: number): number => {
    const rail = topLevel('.transparency-rail');
    const railInner =
        pxIn(declaration(rail, 'width')) -
        2 * horizontal(declaration(rail, 'padding')) -
        pxIn(declaration(rail, 'border-left'));

    const panel = topLevel('.transparency-panel');
    const table =
        railInner -
        2 * horizontal(declaration(panel, 'padding')) -
        2 * pxIn(declaration(panel, 'border'));

    const share = Number(
        /([\d.]+)%/.exec(declaration(topLevel(`.token-meter th:nth-child(${column})`), 'width'))![1],
    );

    return (table * share) / 100 - 2 * horizontal(effective(cell, 'padding'));
};

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

    it('names each agent once, without the suffix the column heading already carries', () => {
        // The column is headed `Agent`, so a cell reading `Troubleshooting
        // Agent` says the noun twice — and the second one is what does not
        // fit. Every other panel in the rail already goes through the shared
        // roster helper; this was the one place reading `agent_name` raw off
        // the wire, which is why it was also the one place breaking a name
        // mid-word.
        const meter = recordTokenUsage(
            emptyMeter(),
            usage('TroubleshootingAgent', 'Troubleshooting Agent', 900, 100),
        );

        render(<TokenMeterPanel meter={meter} models={models} />);

        const name = within(screen.getByTestId('meter-row-TroubleshootingAgent')).getByTestId(
            'meter-agent',
        );
        expect(name).toHaveTextContent('Troubleshooting');
        expect(name.textContent).not.toMatch(/agent/i);
    });

    it('gives every name in the roster room to break on a space rather than mid-word', () => {
        // #70: `Troubleshooting Agent` rendered as `Troubleshoo` / `ting
        // Agent` in the panel whose job is to be the most credible thing in
        // the room. Two faults, and this is the second: the suffix went, and
        // the column still has to hold the word that is left. Every roster
        // name the pack authors is rendered here and measured against the room
        // the stylesheets actually give it — `Store SOP Assistant` broken at
        // its spaces is legible, `Troubleshoo`/`ting` is not.
        let meter = emptyMeter();
        rosterNames().forEach((name, index) => {
            // The pack's own `WorkforceAgent` rather than the wire's
            // `Workforce Agent`: the backend humanises the executor id and the
            // helper splits camelCase itself, so both spellings land on the
            // same displayed name, and this one is the repository's.
            meter = recordTokenUsage(meter, usage(`executor-${index}`, name, 10, 5));
        });
        meter = recordSourceUsed(meter, sopAnswer);
        meter = recordPolicyBlock(meter, {
            kind: 'policy_block',
            code: 'identity_boundary',
            message: 'refused',
        });

        render(<TokenMeterPanel meter={meter} models={models} />);

        screen.getAllByTestId('meter-agent').forEach((cell) => {
            const room = columnTextPx(cell, 1);
            unbreakableRuns(cell.textContent || '').forEach((run) => {
                expect(
                    wordPx(run),
                    `${JSON.stringify(run)} needs ${wordPx(run).toFixed(1)}px and the Agent ` +
                        `column gives it ${room.toFixed(1)}px, so a browser breaks it mid-word`,
                ).toBeLessThanOrEqual(room);
            });
        });
    });

    it('gives the model column room for the longest run of a deployment name', () => {
        // The other column that carries words. It is where the Agent column's
        // room came from (#70), so it is the one that a further point taken for
        // a longer agent name would silently cost — and a deployment set as
        // `gp` / `t-` is the same fault one column to the right.
        let meter = emptyMeter();
        const deployments: Record<string, string> = {};
        rosterNames().forEach((name, index) => {
            const key = `executor-${index}`;
            meter = recordTokenUsage(meter, usage(key, name, 10, 5));
            deployments[key] = rosterDeployments()[index];
        });

        render(<TokenMeterPanel meter={meter} models={deployments} />);

        screen.getAllByTestId('meter-model').forEach((cell) => {
            const room = columnTextPx(cell, 2);
            unbreakableRuns(cell.textContent || '').forEach((run) => {
                expect(
                    wordPx(run),
                    `${JSON.stringify(run)} needs ${wordPx(run).toFixed(1)}px and the Model ` +
                        `column gives it ${room.toFixed(1)}px. A deployment name may wrap at its ` +
                        'own hyphens and may not be broken anywhere else',
                ).toBeLessThanOrEqual(room);
            });
        });
    });

    it('shows a row per agent with its call count and tokens', () => {
        let meter = emptyMeter();
        meter = recordTokenUsage(meter, usage('shift_tasks_agent', 'Shift Tasks Agent', 900, 100));
        meter = recordTokenUsage(meter, usage('shift_tasks_agent', 'Shift Tasks Agent', 100, 20));

        render(<TokenMeterPanel meter={meter} models={models} />);

        const row = screen.getByTestId('meter-row-shift_tasks_agent');
        expect(row).toHaveTextContent('Shift Tasks');
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

        // And the cross-platform row is still the agent the tenant published.
        // It has no `Agent` suffix to lose, so the shared helper leaves it
        // alone — which is worth asserting, because that helper does rewrite
        // what it is handed, and this is the one name on the table the
        // audience is being asked to believe belongs to another platform.
        expect(within(copilot).getByTestId('meter-agent')).toHaveTextContent(
            'Store SOP Assistant',
        );
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

    it('leaves its own row label alone, because the gate is not an agent', () => {
        // The roster helper is for names that arrived off the wire. This row's
        // name is the meter's own constant and reads as the **Identity
        // boundary gate** is written everywhere else — put through a helper
        // that title-cases what it is given, the one row whose zeros are
        // measurements starts calling itself something the glossary does not.
        const meter = recordPolicyBlock(emptyMeter(), {
            kind: 'policy_block',
            code: 'identity_boundary',
            message: 'refused',
        });

        render(<TokenMeterPanel meter={meter} models={models} />);

        expect(
            within(screen.getByTestId(`meter-row-${GUARDRAIL_ROW_KEY}`)).getByTestId('meter-agent'),
        ).toHaveTextContent(GUARDRAIL_ROW_NAME);
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
