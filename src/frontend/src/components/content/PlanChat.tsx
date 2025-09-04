import React, { useState, useRef, useCallback, useEffect } from "react";
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

// streaming message types - inherit from StreamingPlanUpdate and override message_type
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

// orchestration status
interface OrchestrationStatus {
  status: 'idle' | 'planning' | 'executing' | 'completed' | 'error';
  current_step: number;
  total_steps: number;
  current_step_title?: string;
  active_agents: string[];
}

// Extended PlanChatProps to include plan data communication to PlanPanelRight
interface ExtendedPlanChatProps extends PlanChatProps {
  onPlanReceived?: (planData: ParsedPlanData) => void; // Communicate plan to parent/PlanPanelRight
}

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
  const [groupedStreamingMessages, setGroupedStreamingMessages] = useState<GroupedMessage[]>([]);
  
  // Add state for plan approval requests
  const [planApprovalRequest, setPlanApprovalRequest] = useState<ParsedPlanData | null>(null);
  const [processingApproval, setProcessingApproval] = useState(false);
  const [planApproved, setPlanApproved] = useState(false);
  
  // Add state for human clarification - only show after approve is clicked
  const [userFeedback, setUserFeedback] = useState('');
  const [showClarificationInput, setShowClarificationInput] = useState(false);

  // loading states
  const [isInitialLoading, setIsInitialLoading] = useState(true); // Full-screen loading
  const [showLoadingSpinner, setShowLoadingSpinner] = useState(false); // Inline loading
  const [hasStreamingStarted, setHasStreamingStarted] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState(loadingMessages[0]);
  const [planExecuting, setPlanExecuting] = useState(false);
  
  // orchestration tracking
  const [orchestrationStatus, setOrchestrationStatus] = useState<OrchestrationStatus>({
    status: 'idle',
    current_step: 0,
    total_steps: 0,
    active_agents: []
  });
  
  // Track final results and completion
  const [finalResults, setFinalResults] = useState<RobustStreamingMessage[]>([]);
  const [planCompleted, setPlanCompleted] = useState(false);

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
    
    // Special handling for orchestrator/system agents
    if (agentName.toLowerCase().includes('orchestrator') || 
        agentName.toLowerCase() === 'system' ||
        agentName.toLowerCase().includes('planner')) {
      return 'BOT';
    }
    
    // Clean up the agent name for display
    let cleanName = TaskService.cleanTextToSpaces(agentName);
    
    // If it's a generic agent type, make it more readable
    if (cleanName.toLowerCase().includes('agent')) {
      cleanName = cleanName.replace(/agent/gi, '').trim();
    }
    
    // Capitalize first letter of each word
    return cleanName.replace(/\b\w/g, l => l.toUpperCase()) || 'Assistant';
  };

  //  user's original task as dialogue
  const renderUserTaskDialogue = () => {
    // user's original task
    const userTask = planApprovalRequest?.user_request || 
                     planData?.plan?.description ||
                     // Fallback: look for first human message
                     messages.find(msg => msg.source === AgentType.HUMAN)?.content;

    if (!userTask || userTask.trim() === '') return null;

    return (
      <div key="user-task-dialogue" className="message user" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ 
            justifyContent: 'flex-end',
            gap: '8px',
            alignItems: 'center'
          }}>
            {/* <Tag
              size="extra-small"
              shape="rounded"
              appearance="brand"
              icon={<PersonRegular />}
            >
              YOU
            </Tag>
            <Body1 className="speaker-name">You</Body1> */}
          </div>
        </div>

        <Body1>
          <div className="plan-chat-message-content" style={{ padding: '16px 20px' }}>
            <div style={{ 
              padding: '0',
              lineHeight: 1.6,
              marginBottom: '12px'
            }}>
              <Text size={300}>
                {userTask}
              </Text>
            </div>

            {/* <div style={{ 
              marginTop: '12px',
              fontSize: '12px',
              color: 'var(--colorNeutralForeground3)',
              fontStyle: 'italic'
            }}>
              Original task request
            </div> */}
          </div>
        </Body1>
      </div>
    );
  };

  //  Initialize with full-screen loading
  useEffect(() => {
    // Start with full-screen loading on page load
    if (!hasStreamingStarted && streamingMessages.length === 0 && !planApprovalRequest && messages.length === 0) {
      setIsInitialLoading(true);
    } else {
      setIsInitialLoading(false);
    }
  }, [hasStreamingStarted, streamingMessages.length, planApprovalRequest, messages.length]);

  // Loading message rotation effect
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

  //  Real-time streaming with robust orchestration tracking
  useEffect(() => {
    console.log('🔍 Processing streaming messages:', streamingMessages.length);
    
    if (streamingMessages.length > 0) {
      // Hide full-screen loading as soon as we get ANY streaming message
      if (!hasStreamingStarted) {
        console.log('🚀 Streaming started, hiding full-screen loading');
        setHasStreamingStarted(true);
        setIsInitialLoading(false);
        setShowLoadingSpinner(false);
        setPlanExecuting(true);
      }
      
      // Process streaming messages
      const robustMessages = streamingMessages.map(msg => ({
        ...msg,
        message_type: msg.message_type || 'action',
        is_final: false, // Will be determined by status and content
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
      
      // Filter out undefined values from active agents array
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
      
      //  Track final results
      const finalResultMessages = robustMessages.filter(msg => 
        msg.message_type === 'final_result' || 
        (msg.message_type === 'result' && msg.status === 'completed')
      );
      
      if (finalResultMessages.length > 0) {
        setFinalResults(finalResultMessages);
        
        // Check if plan is completed
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
      
      console.log('🤖 Active agents:', activeAgents);
      console.log('🎯 Orchestration status:', orchestrationStatus.status);
    }
  }, [streamingMessages, hasStreamingStarted, orchestrationStatus.status]);

  // Add WebSocket listener for plan approval requests
  useEffect(() => {
    console.log('🔌 PlanChat setting up plan approval listener');
    
    // Handle v3 plan approval requests
    const unsubscribePlanApprovalRequest = webSocketService.onPlanApprovalRequest((approvalRequest: any) => {
      console.log('📥 Received plan approval request immediately:', approvalRequest);
      
      let parsedPlanData: ParsedPlanData | null = null;
      
      if (approvalRequest.parsedData) {
        parsedPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest);
        if (parsedPlanData) {
          console.log('✅ Parsed plan data - showing immediately:', parsedPlanData);
          setPlanApprovalRequest(parsedPlanData);
          
          // Send plan data to PlanPanelRight via parent
          onPlanReceived?.(parsedPlanData);
          
          // Reset states
          setPlanExecuting(false);
          setIsInitialLoading(false); // Hide full-screen loading
          setShowLoadingSpinner(false);
          setHasStreamingStarted(false);
          setPlanApproved(false);
          setPlanCompleted(false);
          setFinalResults([]);
          setOrchestrationStatus({
            status: 'idle',
            current_step: 0,
            total_steps: parsedPlanData.steps?.length || 0,
            active_agents: []
          });
        } else {
          console.error('❌ Failed to parse plan approval request');
        }
      } else {
        console.log('✅ Direct plan approval data - showing immediately');
        parsedPlanData = approvalRequest;
        setPlanApprovalRequest(approvalRequest);
        
        // Send plan data to PlanPanelRight via parent
        onPlanReceived?.(approvalRequest);
        
        // Reset states
        setPlanExecuting(false);
        setIsInitialLoading(false); // Hide full-screen loading
        setShowLoadingSpinner(false);
        setHasStreamingStarted(false);
        setPlanApproved(false);
        setPlanCompleted(false);
        setFinalResults([]);
        setOrchestrationStatus({
          status: 'idle',
          current_step: 0,
          total_steps: approvalRequest.steps?.length || 0,
          active_agents: []
        });
      }
      
      setUserFeedback('');
      setShowClarificationInput(false);
      setTimeout(() => scrollToBottom(), 100);
    });

    return () => {
      console.log('🔌 PlanChat cleaning up plan approval listeners');
      unsubscribePlanApprovalRequest();
    };
  }, [onPlanReceived]);

  // Handle sending final plan approval to backend
  const handleSendFinalPlan = useCallback(async () => {
    if (!planApprovalRequest) return;
    
    console.log('🚀 Starting plan execution...');
    setProcessingApproval(true);
    setPlanExecuting(true);
    setShowLoadingSpinner(true); // Use inline loading for post-approval
    setHasStreamingStarted(false);
    setOrchestrationStatus(prev => ({ ...prev, status: 'planning' }));
    
    try {
       const approvalResponse = {
        plan_id: planApprovalRequest.id,
        session_id: planData?.plan?.session_id || '',
        approved: true,
        feedback: userFeedback || 'Plan approved by user'
      };

      console.log('🚀 Sending FINAL plan approval to backend:', approvalResponse);

      // Send final approval response via WebSocket
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
      
      console.log('📡 Subscribing to plan for streaming messages:', planApprovalRequest.id);
      webSocketService.subscribeToPlan(planApprovalRequest.id);
      
      // Notify parent component that plan was approved
      onPlanApproval?.(true);
      
      // Clear clarification UI state but keep approval request
      setUserFeedback('');
      setShowClarificationInput(false);
      setPlanApproved(true);
      
      console.log('✅ Final plan approved and sent to backend:', planApprovalRequest.id);
      
    } catch (error) {
      console.error('❌ Failed to send final plan approval:', error);
      setShowLoadingSpinner(false);
      setPlanExecuting(false);
      setHasStreamingStarted(false);
      setOrchestrationStatus(prev => ({ ...prev, status: 'error' }));
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

  // Render ChatGPT-style "Agent is working..." message
  const renderAgentWorkingMessage = () => {
    if (!planApproved || !planExecuting || orchestrationStatus.active_agents.length === 0) return null;

    const workingAgent = getAgentDisplayName(orchestrationStatus.active_agents[0]);

    return (
      <div key="agent-working" className="message assistant agent-working" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
            <Body1 className="speaker-name">BOT</Body1>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance="brand"
            >
              ORCHESTRATOR
            </Tag>
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
          <div className="plan-chat-message-content" style={{ padding: '16px 20px' }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '12px',
              padding: '12px 0'
            }}>
              <LoadingMessage 
                loadingMessage={`${workingAgent} is working on the final result...`}
                iconSrc={Octo}
                iconWidth={20}
                iconHeight={20}
              />
            </div>
            <div style={{ 
              color: 'var(--colorNeutralForeground3)',
              fontStyle: 'italic',
              fontSize: '12px',
              marginTop: '8px'
            }}>
              Plan execution in progress. You'll see real-time updates as agents complete their tasks.
            </div>
          </div>
        </Body1>
      </div>
    );
  };

  // Render full-screen loading overlay
  const renderFullScreenLoading = () => {
    if (!isInitialLoading) return null;

    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'var(--colorNeutralBackground1)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000
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
            marginTop: '20px',
            color: 'var(--colorNeutralForeground2)',
            fontSize: '16px'
          }}>
            Preparing your multi-agent workspace...
          </div>
          <div style={{ 
            marginTop: '12px',
            color: 'var(--colorNeutralForeground3)',
            fontSize: '14px',
            fontStyle: 'italic'
          }}>
            Our orchestrator is assembling the perfect team for your task
          </div>
        </div>
      </div>
    );
  };

  // ✅ Render octopus loading spinner (inline)
  const renderLoadingSpinner = () => {
    if (!showLoadingSpinner) return null;

    return (
      <div key="loading-spinner" className="message assistant" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
            <Body1 className="speaker-name">BOT</Body1>
            <Tag
              size="extra-small"
              shape="rounded"
              style={{ 
                backgroundColor: 'var(--colorPaletteYellowBackground2)',
                color: 'var(--colorPaletteYellowForeground2)',
                border: '1px solid var(--colorPaletteYellowBorder2)'
              }}
            >
              Working
            </Tag>
          </div>
        </div>
        <Body1>
          <div className="plan-chat-message-content" style={{ padding: '16px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 0' }}>
              <LoadingMessage 
                loadingMessage={loadingMessage}
                iconSrc={Octo}
                iconWidth={24}
                iconHeight={24}
              />
            </div>
            <div style={{ 
              color: 'var(--colorNeutralForeground2)',
              fontStyle: 'italic',
              fontSize: '14px',
              marginTop: '8px'
            }}>
              {planApproved ? 'Orchestrator is coordinating agents...' : 'Preparing your plan...'}
            </div>
          </div>
        </Body1>
      </div>
    );
  };

  // ✅ FIXED: Clean up the renderPlanApprovalRequest function
  const renderPlanApprovalRequest = () => {
    if (!planApprovalRequest) return null;

    const getRespondingAgent = (): { displayName: string; agentType: string } => {
      if (planApprovalRequest.team && planApprovalRequest.team.length > 0) {
        const planner = planApprovalRequest.team.find(agent => 
          agent.toLowerCase().includes('planner') || 
          agent.toLowerCase().includes('plan')
        );
        
        if (planner) {
          return {
            displayName: getAgentDisplayName(planner),
            agentType: planner.toUpperCase().replace(/[^A-Z0-9]/g, '_')
          };
        }
        
        const firstAgent = planApprovalRequest.team[0];
        return {
          displayName: getAgentDisplayName(firstAgent),
          agentType: firstAgent.toUpperCase().replace(/[^A-Z0-9]/g, '_')
        };
      }
      
      return { displayName: 'BOT', agentType: 'BOT' };
    };

    const respondingAgent = getRespondingAgent();

    return (
      <>
        {/* Assistant's response with plan */}
        <div key="plan-approval" className="message assistant approval-request" style={{ marginBottom: '24px' }}>
          <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
            <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
              <Body1 className="speaker-name">{respondingAgent.displayName}</Body1>
              <Tag
                size="extra-small"
                shape="rounded"
                appearance="brand"
                className="agent-tag"
              >
                {respondingAgent.agentType}
              </Tag>
              <Tag
                size="extra-small"
                shape="rounded"
                appearance="outline"
                icon={planApproved ? <CheckmarkCircleRegular /> : <ClockRegular />}
              >
                {planApproved ? 'Approved' : 'Plan Ready'}
              </Tag>
            </div>
          </div>

          <Body1>
            <div className="plan-chat-message-content" style={{ padding: '20px 24px' }}>
              <div style={{ marginBottom: '24px' }}>
                <Text size={400} weight="semibold" style={{ display: 'block', marginBottom: '12px' }}>
                  Plan Created! 🎯
                </Text>
                <Text size={300}>
                  I've created a plan with {planApprovalRequest.steps?.length || 0} steps to help you accomplish your goal. 
                  Would you like me to proceed with executing this plan?
                </Text>

                {/* ✅ ENHANCED: Show actual plan steps in PlanChat (detailed view) */}
                {planApprovalRequest.steps && planApprovalRequest.steps.length > 0 && !planApproved && (
                  <div style={{ marginTop: '24px', marginBottom: '24px' }}>
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      marginBottom: '16px',
                      gap: '12px' 
                    }}>
                      <Text size={300} weight="semibold">
                        Plan Overview ({planApprovalRequest.steps.length} steps):
                      </Text>
                      <Text size={200} style={{ 
                        color: 'var(--colorNeutralForeground3)',
                        fontStyle: 'italic'
                      }}>
                        Also available in the right panel
                      </Text>
                    </div>
                    
                    {/* Show detailed plan steps */}
                    <div style={{ 
                      display: 'flex', 
                      flexDirection: 'column', 
                      gap: '12px',
                      padding: '20px',
                      backgroundColor: 'var(--colorNeutralBackground2)',
                      borderRadius: '8px',
                      border: '1px solid var(--colorNeutralStroke2)',
                      marginBottom: '16px'
                    }}>
                      {planApprovalRequest.steps.map((step, index) => (
                        <div key={step.id || index} style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '16px',
                          padding: '16px',
                          backgroundColor: 'var(--colorNeutralBackground1)',
                          borderRadius: '6px',
                          border: '1px solid var(--colorNeutralStroke2)'
                        }}>
                          <span style={{ 
                            backgroundColor: 'var(--colorBrandBackground)', 
                            color: 'var(--colorNeutralForegroundOnBrand)',
                            borderRadius: '50%',
                            width: '28px',
                            height: '28px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '12px',
                            fontWeight: 600,
                            flexShrink: 0,
                            marginTop: '2px'
                          }}>
                            {step.id}
                          </span>
                          
                          <div style={{ flex: 1 }}>
                            <Text size={300} style={{ 
                              color: 'var(--colorNeutralForeground1)',
                              lineHeight: 1.5,
                              marginBottom: step.agent ? '8px' : '0'
                            }}>
                              {step.cleanAction}
                            </Text>
                            
                            {/* Show assigned agent if available */}
                            {step.agent && (
                              <Tag
                                size="extra-small"
                                appearance="outline"
                                style={{ 
                                  fontSize: '10px',
                                  height: '20px',
                                  minHeight: '20px',
                                  marginTop: '4px'
                                }}
                              >
                                {getAgentDisplayName(step.agent)}
                              </Tag>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginBottom: '24px', fontStyle: 'italic', color: 'var(--colorNeutralForeground2)' }}>
                  {planApproved ? 'Plan approved and execution started. Monitor progress above.' : 'If the plan looks good, we can move forward with execution.'}
                </div>
              </div>

              {/* Human clarification input */}
              {showClarificationInput && !planApproved && (
                <div style={{ 
                  marginTop: '24px',
                  marginBottom: '24px',
                  padding: '20px',
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
                    Any additional feedback or modifications? (optional)
                  </h4>
                  <p style={{ 
                    margin: '0 0 16px 0', 
                    fontSize: '12px', 
                    color: 'var(--colorNeutralForeground2)',
                    lineHeight: 1.4
                  }}>
                    Add any additional context or clarifications for the agents executing this plan.
                  </p>
                  <Textarea
                    value={userFeedback}
                    onChange={(_, data) => setUserFeedback(data.value)}
                    placeholder="Any additional context or clarifications for the agents..."
                    rows={3}
                    style={{ width: '100%', marginBottom: '16px' }}
                  />
                  <div style={{ 
                    display: 'flex', 
                    gap: '12px', 
                    alignItems: 'center',
                    justifyContent: 'flex-start'
                  }}>
                    <Button
                      appearance="primary"
                      size="medium"
                      onClick={handleSendFinalPlan}
                      disabled={processingApproval}
                      icon={processingApproval ? <Spinner size="tiny" /> : <CheckmarkCircleRegular />}
                      style={{ minWidth: '140px' }}
                    >
                      {processingApproval ? 'Starting Plan...' : 'Start Plan'}
                    </Button>
                    <Button
                      appearance="subtle"
                      size="medium"
                      onClick={() => {
                        setShowClarificationInput(false);
                        setUserFeedback('');
                      }}
                      disabled={processingApproval}
                      style={{ minWidth: '80px' }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {/* ✅ ENHANCED: Buttons properly aligned with better spacing */}
              {!showClarificationInput && !planApproved && (
                <div className="assistant-footer" style={{ marginTop: '32px' }}>
                  <div style={{ 
                    display: 'flex', 
                    gap: '16px', 
                    alignItems: 'center',
                    justifyContent: 'flex-start',
                    flexWrap: 'wrap',
                    padding: '20px 0 0 0',
                    borderTop: '1px solid var(--colorNeutralStroke2)'
                  }}>
                    <Button
                      appearance="primary"
                      size="medium"
                      onClick={handleApproveTaskPlan}
                      disabled={processingApproval}
                      icon={<CheckmarkCircleRegular />}
                      style={{ minWidth: '160px', height: '36px' }}
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
                        height: '36px',
                        borderColor: 'var(--colorPaletteRedBorder1)',
                        color: 'var(--colorPaletteRedForeground1)'
                      }}
                    >
                      Reject Plan
                    </Button>
                  </div>
                </div>
              )}

              {/* Show grayed out buttons after selection with better spacing */}
              {planApproved && (
                <div className="assistant-footer" style={{ marginTop: '32px' }}>
                  <div style={{ 
                    display: 'flex', 
                    gap: '16px', 
                    alignItems: 'center',
                    justifyContent: 'flex-start',
                    flexWrap: 'wrap',
                    padding: '20px 0 0 0',
                    borderTop: '1px solid var(--colorNeutralStroke2)',
                    opacity: 0.6
                  }}>
                    <Button
                      appearance="primary"
                      size="medium"
                      disabled={true}
                      icon={<CheckmarkCircleRegular />}
                      style={{ minWidth: '160px', height: '36px' }}
                    >
                      ✓ Plan Approved
                    </Button>
                    <Button
                      appearance="outline"
                      size="medium"
                      disabled={true}
                      style={{ 
                        minWidth: '120px',
                        height: '36px',
                        opacity: 0.5
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

  // ✅ Render final results summary
  const renderFinalResults = () => {
    if (finalResults.length === 0) return null;

    return (
      <div key="final-results" className="message assistant final-results" style={{ marginBottom: '24px' }}>
        <div className="plan-chat-header" style={{ marginBottom: '12px' }}>
          <div className="plan-chat-speaker" style={{ gap: '8px', alignItems: 'center' }}>
            <Body1 className="speaker-name">BOT</Body1>
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
          <div className="plan-chat-message-content" style={{ padding: '20px 24px' }}>
            <div style={{ marginBottom: '20px' }}>
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
                  {TaskService.cleanHRAgent(result.content || '')}
                </ReactMarkdown>
              </div>
            ))}

            <div className="assistant-footer" style={{ marginTop: '24px' }}>
              <div className="assistant-actions" style={{ 
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '12px'
              }}>
                <div>
                  <Button
                    onClick={() => {
                      const allContent = finalResults.map(r => r.content).join('\n\n');
                      navigator.clipboard.writeText(allContent);
                    }}
                    title="Copy Final Results"
                    appearance="subtle"
                    style={{ height: 32, width: 32 }}
                    icon={<Copy />}
                  />
                </div>
                <Tag
                  icon={<DiamondRegular />}
                  appearance="filled"
                  size="extra-small"
                  color="success"
                >
                  Final execution summary
                </Tag>
              </div>
            </div>
          </div>
        </Body1>
      </div>
    );
  };

  // ✅ ENHANCED: Group streaming messages with better orchestration handling
  const groupStreamingMessages = useCallback((messages: StreamingPlanUpdate[]): GroupedMessage[] => {
    const groups: { [key: string]: GroupedMessage } = {};

    messages.forEach((msg) => {
        const robustMsg = msg as RobustStreamingMessage;
        
        // Create a unique key for grouping (agent + step + message type)
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
    }, []);

    // Update grouped messages in real-time
    useEffect(() => {
      if (streamingMessages.length > 0) {
        const grouped = groupStreamingMessages(streamingMessages);
        setGroupedStreamingMessages(grouped);
        setTimeout(() => scrollToBottom(), 50);
      } else {
        setGroupedStreamingMessages([]);
      }
    }, [streamingMessages, groupStreamingMessages]);

    // Auto-scroll behavior
    useEffect(() => {
      scrollToBottom();
    }, [messages, groupedStreamingMessages, planApprovalRequest, showLoadingSpinner, finalResults]);

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

    // ✅ Enhanced message type text for tags
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

    if (!planData && !loading) {
      return (
        <ContentNotFound subtitle="The requested page could not be found." />
      );
    }

  // ✅ ENHANCED: Render a grouped streaming message with orchestration awareness
  const renderGroupedStreamingMessage = (group: GroupedMessage) => {
    const latestMessage = group.messages[group.messages.length - 1] as RobustStreamingMessage;
    const hasMultipleMessages = group.messages.length > 1;
    const displayName = getAgentDisplayName(group.agent_name);
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
            <Body1 className="speaker-name">
              {displayName}
            </Body1>
            <Tag
              size="extra-small"
              shape="rounded"
              appearance={isFinalResult ? "filled" : "brand"}
              className="agent-tag"
              color={isFinalResult ? "success" : undefined}
            >
              {displayName.toUpperCase()}
            </Tag>
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
          <div className="plan-chat-message-content" style={{ padding: '16px 20px' }}>
            {hasMultipleMessages ? (
              group.messages.map((msg, msgIndex) => (
                <div key={`${group.id}-msg-${msgIndex}`} style={{ 
                  marginBottom: msgIndex < group.messages.length - 1 ? '12px' : '0',
                  lineHeight: 1.6
                }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {TaskService.cleanHRAgent(msg.content || '')}
                  </ReactMarkdown>
                </div>
              ))
            ) : (
              <div style={{ lineHeight: 1.6 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {TaskService.cleanHRAgent(latestMessage.content || '')}
                </ReactMarkdown>
              </div>
            )}

            <div className="assistant-footer" style={{ marginTop: '16px' }}>
              <div className="assistant-actions" style={{ 
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '12px'
              }}>
                <div>
                  <Button
                    onClick={() =>
                      latestMessage.content &&
                      navigator.clipboard.writeText(latestMessage.content)
                    }
                    title="Copy Response"
                    appearance="subtle"
                    style={{ height: 32, width: 32 }}
                    icon={<Copy />}
                  />
                </div>

                <Tag
                  icon={<DiamondRegular />}
                  appearance="filled"
                  size="extra-small"
                  color={isFinalResult ? "success" : undefined}
                >
                  {isFinalResult ? `Final result from ${displayName.toLowerCase()}` : `Live updates from ${displayName.toLowerCase()}`}
                </Tag>
              </div>
            </div>
          </div>
        </Body1>
      </div>
    );
  };

// ✅ Enhanced agent working detection
const agentsWorking = streamingMessages.length > 0 && !planCompleted;

const getWorkingAgentName = (): string | null => {
  if (!agentsWorking || orchestrationStatus.active_agents.length === 0) return null;
  return getAgentDisplayName(orchestrationStatus.active_agents[0]);
};

const workingAgentName = getWorkingAgentName();

// Check if we need clarification
const needsClarification = groupedStreamingMessages.some(group => 
  group.messages.some(msg => (msg as RobustStreamingMessage).message_type === 'clarification_needed')
);

// ✅ Enhanced input control
const shouldDisableInput = !planData?.enableChat || 
  submittingChatDisableInput || 
  (agentsWorking && !needsClarification) || 
  (!!planApprovalRequest && !planApproved) ||
  planCompleted ||
  isInitialLoading;

// ✅ Enhanced placeholder text
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

  console.log('🎯 PlanChat State:', {
    isInitialLoading,
    streamingMessages: streamingMessages.length,
    orchestrationStatus: orchestrationStatus.status,
    activeAgents: orchestrationStatus.active_agents.length,
    planCompleted,
    finalResults: finalResults.length
  });

  // Render full-screen loading first
  if (isInitialLoading) {
    return renderFullScreenLoading();
  }

  return (
    <div className="chat-container">
      <div className="messages" 
           ref={messagesContainerRef}
           style={{ paddingBottom: `${inputHeight + 32}px`, padding: '16px' }}>
        {/* WebSocket Connection Status */}
        {wsConnected && (
          <div className="connection-status" style={{ marginBottom: '16px', textAlign: 'center' }}>
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

        <div className="message-wrapper" style={{ maxWidth: '100%' }}>
          {/* Always show user's original task first as dialogue */}
          {renderUserTaskDialogue()}

          {/* ✅ Always render regular messages (chat history) - User's original task */}
          {messages.map((msg, index) => {
            const isHuman = msg.source === AgentType.HUMAN;
            const displayName = isHuman ? 'You' : getAgentDisplayName(msg.source);

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
                  <div className="plan-chat-message-content" style={{ 
                    padding: '16px 20px',
                    lineHeight: 1.6
                  }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {TaskService.cleanHRAgent(msg.content || '')}
                    </ReactMarkdown>

                    {!isHuman && (
                      <div className="assistant-footer" style={{ marginTop: '16px' }}>
                        <div className="assistant-actions" style={{ 
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: '12px'
                        }}>
                          <div>
                            <Button
                              onClick={() => navigator.clipboard.writeText(msg.content)}
                              title="Copy Response"
                              appearance="subtle"
                              style={{ height: 32, width: 32 }}
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

          {/* ✅ Show plan approval request (detailed view stays in PlanChat) */}
          {renderPlanApprovalRequest()}

          {/* ✅ Show inline loading spinner */}
          {renderLoadingSpinner()}

          {/* Show ChatGPT-style "Agent is working..." message */}
          {renderAgentWorkingMessage()}

          {/* ✅ Show streaming messages from agents */}
          {groupedStreamingMessages.map(group => renderGroupedStreamingMessage(group))}

          {/* ✅ Show final results */}
          {renderFinalResults()}
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
              style={{ height: '36px', width: '36px' }}
            />
          </ChatInput>
        </div>
      </div>
    </div>
  );
};

export default PlanChat;