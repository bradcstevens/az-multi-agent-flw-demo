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
import { PersonalAnswer, parsePersonalAnswer } from "../../models/personalAnswer";
import { forgetSignedInDevice } from "../../models/signedInDevice";
import PersonalAnswerCard from "../identity/PersonalAnswerCard";
import { isLane, LANE_LABELS } from "../../models/lane";
import LaneBadge from "../lane/LaneBadge";
import { NewTaskService } from "../../store/NewTaskService";
import { useAppDispatch } from "@/store/hooks";
import { refusalRecorded, requestStarted } from "@/store/slices/transparencySlice";
import { ASSISTANT_NAME } from "../../models/storeSurface";

import ChatInput from "@/commonComponents/modules/ChatInput";
import InlineToaster, { useInlineToaster } from "../toast/InlineToaster";
import PromptCard from "@/commonComponents/components/PromptCard";
import { Send } from "@/commonComponents/imports/bundleicons";
import {
  Clipboard20Regular,
  PersonKey20Regular,
  ShieldCheckmark20Regular,
} from "@fluentui/react-icons";

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
   * The question the Identity boundary gate refused, kept so the sign-in can
   * re-ask it. Cleared the moment anything else is asked.
   */
  const [refusedQuestion, setRefusedQuestion] = useState<string | null>(null);
  /** The signed-in associate's record, once the unlock has answered (#27). */
  const [personalAnswer, setPersonalAnswer] = useState<PersonalAnswer | null>(null);
  const [signingIn, setSigningIn] = useState<boolean>(false);
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
    await submitQuestion(input.trim());
  };

  /**
   * Ask one question.
   *
   * Takes the words rather than reading the box, because the **Mocked unlock**
   * (#27) asks the *same* question a second time after the sign-in and the box
   * has been cleared by then. Re-typing it would put a typo or an autocorrect
   * between the presenter and the payoff, which is the thing the Rehearsed
   * replies exist to prevent (#26).
   */
  const submitQuestion = async (question: string, declaredLane?: string) => {
    if (!question) return;

    setSubmitting(true);
    setPolicyBlock(null);
    setRefusedQuestion(null);
    setPersonalAnswer(null);
    // The Grounding panel's claim is about *this* answer (#24, R6), so the
    // previous one goes dark before the next question is in flight. A
    // question answered inside Foundry emits no source_used at all, and a
    // stale panel would credit Copilot Studio with an answer it never gave.
    dispatch(requestStarted());
    let id = showToast("Creating a plan", "progress");

    try {
      const response = await TaskService.createPlan(
        question,
        selectedTeam?.team_id,
        declaredLane
      );
      setInput("");

      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }

      // The Mocked unlock's answer (#27): the previously refused question,
      // answered out of the signed-in associate's own record. It arrives on a
      // *successful* request with no plan, because it cost no agent and no
      // tokens — exactly as the refusal did. Checked before the plan id, since
      // a null plan here is not a failure to create one.
      const answer = parsePersonalAnswer(response);
      if (answer) {
        dismissToast(id);
        setPersonalAnswer(answer);
        setSubmitting(false);
        return;
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
        // The question, kept so the sign-in can re-ask it on one tap. This is
        // the only place in the walkthrough where the same words are said
        // twice, and the second saying has to be identical to the first or the
        // before-and-after is not a comparison.
        setRefusedQuestion(question);
        // A refusal *is* the gate stating that nobody is signed in. A header
        // that went on naming an associate the gate has just declined to
        // answer for would be the surface saying something that is not so.
        forgetSignedInDevice();
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
  };

  /**
   * The door beside the wall (#27): sign in, then ask again.
   *
   * The sign-in is **mocked end to end** — no Entra, no Okta, no identity
   * provider of any kind. It writes a name into server-side session state and
   * the very same question, unedited, goes back through the very same gate.
   *
   * A sign-in that signed nobody in does **not** re-ask. Asking again
   * anonymously would show the identical refusal a second time and read on
   * stage as the tap having done nothing at all.
   */
  const handleSignIn = async () => {
    const question = refusedQuestion;
    setSigningIn(true);
    try {
      const name = await TaskService.signInDevice();
      if (!name) {
        showToast("Could not sign in", "error");
        return;
      }
      if (question) {
        await submitQuestion(question);
      }
    } finally {
      setSigningIn(false);
    }
  };
  const handleInputChange = (value: string) => {
    setInput(value);
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

              {/*
                The door in the wall (#27). The boundary is meant to read as a
                door rather than a wall, and the delta between the refusal above
                and the answer that replaces it is the licensing and governance
                conversation this whole demo exists to open.

                The sign-in is mocked end to end. It is said out loud, here,
                beside the button — a stakeholder who discovers afterwards that
                an identity provider was implied has stopped believing the rest
                of the demonstration.
              */}
              <div className="home-input-policy-block-door">
                <Button
                  appearance="primary"
                  size="small"
                  data-testid="sign-in-to-continue"
                  icon={<PersonKey20Regular />}
                  disabled={signingIn || submitting}
                  onClick={handleSignIn}
                >
                  Sign in to continue
                </Button>
                <Caption1 className="home-input-policy-block-note">
                  Simulated sign-in — no identity provider is involved.
                </Caption1>
              </div>
            </div>
          )}

          {/*
            The Mocked unlock's answer, rendered where the refusal was, because
            landing it anywhere else would stop the before-and-after being a
            comparison.
          */}
          {personalAnswer && <PersonalAnswerCard answer={personalAnswer} />}


          <ChatInput
            ref={textareaRef} // forwarding
            value={input}
            placeholder="Ask about a store procedure, or report something that is not working."
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
                  {tasksToDisplay.map((task) => (
                    <PromptCard
                      key={task.id}
                      title={task.title}
                      icon={task.icon}
                      description={task.description}
                      onClick={() => {
                        void submitQuestion(task.fullDescription, task.lane);
                      }}
                      disabled={submitting}
                      badge={
                        isLane(task.lane) ? (
                          <LaneBadge lane={task.lane} variant="declared" />
                        ) : undefined
                      }
                    />
                  ))}
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
                <Caption1>No quick tasks are configured yet</Caption1>
              </div>
            )}
            {/*
              No assistant. The stock content packs are suppressed (issue #25),
              so an empty surface here means the store assistant's own pack has
              not reached this deployment — not that the associate forgot to
              choose something. The accelerator's copy asked them to "select a
              team", which is a routing decision presented as a precondition,
              and there is nothing left to select.
            */}
            {!selectedTeam && (
              <div
                className="home-input-unavailable"
                data-testid="assistant-unavailable"
                role="note"
                style={{
                  textAlign: "center",
                  padding: "32px 16px",
                  color: "var(--colorNeutralForeground3)",
                }}
              >
                <Caption1>
                  The {ASSISTANT_NAME} is not loaded on this deployment.
                </Caption1>
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
