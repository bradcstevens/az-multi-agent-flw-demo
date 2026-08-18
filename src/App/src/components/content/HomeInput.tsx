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
import PolicyBlockNotice from "../identity/PolicyBlockNotice";
import { isLane, LANE_LABELS } from "../../models/lane";
import { SENDING } from "../../models/progressNarration";
import {
  requestRouted,
  requestSent,
  requestSettled,
} from "../../store/slices/progressSlice";
import LaneBadge from "../lane/LaneBadge";
import { NewChatService } from "../../store/NewChatService";
import webSocketService from "@/store/WebSocketService";
import { useAppDispatch } from "@/store/hooks";
import { refusalRecorded, requestStarted, startConversation } from "@/store/slices/transparencySlice";
import { ASSISTANT_NAME } from "../../models/storeSurface";
import { SECTION_HEADING } from "../../models/headingOutline";

import ChatInput from "@/commonComponents/modules/ChatInput";
import InlineToaster, { useInlineToaster } from "../toast/InlineToaster";
import PromptCard from "@/commonComponents/components/PromptCard";
import SendControl, { SEND_QUESTION } from "./SendControl";
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
  startingTaskId?: string;
  ticketOnApproval?: boolean;
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
    const cleanup = NewChatService.addResetListener(resetTextarea);
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
  const submitQuestion = async (
    question: string,
    declaredLane?: string,
    startingTaskId?: string,
    ticketOnApproval?: boolean,
  ) => {
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
    // The **Progress narration**'s first phase, and its only authored words
    // (#64, ADR-023): the POST is in flight, and that is all anything knows.
    // The toast reads them out of the same module the chat page will, so the
    // two surfaces cannot disagree across the navigation between them.
    dispatch(requestSent());
    let id = showToast(SENDING, "progress");

    try {
      const response = ticketOnApproval
        ? await TaskService.createPlan(
            question,
            selectedTeam?.team_id,
            declaredLane,
            undefined,
            startingTaskId,
          )
        : await TaskService.createPlan(
            question,
            selectedTeam?.team_id,
            declaredLane,
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
        // Answered here, with no plan and no chat page. Nothing downstream
        // could ever stop a narration left running.
        dispatch(requestSettled());
        dismissToast(id);
        setPersonalAnswer(answer);
        setSubmitting(false);
        return;
      }

      // The lane taken, as the lane router reported it — a feature of the
      // assistant, not an implementation detail (ADR-013). It is not always
      // the lane declared: free-typed input declares nothing, and an
      // unreadable declaration falls open to the Deliberate lane. It is
      // carried to the chat page, where the answer (or the approval step)
      // arrives, so it outlives this toast.
      if (response.plan_id && response.plan_id !== null) {
        // The lane the router decided, read from the same `response.lane` the
        // `LaneBadge` reads. Recorded before the navigation, because the phase
        // outliving that navigation is the whole reason it lives in a slice —
        // and dispatched even when the response named no lane, because the plan
        // it names is what carries the narration across that navigation.
        dispatch(
          requestRouted({
            lane: isLane(response.lane) ? response.lane : null,
            planId: response.plan_id,
          }),
        );
        dispatch(startConversation(response.session_id));

        // The socket opens here, on the response, and not on the chat page
        // (ADR-021). `process_request` schedules the orchestration *before* it
        // returns this response, so every frame emitted between now and the
        // browser's connect is pushed at a socket that does not exist and
        // dropped in silence — including the first agent's
        // `agent_message_streaming` header, the only signal that names which
        // specialist took the question. Waiting for `navigate`, a mount and a
        // second GET put all three inside that window (#63).
        //
        // This looks misplaced in a submit handler and is not: the chat page
        // keeps its own connect for a reload of /chat/:id, which has no
        // response to hang off. Read ADR-021 before moving it back.
        webSocketService.connect(response.plan_id).catch(() => {
          // The chat page retries, and the surface degrades to polling. A
          // failure here must not take the navigation with it.
        });

        showToast(
          isLane(response.lane)
            ? `Plan created — ${LANE_LABELS[response.lane]}`
            : "Plan created!",
          "success"
        );
        dismissToast(id);

        navigate(`/chat/${response.plan_id}`, {
          state: { lane: response.lane },
        });
      } else {
        dispatch(requestSettled());
        showToast("Failed to create plan", "error");
        dismissToast(id);
      }
    } catch (error: any) {
      dispatch(requestSettled());
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

  // Convert team starting_tasks to ExtendedQuickTask format.
  // Context dependence, not graph membership, decides whether a Quick Task can
  // begin cold from the home grid (issue #132, ADR-033).
  const tasksToDisplay: ExtendedQuickTask[] =
    selectedTeam && selectedTeam.starting_tasks
      ? selectedTeam.starting_tasks
          .filter((task) => typeof task === "string" || task.context_dependent !== true)
          .map((task, index) => {
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
              startingTaskId: startingTask.id,
              ticketOnApproval: startingTask.ticket_on_approval,
            };
          }
          })
      : [];

  return (
    <div className="home-input-container">
      <div className="home-input-content">
        <div className="home-input-center-content">
          <div className="home-input-title-wrapper">
            {/*
              The question input region's heading (#57). One level below the
              conversation header's, which names the assistant.
            */}
            <Title2 as={SECTION_HEADING} className="home-input-title">
              How can I help?
            </Title2>
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
            <PolicyBlockNotice block={policyBlock}>
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
              </div>
            </PolicyBlockNotice>
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
            <SendControl
              label={SEND_QUESTION}
              onSend={handleSubmit}
              unavailable={submitting}
            />
          </ChatInput>

          <InlineToaster />

          <div className="home-input-quick-tasks-section">
            {tasksToDisplay.length > 0 && (
              <>
                <div className="home-input-quick-tasks-header">
                  <Body1Strong
                    as={SECTION_HEADING}
                    className="home-input-quick-tasks-title"
                  >
                    Quick tasks
                  </Body1Strong>
                </div>

                <div className="home-input-quick-tasks">
                  {tasksToDisplay.map((task) => (
                    <PromptCard
                      key={task.id}
                      title={task.title}
                      icon={task.icon}
                      description={task.description}
                      onClick={() => {
                        void submitQuestion(
                          task.fullDescription,
                          task.lane,
                          task.startingTaskId,
                          task.ticketOnApproval,
                        );
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
                  color: "var(--colorNeutralForeground3)",
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
