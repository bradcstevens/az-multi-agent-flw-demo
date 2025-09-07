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
import { WebsocketMessageType } from "@/models";
import getUserPlan from "./streaming/StreamingUserPlan";
import renderUserPlanMessage from "./streaming/StreamingUserPlanMessage";
import renderPlanResponse from "./streaming/StreamingPlanResponse";
import renderThinkingState from "./streaming/StreamingPlanState";
import ContentNotFound from "../NotFound/ContentNotFound";
import PlanChatBody from "./PlanChatBody";
interface SimplifiedPlanChatProps extends PlanChatProps {
  onPlanReceived?: (planData: MPlanData) => void;
  initialTask?: string;
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
}) => {
  const navigate = useNavigate();
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const { showToast, dismissToast } = useInlineToaster();
  // States
  const [planApprovalRequest, setPlanApprovalRequest] = useState<MPlanData | null>(null);
  const [processingApproval, setProcessingApproval] = useState(false);
  const [waitingForPlan, setWaitingForPlan] = useState(true);
  const [userFeedback, setUserFeedback] = useState('');
  const [showFeedbackInput, setShowFeedbackInput] = useState(false);


  // Auto-scroll helper
  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
      }
    }, 100);
  }, []);

  // Listen for m_plan streaming
  useEffect(() => {
    const unsubscribe = webSocketService.on(WebsocketMessageType.PLAN_APPROVAL_REQUEST, (approvalRequest: any) => {
      console.log('📋 Plan received:', approvalRequest);

      let mPlanData: MPlanData | null = null;

      // Handle the different message structures
      if (approvalRequest.parsedData) {
        // Direct parsedData property
        mPlanData = approvalRequest.parsedData;
      } else if (approvalRequest.data && typeof approvalRequest.data === 'object') {
        // Data property with nested object
        if (approvalRequest.data.parsedData) {
          mPlanData = approvalRequest.data.parsedData;
        } else {
          // Try to parse the data object directly
          mPlanData = approvalRequest.data;
        }
      } else if (approvalRequest.rawData) {
        // Parse the raw data string
        mPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest.rawData);
      } else {
        // Try to parse the entire object
        mPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest);
      }

      if (mPlanData) {
        console.log('✅ Parsed plan data:', mPlanData);
        setPlanApprovalRequest(mPlanData);
        setWaitingForPlan(false);
        onPlanReceived?.(mPlanData);
        scrollToBottom();
      } else {
        console.error('❌ Failed to parse plan data', approvalRequest);
      }
    });

    return () => unsubscribe();
  }, [onPlanReceived, scrollToBottom]);

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
        feedback: userFeedback || 'Plan approved by user'
      });

      dismissToast(id);
      setShowFeedbackInput(false);
      onPlanApproval?.(true);

    } catch (error) {
      dismissToast(id);
      showToast("Failed to submit approval", "error");
      console.error('❌ Failed to approve plan:', error);
    } finally {
      setProcessingApproval(false);
    }
  }, [planApprovalRequest, planData, userFeedback, onPlanApproval]);

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
        feedback: userFeedback || 'Plan rejected by user'
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
        {renderPlanResponse(planApprovalRequest, handleApprovePlan, handleRejectPlan, processingApproval)}
      </div>

      {/* Chat Input - only show if no plan is waiting for approval */}
      <PlanChatBody
        planData={planData}
        input={input}
        setInput={setInput}
        submittingChatDisableInput={submittingChatDisableInput}
        OnChatSubmit={OnChatSubmit}
        showChatInput={!planApprovalRequest}
        waitingForPlan={waitingForPlan}
        loading={false} />
    </div>
  );
};

export default PlanChat;