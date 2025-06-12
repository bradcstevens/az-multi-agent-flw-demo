import {
  Body1,
  Body1Strong,
  Button,
  Caption1,
  Card,
  Title2,
} from "@fluentui/react-components";
import { FoodToast20Regular, Send20Regular } from "@fluentui/react-icons";
import React, { useRef, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./../../styles/HomeInput.css";
import "./../../styles/Chat.css";
import "../../styles/prism-material-oceanic.css";
import { HomeInputProps, quickTasks, QuickTask } from "../../models/homeInput";
import { TaskService } from "../../services/TaskService";
import { NewTaskService } from "../../services/NewTaskService";
import ChatInput from "@/coral/modules/ChatInput";
import InlineToaster, { useInlineToaster } from "../toast/InlineToaster";

const HomeInput: React.FC<HomeInputProps> = ({
  onInputSubmit,
  onQuickTaskSelect,
}) => {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const { showToast } = useInlineToaster();

  const resetTextarea = () => {
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.focus();
    }
  };

  useEffect(() => {
    const cleanup = NewTaskService.addResetListener(resetTextarea);
    return cleanup;
  }, []);

  const handleSubmit = async () => {
    if (input.trim()) {
      try {
        const response = await TaskService.submitInputTask(input.trim());

        setInput("");
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
        }

        showToast("Task created!", "success");
        navigate(`/plan/${response.plan_id}`);
      } catch (error) {
        console.error("Failed to create task:", error);
        showToast("Something went wrong", "error");
      }
    }
  };

  const handleQuickTaskClick = (task: QuickTask) => {
    setInput(task.description);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
    onQuickTaskSelect(task.description);
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  const handleClick = () => {
showToast("Creating a task plan...", "error", { dismissible: true });
  };

  return (
    <div className="home-input-container">
      <div className="home-input-content">
        <div className="home-input-center-content">
          <div className="home-input-title-wrapper">
            <Title2>How can I help?</Title2>
          </div>

          <ChatInput
            value={input}
            placeholder="Describe what you'd like to do or use / to reference files, people, and more"
            onChange={setInput}
          >
            <Button
              appearance="subtle"
              className="home-input-send-button"
              onClick={handleSubmit}
              disabled={!input.trim()}
              icon={<Send20Regular />}
            />
            <Button
              appearance="subtle"
              icon={<FoodToast20Regular />}
              onClick={handleClick}
            ></Button>
          </ChatInput>

          {/* Inline Toaster lives right under chat input */}
          <InlineToaster />

          <div className="home-input-quick-tasks-section">
            <div className="home-input-quick-tasks-header">
              <Body1Strong>Quick tasks</Body1Strong>
            </div>
            <div className="home-input-quick-tasks">
              {quickTasks.map((task) => (
                <Card
                  key={task.id}
                  style={{
                    flex: "1 ",
                    display: "flex",
                    flexDirection: "column",
                    padding: "16px",
                    backgroundColor: "var(--colorNeutralBackground3)",
                    border: "1px solid var(--colorNeutralStroke2)",
                    borderRadius: "8px",
                    cursor: "pointer",
                    boxShadow: "none",
                  }}
                  onMouseOver={(e) =>
                    (e.currentTarget.style.backgroundColor =
                      "var(--colorNeutralBackground4Hover)")
                  }
                  onMouseOut={(e) =>
                    (e.currentTarget.style.backgroundColor =
                      "var(--colorNeutralBackground3)")
                  }
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
        </div>
      </div>
    </div>
  );
};

export default HomeInput;
