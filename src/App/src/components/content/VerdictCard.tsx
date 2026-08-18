import React from 'react';
import { Body1, Body1Strong, Caption1 } from '@fluentui/react-components';

import { Verdict } from '@/models/verdict';

export interface VerdictCardProps {
    verdict: Verdict;
}

const VerdictCard: React.FC<VerdictCardProps> = ({ verdict }) => (
    <section className="verdict-record" data-testid="verdict-record">
        <div>
            <Body1Strong>
                {verdict.assignee.name} {verdict.outcome}
            </Body1Strong>
        </div>
        <div><Body1>{verdict.words}</Body1></div>
        {verdict.stoppedLine ? (
            <div>
                <Body1 data-testid="verdict-plan-stopped">{verdict.stoppedLine}</Body1>
            </div>
        ) : null}
        {verdict.provenanceLine ? (
            <div>
                <Caption1 data-testid="verdict-provenance">{verdict.provenanceLine}</Caption1>
            </div>
        ) : null}
    </section>
);

export default VerdictCard;
