import {
  Body1Strong,
  Button,
  Caption1,
  Title2
} from "@fluentui/react-components";

import React, { useRef, useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import "./../../styles/Chat.css";
import "../../styles/prism-material-oceanic.css";
import "./../../styles/HomeInput.css";

import { HomeInputProps, iconMap, QuickTask } from "../../models/homeInput";
import { TaskService } from "../../store/TaskService";
import { parsePolicyBlock, PolicyBlock } from "../../api/policyBlock";
import { isLane, LANE_LABELS } from "../../models/lane";
import LaneBadge from "../lane/LaneBadge";
import { NewTaskService } from "../../store/NewTaskService";
import { useAppDispatch } from "@/store/hooks";
import { refusalRecorded } from "@/store/slices/transparencySlice";

import ChatInput from "@/commonComponents/modules/ChatInput";
import InlineToaster, { useInlineToaster } from "../toast/InlineToaster";
import PromptCard from "@/commonComponents/components/PromptCard";
import { Send } from "@/commonComponents/imports/bundleicons";
import { Clipboard20Regular, ShieldCheckmark20Regular } from "@fluentui/react-icons";

// Icon mapping function to convert string icons to FluentUI icons
const getIconFromString = (
  iconString: string | React.ReactNode
): React.ReactNode => {
  // If it's already a React node, return it
  if (typeof iconString !== "string") {
    return iconString;
  }

  return iconMap[iconString] || iconMap["default"] || <Clipboard20Regular />;
};

const truncateDescription = (
  description: string,
  maxLength: number = 180
): string => {
  if (!description) return "";

  if (description.length <= maxLength) {
    return description;
  }

  const truncated = description.substring(0, maxLength);
  const lastSpaceIndex = truncated.lastIndexOf(" ");

  const cutPoint = lastSpaceIndex > maxLength - 20 ? lastSpaceIndex : maxLength;

  return description.substring(0, cutPoint) + "...";
};

// Extended QuickTask interface to store both truncated and full descriptions
interface ExtendedQuickTask extends QuickTask {
  fullDescription: string; // Store the full, untruncated description
  lane?: string; // The Lane this Quick Task declares (issue #16, ADR-013)
}

const HomeInput: React.FC<HomeInputProps> = ({ selectedTeam }) => {
  const dispatch = useAppDispatch();
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [input, setInput] = useState<string>("");
  const [policyBlock, setPolicyBlock] = useState<PolicyBlock | null>(null);
  /**
   * The Lane declared by the Quick Task that was tapped, if the text in the
   * box is still that task's prompt. Editing the text clears it — edited text
   * is free-typed input, and free-typed input is the keyword fallback's job.
   */
  const [declaredLane, setDeclaredLane] = useState<string | undefined>(undefined);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const location = useLocation(); // ✅ location.state used to control focus
  const { showToast, dismissToast } = useInlineToaster();

  // Check if the selected team is the Contract Compliance Review Team
  const isLegalTeam = selectedTeam?.name
    ?.toLowerCase()
    .includes("contract compliance");

  useEffect(() => {
    if (location.state?.focusInput) {
      textareaRef.current?.focus();
    }
  }, [location]);

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
      setSubmitting(true);
      setPolicyBlock(null);
      let id = showToast("Creating a plan", "progress");

      try {
        const response = await TaskService.createPlan(
          input.trim(),
          selectedTeam?.team_id,
          declaredLane
        );
        setInput("");

        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
        }

        // The lane taken, as the lane router reported it — a feature of the
        // assistant, not an implementation detail (ADR-013). It is not always
        // the lane declared: free-typed input declares nothing, and an
        // unreadable declaration falls open to the Deliberate lane. It is
        // carried to the plan page, where the answer (or the approval step)
        // arrives, so it outlives this toast.
        if (response.plan_id && response.plan_id !== null) {
          showToast(
            isLane(response.lane)
              ? `Plan created — ${LANE_LABELS[response.lane]}`
              : "Plan created!",
            "success"
          );
          dismissToast(id);

          navigate(`/plan/${response.plan_id}`, {
            state: { lane: response.lane },
          });
        } else {
          showToast("Failed to create plan", "error");
          dismissToast(id);
        }
      } catch (error: any) {
        dismissToast(id);

        // A Policy block is the Identity boundary gate working, so it gets its
        // own surface rather than the error toast (ADR-014). Rendering it as
        // an error would make a governed refusal look like a bug — and look
        // identical to a retrieval miss, which is an answer, not a policy.
        const refusal = parsePolicyBlock(error);
        if (refusal) {
          setPolicyBlock(refusal);
          // The refusal goes on the Token meter too (#24, R7): a refused
          // request adds nothing, and the row showing a measured zero beside
          // rows that cost something is what makes "nothing" legible.
          dispatch(refusalRecorded(refusal));
          setInput("");
          setSubmitting(false);
          return;
        }

        let errorMessage = "Unable to create plan. Please try again.";
        // Check if this is an RAI validation error
        try {
          // errorDetail = JSON.parse(error);
          errorMessage = error?.message || errorMessage;
        } catch (parseError) {
          console.error("Error parsing error response", parseError);
        }

        showToast(errorMessage, "error");
      } finally {
        setInput("");
        setSubmitting(false);
      }
    }
  };

  const handleQuickTaskClick = (task: ExtendedQuickTask) => {
    setInput(task.fullDescription);
    setDeclaredLane(task.lane);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  /**
   * Typing over a Quick Task's prompt makes it free-typed input, so the
   * declared Lane goes with it — the backend's keyword fallback is what routes
   * text the presenter wrote, and a stale declaration would outrank it.
   */
  const handleInputChange = (value: string) => {
    setInput(value);
    setDeclaredLane(undefined);
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  // Convert team starting_tasks to ExtendedQuickTask format
  const tasksToDisplay: ExtendedQuickTask[] =
    selectedTeam && selectedTeam.starting_tasks
      ? selectedTeam.starting_tasks.map((task, index) => {
          // Handle both string tasks and StartingTask objects
          if (typeof task === "string") {
            return {
              id: `team-task-${index}`,
              title: task,
              description: truncateDescription(task),
              fullDescription: task, // Store the full description
              icon: getIconFromString("📋"),
            };
          } else {
            // Handle StartingTask objects
            const startingTask = task as any; // Type assertion for now
            const taskDescription =
              startingTask.prompt || startingTask.name || "Task description";
            return {
              id: startingTask.id || `team-task-${index}`,
              title: startingTask.name || startingTask.prompt || "Task",
              description: truncateDescription(taskDescription),
              fullDescription: taskDescription, // Store the full description
              icon: getIconFromString(startingTask.logo || "📋"),
              lane: startingTask.lane,
            };
          }
        })
      : [];

  return (
    <div className="home-input-container">
      <div className="home-input-content">
        <div className="home-input-center-content">
          <div className="home-input-title-wrapper">
            <Title2>How can I help?</Title2>
          </div>

          {/* Legal Disclaimer for Contract Compliance Review Team */}
          {isLegalTeam && (
            <div
              style={{
                color: "var(--colorNeutralForeground3)",
                marginTop: "8px",
                paddingBottom: "8px",
                textAlign: "center",
              }}
            >
              <Caption1>
                <strong>Disclaimer:</strong> This tool is not intended to give
                legal advice; it is intended solely for the purpose of assessing
                contract compliance against internal guidance and policy frameworks.
              </Caption1>
            </div>
          )}

          {/* Show RAI error if present */}
          {/* {raiError && (
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
                    )} */}

          {/*
            A Policy block: the Identity boundary gate refusing a personal
            question on a shared store device (ADR-014). Deliberately not a
            toast and deliberately not styled as an error — it reads as policy,
            and it is visibly a different thing from a retrieval miss, which
            arrives as an answer rather than as a failed request.
          */}
          {policyBlock && (
            <div
              className="home-input-policy-block"
              role="note"
              aria-live="polite"
              data-testid="policy-block"
              data-policy-code={policyBlock.code}
            >
              <div className="home-input-policy-block-header">
                <ShieldCheckmark20Regular aria-hidden="true" />
                <Body1Strong>Store-scoped assistant</Body1Strong>
              </div>
              <Caption1>{policyBlock.message}</Caption1>
            </div>
          )}

          <ChatInput
            ref={textareaRef} // forwarding
            value={input}
            placeholder="Tell us what needs planning, building, or connecting—we'll handle the rest."
            onChange={handleInputChange}
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
                  <div>
                    {tasksToDisplay.map((task) => (
                      <PromptCard
                        key={task.id}
                        title={task.title}
                        icon={task.icon}
                        description={task.description}
                        onClick={() => handleQuickTaskClick(task)}
                        disabled={submitting}
                        badge={
                          isLane(task.lane) ? (
                            <LaneBadge lane={task.lane} variant="declared" />
                          ) : undefined
                        }
                      />
                    ))}
                  </div>
                </div>
              </>
            )}
            {tasksToDisplay.length === 0 && selectedTeam && (
              <div
                style={{
                  textAlign: "center",
                  padding: "32px 16px",
                  color: "#666",
                }}
              >
                <Caption1>No starting tasks available for this team</Caption1>
              </div>
            )}
            {!selectedTeam && (
              <div
                style={{
                  textAlign: "center",
                  padding: "32px 16px",
                  color: "#666",
                }}
              >
                <Caption1>Select a team to see available tasks</Caption1>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const MemoizedHomeInput = React.memo(HomeInput);
MemoizedHomeInput.displayName = 'HomeInput';
export default MemoizedHomeInput;
