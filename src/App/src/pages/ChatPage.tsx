import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Spinner, Text } from '@fluentui/react-components';

/* ── Services / API ──────────────────────────────────────────── */
import { APIService } from '../api/apiService';
import { PlanDataService } from '../store/PlanDataService';
import webSocketService from '../store/WebSocketService';

/* ── Models ──────────────────────────────────────────────────── */
import {
    AgentMessageData,
    AgentMessageType,
} from '../models';
import {
    PlanVerdictState,
    applyPlanVerdict,
    pendingVerdictFor,
} from '../models/reviewablePlan';

/* ── Redux ───────────────────────────────────────────────────── */
import { useAppDispatch, useAppSelector } from '../store/hooks';
import {
    selectPlanData,
    selectPlanLoading,
    selectErrorLoading,
    selectPlanApprovalRequest,
    selectProcessingApproval,
    selectShowApprovalButtons,
    selectShowProcessingPlanSpinner,
    selectShowCancellationDialog,
    selectCancellingPlan,
    selectReloadLeftList,
    selectShowTimeoutDialog,
    selectTimeoutMessage,
    setReloadLeftList,
    setProcessingApproval,
    setShowProcessingPlanSpinner,
    setShowCancellationDialog,
    setCancellingPlan,
    setErrorLoading,
    planApprovalAccepted,
    planSentBack,
} from '../store/slices/planSlice';
import {
    selectInput,
    selectSubmittingChatDisable,
    selectPendingClarificationRequestId,
    selectAgentMessages,
    setInput,
    setSubmittingChatDisableInput,
    clarificationAnswered,
    addAgentMessage,
} from '../store/slices/chatSlice';
import {
    selectStreamingMessages,
    selectStreamingMessageBuffer,
    selectShowBufferingText,
} from '../store/slices/streamingSlice';
import { selectWsConnected } from '../store/slices/appSlice';
import { selectSelectedTeam } from '../store/slices/teamSlice';
import {
    followOnTaskFor,
    rehearsedRepliesFor,
    ticketStatusReplyFor,
} from '../models/rehearsedReply';
import { CANNOT_CONTINUE, turnModeFor } from '../models/resume';
import { PersonalAnswer, parsePersonalAnswer } from '../models/personalAnswer';
import { PolicyBlock, parsePolicyBlock } from '../api/policyBlock';
import { forgetSignedInDevice } from '../models/signedInDevice';
import { StartingTask, TicketStatusReply } from '../models/Team';
import { selectRaisedTicket, ticketRaised } from '../store/slices/ticketSlice';
import { TaskService } from '../store/TaskService';

/* ── Custom Hooks ────────────────────────────────────────────── */
import { usePlanWebSocket } from '../hooks/usePlanWebSocket';
import { usePlanActions } from '../hooks/usePlanActions';
import { useAutoScroll } from '../hooks/useAutoScroll';
import { usePlanCancellationAlert } from '../hooks/usePlanCancellationAlert';
import { useTransparencySignals } from '../hooks/useTransparencySignals';
import {
    conversationStarted,
    refusalRecorded,
    requestStarted,
} from '../store/slices/transparencySlice';
import { usePresenterChord } from '../hooks/usePresenterChord';

/* ── Components ──────────────────────────────────────────────── */
import PlanChat from '../components/content/PlanChat';
import PlanPanelRight from '../components/content/PlanPanelRight';
import ChatPanelLeft from '../components/content/ChatPanelLeft';
import CoralShellColumn from '../commonComponents/components/Layout/CoralShellColumn';
import CoralShellRow from '../commonComponents/components/Layout/CoralShellRow';
import Content from '../commonComponents/components/Content/Content';
import ContentToolbar from '../commonComponents/components/Content/ContentToolbar';
import StoreIdentity from '../components/branding/StoreIdentity';
import { ASSISTANT_NAME } from '../models/storeSurface';
import LaneBadge from '../components/lane/LaneBadge';
import { isLane, LANE_LABELS } from '../models/lane';
import { LOADING_PLAN, SENDING } from '../models/progressNarration';
import {
    requestRouted,
    planOpened,
    requestSent,
    requestSettled,
    selectProgressNarration,
} from '../store/slices/progressSlice';
import { useInlineToaster } from '../components/toast/InlineToaster';
import Octo from '../commonComponents/imports/Octopus.png';
import LoadingMessage from '../commonComponents/components/LoadingMessage';
import PlanCancellationDialog from '../components/common/PlanCancellationDialog';
import TimeoutDialog from '../components/common/TimeoutDialog';
import '../styles/ChatPage.css';

// Singleton API service
const apiService = new APIService();

/* ================================================================
 *  ChatPage — refactored to use Redux + extracted hooks
 * ================================================================ */
const ChatPage: React.FC = () => {
    /*
      The route is `/chat/:id` and the id in it is a **Plan**'s (ADR-025): a
      Chat is a Session and can hold more than one Plan, so the surface says
      chat while the identity in the URL stays the precise one.
    */
    const { id: planId } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    /**
     * The Lane this plan was routed into, handed over by the surface that
     * submitted the request (issue #16, ADR-013). Router state is thrown away
     * by a reload, so it is only the first of two sources — see
     * `laneFromSessionState` below.
     */
    const laneFromRouterState = (location.state as { lane?: string } | null)?.lane;
    const dispatch = useAppDispatch();
    const { showToast, dismissToast } = useInlineToaster();
    const { messagesContainerRef, finalResultRef, scrollToBottom, scrollToFinalResult } = useAutoScroll();
    const { loadPlanData, resetPlanVariables } = usePlanActions();

    /* ── Redux Selectors (granular — Point 10) ──────────────── */
    const planData = useAppSelector(selectPlanData);
    const raisedTicket = useAppSelector(selectRaisedTicket);
    const loading = useAppSelector(selectPlanLoading);
    const errorLoading = useAppSelector(selectErrorLoading);
    const planApprovalRequest = useAppSelector(selectPlanApprovalRequest);
    const processingApproval = useAppSelector(selectProcessingApproval);
    const showApprovalButtons = useAppSelector(selectShowApprovalButtons);
    const showProcessingPlanSpinner = useAppSelector(selectShowProcessingPlanSpinner);
    const showCancellationDialog = useAppSelector(selectShowCancellationDialog);
    const cancellingPlan = useAppSelector(selectCancellingPlan);
    const reloadLeftList = useAppSelector(selectReloadLeftList);
    /* What the surface says while this request is in flight (#64, ADR-023). */
    const narration = useAppSelector(selectProgressNarration);
    const input = useAppSelector(selectInput);
    const submittingChatDisableInput = useAppSelector(selectSubmittingChatDisable);
    const clarificationRequestId = useAppSelector(selectPendingClarificationRequestId);
    const agentMessages = useAppSelector(selectAgentMessages);
    const streamingMessages = useAppSelector(selectStreamingMessages);
    const streamingMessageBuffer = useAppSelector(selectStreamingMessageBuffer);
    const showBufferingText = useAppSelector(selectShowBufferingText);
    const wsConnected = useAppSelector(selectWsConnected);
    const selectedTeam = useAppSelector(selectSelectedTeam);
    const showTimeoutDialog = useAppSelector(selectShowTimeoutDialog);
    const timeoutMessage = useAppSelector(selectTimeoutMessage);

    /* ── Cancellation alert hook ────────────────────────────── */
    const [pendingNavigation, setPendingNavigation] = React.useState<(() => void) | null>(null);
    const [processingElapsedSeconds, setProcessingElapsedSeconds] = React.useState<number>(0);
    /*
      **One** in-flight lock for both continuation paths (#77). The follow-on
      card acquired one because a second tap lands before React has re-rendered
      it disabled; **Resume** needs the same guard, and two locks would let the
      card and the box submit at once — two turns into one session, of which
      `process_request` cancels the first. It is the seam's, not either
      caller's, because a lock a caller owns is a lock the next caller forgets.
    */
    const [continuationSubmitting, setContinuationSubmitting] = React.useState(false);
    const continuationSubmissionRef = React.useRef(false);
    /*
      What the last continuation turn produced when it produced no plan. Both
      are ordinary outcomes of a question typed into a chat — the **Identity
      boundary** gate refusing a personal question, and the **Mocked unlock**
      answering one — and neither is a failed request. Held here, cleared when
      the next turn starts and when another chat is opened.
    */
    const [continuationAnswer, setContinuationAnswer] = React.useState<PersonalAnswer | null>(null);
    const [continuationRefusal, setContinuationRefusal] = React.useState<PolicyBlock | null>(null);
    /*
      Whether this chat has a turn working *right now* (#77). It matters
      because a **Resume** turn does not queue: `process_request` cancels
      whatever orchestration that user already had running before scheduling
      the next, so a turn typed over a working one takes its place and the
      answer being waited for never arrives.

      The spinner alone, and deliberately not `showApprovalButtons`. That flag
      is set from the *stored* `overall_status` on every load, so counting it
      would close the box on every reopened chat that never finished — which is
      exactly the chat #74 said is most worth resuming. The spinner is the only
      signal here that reports a turn *this* browser is watching work, which is
      all ADR-023 lets the surface claim.
    */
    const turnInFlight = showProcessingPlanSpinner;

    /* ── The Rehearsed replies for this plan (issue #26) ─────── */
    /*
      Resolved from the plan's own initial goal rather than carried in router
      state, for the same reason the lane taken is read back from session
      state: a reloaded or bookmarked plan has no router state, and a presenter
      who reloads mid-beat is exactly the presenter who needs the tap. A goal
      that matches no Quick Task prompt — which is what an edited prompt is —
      resolves to none, and the surface says nothing.
    */
    const planTeam = planData?.team ?? selectedTeam;
    const rehearsedReplies = React.useMemo(
        () => rehearsedRepliesFor(planTeam, planData?.plan?.initial_goal),
        [planTeam, planData?.plan?.initial_goal],
    );
    const followOnTask = React.useMemo(
        () => followOnTaskFor(planTeam, planData?.plan?.initial_goal),
        [planTeam, planData?.plan?.initial_goal],
    );
    const ticketStatusReply = React.useMemo(
        () => ticketStatusReplyFor(planTeam, planData?.plan?.initial_goal),
        [planTeam, planData?.plan?.initial_goal],
    );

    /* ── The lane taken, recovered after a reload (issue #20) ─── */
    const [laneFromSessionState, setLaneFromSessionState] = React.useState<string | undefined>(undefined);
    const planSessionId = planData?.plan?.session_id;

    useEffect(() => {
        /*
          A reloaded or bookmarked plan has no router state, so the lane taken
          is read back from server-side session state — the browser cannot
          re-derive it, and re-deriving it here would be a second lane router
          with its own opinion. A failed read leaves the badge unrendered
          rather than guessing a lane.
        */
        if (laneFromRouterState || !planSessionId) return;
        let cancelled = false;
        apiService
            .getSessionState(planSessionId)
            .then((state) => {
                if (!cancelled && typeof state?.lane === 'string') {
                    setLaneFromSessionState(state.lane);
                }
            })
            .catch(() => undefined);
        return () => {
            cancelled = true;
        };
    }, [laneFromRouterState, planSessionId]);

    useEffect(() => {
        /*
          A ticket is a persisted property of this **Chat**, not of the browser
          that watched its approval. Restore only a submitted ticket, through
          the session-scoped read, so reopening its Chat retains the authored
          Fast inquiry while a fresh Chat still has none.
        */
        if (!planSessionId) return;
        let cancelled = false;
        apiService
            .getChatTicket(planSessionId)
            .then((ticket) => {
                if (!cancelled) dispatch(ticketRaised(ticket));
            })
            .catch(() => undefined);
        return () => {
            cancelled = true;
        };
    }, [dispatch, planSessionId]);

    const laneTaken = laneFromRouterState ?? laneFromSessionState;

    const { isPlanActive } = usePlanCancellationAlert({ planData });

    /* ── Memoized formatErrorMessage ────────────────────────── */
    const formatErrorMessage = useCallback((content: string): string => {
        const lines = content.split('\n');
        return lines
            .map((line, idx) => {
                if (idx === 0) return `\u26A0\uFE0F ${line}`;
                if (line.trim() === '') return '';
                return `&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;${line}`;
            })
            .join('\n');
    }, []);

    /* ── WebSocket subscriptions (extracted hook) ───────────── */
    usePlanWebSocket({ planId, scrollToBottom, scrollToFinalResult, formatErrorMessage, showToast });

    // The three transparency signals (#23) and the hidden chord that fires the
    // last of them (#24). Both live here rather than in `usePlanWebSocket`
    // because they are one feature of their own — the audience watching the
    // architecture work — and neither touches the plan's own flow.
    useTransparencySignals();
    usePresenterChord();

    /* ── Navigation with cancellation check ─────────────────── */
    const handleNavigationWithAlert = useCallback(
        (navigationFn: () => void) => {
            if (!isPlanActive()) {
                navigationFn();
                return;
            }
            setPendingNavigation(() => navigationFn);
            dispatch(setShowCancellationDialog(true));
        },
        [isPlanActive, dispatch],
    );

    const handleConfirmCancellation = useCallback(async () => {
        // Leaving a Chat is navigation, not a **Verdict** (ADR-031 decision 2):
        // no `/v4/plan_approval` call is made from here. The run behind an
        // abandoned turn is ended by the Chat's own cancellation, which is #121.
        dispatch(setCancellingPlan(true));
        try {
            pendingNavigation?.();
            webSocketService.disconnect();
        } finally {
            dispatch(setCancellingPlan(false));
            dispatch(setShowCancellationDialog(false));
            setPendingNavigation(null);
        }
    }, [pendingNavigation, dispatch]);

    const handleCancelDialog = useCallback(() => {
        dispatch(setShowCancellationDialog(false));
        setPendingNavigation(null);
    }, [dispatch]);

    const handleTimeoutGoHome = useCallback(() => {
        navigate('/');
    }, [navigate]);

    /* ── The Verdict on a Reviewable plan ───────────────────── */
    /**
     * Approve, or send it back saying what to change. There is no third
     * verdict (#108, ADR-028): leaving the conversation is navigation, and the
     * path that destroyed the plan is gone.
     *
     * The reducer beside this is what makes approval terminal — it returns the
     * state it was given when there is nothing to say, and that identity is
     * what tells the surface not to send.
     */
    const [verdict, setVerdict] = useState<PlanVerdictState>(() =>
        pendingVerdictFor(planApprovalRequest ?? {}),
    );

    useEffect(() => {
        setVerdict(pendingVerdictFor(planApprovalRequest ?? {}));
    }, [planApprovalRequest?.id, planApprovalRequest?.revision]);

    const handleApprovePlan = useCallback(async () => {
        if (!planApprovalRequest) return;
        const next = applyPlanVerdict(verdict, { kind: 'approve' });
        if (next === verdict) return;
        setVerdict(next);
        dispatch(setProcessingApproval(true));
        const id = showToast('Submitting Approval', 'progress');
        try {
            await apiService.approvePlan({
                m_plan_id: planApprovalRequest.id,
                plan_id: planData?.plan?.id ?? '',
                approved: true,
                feedback: 'Plan approved by user',
            });
            dismissToast(id);
            /* P0: single compound action replaces 3 separate dispatches */
            dispatch(planApprovalAccepted());
        } catch {
            dismissToast(id);
            showToast('Failed to submit approval', 'error');
        } finally {
            dispatch(setProcessingApproval(false));
        }
    }, [planApprovalRequest, planData, verdict, showToast, dismissToast, dispatch]);

    const handleRejectPlan = useCallback(
        async (feedback: string) => {
            if (!planApprovalRequest) return;
            const next = applyPlanVerdict(verdict, { kind: 'revise', feedback });
            if (next === verdict) return;
            setVerdict(next);
            dispatch(setProcessingApproval(true));
            const id = showToast('Sending the plan back', 'progress');
            try {
                await apiService.approvePlan({
                    m_plan_id: planApprovalRequest.id,
                    plan_id: planData?.plan?.id ?? '',
                    approved: false,
                    feedback: feedback.trim(),
                });
                dismissToast(id);
                /* The revised plan arrives in this same conversation. */
                dispatch(planSentBack());
            } catch {
                dismissToast(id);
                showToast('Failed to send the plan back', 'error');
                dispatch(planSentBack());
            }
        },
        [planApprovalRequest, planData, verdict, showToast, dismissToast, dispatch],
    );

    /**
     * One new turn in **this Chat's Session** (ADR-027).
     *
     * The seam both continuation paths go through: the authored **Follow-on
     * task** card, which is the rehearsed one, and **Resume**, which is the
     * recovery one. It is one function rather than two because everything
     * around the request is what a continuation must not forget — the previous
     * answer's provenance going dark, the **Progress narration**'s three
     * beats, the socket connected before the navigation (ADR-021), and the
     * navigation itself. A second caller writing its own copy is a second
     * caller quietly dropping one of them.
     *
     * The `session_id` is read from the plan on screen, so the turn joins the
     * conversation the associate is looking at rather than starting one beside
     * it. Fails closed: a chat this build cannot name a session for is not
     * continued, because minting one here starts a *new* conversation under an
     * old heading and loses exactly the persisted records resume exists for.
     */
    const submitTurnIntoSession = useCallback(
        async (
            prompt: string,
            options: { lane?: string; startingTaskId?: string } = {},
        ) => {
            const sessionId = planData?.plan?.session_id;
            if (!sessionId) {
                showToast(CANNOT_CONTINUE, 'error');
                return;
            }
            if (continuationSubmissionRef.current) return;
            continuationSubmissionRef.current = true;
            setContinuationSubmitting(true);
            dispatch(setSubmittingChatDisableInput(true));
            // The previous turn's plan-less outcome is about the previous
            // turn. Left up, a refusal would sit beside the answer that
            // replaced it and read as though it were still in force.
            setContinuationAnswer(null);
            setContinuationRefusal(null);

            // A new turn produces a new answer, so the previous answer's
            // provenance goes dark (#24). A Foundry-only turn emits no
            // replacement `source_used`, and a panel left up would attribute
            // it to Copilot Studio.
            dispatch(requestStarted());
            // No plan id yet — the turn creates one, and `requestRouted` records
            // it off the response before the navigation, exactly as `HomeInput` does.
            dispatch(requestSent());
            const id = showToast(SENDING, 'progress');
            try {
                const response = await TaskService.createPlan(
                    prompt,
                    planTeam?.team_id,
                    options.lane,
                    sessionId,
                    options.startingTaskId,
                );
                /*
                  The **Mocked unlock**'s answer (#27): a *successful* request
                  with no plan, because it cost no agent and no tokens.
                  Checked before the plan id, since a null plan here is not a
                  failure to create one — and the turn that reaches this from
                  inside a chat is new with resume, which is what made the old
                  `throw` reachable.
                */
                const answer = parsePersonalAnswer(response);
                if (answer) {
                    dispatch(requestSettled());
                    dismissToast(id);
                    setContinuationAnswer(answer);
                    return;
                }
                if (!response.plan_id) {
                    throw new Error('The turn did not create a plan');
                }

                dispatch(
                    requestRouted({
                        lane: isLane(response.lane) ? response.lane : null,
                        planId: response.plan_id,
                    }),
                );
                webSocketService.connect(response.plan_id).catch(() => {
                    // The chat page retries, and the surface degrades to polling.
                });
                dismissToast(id);
                showToast(
                    isLane(response.lane)
                        ? `Plan created — ${LANE_LABELS[response.lane]}`
                        : 'Plan created!',
                    'success',
                );
                navigate(`/chat/${response.plan_id}`, { state: { lane: response.lane } });
            } catch (error: unknown) {
                dispatch(requestSettled());
                dismissToast(id);
                /*
                  A **Policy block** is the **Identity boundary** gate working,
                  so it gets the surface `HomeInput` gives it rather than the
                  error toast (ADR-014). Rendering a governed refusal as a
                  failed request makes the demo's centrepiece look like a bug —
                  and resume is what made a personal question typable from
                  inside a chat at all.
                */
                const refusal = parsePolicyBlock(error);
                if (refusal) {
                    setContinuationRefusal(refusal);
                    // A refusal *is* the gate stating that nobody is signed
                    // in. A header that went on naming an associate the gate
                    // has just declined to answer for would be the surface
                    // saying something that is not so.
                    forgetSignedInDevice();
                    // And it goes on the **Token meter** (#24, R7): a refused
                    // request adds nothing, and the row showing a measured
                    // zero beside rows that cost something is what makes
                    // "nothing" legible. The meter is one claim about this
                    // conversation, whichever surface the question was typed
                    // into.
                    dispatch(refusalRecorded(refusal));
                    return;
                }
                showToast('Unable to create plan. Please try again.', 'error');
            } finally {
                continuationSubmissionRef.current = false;
                setContinuationSubmitting(false);
                dispatch(setSubmittingChatDisableInput(false));
            }
        },
        [
            planData,
            planTeam,
            dispatch,
            showToast,
            dismissToast,
            navigate,
        ],
    );

    const handleFollowOnTask = useCallback(
        (task: StartingTask) =>
            submitTurnIntoSession(task.prompt, {
                lane: task.lane,
                startingTaskId: task.id,
            }),
        [submitTurnIntoSession],
    );

    const handleTicketStatusReply = useCallback(
        (reply: TicketStatusReply) =>
            submitTurnIntoSession(reply.prompt, { lane: reply.lane }),
        [submitTurnIntoSession],
    );

    /* ── Chat submission ────────────────────────────────────── */
    /*
      The question on screen *now*, read after the answer's POST returns. The
      callback closes over the question it was answering, which is the right
      identifier to answer against and the wrong one to decide what the surface
      should do once the answer lands.
    */
    const pendingClarificationIdRef = React.useRef<string | null>(clarificationRequestId);
    useEffect(() => {
        pendingClarificationIdRef.current = clarificationRequestId;
    }, [clarificationRequestId]);

    const handleOnchatSubmit = useCallback(
        async (chatInput: string) => {
            /*
              One box, two acts, and which one this is belongs to `resume.ts`
              rather than to this callback — `PlanChatBody` decides whether the
              box may be used at all from the same rule, and a box open over a
              submit path that disagreed with it is exactly the shape of #68.

              A pending **Clarification** wins: a turn typed while the
              orchestration is waiting on an answer *is* that answer, and
              starting a new plan with it strands the turn that asked.
            */
            const answering = clarificationRequestId?.trim() ? clarificationRequestId : null;
            const mode = turnModeFor(answering, planData?.plan?.session_id);
            if (mode === 'none') return;
            if (!chatInput.trim()) {
                if (mode === 'clarification') {
                    showToast('Please enter a clarification', 'error');
                }
                return;
            }

            if (mode === 'resume') {
                /*
                  **Resume** (#77, ADR-027): a new turn in this Chat's Session,
                  carrying that session rather than minting a new one. What
                  travels is the typed words alone — the transcript above them
                  is display-only and is never replayed into an agent's
                  context, because the **Workflow cache** is process-local and
                  keyed by user, so there is no per-Chat agent thread to
                  restore and claiming one would be a continuity this cannot
                  keep. What genuinely survives is what was persisted against
                  the session: the **Attempted steps**, the identity, the
                  **Lane** and the **Simulated ticket**.

                  No lane is declared, because typed input is free-typed input
                  and belongs to the **Lane keyword fallback**; no **Quick
                  Task** id, because none was tapped.
                */
                /*
                  The box's own refusal, restated here because the box is not
                  the only way in — `RehearsedReplies` calls this directly — and
                  a guard stated only at the surface is a guard the second
                  caller does not have. Silent: what is refused is already
                  said, in the box, by `TURN_STILL_WORKING`.
                */
                if (turnInFlight) return;
                dispatch(setInput(''));
                await submitTurnIntoSession(chatInput);
                return;
            }

            // The mode switch's last arm, written as a guard because the rule
            // lives in `resume.ts` and TypeScript cannot read it: reaching here
            // with no question to answer is the empty `request_id` of #68.
            if (mode !== 'clarification' || !answering) return;

            dispatch(setInput(''));
            if (!planData?.plan) return;
            // The previous turn's refusal is about the previous turn. Left up
            // beside the answer that replaced it, it reads as though it were
            // still in force.
            setContinuationRefusal(null);
            // A clarification produces a new answer, so the previous answer's
            // provenance goes dark (#24). A Foundry-only follow-up emits no
            // replacement `source_used`, and a panel left up would attribute it
            // to Copilot Studio.
            dispatch(requestStarted());
            dispatch(setSubmittingChatDisableInput(true));
            const id = showToast('Submitting clarification', 'progress');
            try {
                await PlanDataService.submitClarification({
                    request_id: answering,
                    answer: chatInput,
                    plan_id: planData.plan.id,
                    m_plan_id: planApprovalRequest?.id || '',
                });
                dispatch(setInput(''));
                // The question is settled, so nothing is pending against it. A
                // clarification left in the store outlives its answer, and the
                // surface goes on offering to answer it — named, so a slower
                // answer cannot retire a question asked after it.
                dispatch(clarificationAnswered(answering));
                dismissToast(id);
                showToast('Clarification submitted successfully', 'success');
                const agentMessageData: AgentMessageData = {
                    agent: 'human',
                    agent_type: AgentMessageType.HUMAN_AGENT,
                    timestamp: Date.now(),
                    steps: [],
                    next_steps: [],
                    content: chatInput,
                    raw_data: chatInput,
                };
                dispatch(addAgentMessage(agentMessageData));
                /*
                  The turn is in flight again — unless the next question has
                  already arrived, in which case it is waiting on the associate
                  and this answer is the slow one. Re-locking the box then
                  closes it over a question the backend is waiting on (#68).
                */
                if (pendingClarificationIdRef.current === answering) {
                    dispatch(setSubmittingChatDisableInput(true));
                    dispatch(setShowProcessingPlanSpinner(true));
                    // The associate answered, so the turn is in flight again — the
                    // pause for a **Clarification** settled it (#64, ADR-023).
                    dispatch(requestSent(planData.plan.id));
                }
                scrollToBottom();
            } catch (error: unknown) {
                dispatch(requestSettled());
                dispatch(setShowProcessingPlanSpinner(false));
                dismissToast(id);
                dispatch(setSubmittingChatDisableInput(false));
                /*
                  A **Policy block** here is the **Identity boundary** gate
                  working on the clarification seam (ADR-034, #115), so it gets
                  the surface a refusal already has rather than the error
                  toast — a governed refusal reported as a failed submission
                  reads as a bug, which is the confusion ADR-014 exists to
                  remove.

                  Nothing is settled: `clarificationAnswered` is only on the
                  success path, so the question stays pending and the box stays
                  open — the refusal is of *those words*, not of the turn, and
                  the associate answers again.
                */
                const refusal = parsePolicyBlock(error);
                if (refusal) {
                    setContinuationRefusal(refusal);
                    // The refusal *is* the gate stating that nobody is signed
                    // in, and the meter carries the measured zero — both are
                    // claims about this conversation rather than about the
                    // surface the words were typed into.
                    forgetSignedInDevice();
                    dispatch(refusalRecorded(refusal));
                    scrollToBottom();
                    return;
                }
                showToast('Failed to submit clarification', 'error');
            }
        },
        [
            planData,
            clarificationRequestId,
            planApprovalRequest,
            showToast,
            dismissToast,
            dispatch,
            scrollToBottom,
            submitTurnIntoSession,
            turnInFlight,
        ],
    );

    /* ── Left-panel handlers ────────────────────────────────── */
    const handleNewChatButton = useCallback(() => {
        handleNavigationWithAlert(() => navigate('/', { state: { focusInput: true } }));
    }, [navigate, handleNavigationWithAlert]);

    const resetReload = useCallback(() => {
        dispatch(setReloadLeftList(false));
    }, [dispatch]);

    /* ── Plan execution elapsed timer ───────────────────────── */
    useEffect(() => {
        if (!showProcessingPlanSpinner) {
            setProcessingElapsedSeconds(0);
            return;
        }

        setProcessingElapsedSeconds(0);
        const interval = setInterval(() => {
            setProcessingElapsedSeconds((currentSeconds: number) => currentSeconds + 1);
        }, 1000);

        return () => clearInterval(interval);
    }, [showProcessingPlanSpinner]);

    /* ── Initial plan load ──────────────────────────────────── */
    useEffect(() => {
        // A different plan is a different conversation, so the provenance and
        // the alerts pushed into the previous one go (#24). Dispatched here
        // rather than only inside `resetPlanVariables`, which runs on the
        // no-planId error path alone and so would leave a stale Grounding
        // panel and old alerts on screen for every ordinary navigation. It is
        // safe at this point: any signal for *this* plan arrives later, over a
        // socket that has not connected yet.
        dispatch(conversationStarted());
        /*
          The narration follows the request that made this navigation and
          nothing else (#64, ADR-023). Opening an earlier task from the left
          panel while a request is in flight would otherwise leave "Shift Tasks
          Agent is responding..." over a conversation that finished last week.
        */
        dispatch(planOpened(planId));
        // A refusal and a personal answer are about the turn that produced
        // them, which was typed into the chat being left.
        setContinuationAnswer(null);
        setContinuationRefusal(null);

        if (!planId) {
            resetPlanVariables();
            dispatch(setErrorLoading(true));
            return;
        }
        loadPlanData(planId, false);
    }, [planId, loadPlanData, resetPlanVariables, dispatch]);

    /* ── Render: Error state ────────────────────────────────── */
    if (errorLoading) {
        return (
            <CoralShellColumn>
                <CoralShellRow>
                    <ChatPanelLeft
                        reloadChats={reloadLeftList}
                        onNewChatButton={handleNewChatButton}
                        restReload={resetReload}
                        onNavigationWithAlert={handleNavigationWithAlert}
                    />
                    <Content>
                        <div className="plan-error-message">
                            <Text size={500}>An error occurred while loading the plan</Text>
                        </div>
                    </Content>
                </CoralShellRow>
            </CoralShellColumn>
        );
    }

    /* ── Render: Normal state ───────────────────────────────── */
    return (
        <CoralShellColumn>
            <CoralShellRow>
                <ChatPanelLeft
                    reloadChats={reloadLeftList}
                    onNewChatButton={handleNewChatButton}
                    restReload={resetReload}
                    onNavigationWithAlert={handleNavigationWithAlert}
                />

                <Content>
                    {loading || !planData ? (
                        <>
                            <div className="plan-loading-spinner">
                                <Spinner size="medium" />
                                <Text>{LOADING_PLAN}</Text>
                            </div>
                            {/*
                              What a signal has reported about the request
                              itself, which is a different claim from the plan
                              record being fetched — and nothing at all when
                              nothing has reported anything, as on a reload
                              (#64, ADR-023).
                            */}
                            {narration && <LoadingMessage loadingMessage={narration} iconSrc={Octo} />}
                        </>
                    ) : (
                        <>
                            <ContentToolbar panelTitle={ASSISTANT_NAME}>
                                <StoreIdentity />
                                {/*
                                  The Lane this plan was routed into (ADR-013).
                                  It is the lane *taken*, which is why it sits
                                  beside the plan rather than beside the Quick
                                  Task that declared one — and why a reload
                                  reads it back from server-side session state
                                  rather than re-deriving it here.
                                */}
                                {isLane(laneTaken) && (
                                    <LaneBadge lane={laneTaken} variant="taken" />
                                )}
                            </ContentToolbar>
                            <PlanChat
                                planData={planData}
                                OnChatSubmit={handleOnchatSubmit}
                                loading={loading}
                                setInput={(val: string) => dispatch(setInput(val))}
                                submittingChatDisableInput={submittingChatDisableInput}
                                input={input}
                                streamingMessages={streamingMessages}
                                wsConnected={wsConnected}
                                planApprovalRequest={planApprovalRequest}
                                messagesContainerRef={messagesContainerRef}
                                finalResultRef={finalResultRef}
                                streamingMessageBuffer={streamingMessageBuffer}
                                showBufferingText={showBufferingText}
                                agentMessages={agentMessages}
                                showProcessingPlanSpinner={showProcessingPlanSpinner}
                                processingElapsedSeconds={processingElapsedSeconds}
                                showApprovalButtons={showApprovalButtons}
                                processingApproval={processingApproval}
                                handleApprovePlan={handleApprovePlan}
                                handleRejectPlan={handleRejectPlan}
                                rehearsedReplies={rehearsedReplies}
                                followOnTask={followOnTask}
                                onFollowOnTask={handleFollowOnTask}
                                ticketStatusReply={ticketStatusReply}
                                onTicketStatusReply={handleTicketStatusReply}
                                hasRaisedTicket={raisedTicket !== null}
                                continuationSubmitting={continuationSubmitting}
                                turnInFlight={turnInFlight}
                                personalAnswer={continuationAnswer}
                                policyRefusal={continuationRefusal}
                            />
                        </>
                    )}
                </Content>

                <PlanPanelRight
                    planData={planData}
                    loading={loading}
                    planApprovalRequest={planApprovalRequest}
                />
            </CoralShellRow>

            <PlanCancellationDialog
                isOpen={showCancellationDialog}
                onConfirm={handleConfirmCancellation}
                onCancel={handleCancelDialog}
                loading={cancellingPlan}
            />

            <TimeoutDialog
                isOpen={showTimeoutDialog}
                message={timeoutMessage}
                onGoHome={handleTimeoutGoHome}
            />
        </CoralShellColumn>
    );
};

const MemoizedChatPage = React.memo(ChatPage);
MemoizedChatPage.displayName = 'ChatPage';
export default MemoizedChatPage;
