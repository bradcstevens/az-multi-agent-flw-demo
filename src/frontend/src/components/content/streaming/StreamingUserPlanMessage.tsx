import { PersonRegular } from "@fluentui/react-icons";
import getUserTask from "./StreamingUserPlan";
import { MPlanData, ProcessedPlanData } from "@/models";

// Render user task message
const renderUserPlanMessage = (planApprovalRequest: MPlanData | null,
    initialTask?: string,
    planData?: ProcessedPlanData) => {
    const userTask = getUserTask(planApprovalRequest, initialTask, planData);

    return (
        <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '16px',
            marginBottom: '32px',
            padding: '0 24px'
        }}>
            {/* User Avatar */}
            <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: 'var(--colorBrandBackground)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
            }}>
                <PersonRegular style={{ fontSize: '16px', color: 'white' }} />
            </div>

            {/* User Message */}
            <div style={{ flex: 1, maxWidth: 'calc(100% - 48px)' }}>
                <div style={{
                    fontSize: '16px',
                    lineHeight: '1.6',
                    color: 'var(--colorNeutralForeground1)',
                    wordWrap: 'break-word'
                }}>
                    {userTask}
                </div>
            </div>
        </div>
    );
};
export default renderUserPlanMessage;