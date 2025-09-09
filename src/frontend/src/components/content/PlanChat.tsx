import React, { useState, useRef, useCallback, useEffect } from "react";
import {
  Button,
  Body1,
  Spinner,
  Tag,
  Textarea,
} from "@fluentui/react-components";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  CheckmarkRegular,
  DismissRegular,
  SendRegular,
  PersonRegular,
  BotRegular,
} from "@fluentui/react-icons";
import { PlanChatProps, MPlanData } from "../../models/plan";
import webSocketService from "../../services/WebSocketService";
import { PlanDataService } from "../../services/PlanDataService";
import { apiService } from "../../api/apiService";
import { useNavigate } from "react-router-dom";
import ChatInput from "../../coral/modules/ChatInput";
import InlineToaster, {
  useInlineToaster,
} from "../toast/InlineToaster";
import { AgentMessageData, WebsocketMessageType } from "@/models";
import getUserPlan from "./streaming/StreamingUserPlan";
import renderUserPlanMessage from "./streaming/StreamingUserPlanMessage";
import renderPlanResponse from "./streaming/StreamingPlanResponse";
import renderThinkingState from "./streaming/StreamingPlanState";
import ContentNotFound from "../NotFound/ContentNotFound";
import PlanChatBody from "./PlanChatBody";
import renderBufferMessage from "./streaming/StreamingBufferMessage";
import renderAgentMessages from "./streaming/StreamingAgentMessage";

interface SimplifiedPlanChatProps extends PlanChatProps {
  onPlanReceived?: (planData: MPlanData) => void;
  initialTask?: string;
  planApprovalRequest: MPlanData | null;
  waitingForPlan: boolean;
  messagesContainerRef: React.RefObject<HTMLDivElement>;
  streamingMessageBuffer: string;
  agentMessages: AgentMessageData[];
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
  streamingMessageBuffer,
  agentMessages

}) => {
  const navigate = useNavigate();

  const { showToast, dismissToast } = useInlineToaster();
  // States

  const [processingApproval, setProcessingApproval] = useState(false);

  const [showApprovalButtons, setShowApprovalButtons] = useState(true);




  // Listen for m_plan streaming


  // Handle plan approval
  const handleApprovePlan = useCallback(async () => {
    if (!planApprovalRequest) return;

    setProcessingApproval(true);
    let id = showToast("Submitting Approval", "progress");
    try {
      await apiService.approvePlan({
        m_plan_id: planApprovalRequest.id,
        plan_id: planData?.plan?.id,
        approved: true,
        feedback: 'Plan approved by user'
      });

      dismissToast(id);
      onPlanApproval?.(true);
      setShowApprovalButtons(false);

    } catch (error) {
      dismissToast(id);
      showToast("Failed to submit approval", "error");
      console.error('❌ Failed to approve plan:', error);
    } finally {
      setProcessingApproval(false);
    }
  }, [planApprovalRequest, planData, onPlanApproval]);

  // Handle plan rejection  
  const handleRejectPlan = useCallback(async () => {
    if (!planApprovalRequest) return;

    setProcessingApproval(true);
    let id = showToast("Submitting cancellation", "progress");
    try {
      await apiService.approvePlan({
        m_plan_id: planApprovalRequest.id,
        plan_id: planData?.plan?.id,
        approved: false,
        feedback: 'Plan rejected by user'
      });

      dismissToast(id);
      onPlanApproval?.(false);
      navigate('/');

    } catch (error) {
      dismissToast(id);
      showToast("Failed to submit cancellation", "error");
      console.error('❌ Failed to reject plan:', error);
      navigate('/');
    } finally {
      setProcessingApproval(false);
    }
  }, [planApprovalRequest, planData, onPlanApproval, navigate]);

  if (!planData)
    return (
      <ContentNotFound subtitle="The requested page could not be found." />
    );
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      backgroundColor: 'var(--colorNeutralBackground1)'
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
        {renderAgentMessages(agentMessages)}


        {/* Streaming plan updates */}
        {renderBufferMessage(streamingMessageBuffer)}
      </div>

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

export default PlanChat;