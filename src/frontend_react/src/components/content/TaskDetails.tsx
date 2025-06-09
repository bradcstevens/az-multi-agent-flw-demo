import { TaskDetailsProps } from "@/models";
import {
    Body1,
    Button,
    Card,
    Checkbox,
    Divider,
    Persona,
    Text,
    Subtitle1,
    Avatar,
} from "@fluentui/react-components";
import { Add20Regular, CheckmarkCircle20Regular, Dismiss20Regular, CircleHalfFill20Regular } from "@fluentui/react-icons";
import React from "react";
import "../../styles/TaskDetails.css";

const TaskDetails: React.FC<TaskDetailsProps> = ({
    planData,
    OnApproveStep,
    OnRejectStep
}) => {
    const completedCount = planData.plan.completed || 0;
    const total = planData.plan.total_steps || 1; // Avoid division by zero
    const subTasks = planData.steps || [];
    const progress = completedCount / total;
    const agents = planData.agents || [];
    // Helper function to render the appropriate status icon
    const renderStatusIcon = (status: string) => {
        switch (status) {
            case 'completed':
                return <CheckmarkCircle20Regular className="task-details-status-completed" />;
            case 'working':
                return <CircleHalfFill20Regular className="task-details-status-working" />;
            case 'removed':
                return <Dismiss20Regular className="task-details-status-removed" />;
            default:
                return null;
        }
    }; return (
        <div className="task-details-container">
            <div className="task-details-section">
                <Subtitle1 className="task-details-section-title">Progress</Subtitle1>

                <div className="task-details-progress-header">
                    <div style={{ display: "flex", alignItems: "center" }}>
                        <div className="task-details-progress-ring">
                            {/* This is a simplified progress ring - in a real implementation you'd use a proper circular progress component */}
                            <svg width="56" height="56" viewBox="0 0 56 56">
                                <circle cx="28" cy="28" r="24" fill="none" stroke="#f0f0f0" strokeWidth="4" />
                                <circle
                                    cx="28"
                                    cy="28"
                                    r="24"
                                    fill="none"
                                    stroke="#0078d4"
                                    strokeWidth="4"
                                    strokeDasharray={`${progress * 150.8} 150.8`}
                                    strokeDashoffset="0"
                                    strokeLinecap="round"
                                    transform="rotate(-90 28 28)"
                                />
                            </svg>
                            <div className="task-details-progress-text">{completedCount}/{total}</div>
                        </div>
                        <div>
                            <div className="task-details-task-title">{planData.plan.initial_goal}</div>
                            <Text size={200}>{planData.plan.completed} of {total} completed</Text>
                        </div>
                    </div>
                </div>

                <div className="task-details-subtask-list">
                    {subTasks.map((subtask) => (
                        <div key={subtask.id} className="task-details-subtask-item">
                            <div className="task-details-status-icon">
                                {renderStatusIcon(subtask.status)}
                            </div>
                            <div className="task-details-subtask-content">
                                <span className="task-details-subtask-name">{subtask.action}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <Divider />

            <div className="task-details-section">
                <Subtitle1 className="task-details-section-title">Agents</Subtitle1>
                <div className="task-details-agent-list">
                    {agents.map((agent) => (
                        <div key={agent} className="task-details-agent-card">
                            <Avatar
                                name={agent}
                                size={32}
                                badge={{ status: 'available' }}
                            // image={{ src: agent.avatarUrl }}
                            />
                            <div className="task-details-agent-details">
                                <span className="task-details-agent-name">{agent}</span>
                                <span className="task-details-agent-description">agent description</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <Divider />

            {/* <div className="task-details-section">
                <Subtitle1 className="task-details-section-title">Humans</Subtitle1>
                <div className="task-details-human-list">
                    {humans.map((human) => (
                        <div key={human.id} className="task-details-agent-card">
                            <Avatar
                                name={human.name}
                                size={32}
                                image={{ src: human.avatarUrl }}
                            />
                            <div className="task-details-agent-details">
                                <span className="task-details-agent-name">{human.name}</span>
                                <span className="task-details-agent-description">{human.email}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div> */}
        </div>
    );
};

export default TaskDetails; 