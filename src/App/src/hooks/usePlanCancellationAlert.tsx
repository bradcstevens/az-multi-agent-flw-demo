import { useCallback } from 'react';
import { APIService } from '../api/apiService';

interface UsePlanCancellationAlertProps {
  planData: any;
  planApprovalRequest: any;
  onNavigate: () => void;
}

/** Handles cancellation alerts when navigation leaves a Deliberate request. */
export const usePlanCancellationAlert = ({
  planData,
  planApprovalRequest,
  onNavigate
}: UsePlanCancellationAlertProps) => {
  const apiService = new APIService();

  const requiresCancellationConfirmation = useCallback(() => {
    return planData?.plan?.lane === 'deliberate';
  }, [planData]);

  /**
   * Handle the confirmation dialog and plan cancellation
   */
  const handleNavigationWithConfirmation = useCallback(async () => {
    if (!requiresCancellationConfirmation()) {
      // No cancellation confirmation is required.
      onNavigate();
      return;
    }

    // Show confirmation dialog
    const userConfirmed = window.confirm(
      "If you continue, the plan process will be stopped and the plan will be cancelled."
    );

    if (!userConfirmed) {
      // User cancelled, do nothing
      return;
    }

    try {
      // User confirmed, cancel the plan
      if (planApprovalRequest?.id) {
        await apiService.approvePlan({
          m_plan_id: planApprovalRequest.id,
          plan_id: planData?.plan?.id,
          approved: false,
          feedback: 'Plan cancelled by user navigation'
        });
      }

      // Navigate after successful cancellation
      onNavigate();
    } catch {
      // Show error but still allow navigation
      alert('Failed to cancel the plan properly, but navigation will continue.');
      onNavigate();
    }
  }, [requiresCancellationConfirmation, onNavigate, planApprovalRequest, planData, apiService]);

  return {
    requiresCancellationConfirmation,
    handleNavigationWithConfirmation
  };
};

export default usePlanCancellationAlert;