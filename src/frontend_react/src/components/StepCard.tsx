import React from 'react';
import { Step, StepStatus, AgentType } from '../models';

interface StepCardProps {
    step: Step;
    onApprove: (stepId: string, feedback?: string) => void;
    onReject: (stepId: string, feedback: string, updatedAction?: string) => void;
}

/**
 * Component to display a single step card with action buttons
 */
const StepCard: React.FC<StepCardProps> = ({ step, onApprove, onReject }) => {
    const [feedback, setFeedback] = React.useState('');
    const [updatedAction, setUpdatedAction] = React.useState('');
    const [showFeedbackForm, setShowFeedbackForm] = React.useState(false);

    const getStatusBadgeColor = (status: StepStatus): string => {
        switch (status) {
            case StepStatus.PLANNED: return 'bg-blue-100 text-blue-800';
            case StepStatus.AWAITING_FEEDBACK: return 'bg-yellow-100 text-yellow-800';
            case StepStatus.APPROVED: return 'bg-green-100 text-green-800';
            case StepStatus.REJECTED: return 'bg-red-100 text-red-800';
            case StepStatus.ACTION_REQUESTED: return 'bg-purple-100 text-purple-800';
            case StepStatus.COMPLETED: return 'bg-green-500 text-white';
            case StepStatus.FAILED: return 'bg-red-500 text-white';
            default: return 'bg-gray-100 text-gray-800';
        }
    };

    const getAgentBadgeColor = (agent: AgentType): string => {
        switch (agent) {
            case AgentType.HR: return 'bg-pink-100 text-pink-800';
            case AgentType.MARKETING: return 'bg-orange-100 text-orange-800';
            case AgentType.PROCUREMENT: return 'bg-blue-100 text-blue-800';
            case AgentType.PRODUCT: return 'bg-green-100 text-green-800';
            case AgentType.GENERIC: return 'bg-gray-100 text-gray-800';
            case AgentType.TECH_SUPPORT: return 'bg-purple-100 text-purple-800';
            case AgentType.PLANNER: return 'bg-indigo-100 text-indigo-800';
            case AgentType.GROUP_CHAT_MANAGER: return 'bg-teal-100 text-teal-800';
            case AgentType.HUMAN: return 'bg-yellow-100 text-yellow-800';
            default: return 'bg-gray-100 text-gray-800';
        }
    };

    const handleReject = () => {
        onReject(step.id, feedback, updatedAction || undefined);
        setFeedback('');
        setUpdatedAction('');
        setShowFeedbackForm(false);
    };

    const handleApprove = () => {
        onApprove(step.id, feedback || undefined);
        setFeedback('');
        setShowFeedbackForm(false);
    };

    return (
        <div className="border rounded-lg p-4 mb-4 shadow-sm bg-white">
            <div className="flex justify-between items-start mb-3">
                <div>
                    <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full mr-2 ${getStatusBadgeColor(step.status)}`}>
                        {step.status}
                    </span>
                    <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${getAgentBadgeColor(step.agent)}`}>
                        {step.agent}
                    </span>
                </div>
                <span className="text-xs text-gray-500">
                    {new Date(step.timestamp).toLocaleString()}
                </span>
            </div>

            <h3 className="font-medium text-gray-900 mb-2">Action:</h3>
            <p className="text-gray-700 mb-4 whitespace-pre-line">{step.action}</p>

            {step.agent_reply && (
                <>
                    <h3 className="font-medium text-gray-900 mb-2">Agent Reply:</h3>
                    <p className="text-gray-700 mb-4 whitespace-pre-line">{step.agent_reply}</p>
                </>
            )}

            {step.human_feedback && (
                <>
                    <h3 className="font-medium text-gray-900 mb-2">Your Feedback:</h3>
                    <p className="text-gray-700 mb-4 whitespace-pre-line">{step.human_feedback}</p>
                </>
            )}

            {step.status === StepStatus.AWAITING_FEEDBACK && (
                <div className="mt-4">
                    {!showFeedbackForm && (
                        <div className="flex space-x-2">
                            <button
                                onClick={() => onApprove(step.id)}
                                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                            >
                                Approve
                            </button>
                            <button
                                onClick={() => setShowFeedbackForm(true)}
                                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
                            >
                                Add Feedback
                            </button>
                        </div>
                    )}

                    {showFeedbackForm && (
                        <div className="space-y-3">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Feedback (optional for approval, required for rejection)
                                </label>
                                <textarea
                                    value={feedback}
                                    onChange={(e) => setFeedback(e.target.value)}
                                    className="w-full px-3 py-2 border rounded-md"
                                    rows={3}
                                    placeholder="Enter your feedback..."
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Updated Action (optional, only for rejection)
                                </label>
                                <textarea
                                    value={updatedAction}
                                    onChange={(e) => setUpdatedAction(e.target.value)}
                                    className="w-full px-3 py-2 border rounded-md"
                                    rows={3}
                                    placeholder="Enter updated action..."
                                />
                            </div>

                            <div className="flex space-x-2">
                                <button
                                    onClick={handleApprove}
                                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                                >
                                    Approve
                                </button>
                                <button
                                    onClick={handleReject}
                                    className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                                    disabled={!feedback}
                                >
                                    Reject
                                </button>
                                <button
                                    onClick={() => {
                                        setShowFeedbackForm(false);
                                        setFeedback('');
                                        setUpdatedAction('');
                                    }}
                                    className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default StepCard;
