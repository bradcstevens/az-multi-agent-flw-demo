import React from "react";
import {
  Body1,
} from "@fluentui/react-components";
import {
  PersonRegular,
  ArrowTurnDownRightRegular,
} from "@fluentui/react-icons";
import { MPlanData, PlanDetailsProps } from "../../models";
import { TaskService } from "../../services/TaskService";
import { AgentTypeUtils, AgentType } from "../../models/enums";
import ContentNotFound from "../NotFound/ContentNotFound";


const PlanPanelRight: React.FC<PlanDetailsProps> = ({
  planData,
  loading,
  planApprovalRequest
}) => {

  // Helper function to get clean agent display name
  const getAgentDisplayName = (agentName: string): string => {
    if (!agentName) return 'Assistant';

    let cleanName = TaskService.cleanTextToSpaces(agentName);
    if (cleanName.toLowerCase().includes('agent')) {
      cleanName = cleanName.replace(/agent/gi, '').trim();
    }
    return cleanName.replace(/\b\w/g, l => l.toUpperCase()) || 'Assistant';
  };

  // Helper function to get agent icon based on name and type
  const getAgentIcon = (agentName: string) => {
    // Try to determine agent type from name
    const cleanName = agentName.toLowerCase();
    let agentType: AgentType;

    if (cleanName.includes('coder')) {
      agentType = AgentType.CODER;
    } else if (cleanName.includes('executor')) {
      agentType = AgentType.EXECUTOR;
    } else if (cleanName.includes('filesurfer')) {
      agentType = AgentType.FILE_SURFER;
    } else if (cleanName.includes('websurfer')) {
      agentType = AgentType.WEB_SURFER;
    } else if (cleanName.includes('hr')) {
      agentType = AgentType.HR;
    } else if (cleanName.includes('marketing')) {
      agentType = AgentType.MARKETING;
    } else if (cleanName.includes('procurement')) {
      agentType = AgentType.PROCUREMENT;
    } else if (cleanName.includes('proxy')) {
      agentType = AgentType.GENERIC;
    } else {
      agentType = AgentType.GENERIC;
    }

    // Get the icon name from the utility
    const iconName = AgentTypeUtils.getAgentIcon(agentType);

    // Return the appropriate icon component or fallback to PersonRegular
    return <PersonRegular style={{
      color: 'var(--colorPaletteBlueForeground2)',
      fontSize: '16px'
    }} />;
  };

  if (!planData && !loading) {
    return <ContentNotFound subtitle="The requested page could not be found." />;
  }

  if (!planApprovalRequest) {
    return null;
  }

  // Parse plan steps - items ending with colons are headings, others are substeps
  const parsePlanSteps = () => {
    if (!planApprovalRequest.steps || planApprovalRequest.steps.length === 0) return [];

    const result: Array<{ type: 'heading' | 'substep'; text: string }> = [];

    planApprovalRequest.steps.forEach(step => {
      const action = step.cleanAction || step.action || '';
      const trimmedAction = action.trim();

      if (trimmedAction) {
        // Check if the step ends with a colon
        if (trimmedAction.endsWith(':')) {
          // This is a heading
          result.push({ type: 'heading', text: trimmedAction });
        } else {
          // This is a substep
          result.push({ type: 'substep', text: trimmedAction });
        }
      }
    });

    return result;
  };

  // Render Plan Section with scrolling
  const renderPlanSection = () => {
    const parsedSteps = parsePlanSteps();

    return (
      <div style={{
        paddingBottom: '20px',
        marginBottom: '20px',
        borderBottom: '1px solid var(--colorNeutralStroke2)',
        maxHeight: '50vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <Body1 style={{
          marginBottom: '16px',
          flexShrink: 0,
          fontSize: '14px',
          fontWeight: 600,
          color: 'var(--colorNeutralForeground1)'
        }}>
          Plan
        </Body1>

        {/* Scrollable Plan Steps */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          paddingRight: '8px'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {parsedSteps.map((step, index) => (
              <div key={index}>
                {step.type === 'heading' ? (
                  // Heading - no arrow, just the text
                  <Body1 style={{
                    fontSize: '14px',
                    fontWeight: 600,
                    color: 'var(--colorNeutralForeground1)',
                    marginBottom: '4px'
                  }}>
                    {step.text}
                  </Body1>
                ) : (
                  // Sub-step - with arrow
                  <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '8px',
                    marginBottom: '4px'
                  }}>
                    <ArrowTurnDownRightRegular style={{
                      fontSize: '16px',
                      color: 'var(--colorNeutralForeground2)',
                      marginTop: '2px',
                      flexShrink: 0
                    }} />
                    <Body1 style={{
                      fontSize: '14px',
                      color: 'var(--colorNeutralForeground1)',
                      lineHeight: 1.4
                    }}>
                      {step.text}
                    </Body1>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // Render Agents Section
  const renderAgentsSection = () => {
    const agents = planApprovalRequest?.team || [];

    return (
      <div style={{
        flex: 1,
        overflow: 'auto'
      }}>
        <Body1 style={{
          marginBottom: '16px',
          fontSize: '14px',
          fontWeight: 600,
          color: 'var(--colorNeutralForeground1)'
        }}>
          Agent Team
        </Body1>

        {agents.length === 0 ? (
          <div style={{
            textAlign: 'center',
            color: 'var(--colorNeutralForeground3)',
            fontSize: '14px',
            fontStyle: 'italic',
            padding: '20px'
          }}>
            No agents assigned yet...
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {agents.map((agentName, index) => (
              <div key={`${agentName}-${index}`} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '8px 0'
              }}>
                {/* Agent Icon */}
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
                  {getAgentIcon(agentName)}
                </div>

                {/* Agent Info - just name */}
                <div style={{ flex: 1 }}>
                  <Body1 style={{
                    fontWeight: 600,
                    fontSize: '14px',
                    color: 'var(--colorNeutralForeground1)'
                  }}>
                    {getAgentDisplayName(agentName)} Agent
                  </Body1>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Main render
  return (
    <div style={{
      width: '280px',
      height: '100vh',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      borderLeft: '1px solid var(--colorNeutralStroke1)',
      // backgroundColor: 'var(--colorNeutralBackground1)'
    }}>
      {/* Plan section on top */}
      {renderPlanSection()}

      {/* Agents section below with line demarcation */}
      {renderAgentsSection()}
    </div>
  );
};

export default PlanPanelRight;