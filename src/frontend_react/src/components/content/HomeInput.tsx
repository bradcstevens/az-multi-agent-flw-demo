
import {
    Body1,
    Body1Strong,
    Button,
    Caption1,
    Card,
    Text,
    Title2,
    Toast,
    ToastBody,
    ToastTitle,
} from "@fluentui/react-components";
import {
    Send20Regular,
} from "@fluentui/react-icons";
import React, { useRef, useEffect, useState } from "react";
import { useNavigate } from 'react-router-dom';
import "./../../styles/HomeInput.css";
import "./../../styles/Chat.css";
import "../../styles/prism-material-oceanic.css"
import { HomeInputProps, quickTasks, QuickTask } from "../../models/homeInput";
import { TaskService } from "../../services/TaskService";
import { NewTaskService } from "../../services/NewTaskService";
import ChatInput from "@/coral/modules/ChatInput";


const HomeInput: React.FC<HomeInputProps> = ({
    onInputSubmit,
    onQuickTaskSelect,
}) => {
    const [input, setInput] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [showToast, setShowToast] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const navigate = useNavigate();

    /**
     * Reset textarea to empty state
     */
    const resetTextarea = () => {
        setInput("");
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.focus();
        }
    };

    // Listen for new task reset events
    useEffect(() => {
        const cleanup = NewTaskService.addResetListener(resetTextarea);
        return cleanup;
    }, []);

    const handleSubmit = async () => {
        if (input.trim()) {
            setSubmitting(true);
            setShowToast(true);
            setError(null);
            try {
                // Submit the input task using TaskService
                const response = await TaskService.submitInputTask(input.trim());

                // Clear the input field
                //setInput("");
                if (textareaRef.current) {
                    textareaRef.current.style.height = "auto";
                }

                console.log('Task response', response);
                if (response.plan_id != null) {
                    // plan_id is valid (not null or undefined)
                    navigate(`/plan/${response.plan_id}`);
                } else {
                    // plan_id is not valid, handle accordingly
                    console.log('Invalid plan:', response.status);
                    setShowToast(false);
                    setError("Failed to create task. Please try again.");
                }

            } catch (error: any) {
                console.log('Failed to create task:', error);
                setError(error.message || "Failed to create task.");
            } finally {
                setSubmitting(false);
            }
        }
    };
    const handleQuickTaskClick = (task: QuickTask) => {
        // Copy task description to textarea
        setInput(task.description);

        // Focus on textarea
        if (textareaRef.current) {
            textareaRef.current.focus();
        }

        // Call the onQuickTaskSelect with the task description
        onQuickTaskSelect(task.description);
    };


    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [input]);

    return (
        <div className="home-input-container">
            <div className="home-input-content">
                <div className="home-input-center-content">
                    <div className="home-input-title-wrapper">
                        <Title2>How can I help?</Title2>
                    </div>

                    <ChatInput
                        value={input}
                        placeholder="Describe what you'd like to do or use / to reference files, people, and more" onChange={setInput}
                        disabledChat={submitting}
                    >
                        <Button
                            appearance="subtle"
                            className="home-input-send-button"
                            onClick={handleSubmit}
                            disabled={submitting}
                            icon={<Send20Regular />}
                        />
                    </ChatInput>

                    <div className="home-input-quick-tasks-section">
                        <div className="home-input-quick-tasks-header">
                            <Body1Strong>Quick tasks</Body1Strong>
                        </div>
                        <div className="home-input-quick-tasks">
                            {quickTasks.map((task) => (
                                <Card
                                    key={task.id}
                                    className="home-input-quick-task-card"
                                    onClick={() => handleQuickTaskClick(task)}
                                >
                                    <div className="home-input-quick-task-content">
                                        <div className="home-input-quick-task-icon">
                                            {task.icon}
                                        </div>
                                        <div className="home-input-quick-task-text-content">
                                            <Body1Strong>{task.title}</Body1Strong>
                                            <Body1 className="home-input-quick-task-description">
                                                {task.description}
                                            </Body1>
                                        </div>
                                    </div>
                                </Card>
                            ))}
                        </div>
                    </div>
                    {/* Toast appears after quick tasks */}
                    {showToast && (
                        <div style={{ marginTop: 16 }}>
                            <Toast>
                                <ToastTitle>Task submitted!</ToastTitle>
                                <ToastBody>Your task is processing.</ToastBody>
                            </Toast>
                        </div>
                    )}
                    {error && (
                        <div style={{ marginTop: 16 }}>
                            <Toast>
                                <ToastTitle>Task failed!</ToastTitle>
                                <ToastBody>{error}</ToastBody>
                            </Toast>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default HomeInput; 