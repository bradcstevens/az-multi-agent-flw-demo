import { Spinner } from "@fluentui/react-components";
import ProcessingStatusIndicator from "../../common/ProcessingStatusIndicator.tsx";

/**
 * The in-flight indicator above the reply, showing the **Progress narration**
 * (issue #64, ADR-023).
 *
 * It takes the words rather than a boolean, and `null` means say nothing —
 * which is also what makes it *stop*. Under the boolean it took before, the
 * Fast lane had nothing that could ever clear it, so "Creating your plan..."
 * ran under the answer for the rest of the conversation (#69).
 */
const renderThinkingState = (narration: string | null) => {
    if (!narration) return null;

    return (
        <div style={{
            margin: '0 auto 32px auto',
            padding: '0 24px'
        }}>
            <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '16px'
            }}>
                <div style={{ flex: 1, maxWidth: 'calc(100% - 48px)' }}>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        padding: '16px 0',
                        color: 'var(--colorNeutralForeground2)',
                        fontSize: '14px'
                    }}>
                        <Spinner size="small" />
                        <span>{narration}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

/**
 * The same narration, in the position an approved plan runs in.
 *
 * The elapsed time beside it is measured, not narrated — it is the one number
 * here nobody authored.
 */
const renderPlanExecutionMessage = (
    narration: string | null,
    processingElapsedSeconds?: number,
) => {
    if (!narration) return null;

    return (
        <ProcessingStatusIndicator
            message={narration}
            elapsedSeconds={processingElapsedSeconds}
        />
    );
};

export { renderPlanExecutionMessage, renderThinkingState };
