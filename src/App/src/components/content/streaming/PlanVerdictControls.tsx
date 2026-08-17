import { Body1, Button, Field, Textarea, makeStyles } from '@fluentui/react-components';
import React, { useState } from 'react';

import { PlanApprovalStep, revisionSuggestionsFor } from '@/models/reviewablePlan';

const useStyles = makeStyles({
    container: {
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        marginTop: '20px',
    },
    suggestions: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
    },
    verdicts: {
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
    },
    prompt: {
        color: 'var(--colorNeutralForeground2)',
        fontSize: '14px',
        lineHeight: '1.5',
    },
});

export const SEND_BACK_PROMPT = 'What would you change?';
export const SEND_BACK_LABEL = 'Send back with changes';
export const APPROVE_LABEL = 'Approve Task Plan';

interface PlanVerdictControlsProps {
    steps: PlanApprovalStep[];
    onApprove: () => void;
    onSendBack: (feedback: string) => void;
    processing: boolean;
}

/**
 * The two things an associate may say about a Reviewable plan (#108).
 *
 * There is no third control: leaving the conversation is navigation, not a
 * verdict, and lives on the rail rather than here. The starters beside the box
 * are **derived** from the plan on screen (ADR-033) — a different plan offers a
 * different set — and the box is there for when none of them fit, so nobody is
 * limited to what somebody anticipated.
 */
export const PlanVerdictControls: React.FC<PlanVerdictControlsProps> = ({
    steps,
    onApprove,
    onSendBack,
    processing,
}) => {
    const styles = useStyles();
    const [feedback, setFeedback] = useState('');
    const suggestions = revisionSuggestionsFor(steps);

    return (
        <div className={styles.container} data-testid="plan-verdict-controls">
            <Body1 className={styles.prompt}>
                If the plan looks good we can move forward with the first step. If it
                does not, say what you would change and it comes back revised.
            </Body1>

            {suggestions.length > 0 && (
                <div className={styles.suggestions} data-testid="send-back-suggestions">
                    {suggestions.map((suggestion) => (
                        <Button
                            key={suggestion}
                            appearance="outline"
                            size="small"
                            disabled={processing}
                            onClick={() => setFeedback(suggestion)}
                        >
                            {suggestion}
                        </Button>
                    ))}
                </div>
            )}

            <Field label={SEND_BACK_PROMPT}>
                <Textarea
                    aria-label={SEND_BACK_PROMPT}
                    value={feedback}
                    disabled={processing}
                    onChange={(_event, data) => setFeedback(data.value)}
                />
            </Field>

            <div className={styles.verdicts}>
                <Button
                    appearance="primary"
                    size="medium"
                    onClick={onApprove}
                    disabled={processing}
                >
                    {processing ? 'Processing...' : APPROVE_LABEL}
                </Button>
                <Button
                    appearance="secondary"
                    size="medium"
                    onClick={() => onSendBack(feedback)}
                    disabled={processing || !feedback.trim()}
                >
                    {SEND_BACK_LABEL}
                </Button>
            </div>
        </div>
    );
};

export default PlanVerdictControls;
