import ChatInput from "@/coral/modules/ChatInput";
import { PlanChatProps } from "@/models";
import { Button, Caption1 } from "@fluentui/react-components";
import { Send } from "@/coral/imports/bundleicons";

interface SimplifiedPlanChatProps extends PlanChatProps {
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
                backgroundColor: 'var(--colorNeutralBackground1)',
                padding: '20px 0'
            }}
        >
            <div
                style={{
                    maxWidth: '800px',
                    margin: '0 auto',
                    padding: '0 24px'
                }}
            >
                {/* Chat Input Container */}
                <div style={{
                    position: 'relative',
                    width: '100%'
                }}>
                    <ChatInput
                        value={input}
                        onChange={setInput}
                        onEnter={() => OnChatSubmit(input)}
                        disabledChat={submittingChatDisableInput}
                        placeholder={
                            waitingForPlan
                                ? "Creating plan..."
                                : "Tell us what needs planning, building, or connecting—we'll handle the rest."
                        }
                        style={{
                            minHeight: '56px',
                            fontSize: '16px',
                            borderRadius: '8px',
                            border: '2px solid var(--colorNeutralStroke2)',
                            backgroundColor: 'var(--colorNeutralBackground1)',
                            padding: '16px 60px 16px 20px',
                            width: '100%',
                            boxSizing: 'border-box',
                            alignItems: 'flex-start',
                            textAlign: 'left',
                            verticalAlign: 'top'
                        }}
                    >
                        <Button
                            appearance="subtle"
                            className="home-input-send-button"
                            onClick={() => OnChatSubmit(input)}
                            disabled={submittingChatDisableInput}
                            icon={<Send />}
                            style={{
                                position: 'absolute',
                                right: '12px',
                                top: '16px',
                                height: '32px',
                                width: '32px',
                                borderRadius: '4px',
                                backgroundColor: 'transparent',
                                border: 'none',
                                color: submittingChatDisableInput 
                                    ? 'var(--colorNeutralForegroundDisabled)' 
                                    : 'var(--colorBrandForeground1)'
                            }}
                        />
                    </ChatInput>

                    {/* AI disclaimer */}
                    <div style={{
                        color: 'var(--colorNeutralForeground3)',
                        marginTop: '8px',
                        paddingBottom: '8px',
                        textAlign: 'center'
                    }}>
                        {/* <Caption1>AI-generated content may be incorrect</Caption1> */}
                    </div>
                </div>
            </div>
            <div
                style={{
                    marginTop: '8px',
                    paddingBottom: '8px',
                }}
            >
               
            </div>
        </div>
    );
}

export default PlanChatBody;