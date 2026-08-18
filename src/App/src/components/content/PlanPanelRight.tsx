import React from "react";
import { PlanDetailsProps } from "../../models";
import ContentNotFound from "../NotFound/ContentNotFound";
import AgentTeamPanel from "../transparency/AgentTeamPanel";
import TransparencyRail from "../transparency/TransparencyRail";
import SimulatedTicketCard from "../escalation/SimulatedTicketCard";
import { useAppSelector } from "../../store/hooks";
import { selectRaisedTicket } from "../../store/slices/ticketSlice";
import { selectSelectedTeam, selectTeamAgentCount } from "../../store/slices/teamSlice";
import { selectParticipatingExecutors } from "../../store/slices/progressSlice";
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
  const participatingExecutors = useAppSelector(selectParticipatingExecutors);

  if (!planData && !loading) {
    return <ContentNotFound subtitle="The requested page could not be found." />;
  }

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
      participatingExecutors={participatingExecutors}
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
        the breakpoint would be inert for the whole chat surface.
      */}
      {raisedTicket && <SimulatedTicketCard ticket={raisedTicket} />}

      {/* The rail is evidence only; the reviewable plan lives in the conversation. */}
      <TransparencyRail team={planData?.team ?? null}>
        {renderAgentsSection()}
      </TransparencyRail>
    </div>
  );
};

const MemoizedPlanPanelRight = React.memo(PlanPanelRight);
MemoizedPlanPanelRight.displayName = 'PlanPanelRight';
export default MemoizedPlanPanelRight;