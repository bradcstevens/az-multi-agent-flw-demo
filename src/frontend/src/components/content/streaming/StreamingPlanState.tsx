import { Spinner } from "@fluentui/react-components";
import { BotRegular } from "@fluentui/react-icons";

// Render AI thinking/planning state
const renderThinkingState = (waitingForPlan: boolean) => {
    if (!waitingForPlan) return null;

    return (
        <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '16px',
            marginBottom: '32px',
            padding: '0 24px'
        }}>
            {/* AI Avatar */}
            <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: 'var(--colorNeutralBackground3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
            }}>
                <BotRegular style={{ fontSize: '16px', color: 'var(--colorNeutralForeground2)' }} />
            </div>

            {/* Thinking Message */}
            <div style={{ flex: 1, maxWidth: 'calc(100% - 48px)' }}>
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '16px 0',
                    color: 'var(--colorNeutralForeground2)',
                    fontSize: '15px'
                }}>
                    <Spinner size="small" />
                    <span>Creating your plan...</span>
                </div>
            </div>
        </div>
    );
};
export default renderThinkingState;