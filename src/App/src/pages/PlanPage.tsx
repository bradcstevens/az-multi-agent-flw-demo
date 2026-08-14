import React, { useCallback, useEffect} from 'react';
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
    selectLoadingMessage,
    selectReloadLeftList,
    selectWaitingForPlan,
    selectShowTimeoutDialog,
    selectTimeoutMessage,
    setReloadLeftList,
    setProcessingApproval,
    setShowProcessingPlanSpinner,
    setShowCancellationDialog,
    setCancellingPlan,
    setLoadingMessage,
    setErrorLoading,
    planApprovalAccepted,
    planApprovalRejected,
} from '../store/slices/planSlice';
import {
    selectInput,
    selectSubmittingChatDisable,
    selectClarificationMessage,
    selectAgentMessages,
    setInput,
    setSubmittingChatDisableInput,
    addAgentMessage,
} from '../store/slices/chatSlice';
import {
    selectStreamingMessages,
    selectStreamingMessageBuffer,
    selectShowBufferingText,
} from '../store/slices/streamingSlice';
import { selectWsConnected } from '../store/slices/appSlice';
import { selectSelectedTeam } from '../store/slices/teamSlice';
import { followOnTaskFor, rehearsedRepliesFor } from '../models/rehearsedReply';
import { StartingTask } from '../models/Team';
import { TaskService } from '../store/TaskService';

/* ── Custom Hooks ────────────────────────────────────────────── */
import { usePlanWebSocket } from '../hooks/usePlanWebSocket';
import { usePlanActions } from '../hooks/usePlanActions';
import { useAutoScroll } from '../hooks/useAutoScroll';
import { usePlanCancellationAlert } from '../hooks/usePlanCancellationAlert';
import { useTransparencySignals } from '../hooks/useTransparencySignals';
import { conversationStarted, requestStarted } from '../store/slices/transparencySlice';
import { usePresenterChord } from '../hooks/usePresenterChord';

/* ── Components ──────────────────────────────────────────────── */
import PlanChat from '../components/content/PlanChat';
import PlanPanelRight from '../components/content/PlanPanelRight';
import PlanPanelLeft from '../components/content/PlanPanelLeft';
import CoralShellColumn from '../commonComponents/components/Layout/CoralShellColumn';
import CoralShellRow from '../commonComponents/components/Layout/CoralShellRow';
import Content from '../commonComponents/components/Content/Content';
import ContentToolbar from '../commonComponents/components/Content/ContentToolbar';
import StoreIdentity from '../components/branding/StoreIdentity';
import { ASSISTANT_NAME } from '../models/storeSurface';
import LaneBadge from '../components/lane/LaneBadge';
import { isLane, LANE_LABELS } from '../models/lane';
import { useInlineToaster } from '../components/toast/InlineToaster';
import Octo from '../commonComponents/imports/Octopus.png';
import LoadingMessage, { loadingMessages } from '../commonComponents/components/LoadingMessage';
import PlanCancellationDialog from '../components/common/PlanCancellationDialog';
import TimeoutDialog from '../components/common/TimeoutDialog';
import '../styles/PlanPage.css';

// Singleton API service
const apiService = new APIService();

const getPlanProcessingStatusMessage = (elapsedSeconds: number): string => {
    if (elapsedSeconds < 8) {
        return 'Processing your plan and coordinating with AI agents...';
    }

    if (elapsedSeconds < 20) {
        return 'Assigning tasks to specialized agents...';
    }

    if (elapsedSeconds < 35) {
        return 'Agents are analyzing and researching...';
    }

    if (elapsedSeconds < 50) {
        return 'Compiling results from agents...';
    }

    if (elapsedSeconds < 90) {
        return 'Finalizing responses...';
    }

    return 'Still processing, please wait...';
};

/* ================================================================
 *  PlanPage — refactored to use Redux + extracted hooks
 * ================================================================ */
const PlanPage: React.FC = () => {
    const { planId } = useParams<{ planId: string }>();
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
    const loading = useAppSelector(selectPlanLoading);
    const errorLoading = useAppSelector(selectErrorLoading);
    const planApprovalRequest = useAppSelector(selectPlanApprovalRequest);
    const processingApproval = useAppSelector(selectProcessingApproval);
    const showApprovalButtons = useAppSelector(selectShowApprovalButtons);
    const showProcessingPlanSpinner = useAppSelector(selectShowProcessingPlanSpinner);
    const showCancellationDialog = useAppSelector(selectShowCancellationDialog);
    const cancellingPlan = useAppSelector(selectCancellingPlan);
    const loadingMessage = useAppSelector(selectLoadingMessage);
    const reloadLeftList = useAppSelector(selectReloadLeftList);
    const waitingForPlan = useAppSelector(selectWaitingForPlan);
    const input = useAppSelector(selectInput);
    const submittingChatDisableInput = useAppSelector(selectSubmittingChatDisable);
    const clarificationMessage = useAppSelector(selectClarificationMessage);
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
    const [followOnSubmitting, setFollowOnSubmitting] = React.useState(false);
    const followOnSubmissionRef = React.useRef(false);
    const processingStatusMessage = getPlanProcessingStatusMessage(processingElapsedSeconds);

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

    const laneTaken = laneFromRouterState ?? laneFromSessionState;

    const { isPlanActive } = usePlanCancellationAlert({
        planData,
        planApprovalRequest,
        onNavigate: pendingNavigation || (() => {}),
    });

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
        dispatch(setCancellingPlan(true));
        try {
            if (planApprovalRequest?.id) {
                await apiService.approvePlan({
                    m_plan_id: planApprovalRequest.id,
                    plan_id: planData?.plan?.id ?? '',
                    approved: false,
                    feedback: 'Plan cancelled by user navigation',
                });
            }
            pendingNavigation?.();
            webSocketService.disconnect();
        } catch {
            showToast('Failed to cancel the plan properly, but navigation will continue.', 'error');
            pendingNavigation?.();
        } finally {
            dispatch(setCancellingPlan(false));
            dispatch(setShowCancellationDialog(false));
            setPendingNavigation(null);
        }
    }, [planApprovalRequest, planData, pendingNavigation, showToast, dispatch]);

    const handleCancelDialog = useCallback(() => {
        dispatch(setShowCancellationDialog(false));
        setPendingNavigation(null);
    }, [dispatch]);

    const handleTimeoutGoHome = useCallback(() => {
        navigate('/');
    }, [navigate]);

    /* ── Plan Approval / Rejection ──────────────────────────── */
    const handleApprovePlan = useCallback(async () => {
        if (!planApprovalRequest) return;
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
    }, [planApprovalRequest, planData, showToast, dismissToast, dispatch]);

    const handleRejectPlan = useCallback(async () => {
        if (!planApprovalRequest) return;
        dispatch(setProcessingApproval(true));
        const id = showToast('Submitting cancellation', 'progress');
        try {
            await apiService.approvePlan({
                m_plan_id: planApprovalRequest.id,
                plan_id: planData?.plan?.id ?? '',
                approved: false,
                feedback: 'Plan rejected by user',
            });
            dismissToast(id);
            navigate('/');
        } catch {
            dismissToast(id);
            showToast('Failed to submit cancellation', 'error');
            navigate('/');
        } finally {
            /* P0: single compound action replaces multiple state resets */
            dispatch(planApprovalRejected());
        }
    }, [planApprovalRequest, planData, navigate, showToast, dismissToast, dispatch]);

    const handleFollowOnTask = useCallback(async (task: StartingTask) => {
        if (followOnSubmissionRef.current) return;
        const sessionId = planData?.plan?.session_id;
        if (!sessionId) {
            showToast('Could not continue this conversation', 'error');
            return;
        }

        followOnSubmissionRef.current = true;
        setFollowOnSubmitting(true);
        dispatch(requestStarted());
        const id = showToast('Creating a plan', 'progress');
        try {
            const response = await TaskService.createPlan(
                task.prompt,
                planTeam?.team_id,
                task.lane,
                sessionId,
                task.id,
            );
            if (!response.plan_id) {
                throw new Error('The follow-on task did not create a plan');
            }

            webSocketService.connect(response.plan_id).catch(() => {
                // The plan page retries, and the surface degrades to polling.
            });
            dismissToast(id);
            showToast(
                isLane(response.lane)
                    ? `Plan created — ${LANE_LABELS[response.lane]}`
                    : 'Plan created!',
                'success',
            );
            navigate(`/plan/${response.plan_id}`, { state: { lane: response.lane } });
        } catch {
            dismissToast(id);
            showToast('Unable to create plan. Please try again.', 'error');
        } finally {
            followOnSubmissionRef.current = false;
            setFollowOnSubmitting(false);
        }
    }, [
        planData,
        planTeam,
        dispatch,
        showToast,
        dismissToast,
        navigate,
    ]);

    /* ── Chat submission ────────────────────────────────────── */
    const handleOnchatSubmit = useCallback(
        async (chatInput: string) => {
            if (!chatInput.trim()) {
                showToast('Please enter a clarification', 'error');
                return;
            }
            dispatch(setInput(''));
            if (!planData?.plan) return;
            // A clarification produces a new answer, so the previous answer's
            // provenance goes dark (#24). A Foundry-only follow-up emits no
            // replacement `source_used`, and a panel left up would attribute it
            // to Copilot Studio.
            dispatch(requestStarted());
            dispatch(setSubmittingChatDisableInput(true));
            const id = showToast('Submitting clarification', 'progress');
            try {
                await PlanDataService.submitClarification({
                    request_id: clarificationMessage?.request_id || '',
                    answer: chatInput,
                    plan_id: planData.plan.id,
                    m_plan_id: planApprovalRequest?.id || '',
                });
                dispatch(setInput(''));
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
                dispatch(setSubmittingChatDisableInput(true));
                dispatch(setShowProcessingPlanSpinner(true));
                scrollToBottom();
            } catch {
                dispatch(setShowProcessingPlanSpinner(false));
                dismissToast(id);
                dispatch(setSubmittingChatDisableInput(false));
                showToast('Failed to submit clarification', 'error');
            }
        },
        [planData, clarificationMessage, planApprovalRequest, showToast, dismissToast, dispatch, scrollToBottom],
    );

    /* ── Left-panel handlers ────────────────────────────────── */
    const handleNewTaskButton = useCallback(() => {
        handleNavigationWithAlert(() => navigate('/', { state: { focusInput: true } }));
    }, [navigate, handleNavigationWithAlert]);

    const resetReload = useCallback(() => {
        dispatch(setReloadLeftList(false));
    }, [dispatch]);

    /* ── Loading message rotation ───────────────────────────── */
    useEffect(() => {
        if (!loading) return;
        let index = 0;
        dispatch(setLoadingMessage(loadingMessages[0]));
        const interval = setInterval(() => {
            index = (index + 1) % loadingMessages.length;
            dispatch(setLoadingMessage(loadingMessages[index]));
        }, 3000);
        return () => clearInterval(interval);
    }, [loading, dispatch]);

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
                    <PlanPanelLeft
                        reloadTasks={reloadLeftList}
                        onNewTaskButton={handleNewTaskButton}
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
                <PlanPanelLeft
                    reloadTasks={reloadLeftList}
                    onNewTaskButton={handleNewTaskButton}
                    restReload={resetReload}
                    onNavigationWithAlert={handleNavigationWithAlert}
                />

                <Content>
                    {loading || !planData ? (
                        <>
                            <div className="plan-loading-spinner">
                                <Spinner size="medium" />
                                <Text>Loading plan data...</Text>
                            </div>
                            <LoadingMessage loadingMessage={loadingMessage} iconSrc={Octo} />
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
                                waitingForPlan={waitingForPlan}
                                messagesContainerRef={messagesContainerRef}
                                finalResultRef={finalResultRef}
                                streamingMessageBuffer={streamingMessageBuffer}
                                showBufferingText={showBufferingText}
                                agentMessages={agentMessages}
                                showProcessingPlanSpinner={showProcessingPlanSpinner}
                                processingElapsedSeconds={processingElapsedSeconds}
                                processingStatusMessage={processingStatusMessage}
                                showApprovalButtons={showApprovalButtons}
                                processingApproval={processingApproval}
                                handleApprovePlan={handleApprovePlan}
                                handleRejectPlan={handleRejectPlan}
                                rehearsedReplies={rehearsedReplies}
                                followOnTask={followOnTask}
                                onFollowOnTask={handleFollowOnTask}
                                followOnSubmitting={followOnSubmitting}
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

const MemoizedPlanPage = React.memo(PlanPage);
MemoizedPlanPage.displayName = 'PlanPage';
export default MemoizedPlanPage;
