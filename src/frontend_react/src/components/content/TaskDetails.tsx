// TaskDetails.tsx - Merged TSX + Styles

import { HumanFeedbackStatus, Step, TaskDetailsProps } from "@/models";
import {
    Subtitle1,
    Text,
    Divider,
    Avatar,
    Checkbox,
    Body1,
    Body1Strong,
    Caption1,
} from "@fluentui/react-components";
import {
    Add20Regular,
    CheckmarkCircle20Regular,
    Dismiss20Regular,
    CircleHalfFill20Regular,
    CheckboxChecked20Regular,
    DismissSquare20Regular,
} from "@fluentui/react-icons";
import React, { useState } from "react";
import { TaskService } from "@/services";
import PanelRightToolbar from "@/coral/components/Panels/PanelRightToolbar";
import "../../styles/TaskDetails.css";

const TaskDetails: React.FC<TaskDetailsProps> = ({
    planData,
    loading,
    OnApproveStep,
    OnRejectStep,
}) => {
    const [steps, setSteps] = useState(planData.steps || []);
    const [completedCCount, setCompletedCount] = useState(
        planData?.plan.completed || 0
    );
    const [total, setTotal] = useState(planData?.plan.total_steps || 1);
    const [progress, setProgress] = useState(
        (planData?.plan.completed || 0) / (planData?.plan.total_steps || 1)
    );
    const agents = planData?.agents || [];

    const renderStatusIcon = (status: string) => {
        switch (status) {
            case "completed":
            case 'accepted':
                return (<CheckmarkCircle20Regular className="status-icon-completed" />
                );

            case "rejected":
                return (<Dismiss20Regular className="status-icon-rejected" />
                );
            case "planned":
            default:
                return (<CircleHalfFill20Regular className="status-icon-planned" />
                );
        }

    };
    // Pre-step function for approval
    const preOnApproved = async (step: Step) => {
        try {
            // Update the specific step's human_approval_status
            const updatedStep = {
                ...step,
                human_approval_status: 'accepted' as HumanFeedbackStatus
            };

            // Create a new array with the updated step
            const updatedSteps = steps.map(s =>
                s.id === step.id ? updatedStep : s
            );

            // Update local state to reflect changes immediately

            setSteps(updatedSteps);
            setCompletedCount(completedCCount + 1); // Increment completed count
            setProgress((completedCCount + 1) / total); // Update progress
            // Then call the main approval function
            // This could be your existing OnApproveStep function that handles API calls, etc.
            await OnApproveStep(updatedStep);


        } catch (error) {
            console.error('Error in pre-approval step:', error);
            throw error; // Re-throw to allow caller to handle
        }
    };

    // Pre-step function for rejection
    const preOnRejected = async (step: Step) => {
        try {
            // Update the specific step's human_approval_status
            const updatedStep = {
                ...step,
                human_approval_status: 'rejected' as HumanFeedbackStatus
            };

            // Create a new array with the updated step
            const updatedSteps = steps.map(s =>
                s.id === step.id ? updatedStep : s
            );

            // Update local state to reflect changes immediately
            setSteps(updatedSteps);
            setCompletedCount(completedCCount + 1); // Increment completed count
            setProgress((completedCCount + 1) / total); // Update progress
            // Then call the main rejection function
            // This could be your existing OnRejectStep function that handles API calls, etc.
            await OnRejectStep(updatedStep);

        } catch (error) {
            console.error('Error in pre-rejection step:', error);
            throw error; // Re-throw to allow caller to handle
        }
    };

    return (
        <div className="task-details-container">
            <PanelRightToolbar panelTitle="Progress"></PanelRightToolbar>
            <div className="task-details-section">
                <div className="task-details-progress-header">
                    <div className="task-details-progress-card">
                        <div className="task-details-progress-icon">
                            <svg width="56" height="56" viewBox="0 0 56 56">
                                <circle
                                    cx="28"
                                    cy="28"
                                    r="24"
                                    fill="none"
                                    stroke="var(--colorNeutralBackground1)"
                                    strokeWidth="8"
                                />
                                <circle
                                    cx="28"
                                    cy="28"
                                    r="24"
                                    fill="none"
                                    stroke="var(--colorPaletteSeafoamBorderActive)"
                                    strokeWidth="8"
                                    strokeDasharray={`${progress * 150.8} 150.8`}
                                    strokeDashoffset="0"
                                    strokeLinecap="round"
                                    transform="rotate(-90 28 28)"
                                />
                            </svg>
                        </div>
                        <div>
                            <Body1Strong>{planData.plan.initial_goal}</Body1Strong>
                            <br />
                            <Text size={200}>
                                {completedCCount} of {total} completed
                            </Text>
                        </div>
                    </div>
                </div>

                <div className="task-details-subtask-list">
                    {steps.map((step) => {
                        const { description, functionOrDetails } = TaskService.splitSubtaskAction(
                            step.action
                        );
                        const canInteract = planData.enableStepButtons;

                        return (<div key={step.id} className="task-details-subtask-item">
                            <div className="task-details-status-icon">
                                {renderStatusIcon(step.human_approval_status || step.status)}
                            </div>
                            <div className="task-details-subtask-content">
                                <span className={`task-details-subtask-description ${step.human_approval_status === "rejected" ? "strikethrough" : ""}`}>
                                    {description} {functionOrDetails && <Caption1>{functionOrDetails}</Caption1>}
                                </span>
                                <div className="task-details-action-buttons">
                                    {(step.human_approval_status !== "accepted" && step.human_approval_status !== "rejected") && (
                                        <>
                                            <CheckboxChecked20Regular
                                                onClick={
                                                    canInteract ? () => preOnApproved(step) : undefined
                                                }
                                                className={canInteract ? "task-details-action-button" : "task-details-action-button-disabled"}
                                            />
                                            <DismissSquare20Regular
                                                onClick={
                                                    canInteract ? () => preOnRejected(step) : undefined
                                                }
                                                className={canInteract ? "task-details-action-button" : "task-details-action-button-disabled"}
                                            />
                                        </>
                                    )}
                                </div>

                            </div>
                        </div>
                        );
                    })}
                </div>
            </div>

            <div className="task-details-agents-container">
                <div className="task-details-agents-header">
                    <Body1Strong>Agents</Body1Strong>
                </div>
                <div className="task-details-agents-list">
                    {agents.map((agent) => (
                        <div key={agent} className="task-details-agent-card">
                            <Avatar name={agent} size={32} badge={{ status: "available" }} />
                            <div className="task-details-agent-details">
                                <span className="task-details-agent-name">
                                    {TaskService.cleanTextToSpaces(agent)}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default TaskDetails;
