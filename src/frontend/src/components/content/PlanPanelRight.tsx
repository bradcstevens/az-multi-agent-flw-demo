import React from "react";
import {
  Body1,
} from "@fluentui/react-components";
import {
  ArrowTurnDownRightRegular,
} from "@fluentui/react-icons";
import { MPlanData, PlanDetailsProps } from "../../models";
import { getAgentIcon, getAgentDisplayNameWithSuffix } from '../../utils/agentIconUtils'; 
import ContentNotFound from "../NotFound/ContentNotFound";


const PlanPanelRight: React.FC<PlanDetailsProps> = ({
  planData,
  loading,
  planApprovalRequest
}) => {

  if (!planData && !loading) {
    return <ContentNotFound subtitle="The requested page could not be found." />;
  }

  if (!planApprovalRequest) {
    return (
      <div style={{
        width: '280px',
        height: '100vh',
        padding: '20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderLeft: '1px solid var(--colorNeutralStroke1)',
        color: 'var(--colorNeutralForeground3)',
        fontSize: '14px',
        fontStyle: 'italic'
      }}>
        No plan available
      </div>
    );
  }

  // Extract plan steps from the planApprovalRequest
  const extractPlanSteps = () => {
    if (!planApprovalRequest.steps || planApprovalRequest.steps.length === 0) {
      return [];
    }

    return planApprovalRequest.steps.map((step, index) => {
      const action = step.action || step.cleanAction || '';
      const isHeading = action.trim().endsWith(':');
      
      return {
        text: action.trim(),
        isHeading,
        key: `${index}-${action.substring(0, 20)}`
      };
    }).filter(step => step.text.length > 0);
  };

  // Render Plan Section
  const renderPlanSection = () => {
    const planSteps = extractPlanSteps();

    return (
      <div style={{
        marginBottom: '24px',
        paddingBottom: '20px',
        borderBottom: '1px solid var(--colorNeutralStroke1)'
      }}>
        <Body1 style={{
          marginBottom: '16px',
          fontSize: '14px',
          fontWeight: 600,
          color: 'var(--colorNeutralForeground1)'
        }}>
          Plan Overview
        </Body1>

        {planSteps.length === 0 ? (
          <div style={{
            textAlign: 'center',
            color: 'var(--colorNeutralForeground3)',
            fontSize: '14px',
            fontStyle: 'italic',
            padding: '20px'
          }}>
            Plan is being generated...
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {planSteps.map((step, index) => (
              <div key={step.key} style={{ display: 'flex', flexDirection: 'column' }}>
                {step.isHeading ? (
                  // Heading - larger text, bold
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
        )}
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
                  {getAgentIcon(agentName, planData, planApprovalRequest)}
                </div>

                {/* Agent Info - just name */}
                <div style={{ flex: 1 }}>
                  <Body1 style={{
                    fontWeight: 600,
                    fontSize: '14px',
                    color: 'var(--colorNeutralForeground1)'
                  }}>
                    {getAgentDisplayNameWithSuffix(agentName)}
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