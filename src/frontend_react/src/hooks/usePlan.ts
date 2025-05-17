import { useState, useEffect } from 'react';
import { PlanWithSteps, Step, HumanFeedbackStatus, StepStatus } from '../models';
import PlanService from '../api/planService';



/**
 * Custom hook for working with a plan and its steps
 * 
 * @param sessionId The session ID
 * @param planId The plan ID
 * @returns Object containing plan data, loading state, error state, and functions to interact with the plan
 */
export const usePlan = (sessionId: string, planId: string) => {
    const [planWithSteps, setPlanWithSteps] = useState<PlanWithSteps | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<Error | null>(null);

    /**
     * Fetch the plan and its steps
     */
    const fetchPlan = async () => {
        try {
            setLoading(true);


            const data = await PlanService.getPlanWithSteps(sessionId, planId);
            setPlanWithSteps(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Failed to fetch plan'));
        } finally {
        }
    };

    /**
     * Update a step's status and provide feedback
     * 
     * @param stepId The step ID
     * @param approved Whether the step is approved
     * @param feedback Optional feedback message
     * @param updatedAction Optional updated action
     * @returns Promise resolving to the updated step
     */
    const updateStepFeedback = async (
        stepId: string,
        approved: boolean,
        feedback?: string,
        updatedAction?: string
    ) => {
        try {
            const status = approved ? StepStatus.APPROVED : StepStatus.REJECTED;


            const update = {
                status,
                human_feedback: feedback,
                updated_action: updatedAction
            };

            const updatedStep = await PlanService.updateStep(sessionId, planId, stepId, update);

            // Update local state
            if (planWithSteps) {
                const updatedSteps = planWithSteps.steps.map(step =>
                    step.id === stepId ? { ...step, ...updatedStep } : step
                );

                setPlanWithSteps({
                    ...planWithSteps,
                    steps: updatedSteps
                });
            }

            return updatedStep;
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Failed to update step'));
            throw err;
        }
    };

    /**
     * Get steps that are awaiting feedback
     * 
     * @returns Array of steps awaiting feedback
     */
    const getStepsAwaitingFeedback = (): Step[] => {
        if (!planWithSteps) return [];
        return planWithSteps.steps.filter(
            step => step.status === StepStatus.AWAITING_FEEDBACK &&
                step.human_approval_status === HumanFeedbackStatus.REQUESTED
        );
    };

    /**
     * Check if the plan is complete
     * 
     * @returns Boolean indicating if all steps are completed or failed
     */
    const isPlanComplete = (): boolean => {
        if (!planWithSteps) return false;
        return planWithSteps.steps.every(
            step => step.status === StepStatus.COMPLETED || step.status === StepStatus.FAILED
        );
    };

    // Initial fetch
    useEffect(() => {
        if (sessionId && planId) {
            fetchPlan();
        }
    }, [sessionId, planId]);

    return {
        plan: planWithSteps,
        loading,
        error,
        fetchPlan,
        updateStepFeedback,
        getStepsAwaitingFeedback,
        isPlanComplete
    };
};

export default usePlan;
