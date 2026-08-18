import React from 'react';
import { Body1Strong, Caption1 } from '@fluentui/react-components';
import { Person20Regular } from '@fluentui/react-icons';

import { PersonalAnswer } from '../../models/personalAnswer';
import SimulatedBadge from '../branding/SimulatedBadge';
import '../../styles/personalAnswer.css';

/**
 * The **Personal answer** — the previously refused question, answered (#27).
 *
 * Rendered exactly where the **Policy block** was, because the before-and-after
 * is the point: the audience watched one question be declined, and the delta
 * between that surface and this one is the licensing and governance
 * conversation the demo exists to open.
 *
 * **The record is shown whole**, in the order the backend stated it. Picking
 * out the field the question asked about would be a third classifier behind the
 * two the gate already has, and a third classifier can report the wrong number
 * — which, for a claim about somebody's pay, is the worst thing this system
 * could say.
 *
 * The **Simulated label** is unconditional. Every figure here was authored for
 * the walkthrough, no payroll system was queried, and a stakeholder who
 * discovers that afterwards has stopped believing the rest of the demo.
 */
export interface PersonalAnswerCardProps {
    answer: PersonalAnswer;
}

const PersonalAnswerCard: React.FC<PersonalAnswerCardProps> = ({ answer }) => (
    <div
        className="personal-answer"
        role="note"
        aria-live="polite"
        data-testid="personal-answer"
    >
        <div className="personal-answer__header">
            <Person20Regular aria-hidden="true" />
            <Body1Strong data-testid="personal-answer-name">
                {answer.displayName}
            </Body1Strong>
            <SimulatedBadge what="This associate record" />
        </div>

        {answer.role && (
            <Caption1 className="personal-answer__role">{answer.role}</Caption1>
        )}

        {answer.facts.length > 0 && (
            <dl className="personal-answer__facts">
                {answer.facts.map((fact) => (
                    <div className="personal-answer__row" key={fact.label}>
                        <dt className="personal-answer__label">
                            <Caption1>{fact.label}</Caption1>
                        </dt>
                        <dd className="personal-answer__value">
                            <Caption1>{fact.value}</Caption1>
                        </dd>
                    </div>
                ))}
            </dl>
        )}

        {answer.provenanceLine && (
            <Caption1 className="personal-answer__note">{answer.provenanceLine}</Caption1>
        )}
    </div>
);

export default PersonalAnswerCard;
