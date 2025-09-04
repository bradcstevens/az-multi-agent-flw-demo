import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";
import {
  Textarea,
  Button,
  Body1,
  Spinner,
  Tag,
  Text,
} from "@fluentui/react-components";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  CheckmarkCircleRegular,
  ClockRegular,
  PersonRegular,
  ErrorCircleRegular,
  DiamondRegular,
  ArrowDownRegular,
  PlayRegular,
  CheckmarkRegular,
  DismissRegular,
  SendRegular,
} from "@fluentui/react-icons";
import { PlanChatProps, ChatMessage, ParsedPlanData } from "../../models/plan";
import { TaskService } from "../../services/TaskService";
import { PlanDataService } from "../../services/PlanDataService";
import webSocketService, { StreamingPlanUpdate } from "../../services/WebSocketService";
import { AgentType } from "../../models/enums";
import ChatInput from "../../coral/modules/ChatInput";
import ContentNotFound from "../NotFound/ContentNotFound";
import { Send, Copy } from "../../coral/imports/bundleicons";
import { useNavigate } from "react-router-dom";
import LoadingMessage, { loadingMessages } from "../../coral/components/LoadingMessage";
import Octo from "../../coral/imports/Octopus.png";
import InlineToaster from "../toast/InlineToaster";

// Enhanced streaming message types
interface RobustStreamingMessage extends Omit<StreamingPlanUpdate, 'message_type'> {
  message_type: 'thinking' | 'action' | 'result' | 'clarification_needed' | 'plan_approval_request' | 'final_result' | 'orchestration_update' | 'step_started' | 'step_completed';
  step_id?: string;
  is_final?: boolean;
  orchestrator_status?: 'planning' | 'executing' | 'completed' | 'error';
  step_progress?: {
    current_step: number;
    total_steps: number;
    step_title?: string;
  };
}

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
  messages: RobustStreamingMessage[];
  status: string;
  latest_timestamp: string;
  step_id?: string;
  message_type?: string;
  is_orchestration?: boolean;
}

// Orchestration status
interface OrchestrationStatus {
  status: 'idle' | 'planning' | 'executing' | 'completed' | 'error';
  current_step: number;
  total_steps: number;
  current_step_title?: string;
  active_agents: string[];
}

// Extended PlanChatProps
interface ExtendedPlanChatProps extends PlanChatProps {
  onPlanReceived?: (planData: ParsedPlanData) => void;
}

// ✅ OPTIMIZATION: Move helper functions outside component to prevent recreation
const normalizeTimestamp = (timestamp?: string | number): string => {
  if (!timestamp) return new Date().toISOString();
  if (typeof timestamp === 'number') {
    return new Date(timestamp * 1000).toISOString();
  }
  return timestamp;
};

const formatAgentDisplayName = (agentName?: string): string | null => {
  if (!agentName || agentName.trim() === '' || agentName.toLowerCase() === 'system') {
    return null;
  }
  
  const cleaned = agentName.trim();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
};

const getAgentTag = (agentName?: string, source?: string): string | null => {
  if (agentName && agentName.trim() !== '' && agentName.toLowerCase() !== 'system') {
    return agentName.toUpperCase();
  }
  
  if (source && source !== AgentType.HUMAN) {
    return source.toUpperCase();
  }
  
  return null;
};

// ✅ OPTIMIZATION: Optimized grouping function outside component
const groupStreamingMessagesOptimized = (messages: StreamingPlanUpdate[]): GroupedMessage[] => {
  const groups: { [key: string]: GroupedMessage } = {};

  messages.forEach((msg) => {
    const robustMsg = msg as RobustStreamingMessage;
    
    // Create unique key for grouping
    const groupKey = `${robustMsg.agent_name || 'system'}_${robustMsg.step_id || 'general'}_${robustMsg.message_type || 'action'}`;
    
    if (!groups[groupKey]) {
      groups[groupKey] = {
        id: groupKey,
        agent_name: robustMsg.agent_name || 'Assistant',
        messages: [],
        status: robustMsg.status || 'in_progress',
        latest_timestamp: normalizeTimestamp(robustMsg.timestamp),
        step_id: robustMsg.step_id,
        message_type: robustMsg.message_type,
        is_orchestration: robustMsg.agent_name?.toLowerCase().includes('orchestrator') || 
                        robustMsg.agent_name?.toLowerCase().includes('planner') ||
                        robustMsg.message_type === 'orchestration_update'
      };
    }

    groups[groupKey].messages.push(robustMsg);
    
    // Update status to latest
    const msgTimestamp = normalizeTimestamp(robustMsg.timestamp);
    const groupTimestamp = groups[groupKey].latest_timestamp;
    if (msgTimestamp > groupTimestamp) {
      groups[groupKey].status = robustMsg.status || groups[groupKey].status;
      groups[groupKey].latest_timestamp = msgTimestamp;
    }
  });

  return Object.values(groups).sort((a, b) => 
    new Date(a.latest_timestamp).getTime() - new Date(b.latest_timestamp).getTime()
  );
};

const PlanChat: React.FC<ExtendedPlanChatProps> = ({
  planData,
  input,
  loading,
  setInput,
  submittingChatDisableInput,
  OnChatSubmit,
  streamingMessages = [],
  wsConnected = false,
  onPlanApproval,
  onPlanReceived,
}) => {
  const navigate = useNavigate();
  const messages = planData?.messages || [];
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [inputHeight, setInputHeight] = useState(0);
  
  // Plan approval states
  const [planApprovalRequest, setPlanApprovalRequest] = useState<ParsedPlanData | null>(null);
  const [processingApproval, setProcessingApproval] = useState(false);
  const [planApproved, setPlanApproved] = useState(false);
  
  // Clarification states
  const [userFeedback, setUserFeedback] = useState('');
  const [showClarificationInput, setShowClarificationInput] = useState(false);

  // Loading states
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [showLoadingSpinner, setShowLoadingSpinner] = useState(false);
  const [hasStreamingStarted, setHasStreamingStarted] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState(loadingMessages[0]);
  const [planExecuting, setPlanExecuting] = useState(false);
  
  // Orchestration tracking
  const [orchestrationStatus, setOrchestrationStatus] = useState<OrchestrationStatus>({
    status: 'idle',
    current_step: 0,
    total_steps: 0,
    active_agents: []
  });
  
  // Final results tracking
  const [finalResults, setFinalResults] = useState<RobustStreamingMessage[]>([]);
  const [planCompleted, setPlanCompleted] = useState(false);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  // ✅ OPTIMIZATION: Memoize grouped messages to prevent unnecessary recalculations
  const groupedStreamingMessages = useMemo(() => {
    if (streamingMessages.length === 0) return [];
    return groupStreamingMessagesOptimized(streamingMessages);
  }, [streamingMessages]);

  // ✅ NEW: Render task submission dialogue showing what was sent to backend
  const renderTaskSubmissionDialogue = () => {
    const userTask = planApprovalRequest?.user_request || 
                     planData?.plan?.description ||
                     messages.find(msg => msg.source === AgentType.HUMAN)?.content;

    if (!userTask || userTask.trim() === '') return null;

    return (
      <div key="task-submission" className="message user" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ 
            justifyContent: 'flex-end',
            gap: '8px',
            alignItems: 'center'
          }}>
            <Body1 className="speaker-name">You</Body1>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="outline"
              icon={<CheckmarkCircleRegular />}
              color="success"
            >
              Task Submitted
            </Tag>
          </div>
        </div>

        <Body1>
          <div className="plan-chat-message-content" style={{ 
            padding: '16px 20px',
            lineHeight: 1.6,
            backgroundColor: 'var(--colorNeutralBackground2)',
            borderRadius: '8px',
            border: '1px solid var(--colorNeutralStroke2)'
          }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {userTask}
            </ReactMarkdown>
          </div>
        </Body1>
      </div>
    );
  };

  // Initialize with full-screen loading
  useEffect(() => {
    if (!hasStreamingStarted && streamingMessages.length === 0 && !planApprovalRequest && messages.length === 0) {
      setIsInitialLoading(true);
    } else {
      setIsInitialLoading(false);
    }
  }, [hasStreamingStarted, streamingMessages.length, planApprovalRequest, messages.length]);

  // Loading message rotation
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isInitialLoading || showLoadingSpinner) {
      let index = 0;
      interval = setInterval(() => {
        index = (index + 1) % loadingMessages.length;
        setLoadingMessage(loadingMessages[index]);
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [isInitialLoading, showLoadingSpinner]);

  // ✅ OPTIMIZATION: Simplified streaming processing - removed grouping here
  useEffect(() => {
    console.log('🔍 Processing streaming messages:', streamingMessages.length);
    
    if (streamingMessages.length > 0) {
      if (!hasStreamingStarted) {
        console.log('🚀 Streaming started');
        setHasStreamingStarted(true);
        setIsInitialLoading(false);
        setShowLoadingSpinner(false);
        setPlanExecuting(true);
      }
      
      // Process streaming messages
      const robustMessages = streamingMessages.map(msg => ({
        ...msg,
        message_type: msg.message_type || 'action',
        is_final: false,
      } as RobustStreamingMessage));
      
      // Track orchestration status
      const orchestrationMessages = robustMessages.filter(msg => 
        msg.message_type === 'orchestration_update' || 
        msg.agent_name?.toLowerCase().includes('orchestrator') ||
        msg.agent_name?.toLowerCase().includes('planner')
      );
      
      if (orchestrationMessages.length > 0) {
        const latestOrchestration = orchestrationMessages[orchestrationMessages.length - 1];
        setOrchestrationStatus(prev => ({
          ...prev,
          status: latestOrchestration.orchestrator_status || 'executing',
          current_step: latestOrchestration.step_progress?.current_step || prev.current_step,
          total_steps: latestOrchestration.step_progress?.total_steps || prev.total_steps,
          current_step_title: latestOrchestration.step_progress?.step_title,
        }));
      }
      
      // Filter active agents
      const activeAgents = [...new Set(
        robustMessages
          .filter(msg => msg.agent_name && msg.agent_name !== 'system')
          .map(msg => msg.agent_name)
          .filter((name): name is string => name !== undefined)
      )];
      
      setOrchestrationStatus(prev => ({
        ...prev,
        active_agents: activeAgents
      }));
      
      // Track final results
      const finalResultMessages = robustMessages.filter(msg => 
        msg.message_type === 'final_result' || 
        (msg.message_type === 'result' && msg.status === 'completed')
      );
      
      if (finalResultMessages.length > 0) {
        setFinalResults(finalResultMessages);
        
        const hasCompletionMessage = finalResultMessages.some(msg => 
          msg.content?.toLowerCase().includes('completed') ||
          msg.content?.toLowerCase().includes('finished') ||
          msg.message_type === 'final_result'
        );
        
        if (hasCompletionMessage) {
          setPlanCompleted(true);
          setOrchestrationStatus(prev => ({ ...prev, status: 'completed' }));
        }
      }
    }
  }, [streamingMessages, hasStreamingStarted]);

  // WebSocket plan approval listener
  useEffect(() => {
    console.log('🔌 Setting up plan approval listener');
    
    const unsubscribePlanApprovalRequest = webSocketService.onPlanApprovalRequest((approvalRequest: any) => {
      console.log('📥 Received plan approval request:', approvalRequest);
      
      let parsedPlanData: ParsedPlanData | null = null;
      
      if (approvalRequest.parsedData) {
        parsedPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest);
        if (parsedPlanData) {
          setPlanApprovalRequest(parsedPlanData);
          onPlanReceived?.(parsedPlanData);
        }
      } else {
        parsedPlanData = approvalRequest;
        setPlanApprovalRequest(approvalRequest);
        onPlanReceived?.(approvalRequest);
      }
      
      // Reset states
      setPlanExecuting(false);
      setIsInitialLoading(false);
      setShowLoadingSpinner(false);
      setHasStreamingStarted(false);
      setPlanApproved(false);
      setPlanCompleted(false);
      setFinalResults([]);
      setOrchestrationStatus({
        status: 'idle',
        current_step: 0,
        total_steps: parsedPlanData?.steps?.length || 0,
        active_agents: []
      });
      
      setUserFeedback('');
      setShowClarificationInput(false);
      setTimeout(() => scrollToBottom(), 100);
    });

    return () => {
      unsubscribePlanApprovalRequest();
    };
  }, [onPlanReceived]);

  // Handle final plan approval
  const handleSendFinalPlan = useCallback(async () => {
    if (!planApprovalRequest) return;
    
    console.log('🚀 Starting plan execution...');
    setProcessingApproval(true);
    setPlanExecuting(true);
    setShowLoadingSpinner(true);
    setHasStreamingStarted(false);
    setOrchestrationStatus(prev => ({ ...prev, status: 'planning' }));
    
    try {
      const approvalResponse = {
        plan_id: planApprovalRequest.id,
        session_id: planData?.plan?.session_id || '',
        approved: true,
        feedback: userFeedback || 'Plan approved by user'
      };

      webSocketService.sendPlanApprovalResponse(approvalResponse);

      await fetch('/api/v3/plan_approval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_dot_id: planApprovalRequest.id,
          approved: true,
          feedback: userFeedback || 'Plan approved by user'
        })
      });
      
      webSocketService.subscribeToPlan(planApprovalRequest.id);
      onPlanApproval?.(true);
      
      setUserFeedback('');
      setShowClarificationInput(false);
      setPlanApproved(true);
      
    } catch (error) {
      console.error('❌ Failed to send plan approval:', error);
      setShowLoadingSpinner(false);
      setPlanExecuting(false);
      setHasStreamingStarted(false);
      setOrchestrationStatus(prev => ({ ...prev, status: 'error' }));
    } finally {
      setProcessingApproval(false);
    }
  }, [planApprovalRequest, planData?.plan?.session_id, userFeedback, onPlanApproval]);

  // Handle approve button click
  const handleApproveTaskPlan = useCallback(() => {
    setShowClarificationInput(true);
  }, []);

  // Handle reject button click
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

      webSocketService.sendPlanApprovalResponse(rejectionResponse);
      onPlanApproval?.(false);
      navigate('/');
      
    } catch (error) {
      console.error('❌ Failed to send plan rejection:', error);
      navigate('/');
    } finally {
      setProcessingApproval(false);
    }
  }, [planApprovalRequest, planData?.plan?.session_id, onPlanApproval, navigate]);

  // Render agent working message
  const renderAgentWorkingMessage = () => {
    if (!planApproved || !planExecuting || orchestrationStatus.active_agents.length === 0) return null;

    const activeAgent = orchestrationStatus.active_agents[0];
    const displayName = formatAgentDisplayName(activeAgent);
    const agentTag = getAgentTag(activeAgent);

    return (
      <div key="agent-working" className="message assistant agent-working" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
            {displayName && <Body1 className="speaker-name">{displayName}</Body1>}
            {agentTag && (
              <Tag
                size="extra-small"
                shape="rounded"
                appearance="brand"
                className="agent-tag"
              >
                {agentTag}
              </Tag>
            )}
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="outline"
              icon={<Spinner size="extra-tiny" />}
            >
              Working
            </Tag>
          </div>
        </div>
        <Body1>
          <div className="plan-chat-message-content" style={{ 
            padding: '16px 20px',
            backgroundColor: 'var(--colorNeutralBackground1)',
            borderRadius: '8px',
            border: '1px solid var(--colorNeutralStroke2)'
          }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '12px',
              color: 'var(--colorNeutralForeground2)',
              fontStyle: 'italic'
            }}>
              <Spinner size="tiny" />
              {displayName ? `${displayName} is working` : 'Agent is working'} on your plan...
            </div>
          </div>
        </Body1>
      </div>
    );
  };

  // Render full-screen loading
  const renderFullScreenLoading = () => {
    if (!isInitialLoading) return null;

    return (
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'var(--colorNeutralBackground1)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        borderRadius: '12px'
      }}>
        <div style={{ 
          textAlign: 'center',
          maxWidth: '400px',
          padding: '40px'
        }}>
          <LoadingMessage 
            loadingMessage={loadingMessage}
            iconSrc={Octo}
            iconWidth={60}
            iconHeight={60}
          />
          <div style={{ 
            marginTop: '24px',
            color: 'var(--colorNeutralForeground2)',
            fontSize: '18px',
            fontWeight: 500
          }}>
            Analyzing your request...
          </div>
          <div style={{ 
            marginTop: '12px',
            color: 'var(--colorNeutralForeground3)',
            fontSize: '14px',
            fontStyle: 'italic'
          }}>
           
          </div>
        </div>
      </div>
    );
  };

  // Render loading spinner
  const renderLoadingSpinner = () => {
    if (!showLoadingSpinner) return null;

    return (
      <div key="loading-spinner" className="message assistant" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
            <Body1 className="speaker-name">Orchestrator</Body1>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="brand"
              className="agent-tag"
            >
              ORCHESTRATOR
            </Tag>
          </div>
        </div>
        <Body1>
          <div className="plan-chat-message-content" style={{ 
            padding: '16px 20px',
            backgroundColor: 'var(--colorNeutralBackground1)',
            borderRadius: '8px',
            border: '1px solid var(--colorNeutralStroke2)'
          }}>
            <LoadingMessage 
              loadingMessage={loadingMessage}
              iconSrc={Octo}
              iconWidth={24}
              iconHeight={24}
            />
          </div>
        </Body1>
      </div>
    );
  };

  // ✅ REMOVED: renderPlanApprovalRequest - plan approval request removed as requested

  // Render final results
  const renderFinalResults = () => {
    if (finalResults.length === 0) return null;

    return (
      <div key="final-results" className="message assistant final-results" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
            <Body1 className="speaker-name">Orchestrator</Body1>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="filled"
              color="success"
            >
              ORCHESTRATOR
            </Tag>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="outline"
              icon={<CheckmarkCircleRegular />}
              color="success"
            >
              Final Results
            </Tag>
          </div>
        </div>

        <Body1>
          <div className="plan-chat-message-content" style={{ 
            padding: '16px 20px',
            backgroundColor: 'var(--colorNeutralBackground1)',
            borderRadius: '8px',
            border: '1px solid var(--colorNeutralStroke2)'
          }}>
            <div style={{ marginBottom: '16px' }}>
              <Text size={400} weight="semibold" style={{ 
                display: 'block', 
                marginBottom: '12px',
                color: 'var(--colorPaletteGreenForeground2)'
              }}>
                🎉 Plan Execution Complete!
              </Text>
            </div>
            
            {finalResults.map((result, index) => (
              <div key={`final-${index}`} style={{ 
                marginBottom: index < finalResults.length - 1 ? '16px' : '0',
                lineHeight: 1.6
              }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result.content || ''}
                </ReactMarkdown>
              </div>
            ))}
          </div>
        </Body1>
      </div>
    );
  };

  // ✅ OPTIMIZATION: Optimized auto-scroll with debouncing
  const scrollToBottom = useCallback(() => {
    messagesContainerRef.current?.scrollTo({
      top: messagesContainerRef.current.scrollHeight,
      behavior: "smooth",
    });
    setShowScrollButton(false);
  }, []);

  // ✅ OPTIMIZATION: Debounced scroll to bottom
  useEffect(() => {
    const timeoutId = setTimeout(() => scrollToBottom(), 100);
    return () => clearTimeout(timeoutId);
  }, [groupedStreamingMessages, planApprovalRequest, showLoadingSpinner, finalResults, scrollToBottom]);

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
    if (messageType === 'final_result') return 'Final Result';
    if (messageType === 'orchestration_update') return 'Orchestration';
    if (messageType === 'step_started') return 'Step Started';
    if (messageType === 'step_completed') return 'Step Complete';
    
    // Fallback based on status
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'error':
        return 'Error';
      case 'in_progress':
        return 'In Progress';
      default:
        return 'Live';
    }
  };

  // Render grouped streaming message with full WebSocket data
  const renderGroupedStreamingMessage = (group: GroupedMessage) => {
    const latestMessage = group.messages[group.messages.length - 1] as RobustStreamingMessage;
    const hasMultipleMessages = group.messages.length > 1;
    const displayName = formatAgentDisplayName(group.agent_name);
    const agentTag = getAgentTag(group.agent_name);
    const isFinalResult = latestMessage.message_type === 'final_result' || 
                         (latestMessage.message_type === 'result' && latestMessage.status === 'completed');
    
    // Don't render orchestration messages separately - they're handled in the status panel
    if (group.is_orchestration && latestMessage.message_type === 'orchestration_update') {
      return null;
    }

    return (
      <div key={group.id} className="message assistant streaming-message" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
            {displayName && <Body1 className="speaker-name">{displayName}</Body1>}
            {agentTag && (
              <Tag
                size="extra-small"
                shape="rounded"
                appearance={isFinalResult ? "filled" : "brand"}
                className="agent-tag"
                color={isFinalResult ? "success" : undefined}
              >
                {agentTag}
              </Tag>
            )}
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="outline"
              icon={getStatusIcon(group.status)}
              color={isFinalResult ? "success" : undefined}
            >
              {getMessageTypeText(group.message_type, group.status)}
            </Tag>
          </div>
        </div>

        <Body1>
          <div className="plan-chat-message-content" style={{ 
            padding: '16px 20px',
            backgroundColor: 'var(--colorNeutralBackground1)',
            borderRadius: '8px',
            border: '1px solid var(--colorNeutralStroke2)'
          }}>
            {hasMultipleMessages ? (
              // Display all messages in the group
              group.messages.map((msg, msgIndex) => (
                <div key={`${group.id}-msg-${msgIndex}`} style={{ 
                  marginBottom: msgIndex < group.messages.length - 1 ? '16px' : '0',
                  lineHeight: 1.6
                }}>
                  <div style={{ 
                    marginBottom: '8px', 
                    fontSize: '12px', 
                    color: 'var(--colorNeutralForeground3)',
                    fontWeight: '500'
                  }}>
                    {new Date(normalizeTimestamp(msg.timestamp)).toLocaleTimeString()}
                    {msg.step_id && ` • Step ${msg.step_id}`}
                  </div>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content || ''}
                  </ReactMarkdown>
                </div>
              ))
            ) : (
              // Single message
              <div style={{ lineHeight: 1.6 }}>
                <div style={{ 
                  marginBottom: '8px', 
                  fontSize: '12px', 
                  color: 'var(--colorNeutralForeground3)',
                  fontWeight: '500'
                }}>
                  {new Date(normalizeTimestamp(latestMessage.timestamp)).toLocaleTimeString()}
                  {latestMessage.step_id && ` • Step ${latestMessage.step_id}`}
                </div>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {latestMessage.content || ''}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </Body1>
      </div>
    );
  };

  // Enhanced agent working detection
  const agentsWorking = streamingMessages.length > 0 && !planCompleted;

  const getWorkingAgentName = (): string | null => {
    if (!agentsWorking || orchestrationStatus.active_agents.length === 0) return null;
    return formatAgentDisplayName(orchestrationStatus.active_agents[0]);
  };

  const workingAgentName = getWorkingAgentName();

  // Check if we need clarification
  const needsClarification = groupedStreamingMessages.some(group => 
    group.messages.some(msg => (msg as RobustStreamingMessage).message_type === 'clarification_needed')
  );

  // Enhanced input control
  const shouldDisableInput = !planData?.enableChat || 
    submittingChatDisableInput || 
    (agentsWorking && !needsClarification) || 
    (!!planApprovalRequest && !planApproved) ||
    planCompleted ||
    isInitialLoading;

  // Enhanced placeholder text
  const getPlaceholderText = (): string => {
    if (isInitialLoading) {
      return "Loading...";
    }
    if (planCompleted) {
      return "Plan completed! Start a new task to continue...";
    }
    if (planApprovalRequest && !planApproved) {
      return "Waiting for your approval...";
    }
    if (needsClarification) {
      return "Agent needs your input - please provide clarification...";
    }
    if (workingAgentName) {
      return `${workingAgentName} is working on your plan...`;
    }
    if (orchestrationStatus.status === 'executing') {
      return "Plan execution in progress...";
    }
    return "Add more info to this task...";
  };

  if (!planData && !loading) {
    return (
      <ContentNotFound subtitle="The requested page could not be found." />
    );
  }

  // Render full-screen loading first
  if (isInitialLoading) {
    return renderFullScreenLoading();
  }

  return (
    <div className="chat-container" style={{
      // ✅ NEW: Added requested padding and layout styles
      display: 'flex',
      padding: '48px 0 24px 0',
      flexDirection: 'column',
      justifyContent: 'flex-end',
      alignItems: 'center',
      gap: '24px',
      alignSelf: 'stretch'
    }}>
      <div className="messages" 
           ref={messagesContainerRef}
           style={{ 
             paddingBottom: `${inputHeight + 32}px`, 
             padding: '32px', // ✅ MORE PADDING around planChat div
             width: '100%',
             maxWidth: '100%'
           }}>
        
        {wsConnected && (
          <div style={{ 
            padding: '8px 12px', 
            backgroundColor: 'var(--colorPaletteGreenBackground3)', 
            color: 'var(--colorPaletteGreenForeground1)',
            borderRadius: '6px',
            fontSize: '12px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <div style={{ 
              width: '6px', 
              height: '6px', 
              backgroundColor: 'var(--colorPaletteGreenForeground1)', 
              borderRadius: '50%' 
            }} />
            Connected to real-time updates
          </div>
        )}

        <div className="message-wrapper" style={{ maxWidth: '100%' }}>
          
          {/* ✅ NEW: Task submission dialogue - shows what was sent to backend */}
          {renderTaskSubmissionDialogue()}

          {/* Loading spinner */}
          {renderLoadingSpinner()}

          {/* Agent working message */}
          {renderAgentWorkingMessage()}

          {/* All streaming messages - FULL WebSocket content */}
          {groupedStreamingMessages.map(group => renderGroupedStreamingMessage(group))}

          {/* Final results */}
          {renderFinalResults()}

          {/* Regular chat messages */}
          {messages.map((msg, index) => {
            const isHuman = msg.source === AgentType.HUMAN;
            const displayName = isHuman ? 'You' : formatAgentDisplayName(msg.source);
            const agentTag = isHuman ? 'YOU' : getAgentTag(undefined, msg.source);

            // Skip rendering the user's original task again if it's already shown above
            if (isHuman && index === 0 && planApprovalRequest?.user_request) {
              return null;
            }

            return (
              <div
                key={`regular-${index}`}
                className={`message ${isHuman ? 'user' : 'assistant'} ${hasStreamingProperties(msg) && msg.streaming ? 'streaming-message' : ''}`}
                style={{ marginBottom: '24px' }}
              >
                {!isHuman ? (
                  <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
                    <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
                      {displayName && <Body1 className="speaker-name">{displayName}</Body1>}
                      {agentTag && (
                        <Tag
                          size="extra-small"
                          shape="rounded"
                          appearance="brand"
                          className="agent-tag"
                        >
                          {agentTag}
                        </Tag>
                      )}
                      {hasStreamingProperties(msg) && msg.streaming && (
                        <Tag
                          size="extra-small"
                          shape="rounded"
                          appearance="outline"
                          icon={<Spinner size="extra-tiny" />}
                        >
                          Live
                        </Tag>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
                    <div className="plan-chat-speaker" style={{ 
                      justifyContent: 'flex-end',
                      gap: '8px',
                      alignItems: 'center'
                    }}>
                      <Body1 className="speaker-name">You</Body1>
                    </div>
                  </div>
                )}

                <Body1>
                  <div className="plan-chat-message-content" style={{ 
                    padding: '16px 20px',
                    lineHeight: 1.6,
                    backgroundColor: isHuman ? 'var(--colorNeutralBackground2)' : 'var(--colorNeutralBackground1)',
                    borderRadius: '8px',
                    border: '1px solid var(--colorNeutralStroke2)'
                  }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                </Body1>
              </div>
            );
          })}
        </div>
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <Button
          onClick={scrollToBottom}
          appearance="subtle"
          icon={<ArrowDownRegular />}
          style={{
            position: 'fixed',
            bottom: inputHeight + 32,
            right: 32,
            zIndex: 5,
            borderRadius: '50%',
            width: '44px',
            height: '44px',
            minWidth: '44px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
          }}
          title="Scroll to bottom"
        />
      )}

      {/* Toast notifications */}
      <InlineToaster />
      
      {/* Chat input */}
      <div ref={inputContainerRef} className="plan-chat-input-container" style={{ padding: '16px 24px 24px' }}>
        <div className="plan-chat-input-wrapper" style={{
          maxWidth: '100%',
          margin: '0 auto'
        }}>
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
              style={{ height: '40px', width: '40px' }}
            />
          </ChatInput>
        </div>
      </div>
    </div>
  );
};

export default PlanChat;