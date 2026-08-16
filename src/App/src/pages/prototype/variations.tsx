/*
 * PROTOTYPE — throwaway. Not production code. See issue #85.
 *
 * Four radically different answers to "what does a plan worth approving look
 * like", rendering the *same* model so the difference is the surface and never
 * the data. Switch with `?variation=` or the floating bar.
 */

import React, { useState } from 'react';
import {
    Body1,
    Body1Strong,
    Button,
    Caption1,
    Caption1Strong,
    Tag,
    Textarea,
    Title3,
} from '@fluentui/react-components';
import {
    ArrowTurnDownRightRegular,
    BotRegular,
    CheckmarkCircleRegular,
    PersonRegular,
} from '@fluentui/react-icons';
import {
    describeAssignee,
    leavesTheSystem,
    revisionSuggestions,
    whatWaitingMeans,
    whoIsInvolved,
    type ProposedPlan,
    type ProposedStep,
    type ReviewAction,
    type ReviewState,
} from './planApprovalModel';

export interface VariationProps {
    state: ReviewState;
    dispatch: (action: ReviewAction) => void;
}

/* ------------------------------------------------------------------ *
 * Pieces the variations share
 * ------------------------------------------------------------------ */

/**
 * A step's assignee.
 *
 * The prototype's central claim: an agent step and a person step are drawn as
 * different *kinds* of thing, not the same row with a different colour. A
 * person step says who, and says what waiting on them means.
 */
function Who({ step }: { step: ProposedStep }) {
    const person = step.assignee.kind === 'person';
    return (
        <span className={`p-who ${person ? 'p-who--person' : 'p-who--agent'}`}>
            {person ? <PersonRegular aria-hidden="true" /> : <BotRegular aria-hidden="true" />}
            <Caption1Strong>{describeAssignee(step.assignee)}</Caption1Strong>
        </span>
    );
}

/**
 * Nothing has run yet, so nothing may claim it has.
 *
 * The reference image shows "Progress 0/6" and "0%" on a plan that has not
 * started. Under ADR-023 that is a claim no signal reports, so every variation
 * here says the same true thing instead — and says it once.
 */
function NothingHasRunYet() {
    return (
        <Caption1 className="p-nothing-run">
            Nothing has happened yet. Approving is what starts it.
        </Caption1>
    );
}

/** Approve, or send it back. There is no third door — see the model. */
function Verdict({ state, dispatch, compact }: VariationProps & { compact?: boolean }) {
    const [feedback, setFeedback] = useState('');
    const suggestions = revisionSuggestions(state.plan);

    if (state.status === 'approved') {
        return (
            <div className="p-verdict p-verdict--approved">
                <CheckmarkCircleRegular aria-hidden="true" />
                <Body1Strong>Approved. Marcus is being asked now.</Body1Strong>
            </div>
        );
    }

    return (
        <div className={`p-verdict ${compact ? 'p-verdict--compact' : ''}`}>
            <div className="p-verdict__buttons">
                <Button appearance="primary" onClick={() => dispatch({ type: 'approve' })}>
                    Approve and start
                </Button>
                <Button
                    appearance="secondary"
                    disabled={!feedback.trim()}
                    onClick={() => {
                        dispatch({ type: 'revise', feedback: feedback.trim() });
                        setFeedback('');
                    }}
                >
                    Send back with a change
                </Button>
            </div>

            <Caption1 className="p-verdict__prompt">What would you change?</Caption1>
            <div className="p-chips">
                {suggestions.map((suggestion) => (
                    <button
                        key={suggestion}
                        type="button"
                        className="p-chip"
                        onClick={() => setFeedback(suggestion)}
                    >
                        {suggestion}
                    </button>
                ))}
            </div>
            <Textarea
                className="p-verdict__text"
                value={feedback}
                placeholder="…or say it in your own words"
                onChange={(_, data) => setFeedback(data.value)}
                resize="vertical"
            />
        </div>
    );
}

/** "Revision 2, because you said …" — a plan already sent back reads differently. */
function RevisionNote({ plan }: { plan: ProposedPlan }) {
    if (plan.revision === 1) return null;
    return (
        <div className="p-revision">
            <Caption1Strong>Revision {plan.revision}</Caption1Strong>
            <Caption1>You sent the last one back: “{plan.revisedBecause}”</Caption1>
        </div>
    );
}

/* ------------------------------------------------------------------ *
 * 1. Rail — the plan where it lives today
 * ------------------------------------------------------------------ */

export function RailVariation({ state, dispatch }: VariationProps) {
    const { plan } = state;
    return (
        <div className="p-shell">
            <main className="p-conversation">
                <ConversationStub />
            </main>
            <aside className="p-rail">
                <section className="p-rail__plan">
                    <Body1 as="h2" className="p-section-title">
                        Plan Overview
                    </Body1>
                    <RevisionNote plan={plan} />
                    <Caption1 className="p-rail__involves">
                        Reaches {whoIsInvolved(plan)}
                    </Caption1>
                    <NothingHasRunYet />

                    <ol className="p-steps p-steps--tight">
                        {plan.steps.map((step) => (
                            <li
                                key={step.id}
                                className={`p-step ${leavesTheSystem(step) ? 'p-step--outbound' : ''}`}
                            >
                                <Body1 className="p-step__action">{step.action}</Body1>
                                <Who step={step} />
                                {leavesTheSystem(step) && (
                                    <Caption1 className="p-step__waiting">
                                        {whatWaitingMeans(step)}
                                    </Caption1>
                                )}
                            </li>
                        ))}
                    </ol>

                    <Verdict state={state} dispatch={dispatch} compact />
                </section>
                <TransparencyStub />
            </aside>
        </div>
    );
}

/* ------------------------------------------------------------------ *
 * 2. Thread — the plan as something the assistant said
 * ------------------------------------------------------------------ */

export function ThreadVariation({ state, dispatch }: VariationProps) {
    const { plan } = state;
    return (
        <div className="p-shell">
            <main className="p-conversation">
                <ConversationStub />

                <div className="p-bubble">
                    <Caption1Strong className="p-bubble__from">
                        Circle K Frontline Store Assistant
                    </Caption1Strong>
                    <Body1 className="p-bubble__lead">
                        Here is what I would do. Nothing starts until you approve it.
                    </Body1>

                    <div className="p-card">
                        <RevisionNote plan={plan} />
                        <ol className="p-steps">
                            {plan.steps.map((step) => (
                                <li
                                    key={step.id}
                                    className={`p-step ${leavesTheSystem(step) ? 'p-step--outbound' : ''}`}
                                >
                                    <div className="p-step__row">
                                        <Who step={step} />
                                        {leavesTheSystem(step) && (
                                            <Tag size="extra-small" appearance="outline">
                                                waits for a reply
                                            </Tag>
                                        )}
                                    </div>
                                    <Body1 className="p-step__action">{step.action}</Body1>
                                    {leavesTheSystem(step) && (
                                        <Caption1 className="p-step__waiting">
                                            {whatWaitingMeans(step)}
                                        </Caption1>
                                    )}
                                </li>
                            ))}
                        </ol>
                        <NothingHasRunYet />
                    </div>

                    <Verdict state={state} dispatch={dispatch} />
                </div>
            </main>
            <aside className="p-rail">
                <TransparencyStub />
            </aside>
        </div>
    );
}

/* ------------------------------------------------------------------ *
 * 3. Sheet — one thing on the screen, and it is the decision
 * ------------------------------------------------------------------ */

export function SheetVariation({ state, dispatch }: VariationProps) {
    const { plan } = state;
    const open = state.status !== 'approved';

    return (
        <div className="p-shell">
            <main className="p-conversation">
                <ConversationStub />
                {state.status === 'approved' && (
                    <div className="p-bubble">
                        <Verdict state={state} dispatch={dispatch} />
                    </div>
                )}
            </main>
            <aside className="p-rail">
                <TransparencyStub />
            </aside>

            {open && (
                <>
                    <div className="p-scrim" />
                    <section className="p-sheet" role="dialog" aria-label="Approve this plan">
                        <Title3 as="h2">Approve this plan?</Title3>
                        <Body1 className="p-sheet__request">“{plan.request}”</Body1>
                        <RevisionNote plan={plan} />
                        <Caption1 className="p-sheet__involves">
                            This reaches {whoIsInvolved(plan)}.
                        </Caption1>

                        <ol className="p-steps p-steps--sheet">
                            {plan.steps.map((step) => (
                                <li
                                    key={step.id}
                                    className={`p-step ${leavesTheSystem(step) ? 'p-step--outbound' : ''}`}
                                >
                                    <Body1Strong className="p-step__action">
                                        {step.action}
                                    </Body1Strong>
                                    <div className="p-step__row">
                                        <Who step={step} />
                                        {leavesTheSystem(step) && (
                                            <Caption1 className="p-step__waiting">
                                                {whatWaitingMeans(step)}
                                            </Caption1>
                                        )}
                                    </div>
                                </li>
                            ))}
                        </ol>

                        <NothingHasRunYet />
                        <Verdict state={state} dispatch={dispatch} />
                    </section>
                </>
            )}
        </div>
    );
}

/* ------------------------------------------------------------------ *
 * 4. Relay — the people are the spine, the agents are connective tissue
 * ------------------------------------------------------------------ */

export function RelayVariation({ state, dispatch }: VariationProps) {
    const { plan } = state;

    return (
        <div className="p-shell">
            <main className="p-conversation">
                <ConversationStub />

                <div className="p-bubble">
                    <Body1 className="p-bubble__lead">
                        This one has to go past other people. Here is who, and in what order.
                    </Body1>

                    <div className="p-card">
                        <RevisionNote plan={plan} />
                        <ol className="p-relay">
                            {plan.steps.map((step) => {
                                const person = step.assignee.kind === 'person';
                                return (
                                    <li
                                        key={step.id}
                                        className={`p-relay__item ${
                                            person ? 'p-relay__item--person' : 'p-relay__item--agent'
                                        }`}
                                    >
                                        {person ? (
                                            <>
                                                <div className="p-relay__who">
                                                    <PersonRegular aria-hidden="true" />
                                                    <Body1Strong>
                                                        {describeAssignee(step.assignee)}
                                                    </Body1Strong>
                                                </div>
                                                <Body1 className="p-step__action">
                                                    {step.action}
                                                </Body1>
                                                <Caption1 className="p-step__waiting">
                                                    {whatWaitingMeans(step)}
                                                </Caption1>
                                            </>
                                        ) : (
                                            <div className="p-relay__agent">
                                                <ArrowTurnDownRightRegular aria-hidden="true" />
                                                <Caption1>
                                                    {step.action} — {describeAssignee(step.assignee)}
                                                </Caption1>
                                            </div>
                                        )}
                                    </li>
                                );
                            })}
                        </ol>
                        <NothingHasRunYet />
                    </div>

                    <Verdict state={state} dispatch={dispatch} />
                </div>
            </main>
            <aside className="p-rail">
                <TransparencyStub />
            </aside>
        </div>
    );
}

/* ------------------------------------------------------------------ *
 * Context so the variations are judged in place, not on a blank page
 * ------------------------------------------------------------------ */

function ConversationStub() {
    return (
        <div className="p-thread">
            <div className="p-msg p-msg--associate">
                <Body1>Swap my Saturday shift with Marcus Bell</Body1>
            </div>
            <div className="p-msg p-msg--assistant">
                <Caption1Strong className="p-bubble__from">Workforce Agent</Caption1Strong>
                <Body1>
                    Swapping a shift needs the other associate to accept it and your shift lead to
                    approve it (WF-401). The procedure library is simulated.
                </Body1>
            </div>
        </div>
    );
}

/** The rail's real contents, stubbed — they are not what this ticket varies. */
function TransparencyStub() {
    return (
        <div className="p-transparency">
            <Body1 as="h2" className="p-section-title">
                Agent Team
            </Body1>
            <Caption1>Workforce Agent · Shift Tasks Agent · Troubleshooting · Escalation</Caption1>
            <Body1 as="h2" className="p-section-title">
                Grounding
            </Body1>
            <Caption1>WF-401 — Workforce procedure library (simulated)</Caption1>
            <Body1 as="h2" className="p-section-title">
                Token meter
            </Body1>
            <Caption1>Not reported</Caption1>
        </div>
    );
}
