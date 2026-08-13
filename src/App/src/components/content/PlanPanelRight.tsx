import React from "react";
import {
  Body1,
} from "@fluentui/react-components";
import {
  ArrowTurnDownRightRegular,
} from "@fluentui/react-icons";
import { PlanDetailsProps } from "../../models";
import { getAgentDisplayNameWithSuffix } from '../../utils/agentIconUtils';
import ContentNotFound from "../NotFound/ContentNotFound";
import AgentTeamPanel from "../transparency/AgentTeamPanel";
import TransparencyRail from "../transparency/TransparencyRail";
import "../../styles/planpanelright.css";


const PlanPanelRight: React.FC<PlanDetailsProps> = ({
  planData,
  loading,
  planApprovalRequest
}) => {

  if (!planData && !loading) {
    return <ContentNotFound subtitle="The requested page could not be found." />;
  }

  // Extract plan steps from the planApprovalRequest
  const extractPlanSteps = () => {
    if (!planApprovalRequest?.steps || planApprovalRequest.steps.length === 0) {
      return [];
    }

    return planApprovalRequest.steps.map((step, index) => {
      const action = step.action || step.cleanAction || '';
      const isHeading = action.trim().endsWith(':');
      const rawAgent = step.agent || '';
      const isFallback = !rawAgent || rawAgent.toLowerCase() === 'magenticagent';
      const agentName = isFallback ? '' : getAgentDisplayNameWithSuffix(rawAgent);
      const fullText = agentName ? `${agentName} ${action.trim()}` : action.trim();

      return {
        text: fullText,
        agentName,
        isHeading,
        key: `${index}-${action.substring(0, 20)}`
      };
    }).filter(step => step.text.length > 0);
  };

  // Render Plan Section
  const renderPlanSection = () => {
    const planSteps = extractPlanSteps();

    return (
      <div className="plan-section">
        <Body1 className="plan-section__title">
          Plan Overview
        </Body1>

        {planSteps.length === 0 ? (
          <div className="plan-section__empty">
            {/*
              Two different silences, and they must not read alike: a plan on
              its way, and a request that will never have one because it took
              the Fast lane. "Plan is being generated…" for the second is a
              spinner that never resolves.
            */}
            {planApprovalRequest
              ? 'Plan is being generated...'
              : 'No plan to review on this request.'}
          </div>
        ) : (
          <div className="plan-steps">
            {planSteps.map((step) => (
              <div key={step.key} className={`plan-step ${step.isHeading ? 'plan-step--heading' : 'plan-step--substep'}`}>
                {step.isHeading ? (
                  // Heading - larger text, bold
                  <Body1 className="plan-step__heading">
                    {step.agentName ? (
                      <><strong>{step.agentName}</strong> {step.text.slice(step.agentName.length + 1)}</>
                    ) : (
                      step.text
                    )}
                  </Body1>
                ) : (
                  // Sub-step - with arrow
                  <div className="plan-step__content">
                    <ArrowTurnDownRightRegular className="plan-step__arrow" />
                    <Body1 className="plan-step__text">
                      {step.agentName ? (
                        <><strong>{step.agentName}</strong> {step.text.slice(step.agentName.length + 1)}</>
                      ) : (
                        step.text
                      )}
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
  //
  // From the **workflow roster** (issue #24), not from the plan. With Plan
  // review off there is no plan object to read agent names out of (ADR-013),
  // so the previous `planApprovalRequest.team` source left this panel empty for
  // the whole of the Fast lane — which is most of the walkthrough. The roster
  // also carries the per-agent model assignment, which is the point.
  const renderAgentsSection = () => (
    <AgentTeamPanel
      team={planData?.team ?? null}
      plan={planApprovalRequest?.team ?? null}
    />
  );

  // Main render
  return (
    <div className="plan-panel-right">
      {/* Plan section on top */}
      {renderPlanSection()}

      {/* Agents section, and the transparency rail below it */}
      <TransparencyRail team={planData?.team ?? null}>
        {renderAgentsSection()}
      </TransparencyRail>
    </div>
  );
};

const MemoizedPlanPanelRight = React.memo(PlanPanelRight);
MemoizedPlanPanelRight.displayName = 'PlanPanelRight';
export default MemoizedPlanPanelRight;