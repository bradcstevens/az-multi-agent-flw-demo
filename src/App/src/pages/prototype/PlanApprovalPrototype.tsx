/*
 * PROTOTYPE — throwaway. Not production code. See issue #85.
 *
 * Route: /prototype/plan-approval?variation=rail|thread|sheet|relay
 *
 * The question: **what does a plan worth approving look like** in *this*
 * surface — one assistant, a transparency rail, a narration that claims only
 * what a signal reports — rather than in the upstream accelerator's
 * (`docs/images/MACAE-GP2.png`), which counts humans it never asks anything of
 * and shows a progress bar over work that has not started.
 *
 * Four variations, same model, switch at the bottom of the screen. Narrow the
 * window past 900px to see each one at the Stacking breakpoint.
 */

import React, { useMemo, useReducer, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Body1, Caption1, Caption1Strong } from '@fluentui/react-components';
import {
    INITIAL_REVIEW,
    NARRATION_PHASES,
    review,
    type NarrationPhase,
} from './planApprovalModel';
import {
    RailVariation,
    RelayVariation,
    SheetVariation,
    ThreadVariation,
    type VariationProps,
} from './variations';
import './prototype.css';

const VARIATIONS: Array<{
    key: string;
    label: string;
    blurb: string;
    render: (props: VariationProps) => JSX.Element;
}> = [
    {
        key: 'rail',
        label: 'In the rail',
        blurb:
            'Where the plan lives today. The rail is already the place the associate looks for evidence, and it is the column that survives the stacking breakpoint. But the decision sits beside the conversation rather than in it, and on a phone it is below the fold.',
        render: (props) => <RailVariation {...props} />,
    },
    {
        key: 'thread',
        label: 'In the conversation',
        blurb:
            'The plan is something the assistant said, and approving is answering it. Follows ADR-025 — a Chat is the unit of the surface — and matches the Rehearsed reply chips the associate has already used. The rail goes back to being only evidence.',
        render: (props) => <ThreadVariation {...props} />,
    },
    {
        key: 'sheet',
        label: 'As a sheet',
        blurb:
            'The decision takes the screen. Hardest to ignore and the easiest to read on a phone, but it interrupts, and an associate cannot look back at what they asked for while deciding.',
        render: (props) => <SheetVariation {...props} />,
    },
    {
        key: 'relay',
        label: 'As a relay',
        blurb:
            'People are the spine; the specialists are connective tissue between them. Answers "who is this going to reach" first, which is the question a plan worth approving actually raises — but it buries the work the agents do.',
        render: (props) => <RelayVariation {...props} />,
    },
];

export default function PlanApprovalPrototype() {
    const [params, setParams] = useSearchParams();
    const [state, dispatch] = useReducer(review, INITIAL_REVIEW);
    const [phaseIndex, setPhaseIndex] = useState(NARRATION_PHASES.length - 1);

    const active = useMemo(() => {
        const key = params.get('variation');
        return VARIATIONS.find((variation) => variation.key === key) ?? VARIATIONS[0];
    }, [params]);

    const phase = NARRATION_PHASES[phaseIndex];
    const planIsUp = phase.phase === ('Done' as NarrationPhase);

    return (
        <div className="p-root">
            <header className="p-banner">
                <Caption1Strong>PROTOTYPE — issue #85. Throwaway; not on main.</Caption1Strong>
                <Caption1>
                    What does a plan worth approving look like? Same plan in all four — only the
                    surface changes. Narrow the window past 900px for the Stacking breakpoint.
                </Caption1>
            </header>

            <section className="p-narration" aria-label="What the surface says while the plan is being made">
                <div className="p-narration__head">
                    <Caption1Strong>Before the plan arrives (ADR-023)</Caption1Strong>
                    <Caption1>
                        Every phase is an observable event. There is deliberately no “agents
                        selected” phase — no such signal exists.
                    </Caption1>
                </div>
                <div className="p-narration__phases">
                    {NARRATION_PHASES.map((entry, index) => (
                        <button
                            key={entry.phase}
                            type="button"
                            className={`p-phase ${index === phaseIndex ? 'p-phase--on' : ''}`}
                            onClick={() => setPhaseIndex(index)}
                        >
                            {entry.phase}
                        </button>
                    ))}
                </div>
                <div className="p-narration__says">
                    <Body1>
                        {phase.says ? (
                            <>
                                Surface says: <strong>“{phase.says}”</strong>
                            </>
                        ) : (
                            <>Surface says nothing — the indicator is gone.</>
                        )}
                    </Body1>
                    <Caption1>Signal: {phase.signal}</Caption1>
                </div>
            </section>

            <div className="p-stage">
                {planIsUp ? (
                    active.render({ state, dispatch })
                ) : (
                    <div className="p-waiting">
                        <Body1>{phase.says}</Body1>
                        <Caption1>
                            No plan is on screen yet. It appears on the plan_approval_request frame
                            and not before — a plan the associate can see before it exists is the
                            claim ADR-023 forbids.
                        </Caption1>
                    </div>
                )}
            </div>

            <nav className="p-switcher" aria-label="Variation">
                <div className="p-switcher__blurb">
                    <Caption1Strong>{active.label}</Caption1Strong>
                    <Caption1>{active.blurb}</Caption1>
                </div>
                <div className="p-switcher__buttons">
                    {VARIATIONS.map((variation) => (
                        <button
                            key={variation.key}
                            type="button"
                            className={`p-switch ${
                                variation.key === active.key ? 'p-switch--on' : ''
                            }`}
                            onClick={() => setParams({ variation: variation.key })}
                        >
                            {variation.label}
                        </button>
                    ))}
                </div>
            </nav>
        </div>
    );
}
