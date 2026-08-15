import React from "react";
import { Caption1 } from "@fluentui/react-components";
import ChatInput from "@/commonComponents/modules/ChatInput";
import { PlanChatProps } from "@/models";
import { useAppSelector } from "@/store/hooks";
import { selectPendingClarificationRequestId } from "@/store/slices/chatSlice";
import {
    NOTHING_TO_CONTINUE,
    TURN_STILL_WORKING,
    placeholderFor,
    turnModeFor,
} from "@/models/resume";
import SendControl, { SEND_MESSAGE } from "./SendControl";

interface SimplifiedPlanChatProps extends PlanChatProps {
    planData: any;
    input: string;
    setInput: (input: string) => void;
    submittingChatDisableInput: boolean;
    /**
     * Whether this chat has a turn working right now — the surface's own live
     * signals, not the stored plan's status. A reopened chat whose record says
     * `in_progress` may have been abandoned hours ago, and closing the box over
     * that would shut resume out of exactly the chat #74 said is most worth
     * resuming.
     */
    turnInFlight?: boolean;
    OnChatSubmit: (input: string) => void;
}

const PlanChatBody: React.FC<SimplifiedPlanChatProps> = ({
    planData,
    input,
    setInput,
    submittingChatDisableInput,
    turnInFlight = false,
    OnChatSubmit,
}) => {
    /*
      What a turn typed here *is* — the box's own gate, not its caller's, for
      the reason the **Rehearsed replies** own theirs: a gate the caller owns
      is a gate a second caller forgets. Read from `resume.ts` so that what the
      box invites and where `ChatPage` sends it cannot disagree; availability
      derived from the in-flight lock alone only *happened* to be closed when
      nothing was pending (#68).
    */
    const clarificationRequestId = useAppSelector(selectPendingClarificationRequestId);
    const mode = turnModeFor(clarificationRequestId, planData?.plan?.session_id);
    const unavailable = mode === 'none';
    /*
      A **Resume** turn replaces the running one rather than queueing behind it
      — `process_request` cancels the user's in-flight orchestration before it
      schedules the next — so the box refuses while this chat is working, and
      says which of the two closures this is. A pending **Clarification** is
      exempt: there the spinner is up over a turn that cannot progress until
      the box is used.
    */
    const busy = mode === 'resume' && turnInFlight;
    const closed = unavailable || busy;
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
            {closed && (
                /*
                  Outside the dimmed box, because a reason rendered at 30%
                  opacity is a reason nobody reads; and a live region, because
                  the state changes under the associate when a question arrives.
                */
                <div role="status" style={{ textAlign: 'center', paddingBottom: '8px' }}>
                    <Caption1 style={{ color: 'var(--colorNeutralForeground3)' }}>
                        {unavailable ? NOTHING_TO_CONTINUE : TURN_STILL_WORKING}
                    </Caption1>
                </div>
            )}
            <ChatInput
                value={input}
                onChange={setInput}
                onEnter={() => OnChatSubmit(input)}
                disabledChat={submittingChatDisableInput || closed}
                placeholder={placeholderFor(mode)}
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
                    unavailable={submittingChatDisableInput || closed || !input.trim()}
                />
            </ChatInput>
        </div>
    );
}

const MemoizedPlanChatBody = React.memo(PlanChatBody);
MemoizedPlanChatBody.displayName = 'PlanChatBody';
export default MemoizedPlanChatBody;