import React from "react";
import { Caption1 } from "@fluentui/react-components";
import ChatInput from "@/commonComponents/modules/ChatInput";
import { PlanChatProps } from "@/models";
import { useAppSelector } from "@/store/hooks";
import { selectHasPendingClarification } from "@/store/slices/chatSlice";
import SendControl, { SEND_MESSAGE } from "./SendControl";

/** What the box invites while it can carry a message. */
export const TYPE_YOUR_MESSAGE = "Type your message here...";

/**
 * Why the box cannot be used, said out loud (#68).
 *
 * This box answers a **Clarification** and nothing else, so outside one it had
 * nowhere to send what was typed — and sent it anyway, as a clarification
 * answering nothing, under a placeholder inviting the message. A surface may
 * say nothing, but it may not say something that is not so; being unavailable
 * without a reason is the quieter half of the same fault.
 */
export const NOTHING_TO_ANSWER =
    "This conversation is not waiting on a reply. The box opens when an agent asks you a question.";

interface SimplifiedPlanChatProps extends PlanChatProps {
    planData: any;
    input: string;
    setInput: (input: string) => void;
    submittingChatDisableInput: boolean;
    OnChatSubmit: (input: string) => void;
}

const PlanChatBody: React.FC<SimplifiedPlanChatProps> = ({
    planData,
    input,
    setInput,
    submittingChatDisableInput,
    OnChatSubmit,
}) => {
    /*
      The pending-clarification gate lives here, not at the call site, for the
      reason the **Rehearsed replies** own theirs: a gate the caller owns is a
      gate a second caller forgets. Availability derived from the in-flight
      lock alone only *happened* to be closed when nothing was pending.
    */
    const clarificationPending = useAppSelector(selectHasPendingClarification);
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
            {!clarificationPending && (
                /*
                  Outside the dimmed box, because a reason rendered at 30%
                  opacity is a reason nobody reads; and a live region, because
                  the state changes under the associate when a question arrives.
                */
                <div role="status" style={{ textAlign: 'center', paddingBottom: '8px' }}>
                    <Caption1 style={{ color: 'var(--colorNeutralForeground3)' }}>
                        {NOTHING_TO_ANSWER}
                    </Caption1>
                </div>
            )}
            <ChatInput
                value={input}
                onChange={setInput}
                onEnter={() => OnChatSubmit(input)}
                disabledChat={submittingChatDisableInput || !clarificationPending}
                placeholder={clarificationPending ? TYPE_YOUR_MESSAGE : ''}
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
                    unavailable={submittingChatDisableInput || !clarificationPending || !input.trim()}
                />
            </ChatInput>
        </div>
    );
}

const MemoizedPlanChatBody = React.memo(PlanChatBody);
MemoizedPlanChatBody.displayName = 'PlanChatBody';
export default MemoizedPlanChatBody;