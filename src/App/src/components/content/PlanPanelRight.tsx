import React from "react";
import {
  Body1,
} from "@fluentui/react-components";
import {
  ArrowTurnDownRightRegular,
} from "@fluentui/react-icons";
import { PlanDetailsProps } from "../../models";
import { getAgentDisplayNameWithSuffix } from '../../utils/agentIconUtils';
import { PLAN_ARRIVING } from '../../models/progressNarration';
import { SECTION_HEADING } from '../../models/headingOutline';
import ContentNotFound from "../NotFound/ContentNotFound";
import AgentTeamPanel from "../transparency/AgentTeamPanel";
import TransparencyRail from "../transparency/TransparencyRail";
import SimulatedTicketCard from "../escalation/SimulatedTicketCard";
import { useAppSelector } from "../../store/hooks";
import { selectRaisedTicket } from "../../store/slices/ticketSlice";
import { selectSelectedTeam, selectTeamAgentCount } from "../../store/slices/teamSlice";
import "../../styles/planpanelright.css";
import "../../styles/simulatedTicket.css";


const PlanPanelRight: React.FC<PlanDetailsProps> = ({
  planData,
  loading,
  planApprovalRequest
}) => {

  // The Simulated ticket this conversation raised, if it raised one (#22).
  // Read from the slice rather than taken as a prop: it arrives on the socket
  // at the moment the associate approves the plan, and threading it down from
  // the page would put a second copy of the same state one render behind.
  const raisedTicket = useAppSelector(selectRaisedTicket);

  // Who is *available*, for the loading window (#65).
  //
  // This panel renders outside `PlanPage`'s `loading || !planData` branch, so
  // it is on screen for the whole wait with `planData` still null — and it
  // read "No agent roster loaded for this conversation." beside a spinner
  // claiming the agents were being initialised. The **store assistant roster**
  // has been in Redux since `HomePage`'s mount, so the window has something
  // true to say with no dependency on the wire.
  //
  // The count is `selectTeamAgentCount`, not a `.length` beside it: the
  // selector has been exported and unused since the slice was written, and a
  // second count is a second thing to disagree with the first.
  const availableTeam = useAppSelector(selectSelectedTeam);
  const availableCount = useAppSelector(selectTeamAgentCount);

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
        <Body1 as={SECTION_HEADING} className="plan-section__title">
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
              ? PLAN_ARRIVING
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
  //
  // `available` is the same claim one step earlier (#65): the roster this tab
  // is already holding, for the window before the plan fetch returns. It is a
  // fallback and never a replacement — a historical plan opened from the task
  // list ran on its own team, and the team this tab happens to hold is not a
  // claim about it.
  const renderAgentsSection = () => (
    <AgentTeamPanel
      team={planData?.team ?? null}
      plan={planApprovalRequest?.team ?? null}
      available={availableTeam}
      availableCount={availableCount}
    />
  );

  // Main render
  return (
    <div className="plan-panel-right" data-testid="plan-panel-right">
      {/*
        The ticket the approval raised, above the plan it was raised from.
        This panel rather than the reply stream, and deliberately: it is the
        one surface that survives the stacking breakpoint (#25 drops the left
        panel and keeps the rail), and the associate's screen is a phone.

        The panel's own orientation is the shell's to decide (#58): a column
        beside the conversation above the breakpoint, a band beneath it below,
        declared in `storeSurface.css` in the one place that declares it for
        the rail this panel contains. Nothing here may pin a width, a height or
        a side border inline — an inline declaration beats a media query, and
        the breakpoint would be inert for the whole plan surface.
      */}
      {raisedTicket && <SimulatedTicketCard ticket={raisedTicket} />}

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