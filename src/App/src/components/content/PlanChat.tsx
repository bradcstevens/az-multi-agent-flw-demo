import React from "react";
import { PlanChatProps, MPlanData } from "../../models/plan";
import InlineToaster from "../toast/InlineToaster";
import { AgentMessageData, AgentMessageType } from "@/models";
import renderUserPlanMessage from "./streaming/StreamingUserPlanMessage";
import renderPlanResponse from "./streaming/StreamingPlanResponse";
import { renderPlanExecutionMessage, renderThinkingState } from "./streaming/StreamingPlanState";
import ContentNotFound from "../NotFound/ContentNotFound";
import PlanChatBody from "./PlanChatBody";
import renderAgentMessages from "./streaming/StreamingAgentMessage";
import PresenterAlertCard from "../transparency/PresenterAlertCard";
import RehearsedReplies from "./RehearsedReplies";
import FollowOnTask from "./FollowOnTask";
import TicketStatusReply from "./TicketStatusReply";
import { useAppSelector } from "@/store/hooks";
import { selectPresenterAlerts } from "@/store/slices/transparencySlice";
import { selectProgressNarration } from "@/store/slices/progressSlice";
import { StartingTask, TicketStatusReply as TicketStatusReplyModel } from "@/models/Team";
import { PersonalAnswer } from "@/models/personalAnswer";
import { PolicyBlock } from "@/api/policyBlock";
import PersonalAnswerCard from "../identity/PersonalAnswerCard";
import PolicyBlockNotice from "../identity/PolicyBlockNotice";
import "@/styles/planChatContinuation.css";

interface SimplifiedPlanChatProps extends PlanChatProps {
  onPlanReceived?: (planData: MPlanData) => void;
  initialTask?: string;
  planApprovalRequest: MPlanData | null;
  messagesContainerRef: React.RefObject<HTMLDivElement>;
  finalResultRef: React.RefObject<HTMLDivElement>;
  streamingMessageBuffer: string;
  showBufferingText: boolean;
  streamingAgent?: string | null;
  agentMessages: AgentMessageData[];
  /**
   * Whether the in-flight indicator belongs below the replies rather than
   * above them — where an approved plan runs. Placement only: what it *says*,
   * and whether it says anything at all, is the **Progress narration**'s.
   */
  showProcessingPlanSpinner: boolean;
  processingElapsedSeconds: number;
  showApprovalButtons: boolean;
  handleApprovePlan: () => Promise<void>;
  handleRejectPlan: (feedback: string) => Promise<void>;
  processingApproval: boolean;
  /** The Rehearsed replies for this plan (issue #26), if it began as a tap. */
  rehearsedReplies: string[];
  /** The task this conversation can lead to (issue #61, ADR-024). */
  followOnTask?: StartingTask;
  onFollowOnTask?: (task: StartingTask) => void;
  /** The authored inquiry this Chat offers after it raises its Simulated ticket. */
  ticketStatusReply?: TicketStatusReplyModel;
  onTicketStatusReply?: (reply: TicketStatusReplyModel) => void;
  hasRaisedTicket?: boolean;
  /**
   * Whether a continuation turn is in flight — one lock for both paths, since
   * two turns into one session is one turn cancelled (#77).
   */
  continuationSubmitting?: boolean;
  /** Whether this chat has a turn working right now (#77). */
  turnInFlight?: boolean;
  /**
   * What the last continuation turn produced when it produced no plan: the
   * **Mocked unlock**'s answer, or the **Identity boundary** gate's refusal.
   * Neither is a failed request, and neither may arrive as an error toast
   * (ADR-014, #27).
   */
  personalAnswer?: PersonalAnswer | null;
  policyRefusal?: PolicyBlock | null;
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
  messagesContainerRef,
  finalResultRef,
  streamingMessageBuffer,
  showBufferingText,
  streamingAgent = null,
  agentMessages,
  showProcessingPlanSpinner,
  processingElapsedSeconds,
  showApprovalButtons,
  handleApprovePlan,
  handleRejectPlan,
  processingApproval,
  rehearsedReplies,
  followOnTask,
  onFollowOnTask,
  ticketStatusReply,
  onTicketStatusReply,
  hasRaisedTicket = false,
  continuationSubmitting = false,
  turnInFlight = false,
  personalAnswer = null,
  policyRefusal = null,
}) => {
  // Read before the early return: hooks may not sit behind a condition.
  const presenterAlerts = useAppSelector(selectPresenterAlerts);
  /*
    What the surface says while this request is in flight (#64, ADR-023). Read
    from the slice rather than passed in, because the narration is one claim
    made in one place: a component holding its own copy is how six of them came
    to disagree about what the system was doing.
  */
  const narration = useAppSelector(selectProgressNarration);

  if (!planData)
    return (
      <ContentNotFound subtitle="The requested page could not be found." />
    );
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      // `dvh`, not `vh`, for the reason the shell uses it: on iOS Safari
      // `100vh` counts the viewport as though the browser chrome were not
      // there, so the reply stream stood a toolbar taller than the screen.
      height: '100dvh',

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
        {!showProcessingPlanSpinner && renderThinkingState(narration)}

        {/* Plan response with all information */}
        {renderPlanResponse(planApprovalRequest, handleApprovePlan, handleRejectPlan, processingApproval, showApprovalButtons)}
        {renderAgentMessages(
          streamingMessageBuffer && showBufferingText && !showApprovalButtons
            ? [
                ...agentMessages,
                {
                  agent: streamingAgent || 'Assistant',
                  agent_type: AgentMessageType.AI_AGENT,
                  timestamp: Date.now(),
                  steps: [],
                  next_steps: [],
                  content: streamingMessageBuffer,
                  raw_data: '',
                  is_streaming: true,
                },
              ]
            : agentMessages,
          undefined,
          undefined,
          finalResultRef,
        )}

        {/*
          Presenter alerts (issue #24, R8). Rendered after the replies rather
          than among them, and as visibly different objects: an alert answers
          no question, because nobody asked one. An alert mistaken for an
          answer is worse than no alert at all.
        */}
        {presenterAlerts.map((alert, index) => (
          <PresenterAlertCard key={`${alert.timestamp}-${index}`} alert={alert} />
        ))}

        {showProcessingPlanSpinner && renderPlanExecutionMessage(narration, processingElapsedSeconds)}
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
      {hasRaisedTicket && ticketStatusReply && onTicketStatusReply && (
        <TicketStatusReply
          reply={ticketStatusReply}
          onReply={onTicketStatusReply}
          disabled={continuationSubmitting || turnInFlight}
        />
      )}

      {/*
        A continuation turn that produced no plan, said where the box that
        produced it can be seen. The refusal carries no door: signing in is the
        home screen's rehearsed beat (#27), and a second one on this surface is
        a decision no ADR has taken.
      */}
      {(policyRefusal || personalAnswer) && (
        <div className="plan-chat-continuation-outcome">
          {policyRefusal && <PolicyBlockNotice block={policyRefusal} />}
          {personalAnswer && <PersonalAnswerCard answer={personalAnswer} />}
        </div>
      )}

      {followOnTask && onFollowOnTask && (
        <FollowOnTask
          task={followOnTask}
          onSelect={onFollowOnTask}
          /*
            Also while this chat is working: a continuation turn replaces the
            running one rather than queueing behind it, and the card is the
            other way in (#77).
          */
          disabled={continuationSubmitting || turnInFlight}
        />
      )}

      {/* Chat Input - only show if no plan is waiting for approval */}
      <PlanChatBody
        planData={planData}
        input={input}
        setInput={setInput}
        submittingChatDisableInput={submittingChatDisableInput}
        turnInFlight={turnInFlight}
        OnChatSubmit={OnChatSubmit}
        loading={false} />

    </div>
  );
};

const MemoizedPlanChat = React.memo(PlanChat);
MemoizedPlanChat.displayName = 'PlanChat';
export default MemoizedPlanChat;