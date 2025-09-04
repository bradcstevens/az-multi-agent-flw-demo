import React, { useCallback, useEffect, useState } from "react";
import {
  Body1,
  Tag,
  Spinner,
  Title3,
} from "@fluentui/react-components";
import {
  CheckmarkCircleRegular,
  ErrorCircleRegular,
  DiamondRegular,
  ClockRegular,
  PersonRegular,
} from "@fluentui/react-icons";
import { ParsedPlanData } from "../../models";
import { TaskService } from "../../services/TaskService";
import { Step } from "../../models/plan";
import { PlanDataService } from "../../services/PlanDataService";
import webSocketService, { StreamingPlanUpdate } from "../../services/WebSocketService";
import ContentNotFound from "../NotFound/ContentNotFound";

// Clean interface - only display-related props
interface PlanPanelRightProps {
  planData: any;
  OnApproveStep: (step: Step, total: number, completed: number, approve: boolean) => Promise<void>;
  submittingChatDisableInput: boolean;
  processingSubtaskId: string | null;
  loading: boolean;
  streamingMessages?: StreamingPlanUpdate[];
  planApproved: boolean;
  onPlanApproval?: (approved: boolean) => void;
  wsConnected?: boolean;
}

interface GroupedMessage {
  id: string;
  agent_name: string;
  messages: StreamingPlanUpdate[];
  status: string;
  latest_timestamp: string;
  step_id?: string;
}

// ✅ NEW: Interface for agent status tracking
interface AgentStatus {
  name: string;
  displayName: string;
  status: 'planned' | 'active' | 'completed' | 'error';
  role: string;
  latest_message?: string;
  step_count?: number;
  messages_count?: number;
}

const PlanPanelRight: React.FC<PlanPanelRightProps> = ({
  planData,
  loading,
  streamingMessages = [],
  planApproved,
  wsConnected = false,
}) => {
  const [groupedStreamingMessages, setGroupedStreamingMessages] = useState<GroupedMessage[]>([]);
  const [planApprovalRequest, setPlanApprovalRequest] = useState<ParsedPlanData | null>(null);
  const [hasStreamingStarted, setHasStreamingStarted] = useState(false);

  // Helper function to get clean agent display name
  const getAgentDisplayName = (agentName: string): string => {
    if (!agentName) return 'Assistant';
    
    // Special handling for orchestrator/system agents
    if (agentName.toLowerCase().includes('orchestrator') || 
        agentName.toLowerCase() === 'system' ||
        agentName.toLowerCase().includes('planner')) {
      return 'BOT';
    }
    
    let cleanName = TaskService.cleanTextToSpaces(agentName);
    if (cleanName.toLowerCase().includes('agent')) {
      cleanName = cleanName.replace(/agent/gi, '').trim();
    }
    return cleanName.replace(/\b\w/g, l => l.toUpperCase()) || 'Assistant';
  };

  // Helper function to normalize timestamp
  const normalizeTimestamp = (timestamp?: string | number): string => {
    if (!timestamp) return new Date().toISOString();
    if (typeof timestamp === 'number') {
      return new Date(timestamp * 1000).toISOString();
    }
    return timestamp;
  };

  // Track when streaming starts
  useEffect(() => {
    console.log('🔍 Right panel - streaming messages changed:', streamingMessages.length, 'hasStreamingStarted:', hasStreamingStarted);
    
    if (streamingMessages.length > 0 && !hasStreamingStarted) {
      const hasRealAgentContent = streamingMessages.some(msg => 
        msg.agent_name && 
        msg.content && 
        msg.content.trim().length > 0 &&
        msg.agent_name !== 'system'
      );
      
      if (hasRealAgentContent) {
        console.log('🚀 Real streaming content started in right panel');
        setHasStreamingStarted(true);
      }
    }
  }, [streamingMessages, hasStreamingStarted]);

  // Add WebSocket listener for plan approval requests - but only store, don't display until streaming starts
  useEffect(() => {
    const unsubscribePlanApproval = webSocketService.onPlanApprovalRequest((approvalRequest) => {
      if (approvalRequest.parsedData) {
        const parsedData = PlanDataService.parsePlanApprovalRequest(approvalRequest);
        if (parsedData) {
          console.log('📥 Right panel received plan approval request:', parsedData);
          setPlanApprovalRequest(parsedData);
          // Reset states when new plan comes in
          setHasStreamingStarted(false);
        }
      }
    });

    return () => {
      unsubscribePlanApproval();
    };
  }, []);

  // Group streaming messages by agent 
  const groupStreamingMessages = useCallback((messages: StreamingPlanUpdate[]): GroupedMessage[] => {
    const groups: { [key: string]: GroupedMessage } = {};

    messages.forEach((msg) => {
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
      setGroupedStreamingMessages([]);
    }
  }, [streamingMessages, groupStreamingMessages]);

  // ✅ NEW: Get comprehensive agent status combining planned and streaming agents
  const getAgentStatus = useCallback((): AgentStatus[] => {
    const agentStatusMap = new Map<string, AgentStatus>();
    
    // Add planned agents from the plan approval request
    if (planApprovalRequest?.team && planApprovalRequest.team.length > 0) {
      planApprovalRequest.team.forEach(agentName => {
        const displayName = getAgentDisplayName(agentName);
        agentStatusMap.set(agentName, {
          name: agentName,
          displayName,
          status: 'planned',
          role: 'Agent',
          step_count: 0,
          messages_count: 0
        });
      });
    }

    //  Update with streaming agent data
    groupedStreamingMessages.forEach(group => {
      const agentName = group.agent_name;
      const displayName = getAgentDisplayName(agentName);
      
      const existing = agentStatusMap.get(agentName);
      const status = group.status === 'completed' ? 'completed' : 
                   group.status === 'error' ? 'error' : 'active';
      
      agentStatusMap.set(agentName, {
        name: agentName,
        displayName,
        status,
        role: 'Agent',
        latest_message: group.messages[group.messages.length - 1]?.content?.substring(0, 80) + '...',
        step_count: existing?.step_count || 0,
        messages_count: group.messages.length
      });
    });

    //  Count steps per agent from plan
    if (planApprovalRequest?.steps) {
      planApprovalRequest.steps.forEach(step => {
        if (step.agent) {
          const existing = agentStatusMap.get(step.agent);
          if (existing) {
            existing.step_count = (existing.step_count || 0) + 1;
          }
        }
      });
    }

    return Array.from(agentStatusMap.values()).sort((a, b) => {
      // Sort by status priority: active > planned > completed > error
      const statusPriority = { active: 1, planned: 2, completed: 3, error: 4 };
      return statusPriority[a.status] - statusPriority[b.status];
    });
  }, [planApprovalRequest, groupedStreamingMessages]);

  // Get status icon for agents
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckmarkCircleRegular style={{ color: 'var(--colorPaletteGreenForeground1)' }} />;
      case 'error':
        return <ErrorCircleRegular style={{ color: 'var(--colorPaletteRedForeground1)' }} />;
      case 'active':
        return <Spinner size="extra-tiny" />;
      case 'planned':
        return <PersonRegular style={{ color: 'var(--colorPaletteBlueForeground2)' }} />;
      default:
        return <ClockRegular style={{ color: 'var(--colorNeutralForeground3)' }} />;
    }
  };

  if (!planData && !loading) {
    return <ContentNotFound subtitle="The requested page could not be found." />;
  }

  // ✅ ENHANCED: Show waiting message only when we don't have plan approval request
  if (!planApprovalRequest) {
    return (
      <div style={{ 
        width: '280px',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--colorNeutralForeground3)',
        fontSize: '14px',
        padding: '20px',
        textAlign: 'center'
      }}>
        Waiting for plan creation...
      </div>
    );
  }

  // Render Plan Section - show once we have plan approval request
  const renderPlanSection = () => {
    return (
      <div style={{ 
        height: '45%',
        overflow: 'auto',
        marginBottom: '16px',
        padding: '20px',
        backgroundColor: 'var(--colorNeutralBackground2)',
        borderRadius: '8px',
        border: '1px solid var(--colorNeutralStroke2)'
      }}>
        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '20px',
          paddingBottom: '12px',
          borderBottom: '1px solid var(--colorNeutralStroke2)'
        }}>
          <Title3>Plan</Title3>
          <Tag
            size="small"
            shape="rounded"
            appearance="outline"
            icon={planApproved ? <CheckmarkCircleRegular /> : <ClockRegular />}
          >
            {planApproved ? 'Executing' : 'Awaiting Approval'}
          </Tag>
        </div>

        <div>
          <Body1 style={{ 
            marginBottom: '16px', 
            fontStyle: 'italic',
            color: 'var(--colorNeutralForeground2)'
          }}>
            {planApprovalRequest.user_request}
          </Body1>

          {/* Plan Steps */}
          {planApprovalRequest.steps && planApprovalRequest.steps.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {planApprovalRequest.steps.map((step, index) => (
                <div key={step.id || index} style={{
                  padding: '12px',
                  backgroundColor: 'var(--colorNeutralBackground1)',
                  borderRadius: '6px',
                  border: '1px solid var(--colorNeutralStroke2)'
                }}>
                  <Body1 style={{ 
                    fontSize: '12px', 
                    color: 'var(--colorNeutralForeground1)',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '8px'
                  }}>
                    <span style={{ 
                      backgroundColor: 'var(--colorBrandBackground)', 
                      color: 'var(--colorNeutralForegroundOnBrand)',
                      borderRadius: '50%',
                      width: '20px',
                      height: '20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '10px',
                      fontWeight: 600,
                      flexShrink: 0,
                      marginTop: '2px'
                    }}>
                      {step.id}
                    </span>
                    <span style={{ flex: 1, lineHeight: 1.3 }}>
                      {step.cleanAction}
                    </span>
                  </Body1>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  // ✅ ENHANCED: Render Agents Section - show planned agents immediately, update with streaming status
  const renderAgentsSection = () => {
    const agents = getAgentStatus();

    return (
      <div style={{
        height: '55%',
        overflow: 'auto'
      }}>
        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px',
          paddingBottom: '12px',
          borderBottom: '1px solid var(--colorNeutralStroke2)'
        }}>
          <Title3>Agents</Title3>
          <div style={{ display: 'flex', gap: '4px' }}>
            {wsConnected && hasStreamingStarted && (
              <Tag
                size="extra-small"
                appearance="filled"
                color="success"
                icon={<DiamondRegular />}
              >
                Live
              </Tag>
            )}
            <Tag
              size="extra-small"
              appearance="outline"
            >
              {agents.length} Assigned
            </Tag>
          </div>
        </div>

        {agents.length === 0 ? (
          <div style={{ 
            textAlign: 'center',
            color: 'var(--colorNeutralForeground3)',
            fontSize: '12px',
            fontStyle: 'italic',
            padding: '20px'
          }}>
            No agents assigned yet...
          </div>
        ) : (
          agents.map((agent, index) => (
            <div key={`${agent.name}-${index}`} style={{
              padding: '12px',
              marginBottom: '12px',
              backgroundColor: 'var(--colorNeutralBackground2)',
              borderRadius: '6px',
              border: '1px solid var(--colorNeutralStroke2)',
              position: 'relative'
            }}>
              {/* Agent Header */}
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                marginBottom: '8px'
              }}>
                <Body1 style={{ fontWeight: 600, fontSize: '14px' }}>
                  {agent.displayName}
                </Body1>
                <Tag
                  size="extra-small"
                  appearance="outline"
                  icon={getStatusIcon(agent.status)}
                  color={
                    agent.status === 'completed' ? 'success' : 
                    agent.status === 'active' ? 'brand' : 
                    agent.status === 'error' ? 'danger' :
                    'neutral'
                  }
                >
                  {agent.status === 'completed' ? 'Completed' : 
                   agent.status === 'active' ? 'Working' : 
                   agent.status === 'error' ? 'Error' : 
                   'Planned'}
                </Tag>
              </div>

              {/* Agent Role */}
              <Body1 style={{ 
                fontSize: '11px', 
                color: 'var(--colorNeutralForeground3)',
                fontStyle: 'italic',
                marginBottom: '4px'
              }}>
                {agent.role}
                {agent.step_count && agent.step_count > 0 && (
                  <span style={{ marginLeft: '8px' }}>
                    • {agent.step_count} step{agent.step_count !== 1 ? 's' : ''}
                  </span>
                )}
                {agent.messages_count && agent.messages_count > 0 && (
                  <span style={{ marginLeft: '8px' }}>
                    • {agent.messages_count} message{agent.messages_count !== 1 ? 's' : ''}
                  </span>
                )}
              </Body1>

              {/* Latest Message */}
              {agent.latest_message && (
                <Body1 style={{ 
                  fontSize: '10px', 
                  color: 'var(--colorNeutralForeground2)',
                  lineHeight: 1.3,
                  marginTop: '4px'
                }}>
                  {agent.latest_message}
                </Body1>
              )}

              {/* Active indicator for working agents */}
              {agent.status === 'active' && (
                <div style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px',
                  width: '8px',
                  height: '8px',
                  backgroundColor: 'var(--colorPaletteBlueForeground2)',
                  borderRadius: '50%',
                  animation: 'pulse 2s infinite'
                }} />
              )}
            </div>
          ))
        )}

        {/* Recent Activity - only show if we have streaming messages */}
        {groupedStreamingMessages.length > 0 && (
          <div style={{ 
            marginTop: '20px',
            paddingTop: '16px',
            borderTop: '1px solid var(--colorNeutralStroke2)'
          }}>
            <Body1 style={{ 
              fontSize: '12px',
              color: 'var(--colorNeutralForeground2)',
              marginBottom: '8px',
              fontWeight: 600
            }}>
              Recent Activity:
            </Body1>
            {groupedStreamingMessages.slice(-3).map((group, index) => (
              <div key={group.id} style={{
                fontSize: '10px',
                color: 'var(--colorNeutralForeground3)',
                marginBottom: '4px',
                padding: '4px 8px',
                backgroundColor: 'var(--colorNeutralBackground1)',
                borderRadius: '4px'
              }}>
                <strong>{getAgentDisplayName(group.agent_name)}:</strong> {group.messages[group.messages.length - 1]?.content?.substring(0, 50)}...
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Main render - show content in proportional layout (280px width to match left panel)
  return (
    <div style={{ 
      width: '280px',
      height: '100vh',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Plan section - 45% height, scrollable */}
      {renderPlanSection()}
      
      {/* Agents section - 55% height, scrollable */}
      {renderAgentsSection()}

      {/* Add CSS animation for pulse effect */}
      <style>{`
        @keyframes pulse {
          0% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
          100% {
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
};

export default PlanPanelRight;