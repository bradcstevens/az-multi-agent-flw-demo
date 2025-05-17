import React from 'react';
import { PlanStatus } from '../models';
import usePlan from '../hooks/usePlan';
import StepCard from './StepCard';

interface PlanViewProps {
    sessionId: string;
    planId: string;
}

/**
 * Component to display a plan and its steps
 */
const PlanView: React.FC<PlanViewProps> = ({ sessionId, planId }) => {
    const {
        plan,
        loading,
        error,
        updateStepFeedback,
        getStepsAwaitingFeedback,
        isPlanComplete
    } = usePlan(sessionId, planId);

    if (loading) {
        return (
            <div className="flex justify-center items-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded">
                <p className="font-bold">Error</p>
                <p>{error.message}</p>
            </div>
        );
    }

    if (!plan) {
        return (
            <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4 rounded">
                <p>No plan found with ID: {planId}</p>
            </div>
        );
    }

    const handleApproveStep = (stepId: string, feedback?: string) => {
        updateStepFeedback(stepId, true, feedback);
    };

    const handleRejectStep = (stepId: string, feedback: string, updatedAction?: string) => {
        updateStepFeedback(stepId, false, feedback, updatedAction);
    };

    const getPlanStatusBadge = (status: PlanStatus) => {
        switch (status) {
            case PlanStatus.IN_PROGRESS:
                return <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">In Progress</span>;
            case PlanStatus.COMPLETED:
                return <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">Completed</span>;
            case PlanStatus.FAILED:
                return <span className="px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs font-medium">Failed</span>;
            default:
                return null;
        }
    };

    const stepsAwaitingFeedback = getStepsAwaitingFeedback();

    return (
        <div className="max-w-4xl mx-auto p-4">
            <div className="mb-8">
                <div className="flex justify-between items-center mb-4">
                    <h1 className="text-2xl font-bold text-gray-900">Plan</h1>
                    {getPlanStatusBadge(plan.overall_status)}
                </div>

                <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
                    <h2 className="text-xl font-medium text-gray-900 mb-2">Goal</h2>
                    <p className="text-gray-700 whitespace-pre-line mb-4">{plan.initial_goal}</p>

                    {plan.summary && (
                        <>
                            <h2 className="text-xl font-medium text-gray-900 mb-2">Summary</h2>
                            <p className="text-gray-700 whitespace-pre-line mb-4">{plan.summary}</p>
                        </>
                    )}

                    {plan.human_clarification_request && (
                        <>
                            <h2 className="text-xl font-medium text-gray-900 mb-2">Clarification Request</h2>
                            <p className="text-gray-700 whitespace-pre-line mb-4">{plan.human_clarification_request}</p>
                        </>
                    )}

                    {plan.human_clarification_response && (
                        <>
                            <h2 className="text-xl font-medium text-gray-900 mb-2">Your Clarification</h2>
                            <p className="text-gray-700 whitespace-pre-line">{plan.human_clarification_response}</p>
                        </>
                    )}
                </div>

                <div className="mb-6">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-xl font-medium text-gray-900">Steps</h2>
                        <div className="text-sm text-gray-500">
                            {plan.completed} of {plan.total_steps} completed
                        </div>
                    </div>

                    {stepsAwaitingFeedback.length > 0 && (
                        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
                            <div className="flex">
                                <div className="flex-shrink-0">
                                    <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <div className="ml-3">
                                    <p className="text-sm text-yellow-700">
                                        {stepsAwaitingFeedback.length} {stepsAwaitingFeedback.length === 1 ? 'step' : 'steps'} awaiting your feedback
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="space-y-4">
                        {plan.steps.map(step => (
                            <StepCard
                                key={step.id}
                                step={step}
                                onApprove={handleApproveStep}
                                onReject={handleRejectStep}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PlanView;
