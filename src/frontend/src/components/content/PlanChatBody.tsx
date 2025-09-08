import ChatInput from "@/coral/modules/ChatInput";
import { PlanChatProps } from "@/models";
import { Button } from "@fluentui/react-components";
import { SendRegular } from "@fluentui/react-icons";

interface SimplifiedPlanChatProps extends PlanChatProps {
    showChatInput: boolean;
    waitingForPlan: boolean;
}
const PlanChatBody: React.FC<SimplifiedPlanChatProps> = ({
    planData,
    input,
    setInput,
    submittingChatDisableInput,
    OnChatSubmit,
    showChatInput,
    waitingForPlan
}) => {
    if (!showChatInput) {
        return null;
    }
    return (

        <div style={{
            padding: '20px 24px 32px',
            borderTop: '1px solid var(--colorNeutralStroke2)',
            backgroundColor: 'var(--colorNeutralBackground1)',
            maxWidth: '800px',
            margin: '0 auto',
            width: '100%'
        }}>
            <ChatInput
                value={input}
                onChange={setInput}
                onEnter={() => OnChatSubmit(input)}
                disabledChat={submittingChatDisableInput || waitingForPlan}
                placeholder={
                    waitingForPlan
                        ? "Creating plan..."
                        : "Send a message..."
                }
            >
                <Button
                    appearance="transparent"
                    onClick={() => OnChatSubmit(input)}
                    icon={<SendRegular />}
                    disabled={submittingChatDisableInput || waitingForPlan}
                    style={{ height: '40px', width: '40px' }}
                />
            </ChatInput>
        </div>);
}

export default PlanChatBody;