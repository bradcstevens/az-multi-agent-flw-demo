import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Body1,
  Button,
  Tag,
  Textarea,
  Spinner,
} from "@fluentui/react-components";
import {
  CheckmarkCircleRegular,
  ErrorCircleRegular,
  DiamondRegular,
  ClockRegular,
  PersonRegular,
} from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import { AgentType, ChatMessage, ParsedPlanData } from "../../models";
import { TaskService } from "../../services/TaskService";
import { PlanChatProps } from "../../models/plan";
import "../../styles/Chat.css";
import webSocketService, { StreamingPlanUpdate, StreamMessage, ParsedPlanApprovalRequest } from "../../services/WebSocketService";
import ChatInput from "../../coral/modules/ChatInput";
import "../../styles/PlanChat.css";
import InlineToaster from "../toast/InlineToaster";
import ContentNotFound from "../NotFound/ContentNotFound";
import { Send, Copy } from "../../coral/imports/bundleicons";
import { useNavigate } from "react-router-dom";

// Type guard to check if a message has streaming properties
const hasStreamingProperties = (msg: ChatMessage): msg is ChatMessage & { 
  streaming?: boolean; 
  status?: string; 
  message_type?: string;
  step_id?: string;
} => {
  return 'streaming' in msg || 'status' in msg || 'message_type' in msg;
};

interface GroupedMessage {
  id: string;
  agent_name: string;
  messages: StreamingPlanUpdate[];
  status: string;
  latest_timestamp: string;
  step_id?: string;
}

const PlanChat: React.FC<PlanChatProps> = ({
  planData,
  input,
  loading,
  setInput,
  submittingChatDisableInput,
  OnChatSubmit,
  streamingMessages = [],
  wsConnected = false,
  onPlanApproval,
}) => {
  const navigate = useNavigate();
  const messages = planData?.messages || [];
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [inputHeight, setInputHeight] = useState(0);
  const [groupedStreamingMessages, setGroupedStreamingMessages] = useState<GroupedMessage[]>([]);
  
  // Add state for plan approval requests
  const [planApprovalRequest, setPlanApprovalRequest] = useState<ParsedPlanData | null>(null);
  const [processingApproval, setProcessingApproval] = useState(false);
  
  // Add state for human clarification - only show after approve is clicked
  const [userFeedback, setUserFeedback] = useState('');
  const [showClarificationInput, setShowClarificationInput] = useState(false);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  // Helper function to normalize timestamp
  const normalizeTimestamp = (timestamp?: string | number): string => {
    if (!timestamp) return new Date().toISOString();
    if (typeof timestamp === 'number') {
      // Backend sends float timestamp, convert to ISO string
      return new Date(timestamp * 1000).toISOString();
    }
    return timestamp;
  };

  // Helper function to get clean agent display name
  const getAgentDisplayName = (agentName: string): string => {
    if (!agentName) return 'Assistant';
    
    // Clean up the agent name for display
    let cleanName = TaskService.cleanTextToSpaces(agentName);
    
    // If it's a generic agent type, make it more readable
    if (cleanName.toLowerCase().includes('agent')) {
      cleanName = cleanName.replace(/agent/gi, '').trim();
    }
    
    // Capitalize first letter of each word
    return cleanName.replace(/\b\w/g, l => l.toUpperCase()) || 'Assistant';
  };

  // Add WebSocket listener for plan approval requests
  useEffect(() => {
    const unsubscribePlanApproval = webSocketService.on('parsed_plan_approval_request', (message: StreamMessage) => {
      console.log('Plan approval request received in PlanChat:', message);
      
      // The message.data contains the ParsedPlanApprovalRequest
      const approvalRequest = message.data as ParsedPlanApprovalRequest;
      
      // Debug the parsing result
      console.log('Raw approval request data:', approvalRequest);
      
      if (approvalRequest.parsedData) {
        console.log('✅ Parsed data successfully:', approvalRequest.parsedData);
        setPlanApprovalRequest(approvalRequest.parsedData);
      } else {
        console.error('❌ No parsed data found. Raw data:', approvalRequest.rawData?.substring(0, 500));
        
        // Fallback: try to show something basic
        const basicData = {
          id: 'temp-' + Date.now(),
          status: 'PENDING_APPROVAL',
          user_request: 'Plan approval required',
          team: ['System'],
          facts: 'A plan has been created and requires your approval.',
          steps: [
            { id: 1, action: 'Review plan', cleanAction: 'Review plan' }
          ],
          context: {
            task: 'Plan approval required',
            participant_descriptions: {}
          }
        };
        setPlanApprovalRequest(basicData);
      }
      
      // Reset feedback state
      setUserFeedback('');
      setShowClarificationInput(false);
      
      // Auto-scroll to show the approval request
      setTimeout(() => scrollToBottom(), 100);
    });

    return () => {
      unsubscribePlanApproval();
    };
  }, []);

  // Handle sending final plan approval to backend
  const handleSendFinalPlan = useCallback(async () => {
    if (!planApprovalRequest) return;
    
    setProcessingApproval(true);
    
    try {
      const approvalResponse = {
        plan_id: planApprovalRequest.id,
        session_id: planData?.plan?.session_id || '',
        approved: true,
        feedback: userFeedback || 'Plan approved by user',
        user_response: userFeedback || '',
        human_clarification: userFeedback || '' // Additional field for human clarification
      };

      console.log('🚀 Sending FINAL plan approval to backend:', approvalResponse);

      // Send final approval response via WebSocket to trigger backend plan execution
      webSocketService.sendPlanApprovalResponse(approvalResponse);
      
      console.log('📡 Subscribing to plan for streaming messages:', planApprovalRequest.id);
      webSocketService.subscribeToPlan(planApprovalRequest.id);
      
      // Notify parent component that plan was approved
      onPlanApproval?.(true);
      
      // Clear the approval request from UI
      setPlanApprovalRequest(null);
      setUserFeedback('');
      setShowClarificationInput(false);
      
      console.log('✅ Final plan approved and sent to backend:', planApprovalRequest.id);
      
    } catch (error) {
      console.error('❌ Failed to send final plan approval:', error);
    } finally {
      setProcessingApproval(false);
    }
  }, [planApprovalRequest, planData?.plan?.session_id, userFeedback, onPlanApproval]);

  // Handle initial approve button click - show clarification input
  const handleApproveTaskPlan = useCallback(() => {
    console.log('👍 User clicked "Approve Task Plan" - showing clarification input');
    setShowClarificationInput(true);
  }, []);

  // Handle reject button click - redirect to homepage
  const handleRejectPlan = useCallback(async () => {
    if (!planApprovalRequest) return;
    
    setProcessingApproval(true);
    
    try {
      const rejectionResponse = {
        plan_id: planApprovalRequest.id,
        session_id: planData?.plan?.session_id || '',
        approved: false,
        feedback: 'Plan rejected by user',
        user_response: 'Plan rejected by user'
      };

      console.log('❌ Sending plan rejection to backend:', rejectionResponse);

      // Send rejection response via WebSocket
      webSocketService.sendPlanApprovalResponse(rejectionResponse);
      
      // Notify parent component that plan was rejected
      onPlanApproval?.(true);
      
      console.log('🏠 Plan rejected, redirecting to homepage');
      
      // Redirect to homepage to start fresh
      navigate('/');
      
    } catch (error) {
      console.error('❌ Failed to send plan rejection:', error);
      // Still redirect to homepage even if WebSocket fails
      navigate('/');
    } finally {
      setProcessingApproval(false);
    }
  }, [planApprovalRequest, planData?.plan?.session_id, onPlanApproval, navigate]);

  // ✅ FIXED: Render user's original request as a chat message
  const renderUserRequest = () => {
    if (!planApprovalRequest?.user_request) return null;

    return (
      <div className="message user" style={{ marginBottom: '16px' }}>
        <div className="plan-chat-header">
          <div className="plan-chat-speaker" style={{ justifyContent: 'flex-end' }}>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="brand"
              icon={<PersonRegular />}
            >
              YOU
            </Tag>
            <Body1 className="speaker-name">You</Body1>
          </div>
        </div>
        <Body1>
          <div className="plan-chat-message-content">
            {planApprovalRequest.user_request}
          </div>
        </Body1>
      </div>
    );
  };

  // ✅ FIXED: Render plan approval request properly
  const renderPlanApprovalRequest = () => {
    if (!planApprovalRequest) return null;

    return (
      <>
        {/* Show user's original request */}
        {renderUserRequest()}

        {/* Assistant's response with plan */}
        <div className="message assistant approval-request" style={{ marginBottom: '16px' }}>
          <div className="plan-chat-header">
            <div className="plan-chat-speaker">
              <Body1 className="speaker-name">Assistant</Body1>
              <Tag
                size="extra-small"
                shape="rounded"
                appearance="brand"
                className="agent-tag"
              >
                PLANNER
              </Tag>
              <Tag
                size="extra-small"
                shape="rounded"
                appearance="outline"
                icon={<ClockRegular />}
              >
                Plan Ready
              </Tag>
            </div>
          </div>

          <Body1>
            <div className="plan-chat-message-content">
              <div style={{ marginBottom: '20px' }}>
                <p style={{ 
                  margin: '0 0 16px 0', 
                  fontSize: '15px', 
                  fontWeight: 500,
                  color: 'var(--colorNeutralForeground1)'
                }}>
                  I've created a plan for your request! Here's what I'll do:
                </p>

                {/* Steps section with enhanced theme support */}
                {planApprovalRequest.steps && planApprovalRequest.steps.length > 0 && (
                  <div style={{ marginBottom: '20px' }}>
                    <h4 style={{ 
                      margin: '0 0 12px 0', 
                      fontSize: '15px', 
                      fontWeight: 600,
                      color: 'var(--colorNeutralForeground1)'
                    }}>
                      📋 Plan steps:
                    </h4>
                    <div style={{ 
                      backgroundColor: 'var(--colorNeutralBackground2)', 
                      padding: '16px', 
                      borderRadius: '8px',
                      border: '1px solid var(--colorNeutralStroke2)'
                    }}>
                      {planApprovalRequest.steps.map((step, index) => (
                        <div key={step.id || index} style={{ 
                          marginBottom: index < planApprovalRequest.steps.length - 1 ? '12px' : '0',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '8px'
                        }}>
                          <div style={{
                            minWidth: '20px',
                            height: '20px',
                            borderRadius: '50%',
                            backgroundColor: 'var(--colorBrandBackground2)',
                            color: 'var(--colorBrandForeground2)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '12px',
                            fontWeight: 'bold',
                            marginTop: '2px'
                          }}>
                            {index + 1}
                          </div>
                          <div style={{ 
                            fontSize: '14px', 
                            lineHeight: '1.4',
                            color: 'var(--colorNeutralForeground1)'
                          }}>
                            {step.cleanAction || step.action}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Facts section with theme support */}
                {planApprovalRequest.facts && (
                  <div style={{ marginBottom: '20px' }}>
                    <h4 style={{ 
                      margin: '0 0 12px 0', 
                      fontSize: '15px', 
                      fontWeight: 600,
                      color: 'var(--colorNeutralForeground1)'
                    }}>
                      💡 Important notes:
                    </h4>
                    <div style={{ 
                      backgroundColor: 'var(--colorPaletteYellowBackground1)', 
                      padding: '16px', 
                      borderRadius: '8px',
                      fontSize: '14px',
                      lineHeight: '1.5',
                      border: '1px solid var(--colorPaletteYellowBorder1)',
                      color: 'var(--colorNeutralForeground1)'
                    }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {planApprovalRequest.facts}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}

                <p style={{ 
                  margin: '20px 0 0 0', 
                  fontSize: '15px', 
                  fontWeight: 500,
                  color: 'var(--colorNeutralForeground1)'
                }}>
                  Does this plan look good to you? I'm ready to start working on it once you approve! 🚀
                </p>
              </div>

              {/* Human clarification input - only show after "Approve Task Plan" is clicked */}
              {showClarificationInput && (
                <div style={{ 
                  marginTop: '20px',
                  marginBottom: '20px',
                  padding: '16px',
                  backgroundColor: 'var(--colorNeutralBackground2)',
                  borderRadius: '8px',
                  border: '1px solid var(--colorNeutralStroke2)'
                }}>
                  <h4 style={{ 
                    margin: '0 0 12px 0', 
                    fontSize: '14px', 
                    fontWeight: 600,
                    color: 'var(--colorNeutralForeground1)'
                  }}>
                    💬 Human clarification (optional):
                  </h4>
                  <p style={{ 
                    margin: '0 0 12px 0', 
                    fontSize: '12px', 
                    color: 'var(--colorNeutralForeground2)'
                  }}>
                    Add any additional context or clarifications for the agents executing this plan.
                  </p>
                  <Textarea
                    value={userFeedback}
                    onChange={(_, data) => setUserFeedback(data.value)}
                    placeholder="Any additional context or clarifications for the agents..."
                    rows={3}
                    style={{ width: '100%', marginBottom: '12px' }}
                  />
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <Button
                      appearance="primary"
                      size="small"
                      onClick={handleSendFinalPlan}
                      disabled={processingApproval}
                      icon={processingApproval ? <Spinner size="tiny" /> : <CheckmarkCircleRegular />}
                    >
                      {processingApproval ? 'Sending...' : 'Send Final Plan'}
                    </Button>
                    <Button
                      appearance="subtle"
                      size="small"
                      onClick={() => {
                        setShowClarificationInput(false);
                        setUserFeedback('');
                      }}
                      disabled={processingApproval}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {/* Initial action buttons - only show if clarification input is not shown */}
              {!showClarificationInput && (
                <div className="assistant-footer" style={{ marginTop: '24px' }}>
                  <div style={{ 
                    display: 'flex', 
                    gap: '12px', 
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    padding: '16px 0',
                    borderTop: '1px solid var(--colorNeutralStroke2)'
                  }}>
                    <Button
                      appearance="primary"
                      size="medium"
                      onClick={handleApproveTaskPlan}
                      disabled={processingApproval}
                      icon={<CheckmarkCircleRegular />}
                      style={{ minWidth: '150px' }}
                    >
                      Approve Task Plan
                    </Button>
                    <Button
                      appearance="outline"
                      size="medium"
                      onClick={handleRejectPlan}
                      disabled={processingApproval}
                      style={{ 
                        minWidth: '120px',
                        borderColor: 'var(--colorPaletteRedBorder1)',
                        color: 'var(--colorPaletteRedForeground1)'
                      }}
                    >
                      Reject Plan
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </Body1>
        </div>
      </>
    );
  };

  // Group streaming messages by agent 
  const groupStreamingMessages = useCallback((messages: StreamingPlanUpdate[]): GroupedMessage[] => {
    const groups: { [key: string]: GroupedMessage } = {};

    messages.forEach((msg) => {
        // Create a unique key for grouping (agent + step)
        const groupKey = `${msg.agent_name || 'system'}_${msg.step_id || 'general'}`;
        
        if (!groups[groupKey]) {
          groups[groupKey] = {
            id: groupKey,
            agent_name: msg.agent_name || 'Assistant',
            messages: [],
            status: msg.status || 'in_progress',
            latest_timestamp: normalizeTimestamp(msg.timestamp),
            step_id: msg.step_id,
          };
        }

        groups[groupKey].messages.push(msg);
        
         // Update status to latest
        const msgTimestamp = normalizeTimestamp(msg.timestamp);
        const groupTimestamp = groups[groupKey].latest_timestamp;
        if (msgTimestamp > groupTimestamp) {
          groups[groupKey].status = msg.status || groups[groupKey].status;
          groups[groupKey].latest_timestamp = msgTimestamp;
        }
      });

      return Object.values(groups).sort((a, b) => 
        new Date(a.latest_timestamp).getTime() - new Date(b.latest_timestamp).getTime()
      );
    }, []);

    // Update grouped messages when streaming messages change
    useEffect(() => {
      if (streamingMessages.length > 0) {
        const grouped = groupStreamingMessages(streamingMessages);
        setGroupedStreamingMessages(grouped);
      } else {
        // Clear grouped messages when no streaming messages
        setGroupedStreamingMessages([]);
      }
    }, [streamingMessages, groupStreamingMessages]);

    // Auto-scroll behavior
    useEffect(() => {
      scrollToBottom();
    }, [messages, groupedStreamingMessages, planApprovalRequest]);

  useEffect(() => {
      const container = messagesContainerRef.current;
      if (!container) return;

      const handleScroll = () => {
        const { scrollTop, scrollHeight, clientHeight } = container;
        setShowScrollButton(scrollTop + clientHeight < scrollHeight - 100);
      };

      container.addEventListener("scroll", handleScroll);
      return () => container.removeEventListener("scroll", handleScroll);
    }, []);

    useEffect(() => {
      if (inputContainerRef.current) {
        setInputHeight(inputContainerRef.current.offsetHeight);
      }
    }, [input]);

    const scrollToBottom = () => {
      messagesContainerRef.current?.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
      setShowScrollButton(false);
    };

    // Get status icon for streaming messages
    const getStatusIcon = (status: string) => {
      switch (status) {
        case 'completed':
          return <CheckmarkCircleRegular style={{ color: 'var(--colorPaletteGreenForeground1)' }} />;
        case 'error':
          return <ErrorCircleRegular style={{ color: 'var(--colorPaletteRedForeground1)' }} />;
        case 'in_progress':
          return <Spinner size="extra-tiny" />;
        default:
          return <ClockRegular />;
      }
    };

    // Get message type text for tags
    const getMessageTypeText = (messageType?: string, status?: string): string => {
      if (messageType === 'thinking') return 'Thinking';
      if (messageType === 'action') return 'Action';
      if (messageType === 'result') return 'Result';
      if (messageType === 'clarification_needed') return 'Needs Input';
      
      // Fallback based on status
      switch (status) {
        case 'completed':
          return 'Completed';
        case 'error':
          return 'Error';
        case 'in_progress':
          return status === 'in_progress' ? 'In Progress' : 'Live';
        default:
          return 'Live';
      }
    };

    if (!planData && !loading) {
      return (
        <ContentNotFound subtitle="The requested page could not be found." />
      );
    }

  // Render a grouped streaming message
  const renderGroupedStreamingMessage = (group: GroupedMessage) => {
    const latestMessage = group.messages[group.messages.length - 1];
    const hasMultipleMessages = group.messages.length > 1;
    const displayName = getAgentDisplayName(group.agent_name);

    return (
      <div key={group.id} className="message assistant streaming-message">
        <div className="plan-chat-header">
          <div className="plan-chat-speaker">
            <Body1 className="speaker-name">
              {displayName}
            </Body1>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="brand"
              className="agent-tag"
            >
              {displayName.toUpperCase()}
            </Tag>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="outline"
              icon={getStatusIcon(group.status)}
            >
              {getMessageTypeText(latestMessage.message_type, group.status)}
            </Tag>
          </div>
        </div>

        <Body1>
          <div className="plan-chat-message-content">
            {hasMultipleMessages ? (
              // Show all messages if there are multiple
              group.messages.map((msg, msgIndex) => (
                <div key={`${group.id}-msg-${msgIndex}`} style={{ marginBottom: msgIndex < group.messages.length - 1 ? '8px' : '0' }}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypePrism]}
                  >
                    {TaskService.cleanHRAgent(msg.content || '')}
                  </ReactMarkdown>
                </div>
              ))
            ) : (
              // Show single message
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypePrism]}
              >
                {TaskService.cleanHRAgent(latestMessage.content || '')}
              </ReactMarkdown>
            )}

            <div className="assistant-footer">
              <div className="assistant-actions">
                <div>
                  <Button
                    onClick={() =>
                      latestMessage.content &&
                      navigator.clipboard.writeText(latestMessage.content)
                    }
                    title="Copy Response"
                    appearance="subtle"
                    style={{ height: 28, width: 28 }}
                    icon={<Copy />}
                  />
                </div>

                <Tag
                  icon={<DiamondRegular />}
                  appearance="filled"
                  size="extra-small"
                >
                  Live updates from {displayName.toLowerCase()}
                </Tag>
              </div>
            </div>
          </div>
        </Body1>
      </div>
    );
  };

// Check if agents are actively working
const agentsWorking = streamingMessages.length > 0 && 
  groupedStreamingMessages.some(group => 
    group.status === 'in_progress' || 
    group.messages.some(msg => msg.status === 'in_progress')
  );

// Get the name of the currently working agent
const getWorkingAgentName = (): string | null => {
  if (!agentsWorking) return null;
  
  // Find the first agent that's currently in progress
  const workingGroup = groupedStreamingMessages.find(group => 
    group.status === 'in_progress' || 
    group.messages.some(msg => msg.status === 'in_progress')
  );
  
  return workingGroup ? getAgentDisplayName(workingGroup.agent_name) : null;
};

const workingAgentName = getWorkingAgentName();

// Check if we need clarification (any message with clarification_needed type)
const needsClarification = groupedStreamingMessages.some(group => 
  group.messages.some(msg => msg.message_type === 'clarification_needed')
);

// Disable input appropriately:
// - Disable when agents are working (streaming)
// - Enable only for clarification when needed
// - Disable when plan approval is pending
const shouldDisableInput = !planData?.enableChat || 
  submittingChatDisableInput || 
  (agentsWorking && !needsClarification) || 
  !!planApprovalRequest;

// Generate dynamic placeholder text
const getPlaceholderText = (): string => {
  if (planApprovalRequest) {
    return "Waiting for your approval...";
  }
  if (needsClarification) {
    return "Agent needs your input - please provide clarification...";
  }
  if (workingAgentName) {
    return `${workingAgentName} is working on your plan...`;
  }
  return "Add more info to this task...";
};

  console.log('PlanChat - streamingMessages:', streamingMessages);
  console.log('PlanChat - submittingChatDisableInput:', submittingChatDisableInput);
  console.log('PlanChat - shouldDisableInput:', shouldDisableInput);
  console.log('PlanChat - planApprovalRequest:', planApprovalRequest);

  return (
    <div className="chat-container">
      <div className="messages" ref={messagesContainerRef}>
        {/* WebSocket Connection Status */}
        {wsConnected && (
          <div className="connection-status">
            <Tag
              appearance="filled"
              color="success"
              size="extra-small"
              icon={<DiamondRegular />}
            >
              Real-time updates active
            </Tag>
          </div>
        )}

        <div className="message-wrapper">
          {/* ✅ Always render regular messages (including user's original input task) */}
          {messages.map((msg, index) => {
            const isHuman = msg.source === AgentType.HUMAN;
            const displayName = isHuman ? 'You' : getAgentDisplayName(msg.source);

            return (
              <div
                key={`regular-${index}`}
                className={`message ${isHuman ? 'user' : 'assistant'} ${hasStreamingProperties(msg) && msg.streaming ? 'streaming-message' : ''}`}
              >
                {!isHuman ? (
                  <div className="plan-chat-header">
                    <div className="plan-chat-speaker">
                      <Body1 className="speaker-name">
                        {displayName}
                      </Body1>
                      <Tag
                        size="extra-small"
                        shape="rounded"
                        appearance="brand"
                        className="agent-tag"
                      >
                        {displayName.toUpperCase()}
                      </Tag>
                      {hasStreamingProperties(msg) && msg.streaming && (
                        <Tag
                          size="extra-small"
                          shape="rounded"
                          appearance="outline"
                          icon={getStatusIcon(msg.status || 'in_progress')}
                        >
                          {getMessageTypeText(msg.message_type, msg.status)}
                        </Tag>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="plan-chat-header">
                    <div className="plan-chat-speaker" style={{ justifyContent: 'flex-end' }}>
                      <Tag
                        size="extra-small"
                        shape="rounded"
                        appearance="brand"
                        icon={<PersonRegular />}
                      >
                        YOU
                      </Tag>
                      <Body1 className="speaker-name">You</Body1>
                    </div>
                  </div>
                )}

                <Body1>
                  <div className="plan-chat-message-content">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypePrism]}
                    >
                      {TaskService.cleanHRAgent(msg.content)}
                    </ReactMarkdown>

                    {!isHuman && (
                      <div className="assistant-footer">
                        <div className="assistant-actions">
                          <div>
                            <Button
                              onClick={() => navigator.clipboard.writeText(msg.content)}
                              title="Copy Response"
                              appearance="subtle"
                              style={{ height: 28, width: 28 }}
                              icon={<Copy />}
                            />
                          </div>
                          <Tag
                            icon={<DiamondRegular />}
                            appearance="filled"
                            size="extra-small"
                          >
                            {displayName.toLowerCase()}
                          </Tag>
                        </div>
                      </div>
                    )}
                  </div>
                </Body1>
              </div>
            );
          })}

          {/* ✅ Always render streaming messages for real-time agent updates */}
          {groupedStreamingMessages.map(group => renderGroupedStreamingMessage(group))}

          {/* ✅ Always render plan approval request if present */}
          {renderPlanApprovalRequest()}
        </div>
      </div>

      {showScrollButton && (
        <Tag
          onClick={scrollToBottom}
          className="scroll-to-bottom plan-chat-scroll-button"
          shape="circular"
          style={{
            bottom: inputHeight,
            position: "absolute",
            right: 16,
            zIndex: 5,
          }}
        >
          Back to bottom
        </Tag>
      )}
      <InlineToaster />
      <div ref={inputContainerRef} className="plan-chat-input-container">
        <div className="plan-chat-input-wrapper">
          <ChatInput
            value={input}
            onChange={setInput}
            onEnter={() => OnChatSubmit(input)}
            disabledChat={shouldDisableInput}
            placeholder={getPlaceholderText()}
          >
            <Button
              appearance="transparent"
              onClick={() => OnChatSubmit(input)}
              icon={<Send />}
              disabled={shouldDisableInput}
            />
          </ChatInput>
        </div>
      </div>
    </div>
  );
};

export default PlanChat;