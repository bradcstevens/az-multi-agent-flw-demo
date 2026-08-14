import React from "react";
import ChatInput from "@/commonComponents/modules/ChatInput";
import { PlanChatProps } from "@/models";
import SendControl, { SEND_MESSAGE } from "./SendControl";

interface SimplifiedPlanChatProps extends PlanChatProps {
    planData: any;
    input: string;
    setInput: (input: string) => void;
    submittingChatDisableInput: boolean;
    OnChatSubmit: (input: string) => void;
    waitingForPlan: boolean;
}

const PlanChatBody: React.FC<SimplifiedPlanChatProps> = ({
    planData,
    input,
    setInput,
    submittingChatDisableInput,
    OnChatSubmit,
    waitingForPlan
}) => {
    return (
        <div
            style={{
                // position: 'sticky',
                bottom: 0,
                // backgroundColor: 'var(--colorNeutralBackground1)',
                // borderTop: '1px solid var(--colorNeutralStroke2)',
                padding: '16px 24px',
                maxWidth: '800px',
                margin: '0 auto',
                marginBottom: '40px',
                width: '100%',
                boxSizing: 'border-box',
                zIndex: 10
            }}
        >
            <ChatInput
                value={input}
                onChange={setInput}
                onEnter={() => OnChatSubmit(input)}
                disabledChat={submittingChatDisableInput}
                placeholder="Type your message here..."
                style={{
                    fontSize: '16px',
                    borderRadius: '8px',
                    // border: '1px solid var(--colorNeutralStroke1)',
                    // backgroundColor: 'var(--colorNeutralBackground1)',
                    width: '100%',
                    boxSizing: 'border-box',
                }}
            >
                <SendControl
                    label={SEND_MESSAGE}
                    onSend={() => OnChatSubmit(input)}
                    unavailable={submittingChatDisableInput || !input.trim()}
                />
            </ChatInput>
        </div>
    );
}

const MemoizedPlanChatBody = React.memo(PlanChatBody);
MemoizedPlanChatBody.displayName = 'PlanChatBody';
export default MemoizedPlanChatBody;