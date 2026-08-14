import React from 'react';
import { Body1Strong, Caption1 } from '@fluentui/react-components';
import { GaugeRegular } from '@fluentui/react-icons';

import { MeterRow, MeterState } from '../../models/meter';

/**
 * The Token meter (issue #24, R7).
 *
 * The audience is being shown that **two billing models are not uniform**, so
 * the table puts tokens and estimated Copilot Credits side by side and lets
 * each row fill only its own column. A single blended "cost" number would hide
 * the very thing the panel is for.
 *
 * The rendering rule that carries #23's discipline into pixels:
 *
 * - `null` renders **`—`**. Nobody reported it. The Copilot Studio row has no
 *   token count because Direct Line gives us none, and a `0` there would be the
 *   panel inventing a measurement.
 * - `0` renders **`0`**. It is a measurement. Only the guardrail row has one,
 *   and that row is the proof that a refused request adds nothing — which it
 *   can only be if nothing is the only thing that looks like nothing.
 *
 * The **model** column is the per-agent assignment, read from the workflow's
 * agent roster (`deployment_name`), which is how the architecture's "cheap
 * models on cheap work" claim becomes checkable rather than asserted. An agent
 * the roster does not name renders `—` rather than a guess.
 */
export interface TokenMeterPanelProps {
    meter: MeterState;
    /** Executor id → deployment name, from the workflow's agent roster. */
    models?: Record<string, string>;
}

/** `—` for not reported; the number, grouped, for anything we were told. */
const count = (value: number | null): string =>
    value === null ? '—' : value.toLocaleString('en-US');

const rowTitle = (row: MeterRow): string => {
    if (row.billing === 'refused') {
        return (
            'Refused by the identity boundary gate before the lane router and before ' +
            'orchestration — no agent ran, so this zero is measured rather than missing.'
        );
    }
    if (row.billing === 'credits') {
        return (
            'Billed in Copilot Credits, not tokens: 2 estimated per generative answer. ' +
            'Copilot Studio reports no token count over Direct Line, so there is none to show.'
        );
    }
    return 'Billed in tokens on the Foundry deployment named here.';
};

const TokenMeterPanel: React.FC<TokenMeterPanelProps> = ({ meter, models = {} }) => (
    <section className="transparency-panel" data-testid="token-meter-panel">
        <Body1Strong className="transparency-panel__title">
            <GaugeRegular aria-hidden="true" /> What this cost
        </Body1Strong>

        {meter.rows.length === 0 ? (
            <Caption1 data-testid="meter-empty" className="transparency-panel__empty">
                Nothing has been spent yet. Each agent appears here as it runs, with tokens or
                estimated Copilot Credits depending on which platform bills it.
            </Caption1>
        ) : (
            <table className="token-meter" data-testid="meter-table">
                <thead>
                    <tr>
                        <th scope="col" className="token-meter__name">
                            Agent
                        </th>
                        <th scope="col" className="token-meter__name">
                            Model
                        </th>
                        <th scope="col">Calls</th>
                        <th scope="col">Tokens</th>
                        <th scope="col" data-testid="meter-credits-heading">
                            Est. Copilot Credits
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {meter.rows.map((row) => (
                        <tr
                            key={row.key}
                            data-testid={`meter-row-${row.key}`}
                            data-billing={row.billing}
                            title={rowTitle(row)}
                        >
                            <th scope="row" className="token-meter__name" data-testid="meter-agent">
                                {row.agentName}
                            </th>
                            <td className="token-meter__name" data-testid="meter-model">
                                {models[row.key] || '—'}
                            </td>
                            <td className="token-meter__number" data-testid="meter-calls">
                                {row.calls}
                            </td>
                            <td className="token-meter__number" data-testid="meter-tokens">
                                {count(row.totalTokens)}
                            </td>
                            <td className="token-meter__number" data-testid="meter-credits">
                                {count(row.credits)}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        )}
    </section>
);

export default TokenMeterPanel;
