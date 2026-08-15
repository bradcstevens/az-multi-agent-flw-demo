import React from 'react';
import { Body1Strong, Caption1 } from '@fluentui/react-components';
import { ShieldCheckmark20Regular } from '@fluentui/react-icons';

import { PolicyBlock } from '../../api/policyBlock';
import '../../styles/policyBlock.css';

/**
 * The **Policy block**, rendered as policy (issue #14, ADR-014).
 *
 * One component for both surfaces that can be refused. The home screen was the
 * only one until **Resume** (#77) made a personal question typable from inside
 * a chat; the second surface writing its own copy of this is the second
 * surface quietly saying something slightly different about the same refusal,
 * which is the thing the demo can least afford to be vague about.
 *
 * Deliberately not a toast and deliberately not an error: a governed refusal
 * that reads as a bug is the confusion ADR-014 exists to remove, and it must
 * be visibly a different object from a retrieval miss, which arrives as an
 * answer rather than as a failed request.
 *
 * The `children` slot is where the **Mocked unlock**'s door goes — inside the
 * refusal, so the boundary and the way through it are visibly one thing. The
 * chat surface passes none: the door is the home screen's rehearsed beat, and
 * a second one is a decision no ADR has taken.
 */
export const STORE_SCOPED_ASSISTANT = 'Store-scoped assistant';

export interface PolicyBlockNoticeProps {
    block: PolicyBlock;
    children?: React.ReactNode;
}

const PolicyBlockNotice: React.FC<PolicyBlockNoticeProps> = ({ block, children }) => (
    <div
        className="policy-block"
        role="note"
        aria-live="polite"
        data-testid="policy-block"
        data-policy-code={block.code}
    >
        <div className="policy-block__header">
            <ShieldCheckmark20Regular aria-hidden="true" />
            <Body1Strong>{STORE_SCOPED_ASSISTANT}</Body1Strong>
        </div>
        <Caption1>{block.message}</Caption1>
        {children}
    </div>
);

export default PolicyBlockNotice;
