import React from "react";
import { PlanChatProps, MPlanData } from "../../models/plan";
import InlineToaster from "../toast/InlineToaster";
import { AgentMessageData } from "@/models";
import renderUserPlanMessage from "./streaming/StreamingUserPlanMessage";
import renderPlanResponse from "./streaming/StreamingPlanResponse";
import { renderPlanExecutionMessage, renderThinkingState } from "./streaming/StreamingPlanState";
import ContentNotFound from "../NotFound/ContentNotFound";
import PlanChatBody from "./PlanChatBody";
import renderAgentMessages from "./streaming/StreamingAgentMessage";
import StreamingBufferMessage from "./streaming/StreamingBufferMessage";
import PresenterAlertCard from "../transparency/PresenterAlertCard";
import RehearsedReplies from "./RehearsedReplies";
import FollowOnTask from "./FollowOnTask";
import { useAppSelector } from "@/store/hooks";
import { selectPresenterAlerts } from "@/store/slices/transparencySlice";
import { StartingTask } from "@/models/Team";

interface SimplifiedPlanChatProps extends PlanChatProps {
  onPlanReceived?: (planData: MPlanData) => void;
  initialTask?: string;
  planApprovalRequest: MPlanData | null;
  waitingForPlan: boolean;
  messagesContainerRef: React.RefObject<HTMLDivElement>;
  finalResultRef: React.RefObject<HTMLDivElement>;
  streamingMessageBuffer: string;
  showBufferingText: boolean;
  agentMessages: AgentMessageData[];
  showProcessingPlanSpinner: boolean;
  processingElapsedSeconds: number;
  processingStatusMessage: string;
  showApprovalButtons: boolean;
  handleApprovePlan: () => Promise<void>;
  handleRejectPlan: () => Promise<void>;
  processingApproval: boolean;
  /** The Rehearsed replies for this plan (issue #26), if it began as a tap. */
  rehearsedReplies: string[];
  /** The task this conversation can lead to (issue #61, ADR-024). */
  followOnTask?: StartingTask;
  onFollowOnTask?: (task: StartingTask) => void;
  followOnSubmitting?: boolean;
}

const PlanChat: React.FC<SimplifiedPlanChatProps> = ({
  planData,
  input,
  setInput,
  submittingChatDisableInput,
  OnChatSubmit,
  onPlanApproval,
  onPlanReceived,
  initialTask,
  planApprovalRequest,
  waitingForPlan,
  messagesContainerRef,
  finalResultRef,
  streamingMessageBuffer,
  showBufferingText,
  agentMessages,
  showProcessingPlanSpinner,
  processingElapsedSeconds,
  processingStatusMessage,
  showApprovalButtons,
  handleApprovePlan,
  handleRejectPlan,
  processingApproval,
  rehearsedReplies,
  followOnTask,
  onFollowOnTask,
  followOnSubmitting = false,
}) => {
  // Read before the early return: hooks may not sit behind a condition.
  const presenterAlerts = useAppSelector(selectPresenterAlerts);

  if (!planData)
    return (
      <ContentNotFound subtitle="The requested page could not be found." />
    );
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',

    }}>
      {/* Messages Container */}
      <InlineToaster />
      <div
        ref={messagesContainerRef}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '32px 0',
          maxWidth: '800px',
          margin: '0 auto',
          width: '100%'
        }}
      >
        {/* User plan message */}
        {renderUserPlanMessage(planApprovalRequest, initialTask, planData)}

        {/* AI thinking state */}
        {renderThinkingState(waitingForPlan)}

        {/* Plan response with all information */}
        {renderPlanResponse(planApprovalRequest, handleApprovePlan, handleRejectPlan, processingApproval, showApprovalButtons)}
        {renderAgentMessages(agentMessages, undefined, undefined, finalResultRef)}

        {/*
          Presenter alerts (issue #24, R8). Rendered after the replies rather
          than among them, and as visibly different objects: an alert answers
          no question, because nobody asked one. An alert mistaken for an
          answer is worse than no alert at all.
        */}
        {presenterAlerts.map((alert, index) => (
          <PresenterAlertCard key={`${alert.timestamp}-${index}`} alert={alert} />
        ))}

        {showProcessingPlanSpinner && renderPlanExecutionMessage(processingElapsedSeconds, processingStatusMessage)}
        {/* Streaming plan updates — hidden while an approval prompt is pending so
            the approval action is presented at the appropriate step instead of
            after the thinking process visibly completes. */}
        {showBufferingText && !showApprovalButtons && (
          <StreamingBufferMessage
            streamingMessageBuffer={streamingMessageBuffer}
            isStreaming={true}
          />
        )}
      </div>

      {/*
        The Rehearsed replies (issue #26). Above the box, because they are an
        alternative to typing in it — the last place the scripted walkthrough
        still required a keyboard. The pending-clarification gate is the
        component's own, so it cannot be forgotten here.
      */}
      <RehearsedReplies
        replies={rehearsedReplies}
        onReply={OnChatSubmit}
        disabled={submittingChatDisableInput}
      />

      {followOnTask && onFollowOnTask && (
        <FollowOnTask
          task={followOnTask}
          onSelect={onFollowOnTask}
          disabled={followOnSubmitting}
        />
      )}

      {/* Chat Input - only show if no plan is waiting for approval */}
      <PlanChatBody
        planData={planData}
        input={input}
        setInput={setInput}
        submittingChatDisableInput={submittingChatDisableInput}
        OnChatSubmit={OnChatSubmit}
        waitingForPlan={waitingForPlan}
        loading={false} />

    </div>
  );
};

const MemoizedPlanChat = React.memo(PlanChat);
MemoizedPlanChat.displayName = 'PlanChat';
export default MemoizedPlanChat;