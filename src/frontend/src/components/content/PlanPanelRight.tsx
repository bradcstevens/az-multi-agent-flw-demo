import React, { useEffect, useState } from "react";
import PanelRight from "@/coral/components/Panels/PanelRight";
import { TaskDetailsProps } from "@/models";
import { 
    Accordion,
    AccordionHeader,
    AccordionItem,
    AccordionPanel,
    Body1Strong,
    Avatar,
    Text,
    Spinner
} from "@fluentui/react-components";
import { 
    PersonRegular,
    CheckmarkCircleRegular,
    ClockRegular,
    ErrorCircleRegular
} from "@fluentui/react-icons";
import { TaskService } from "../../services/TaskService";
import { StreamingPlanUpdate } from "../../services/WebSocketService";

interface AgentStatus {
    name: string;
    status: 'active' | 'idle' | 'completed' | 'error';
    lastActivity: string;
    currentTask?: string;
}

const PlanPanelRight: React.FC<TaskDetailsProps & { streamingMessages?: StreamingPlanUpdate[], planApproved?: boolean }> = ({
    planData,
    loading,
    streamingMessages = [],
    planApproved = false
}) => {
    const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);

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

    // Get status icon based on agent status
    const getStatusIcon = (status: 'active' | 'idle' | 'completed' | 'error') => {
        switch (status) {
            case 'active':
                return <Spinner size="extra-tiny" />;
            case 'completed':
                return <CheckmarkCircleRegular style={{ color: 'var(--colorPaletteGreenForeground1)' }} />;
            case 'error':
                return <ErrorCircleRegular style={{ color: 'var(--colorPaletteRedForeground1)' }} />;
            case 'idle':
            default:
                return <ClockRegular style={{ color: 'var(--colorNeutralForeground3)' }} />;
        }
    };

    // Get agent status from streaming messages
    const getAgentStatuses = (): AgentStatus[] => {
        const statusMap = new Map<string, AgentStatus>();

        // Initialize with plan agents
        if (planData?.agents) {
            planData.agents.forEach(agent => {
                const cleanName = getAgentDisplayName(agent);
                statusMap.set(agent, {
                    name: cleanName,
                    status: 'idle',
                    lastActivity: 'No recent activity'
                });
            });
        }

        // Update with streaming message data
        streamingMessages.forEach(msg => {
            if (msg.agent_name) {
                const cleanName = getAgentDisplayName(msg.agent_name);
                
                let status: 'active' | 'idle' | 'completed' | 'error' = 'idle';
                
                if (msg.status === 'in_progress') {
                    status = 'active';
                } else if (msg.status === 'completed') {
                    status = 'completed';
                } else if (msg.status === 'error') {
                    status = 'error';
                } else if (msg.status === 'creating_plan') {
                    status = 'active';
                } else if (msg.status === 'pending_approval') {
                    status = 'idle';
                }

                statusMap.set(msg.agent_name, {
                    name: cleanName,
                    status,
                    lastActivity: new Date(msg.timestamp ? (typeof msg.timestamp === 'number' ? msg.timestamp * 1000 : msg.timestamp) : Date.now()).toLocaleTimeString(),
                    currentTask: msg.content?.substring(0, 50) + (msg.content && msg.content.length > 50 ? '...' : '') || undefined
                });
            }
        });

        return Array.from(statusMap.values());
    };

    // Update agent statuses when streaming messages change
    useEffect(() => {
        const statuses = getAgentStatuses();
        setAgentStatuses(statuses);
    }, [streamingMessages, planData?.agents]);

    if (!planData || !planApproved) {
        return (
            <PanelRight
                panelWidth={350}
                defaultClosed={false}
                panelResize={true}
                panelType="first"
            >
                <div style={{ 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    padding: '20px',
                    textAlign: 'center',
                    color: 'var(--colorNeutralForeground3)'
                }}>
                    <ClockRegular style={{ fontSize: '48px', marginBottom: '16px' }} />
                    <Text size={400}>Waiting for plan approval</Text>
                    <Text size={300} style={{ marginTop: '8px' }}>
                        Plans and agents will appear here once approved
                    </Text>
                </div>
            </PanelRight>
        );
    }

    return (
        <PanelRight
            panelWidth={350}
            defaultClosed={false}
            panelResize={true}
            panelType="first"
        >
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <Accordion
                    defaultOpenItems={["plans", "agents"]}
                    multiple
                    collapsible
                    style={{ flex: 1, overflow: 'hidden' }}
                >
                    <AccordionItem value="plans">
                        <AccordionHeader expandIconPosition="end">
                            <Body1Strong>Plans</Body1Strong>
                        </AccordionHeader>
                        <AccordionPanel style={{ maxHeight: '400px', overflowY: 'auto' }}>
                            <div style={{ padding: '8px 0' }}>
                                {planData.steps && planData.steps.length > 0 ? (
                                    planData.steps.map((step, index) => (
                                        <div
                                            key={step.id || index}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'flex-start',
                                                gap: '12px',
                                                padding: '12px 8px',
                                                borderRadius: '8px',
                                                marginBottom: '8px',
                                                backgroundColor: 'var(--colorNeutralBackground1)',
                                                border: '1px solid var(--colorNeutralStroke2)'
                                            }}
                                        >
                                            <div style={{
                                                minWidth: '24px',
                                                height: '24px',
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
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                <Text size={300} weight="semibold" style={{ display: 'block', marginBottom: '4px' }}>
                                                    Step {index + 1}
                                                </Text>
                                                <Text size={200} style={{ 
                                                    color: 'var(--colorNeutralForeground2)',
                                                    lineHeight: '1.4'
                                                }}>
                                                    {step.description || 'Step description'}
                                                </Text>
                                                {step.agent && (
                                                    <Text size={200} style={{ 
                                                        color: 'var(--colorBrandForeground1)',
                                                        marginTop: '4px',
                                                        display: 'block'
                                                    }}>
                                                        Assigned to: {getAgentDisplayName(step.agent)}
                                                    </Text>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div style={{ 
                                        textAlign: 'center', 
                                        padding: '20px',
                                        color: 'var(--colorNeutralForeground3)'
                                    }}>
                                        <Text size={300}>No plan steps available</Text>
                                    </div>
                                )}
                            </div>
                        </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem value="agents">
                        <AccordionHeader expandIconPosition="end">
                            <Body1Strong>Agents</Body1Strong>
                        </AccordionHeader>
                        <AccordionPanel style={{ flex: 1, overflow: 'auto' }}>
                            <div style={{ padding: '8px 0' }}>
                                {agentStatuses.length > 0 ? (
                                    agentStatuses.map((agent, index) => (
                                        <div
                                            key={index}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '12px',
                                                padding: '12px 8px',
                                                borderRadius: '8px',
                                                marginBottom: '8px',
                                                backgroundColor: agent.status === 'active' 
                                                    ? 'var(--colorNeutralBackground2)' 
                                                    : 'transparent',
                                                border: agent.status === 'active' 
                                                    ? '1px solid var(--colorBrandStroke1)' 
                                                    : '1px solid transparent',
                                                transition: 'all 0.2s ease'
                                            }}
                                        >
                                            <Avatar
                                                name={agent.name}
                                                size={32}
                                                icon={<PersonRegular />}
                                            />
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                <div style={{ 
                                                    display: 'flex', 
                                                    alignItems: 'center', 
                                                    gap: '8px',
                                                    marginBottom: '4px'
                                                }}>
                                                    <Text weight="semibold" size={300}>
                                                        {agent.name}
                                                    </Text>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                        {getStatusIcon(agent.status)}
                                                        <Text size={200} style={{ 
                                                            color: agent.status === 'active' 
                                                                ? 'var(--colorBrandForeground1)' 
                                                                : 'var(--colorNeutralForeground3)',
                                                            textTransform: 'capitalize'
                                                        }}>
                                                            {agent.status}
                                                        </Text>
                                                    </div>
                                                </div>
                                                <Text size={200} style={{ 
                                                    color: 'var(--colorNeutralForeground3)',
                                                    display: 'block'
                                                }}>
                                                    {agent.lastActivity}
                                                </Text>
                                                {agent.currentTask && (
                                                    <Text size={200} style={{ 
                                                        color: 'var(--colorNeutralForeground2)',
                                                        fontStyle: 'italic',
                                                        display: 'block',
                                                        marginTop: '2px'
                                                    }}>
                                                        {agent.currentTask}
                                                    </Text>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div style={{ 
                                        textAlign: 'center', 
                                        padding: '20px',
                                        color: 'var(--colorNeutralForeground3)'
                                    }}>
                                        <Text size={300}>No active agents</Text>
                                    </div>
                                )}
                            </div>
                        </AccordionPanel>
                    </AccordionItem>
                </Accordion>
            </div>
        </PanelRight>
    );
};

export default PlanPanelRight;