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

  // Extract user task with better fallback logic
  const getUserTask = () => {
    // Check initialTask first
    if (initialTask && initialTask.trim() && initialTask !== 'Task submitted') {
      return initialTask.trim();
    }

    // Check parsed plan data
    if (planApprovalRequest) {
      // Check user_request field
      if (planApprovalRequest.user_request &&
        planApprovalRequest.user_request.trim() &&
        planApprovalRequest.user_request !== 'Plan approval required') {
        return planApprovalRequest.user_request.trim();
      }

      // Check context task
      if (planApprovalRequest.context?.task &&
        planApprovalRequest.context.task.trim() &&
        planApprovalRequest.context.task !== 'Plan approval required') {
        return planApprovalRequest.context.task.trim();
      }
    }

    // Check planData
    if (planData?.plan?.initial_goal &&
      planData.plan.initial_goal.trim() &&
      planData.plan.initial_goal !== 'Task submitted') {
      return planData.plan.initial_goal.trim();
    }

    // Default fallback
    // return 'Please create a plan for me';
  };

  // Render user task message
  const renderUserTaskMessage = () => {
    const userTask = getUserTask();

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

  // Render AI thinking/planning state
  const renderThinkingState = () => {
    if (!waitingForPlan) return null;

    return (
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '16px',
        marginBottom: '32px',
        padding: '0 24px'
      }}>
        {/* AI Avatar */}
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          backgroundColor: 'var(--colorNeutralBackground3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0
        }}>
          <BotRegular style={{ fontSize: '16px', color: 'var(--colorNeutralForeground2)' }} />
        </div>

        {/* Thinking Message */}
        <div style={{ flex: 1, maxWidth: 'calc(100% - 48px)' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 0',
            color: 'var(--colorNeutralForeground2)',
            fontSize: '15px'
          }}>
            <Spinner size="small" />
            <span>Creating your plan...</span>
          </div>
        </div>
      </div>
    );
  };

  // Render the complete plan with all information
  const renderPlanResponse = () => {
    if (!planApprovalRequest) return null;

    return (
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '16px',
        marginBottom: '32px',
        padding: '0 24px'
      }}>
        {/* AI Avatar */}
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          backgroundColor: 'var(--colorNeutralBackground3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0
        }}>
          <BotRegular style={{ fontSize: '16px', color: 'var(--colorNeutralForeground2)' }} />
        </div>

        {/* Plan Content */}
        <div style={{ flex: 1, maxWidth: 'calc(100% - 48px)' }}>

          {/* Plan Header */}
          <div style={{
            marginBottom: '24px',
            borderBottom: '1px solid var(--colorNeutralStroke2)',
            paddingBottom: '16px'
          }}>
            <h3 style={{
              margin: '0 0 8px 0',
              fontSize: '20px',
              fontWeight: '600',
              color: 'var(--colorNeutralForeground1)'
            }}>
              📋 Plan Generated
            </h3>
            <div style={{
              display: 'flex',
              gap: '12px',
              alignItems: 'center',
              fontSize: '14px',
              color: 'var(--colorNeutralForeground2)'
            }}>
              <span>Plan ID: {planApprovalRequest.id}</span>
              <Tag size="extra-small" appearance="outline">
                {planApprovalRequest.status?.replace(/^.*'([^']*)'.*$/, '$1') || planApprovalRequest.status || 'PENDING_APPROVAL'}
              </Tag>
            </div>
          </div>

          {/* Analysis Section */}
          {planApprovalRequest.facts && (
            <div style={{ marginBottom: '28px' }}>
              <h4 style={{
                margin: '0 0 12px 0',
                fontSize: '16px',
                fontWeight: '600',
                color: 'var(--colorNeutralForeground1)'
              }}>
                🔍 Analysis & Context
              </h4>
              <div style={{
                padding: '20px',
                backgroundColor: 'var(--colorNeutralBackground2)',
                borderRadius: '12px',
                border: '1px solid var(--colorNeutralStroke2)',
                fontSize: '15px',
                lineHeight: '1.6'
              }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {planApprovalRequest.facts}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Action Steps */}
          {planApprovalRequest.steps && planApprovalRequest.steps.length > 0 && (
            <div style={{ marginBottom: '28px' }}>
              <h4 style={{
                margin: '0 0 16px 0',
                fontSize: '16px',
                fontWeight: '600',
                color: 'var(--colorNeutralForeground1)'
              }}>
                📝 Action Plan ({planApprovalRequest.steps.length} steps)
              </h4>
              <div style={{
                backgroundColor: 'var(--colorNeutralBackground1)',
                borderRadius: '12px',
                border: '1px solid var(--colorNeutralStroke2)',
                overflow: 'hidden'
              }}>
                {planApprovalRequest.steps.map((step, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '20px',
                      borderBottom: index < planApprovalRequest.steps.length - 1 ? '1px solid var(--colorNeutralStroke2)' : 'none',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '16px'
                    }}
                  >
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--colorBrandBackground)',
                      color: 'white',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '14px',
                      fontWeight: '600',
                      flexShrink: 0
                    }}>
                      {step.id}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{
                        fontSize: '15px',
                        lineHeight: '1.6',
                        marginBottom: step.agent && step.agent !== 'System' ? '8px' : '0'
                      }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {step.cleanAction || step.action}
                        </ReactMarkdown>
                      </div>
                      {step.agent && step.agent !== 'System' && (
                        <Tag size="small" appearance="brand">
                          {step.agent}
                        </Tag>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Team Assignment */}
          {planApprovalRequest.team && planApprovalRequest.team.length > 0 && (
            <div style={{ marginBottom: '28px' }}>
              <h4 style={{
                margin: '0 0 12px 0',
                fontSize: '16px',
                fontWeight: '600',
                color: 'var(--colorNeutralForeground1)'
              }}>
                👥 Assigned Team
              </h4>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {planApprovalRequest.team.map((member, index) => (
                  <Tag key={index} size="medium" appearance="brand">
                    {member}
                  </Tag>
                ))}
              </div>
            </div>
          )}

          {/* Agent Capabilities */}
          {planApprovalRequest.context?.participant_descriptions &&
            Object.keys(planApprovalRequest.context.participant_descriptions).length > 0 && (
              <div style={{ marginBottom: '28px' }}>
                <h4 style={{
                  margin: '0 0 12px 0',
                  fontSize: '16px',
                  fontWeight: '600',
                  color: 'var(--colorNeutralForeground1)'
                }}>
                  Agent Capabilities
                </h4>
                <div style={{
                  padding: '16px',
                  backgroundColor: 'var(--colorNeutralBackground2)',
                  borderRadius: '12px',
                  border: '1px solid var(--colorNeutralStroke2)',
                  fontSize: '14px'
                }}>
                  {Object.entries(planApprovalRequest.context.participant_descriptions).map(([agent, description]) => (
                    <div key={agent} style={{ marginBottom: '12px' }}>
                      <div style={{ fontWeight: '600', marginBottom: '4px' }}>{agent}:</div>
                      <div style={{ color: 'var(--colorNeutralForeground2)' }}>{description}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}


          {/* Action Buttons - Separate section */}
          <div style={{
            display: 'flex',
            gap: '12px',
            alignItems: 'center',
            padding: '20px',
            backgroundColor: 'var(--colorNeutralBackground2)',
            borderRadius: '12px',
            border: '1px solid var(--colorNeutralStroke2)',
            marginTop: '20px'
          }}>
            <div style={{
              flex: 1,
              fontSize: '14px',
              color: 'var(--colorNeutralForeground2)'
            }}>
              <span>Ready for approval</span>

            </div>

            <Button
              appearance="primary"
              icon={processingApproval ? <Spinner size="extra-tiny" /> : <CheckmarkRegular />}
              onClick={handleApprovePlan}
              disabled={processingApproval}
              size="medium"
              style={{ minWidth: '140px' }}
            >
              {processingApproval ? 'Processing...' : 'Approve'}
            </Button>
            <Button
              appearance="outline"
              icon={<DismissRegular />}
              onClick={handleRejectPlan}
              disabled={processingApproval}
              size="medium"
              style={{ minWidth: '100px' }}
            >
              Cancel
            </Button>
          </div>
        </div>
      </div>
    );
  };

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
        {/* User task message */}
        {renderUserTaskMessage()}

        {/* AI thinking state */}
        {renderThinkingState()}

        {/* Plan response with all information */}
        {renderPlanResponse()}
      </div>

      {/* Chat Input - only show if no plan is waiting for approval */}
      {!planApprovalRequest && (
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
        </div>
      )}
    </div>
  );
};

export default PlanChat;