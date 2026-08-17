import { useCallback } from 'react';
import { PlanStatus } from '../models';

interface UsePlanCancellationAlertProps {
  planData: any;
}

/**
 * Whether this Chat has a turn still running.
 *
 * It answers one question and nothing else. **Leaving a Chat is navigation,
 * not a Verdict** (ADR-031 decision 2, #108): nothing here calls
 * `/v4/plan_approval`, because walking away is not a thing the associate said
 * about the plan. What ends the run behind an abandoned turn is the Chat's own
 * cancellation, which is #121.
 */
export const usePlanCancellationAlert = ({
  planData,
}: UsePlanCancellationAlertProps) => {
  const isPlanActive = useCallback(() => {
    return planData?.plan?.overall_status === PlanStatus.IN_PROGRESS;
  }, [planData]);

  return { isPlanActive };
};

export default usePlanCancellationAlert;
