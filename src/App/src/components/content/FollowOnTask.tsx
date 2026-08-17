import React from 'react';
import { Button } from '@fluentui/react-components';

import { useAppSelector } from '@/store/hooks';
import { selectHasPendingClarification } from '@/store/slices/chatSlice';
import { StartingTask } from '../../models/Team';
import '../../styles/followOnTask.css';

interface FollowOnTaskProps {
  task: StartingTask;
  onSelect: (task: StartingTask) => void;
  disabled: boolean;
}

/**
 * The Follow-on task as a one-tap card (#61, ADR-024).
 *
 * **One control at a time** (#131, ADR-033). The card yields its slot while the
 * orchestration waits on a **Clarification**: the **Rehearsed reply** chips
 * take it, the tap answers, the chips go and the card returns. A tap here in
 * that moment starts a *new turn*, and `process_request` cancels whatever
 * orchestration that user already had running — so it strands the turn that
 * asked, which is the failure the chips' own gate exists to prevent.
 *
 * The gate lives here rather than at the call site, for the reason the chips'
 * does: a gate the caller owns is a gate a second caller forgets. It is the
 * only condition on the card, which is otherwise **ungated** — what decides
 * that a suggestion is on offer at all is the agent's own offer, where the
 * audience can watch it fire.
 */
const FollowOnTask: React.FC<FollowOnTaskProps> = ({ task, onSelect, disabled }) => {
  const clarificationPending = useAppSelector(selectHasPendingClarification);

  if (clarificationPending) return null;

  return (
    <div className="follow-on-task" data-testid="follow-on-task">
      <Button appearance="outline" size="large" disabled={disabled} onClick={() => onSelect(task)}>
        {task.name}
      </Button>
    </div>
  );
};

export default FollowOnTask;
