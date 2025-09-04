import {
    Body1Strong,
    Button,
    Caption1,
    Title2,
} from "@fluentui/react-components";

import React, { useCallback, useRef, useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import "./../../styles/Chat.css";
import "../../styles/prism-material-oceanic.css";
import "./../../styles/HomeInput.css";

import { HomeInputProps, iconMap, QuickTask } from "../../models/homeInput";
import { TaskService } from "../../services/TaskService";
import { NewTaskService } from "../../services/NewTaskService";
import { RAIErrorCard, RAIErrorData } from "../errors";

import ChatInput from "@/coral/modules/ChatInput";
import InlineToaster, { useInlineToaster } from "../toast/InlineToaster";
import PromptCard from "@/coral/components/PromptCard";
import { Send } from "@/coral/imports/bundleicons";
import { Clipboard20Regular } from "@fluentui/react-icons";
import webSocketService from '../../services/WebSocketService';

// Icon mapping function to convert string icons to FluentUI icons
const getIconFromString = (iconString: string | React.ReactNode): React.ReactNode => {
    // If it's already a React node, return it
    if (typeof iconString !== 'string') {
        return iconString;
    }

    return iconMap[iconString] || iconMap['default'] || <Clipboard20Regular />;
};

const HomeInput: React.FC<HomeInputProps> = ({
    selectedTeam,
}) => {
    const [submitting, setSubmitting] = useState(false);
    const [input, setInput] = useState("");
    const [raiError, setRAIError] = useState<RAIErrorData | null>(null);

    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const navigate = useNavigate();
    const location = useLocation(); // ✅ location.state used to control focus
    const { showToast, dismissToast } = useInlineToaster();

    // Generate session ID for this task submission
    const sessionId = React.useMemo(() => {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }, []);

    useEffect(() => {
        if (location.state?.focusInput) {
            textareaRef.current?.focus();
        }
    }, [location]);

    const resetTextarea = () => {
        setInput("");
        setRAIError(null); // Clear any RAI errors
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.focus();
        }
    };

    useEffect(() => {
        const cleanup = NewTaskService.addResetListener(resetTextarea);
        return cleanup;
    }, []);

        const handleSubmit = useCallback(async () => {
        if (!input.trim()) return;
        
        setSubmitting(true);
        setRAIError(null); // Clear any previous RAI errors
        let id = showToast("Creating a plan", "progress");

        try {
            const requestBody = {
                session_id: sessionId,
                description: input.trim(),
                team_id: selectedTeam?.team_id || null
            };

            console.log('🚀 Submitting task to v3 backend:', requestBody);

            // Use v3 API endpoint
            const response = await fetch('/api/v3/process_request', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
            });

            if (response.ok) {
                const result = await response.json();
                console.log('✅ v3 Backend response:', result);
                
                dismissToast(id);
                setInput("");
                
                if (textareaRef.current) {
                    textareaRef.current.style.height = "auto";
                }

                if (result.plan_id) {
                    showToast('Task submitted successfully! Creating plan...', 'success');
                    
                    // Connect WebSocket with process_id from v3 response
                    try {
                        await webSocketService.connect(sessionId, result.plan_id);
                    } catch (wsError) {
                        console.warn('WebSocket connection failed:', wsError);
                        // Continue with navigation even if WebSocket fails
                    }
                    
                    navigate(`/plan/${result.plan_id}`);
                } else {
                    throw new Error('No plan_id received from backend');
                }
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to submit task');
            }
        } catch (error: any) {
            dismissToast(id);
            console.error('❌ Task submission failed:', error);
            
            // Handle RAI validation errors
            let errorDetail = null;
            try {
                if (typeof error?.response?.data?.detail === 'string') {
                    errorDetail = JSON.parse(error.response.data.detail);
                } else {
                    errorDetail = error?.response?.data?.detail;
                }
            } catch (parseError) {
                errorDetail = error?.response?.data?.detail;
            }

            if (errorDetail?.error_type === 'RAI_VALIDATION_FAILED') {
                setRAIError(errorDetail);
            } else {
                const errorMessage = errorDetail?.description ||
                    errorDetail?.message ||
                    error?.response?.data?.message ||
                    error?.message ||
                    "Something went wrong";
                showToast(errorMessage, "error");
            }
        } finally {
            setSubmitting(false);
        }
    }, [input, sessionId, selectedTeam?.team_id, showToast, dismissToast, navigate]);

    const handleQuickTaskClick = (task: QuickTask) => {
        setInput(task.description);
        setRAIError(null); // Clear any RAI errors when selecting a quick task
        if (textareaRef.current) {
            textareaRef.current.focus();
        }

    };

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [input]);

    // Convert team starting_tasks to QuickTask format
    const tasksToDisplay: QuickTask[] = selectedTeam && selectedTeam.starting_tasks ?
        selectedTeam.starting_tasks.map((task, index) => {
            // Handle both string tasks and StartingTask objects
            if (typeof task === 'string') {
                return {
                    id: `team-task-${index}`,
                    title: task,
                    description: task,
                    icon: getIconFromString("📋")
                };
            } else {
                // Handle StartingTask objects
                const startingTask = task as any; // Type assertion for now
                return {
                    id: startingTask.id || `team-task-${index}`,
                    title: startingTask.name || startingTask.prompt || 'Task',
                    description: startingTask.prompt || startingTask.name || 'Task description',
                    icon: getIconFromString(startingTask.logo || "📋")
                };
            }
        }) : [];

    return (
        <div className="home-input-container">
            <div className="home-input-content">
                <div className="home-input-center-content">
                    <div className="home-input-title-wrapper">
                        <Title2>How can I help?</Title2>
                    </div>

                    {/* Show RAI error if present */}
                    {raiError && (
                        <RAIErrorCard
                            error={raiError}
                            onRetry={() => {
                                setRAIError(null);
                                if (textareaRef.current) {
                                    textareaRef.current.focus();
                                }
                            }}
                            onDismiss={() => setRAIError(null)}
                        />
                    )}

                    <ChatInput
                        ref={textareaRef} // forwarding
                        value={input}
                        placeholder="Tell us what needs planning, building, or connecting—we'll handle the rest."
                        onChange={setInput}
                        onEnter={handleSubmit}
                        disabledChat={submitting}
                    >
                        <Button
                            appearance="subtle"
                            className="home-input-send-button"
                            onClick={handleSubmit}
                            disabled={submitting}
                            icon={<Send />}
                        />
                    </ChatInput>

                    <InlineToaster />

                    <div className="home-input-quick-tasks-section">
                        {tasksToDisplay.length > 0 && (
                            <>
                                <div className="home-input-quick-tasks-header">
                                    <Body1Strong>Quick tasks</Body1Strong>
                                </div>

                                <div className="home-input-quick-tasks">
                                    {tasksToDisplay.map((task) => (
                                        <PromptCard
                                            key={task.id}
                                            title={task.title}
                                            icon={task.icon}
                                            description={task.description}
                                            onClick={() => handleQuickTaskClick(task)}
                                            disabled={submitting}
                                        />
                                    ))}
                                </div>
                            </>
                        )}
                        {tasksToDisplay.length === 0 && selectedTeam && (
                            <div style={{
                                textAlign: 'center',
                                padding: '32px 16px',
                                color: '#666'
                            }}>
                                <Caption1>No starting tasks available for this team</Caption1>
                            </div>
                        )}
                        {!selectedTeam && (
                            <div style={{
                                textAlign: 'center',
                                padding: '32px 16px',
                                color: '#666'
                            }}>
                                <Caption1>Select a team to see available tasks</Caption1>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default HomeInput;
