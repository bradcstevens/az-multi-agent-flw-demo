/**
 * usePlanWebSocket — extracts all WebSocket event subscriptions
 * from PlanPage into one reusable hook.
 *
 * Dispatches Redux actions for each event type so PlanPage no longer
 * needs 7+ useEffect blocks for WebSocket handling.
 */
import React, { useEffect } from 'react';
import webSocketService from '@/store/WebSocketService';
import { PlanDataService } from '@/store/PlanDataService';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    setShowProcessingPlanSpinner,
    setShowApprovalButtons,
    setReloadLeftList,
    selectPlanData,
    selectContinueWithWebsocketFlow,
    selectPlanApproved,
    selectShowProcessingPlanSpinner,
    setShowTimeoutDialog,
    setTimeoutMessage,
    approvalRequestReceived,
    planCompletedFinal,
    planFailedFinal,
} from '@/store/slices/planSlice';
import {
    agentResponding,
    requestSettled,
    socketConnected,
} from '@/store/slices/progressSlice';
import {
    setSubmittingChatDisableInput,
    setClarificationMessage,
    addAgentMessage,
} from '@/store/slices/chatSlice';
import {
    appendToStreamingBuffer,
    clearStreamingAnswer,
    completeStreamingAnswer,
    startStreamingAnswer,
    setStreamingAgent,
    setShowBufferingText,
    addStreamingMessage,
} from '@/store/slices/streamingSlice';
import { setWsConnected } from '@/store/slices/appSlice';
import { setSelectedTeam } from '@/store/slices/teamSlice';
import {
    WebsocketMessageType,
    MPlanData,
    AgentMessageData,
    AgentMessageType,
    AgentType,
    PlanStatus,
    ParsedUserClarification,
    StreamMessage,
    ProcessedPlanData,
} from '@/models';
import { APIService } from '@/api/apiService';
import { ToastIntent } from '@/components/toast/InlineToaster';
import { formatElapsedTime } from '@/utils';

const apiService = new APIService();

interface UsePlanWebSocketProps {
    planId: string | undefined;
    scrollToBottom: () => void;
    scrollToFinalResult: () => void;
    formatErrorMessage: (content: string) => string;
    showToast: (content: React.ReactNode, intent?: ToastIntent, options?: { dismissible?: boolean; timeoutMs?: number | null }) => number;
}

/**
 * Creates an AgentMessageResponse and persists it, then optionally reloads the chat list.
 */
function persistAgentMessage(
    agentMessageData: AgentMessageData,
    planData: ProcessedPlanData | null,
    dispatch: ReturnType<typeof useAppDispatch>,
    isFinal = false,
    streamingMessage = '',
) {
    if (!planData?.plan) return;

    const agentMessageResponse = PlanDataService.createAgentMessageResponse(
        agentMessageData,
        planData,
        isFinal,
        streamingMessage,
    );
    apiService
        .sendAgentMessage(agentMessageResponse)
        .then(() => {
            if (isFinal) {
                setTimeout(() => dispatch(setReloadLeftList(true)), 1000);
            }
        })
        .catch(() => {
            if (isFinal) {
                setTimeout(() => dispatch(setReloadLeftList(true)), 1000);
            }
        });
}

export function usePlanWebSocket({
    planId,
    scrollToBottom,
    scrollToFinalResult,
    formatErrorMessage,
    showToast,
}: UsePlanWebSocketProps) {
    const dispatch = useAppDispatch();
    const planData = useAppSelector(selectPlanData);
    const planApproved = useAppSelector(selectPlanApproved);
    const showProcessingPlanSpinner = useAppSelector(selectShowProcessingPlanSpinner);
    const continueWithWebsocketFlow = useAppSelector(selectContinueWithWebsocketFlow);
    const processingStartedAtRef = React.useRef<number | null>(null);

    // Coalesce high-frequency streaming tokens into one flush per animation frame
    // to avoid a synchronous re-render per token freezing the UI on fast streams.
    const streamingChunkQueueRef = React.useRef<string[]>([]);
    const streamingFlushHandleRef = React.useRef<number | null>(null);

    // The plan this page has taken responsibility for a socket for — set when
    // it opens one and when it adopts one opened on the `createPlan` response.
    const socketOwnedForRef = React.useRef<string | null>(null);

    const connectWebSocket = (id: string) => {
        webSocketService.connect(id).catch(() => {
            console.log('WebSocket connection failed, continuing without real-time updates');
        });
    };

    useEffect(() => {
        if (showProcessingPlanSpinner) {
            if (processingStartedAtRef.current === null) {
                processingStartedAtRef.current = Date.now();
            }
        } else {
            processingStartedAtRef.current = null;
        }
    }, [showProcessingPlanSpinner]);

    // ── PLAN_APPROVAL_REQUEST ─────────────────────────────────────
    useEffect(() => {
        const unsub = webSocketService.on(
            WebsocketMessageType.PLAN_APPROVAL_REQUEST,
            (approvalRequest: any) => {
                let mPlanData: MPlanData | null = null;
                if (approvalRequest.parsedData) {
                    mPlanData = approvalRequest.parsedData;
                } else if (approvalRequest.data?.parsedData) {
                    mPlanData = approvalRequest.data.parsedData;
                } else if (approvalRequest.data && typeof approvalRequest.data === 'object') {
                    mPlanData = approvalRequest.data;
                } else if (approvalRequest.rawData) {
                    mPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest.rawData);
                } else {
                    mPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest);
                }
                if (mPlanData) {
                    /* P0: single compound action replaces 4 separate dispatches */
                    dispatch(approvalRequestReceived(mPlanData));
                    // The Deliberate lane's Done: the plan is on screen, so the
                    // request is no longer in flight (#64, ADR-023). The
                    // approval starts a second one.
                    dispatch(requestSettled());
                    scrollToBottom();
                }
            },
        );
        return unsub;
    }, [dispatch, scrollToBottom]);

    // ── AGENT_MESSAGE_STREAMING ───────────────────────────────────
    useEffect(() => {
        const flushStreamingChunks = () => {
            streamingFlushHandleRef.current = null;
            const chunks = streamingChunkQueueRef.current;
            if (chunks.length === 0) return;
            streamingChunkQueueRef.current = [];
            dispatch(setShowBufferingText(true));
            dispatch(appendToStreamingBuffer(chunks.join('')));
        };

        const unsub = webSocketService.on(
            WebsocketMessageType.AGENT_MESSAGE_STREAMING,
            (msg: any) => {
                const streamed = msg.data ?? msg;
                // The one signal that names *which* specialist is responding
                // (#64, ADR-023). Taken from the frame rather than from the
                // plan, which the Fast lane does not have.
                dispatch(agentResponding(streamed.agent ?? null));
                if (streamed.agent) {
                    dispatch(setStreamingAgent(streamed.agent));
                }
                const line = PlanDataService.simplifyHumanClarification(streamed.content || '');
                if (line) {
                    dispatch(startStreamingAnswer());
                    streamingChunkQueueRef.current.push(line);
                    if (streamingFlushHandleRef.current === null) {
                        streamingFlushHandleRef.current = requestAnimationFrame(flushStreamingChunks);
                    }
                }
                if (streamed.is_final) {
                    if (streamingFlushHandleRef.current !== null) {
                        cancelAnimationFrame(streamingFlushHandleRef.current);
                        streamingFlushHandleRef.current = null;
                    }
                    flushStreamingChunks();
                    // This is the stream's own terminal signal. A final result
                    // settles the transcript later, but cannot define when the
                    // model stopped streaming.
                    dispatch(completeStreamingAnswer());
                }
            },
        );
        return () => {
            unsub();
            // Cancel pending frame and flush leftovers so no streamed text is lost
            if (streamingFlushHandleRef.current !== null) {
                cancelAnimationFrame(streamingFlushHandleRef.current);
                streamingFlushHandleRef.current = null;
            }
            if (streamingChunkQueueRef.current.length > 0) {
                const remaining = streamingChunkQueueRef.current.join('');
                streamingChunkQueueRef.current = [];
                dispatch(appendToStreamingBuffer(remaining));
            }
        };
    }, [dispatch]);

    // ── USER_CLARIFICATION_REQUEST ────────────────────────────────
    useEffect(() => {
        const unsub = webSocketService.on(
            WebsocketMessageType.USER_CLARIFICATION_REQUEST,
            (msg: any) => {
                /*
                  The parser is total and returns `null` for a frame it cannot
                  read, and `emit` re-wraps whatever it is handed — so a frame
                  carrying no `request_id` arrived here as `{ data: null }`,
                  walked past a guard that only checked the envelope, and threw
                  inside the listener where the socket service logged it and
                  moved on (#68). A question this surface could not answer is
                  not a question; it opens nothing and says nothing.
                */
                if (!msg?.data?.request_id) return;
                const agentMessageData: AgentMessageData = {
                    agent: AgentType.GROUP_CHAT_MANAGER,
                    agent_type: AgentMessageType.AI_AGENT,
                    timestamp: msg.timestamp || Date.now(),
                    steps: [],
                    next_steps: [],
                    content: msg.data.question || '',
                    raw_data: msg.data || '',
                };
                dispatch(setClarificationMessage(msg.data as ParsedUserClarification));
                dispatch(addAgentMessage(agentMessageData));
                dispatch(setShowBufferingText(false));
                dispatch(setShowProcessingPlanSpinner(false));
                // A question put to the associate is the turn waiting on them,
                // not a request in flight (#64, ADR-023).
                dispatch(requestSettled());
                processingStartedAtRef.current = null;
                dispatch(setSubmittingChatDisableInput(false));
                scrollToBottom();
                persistAgentMessage(agentMessageData, planData, dispatch);
            },
        );
        return unsub;
    }, [dispatch, scrollToBottom, planData]);

    // ── AGENT_TOOL_MESSAGE (currently no-op, kept for future) ─────
    useEffect(() => {
        const unsub = webSocketService.on(WebsocketMessageType.AGENT_TOOL_MESSAGE, () => {});
        return unsub;
    }, []);

    // ── FINAL_RESULT_MESSAGE ──────────────────────────────────────
    useEffect(() => {
        const unsub = webSocketService.on(
            WebsocketMessageType.FINAL_RESULT_MESSAGE,
            (finalMessage: any) => {
                if (!finalMessage) return;
                const completionElapsedSeconds = processingStartedAtRef.current
                    ? Math.max(Math.round((Date.now() - processingStartedAtRef.current) / 1000), 0)
                    : null;
                const completionTimeLine = completionElapsedSeconds !== null
                    ? `\n\n**Total completion time: ${formatElapsedTime(completionElapsedSeconds)}**`
                    : '';
                const messageStatus = finalMessage?.status ?? finalMessage?.data?.status;
                const finalContent = finalMessage?.content ?? finalMessage?.data?.content ?? '';
                if (streamingFlushHandleRef.current !== null) {
                    cancelAnimationFrame(streamingFlushHandleRef.current);
                    streamingFlushHandleRef.current = null;
                }
                streamingChunkQueueRef.current = [];
                // Done, on every terminal status rather than on the one the
                // handler recognises. Any other status used to hang the
                // indicator with the answer already on screen (#69).
                dispatch(requestSettled());
                // And nothing is in flight, so the box is free (#77, ADR-027).
                // Released here for #69's reason — on every terminal status,
                // not on the one branch that remembered — and released rather
                // than locked, because the chat most worth resuming is the one
                // that did not finish.
                dispatch(setSubmittingChatDisableInput(false));

                if (messageStatus === PlanStatus.COMPLETED) {
                    const agentMessageData: AgentMessageData = {
                        agent: AgentType.GROUP_CHAT_MANAGER,
                        agent_type: AgentMessageType.AI_AGENT,
                        timestamp: Date.now(),
                        steps: [],
                        next_steps: [],
                        content: finalContent + completionTimeLine,
                        raw_data: finalMessage,
                        announce: true,
                    };
                    // The persisted whole result is authoritative. The stream
                    // was a preview and must disappear even if it missed words.
                    dispatch(clearStreamingAnswer());
                    dispatch(addAgentMessage(agentMessageData));
                    dispatch(setSelectedTeam(planData?.team || null));
                    /* P0: single compound action replaces setShowProcessingPlanSpinner(false) + markPlanCompleted() */
                    dispatch(planCompletedFinal());
                    processingStartedAtRef.current = null;
                    scrollToFinalResult();
                    webSocketService.disconnect();
                    persistAgentMessage(agentMessageData, planData, dispatch, true);
                } else if (messageStatus === 'error') {
                    // Safety net: handle error status sent as FINAL_RESULT_MESSAGE
                    const errorContent = finalContent || 'An unexpected error occurred. Please try again later.';
                    const errorAgent: AgentMessageData = {
                        agent: 'system',
                        agent_type: AgentMessageType.SYSTEM_AGENT,
                        timestamp: Date.now(),
                        steps: [],
                        next_steps: [],
                        content: formatErrorMessage(errorContent),
                        raw_data: finalMessage,
                    };
                    dispatch(addAgentMessage(errorAgent));
                    dispatch(planFailedFinal());
                    dispatch(clearStreamingAnswer());
                    scrollToBottom();
                    showToast(errorContent, 'error');
                    webSocketService.disconnect();
                } else {
                    // Any other terminal status (e.g. "terminated"): clear the spinner
                    // so the UI doesn't hang after the answer has already arrived.
                    const content = finalContent;
                    if (content) {
                        const terminalMessage: AgentMessageData = {
                            agent: AgentType.GROUP_CHAT_MANAGER,
                            agent_type: AgentMessageType.AI_AGENT,
                            timestamp: Date.now(),
                            steps: [],
                            next_steps: [],
                            content,
                            raw_data: finalMessage,
                        };
                        dispatch(addAgentMessage(terminalMessage));
                    }
                    dispatch(clearStreamingAnswer());
                    dispatch(setShowProcessingPlanSpinner(false));
                    processingStartedAtRef.current = null;
                    scrollToBottom();
                    webSocketService.disconnect();
                }
            },
        );
        return unsub;
    }, [dispatch, scrollToBottom, scrollToFinalResult, planData, formatErrorMessage, showToast]);

    // ── ERROR_MESSAGE ─────────────────────────────────────────────
    useEffect(() => {
        const unsub = webSocketService.on(
            WebsocketMessageType.ERROR_MESSAGE,
            (errorMessage: any) => {
                if (streamingFlushHandleRef.current !== null) {
                    cancelAnimationFrame(streamingFlushHandleRef.current);
                    streamingFlushHandleRef.current = null;
                }
                streamingChunkQueueRef.current = [];
                let errorContent = 'An unexpected error occurred. Please try again later.';
                if (errorMessage?.data?.data?.content) {
                    const c = errorMessage.data.data.content.trim();
                    if (c.length > 0) errorContent = c;
                } else if (errorMessage?.data?.content) {
                    const c = errorMessage.data.content.trim();
                    if (c.length > 0) errorContent = c;
                } else if (errorMessage?.content) {
                    const c = errorMessage.content.trim();
                    if (c.length > 0) errorContent = c;
                } else if (typeof errorMessage === 'string') {
                    const c = errorMessage.trim();
                    if (c.length > 0) errorContent = c;
                }
                const errorAgent: AgentMessageData = {
                    agent: 'system',
                    agent_type: AgentMessageType.SYSTEM_AGENT,
                    timestamp: Date.now(),
                    steps: [],
                    next_steps: [],
                    content: formatErrorMessage(errorContent),
                    raw_data: errorMessage || '',
                };
                dispatch(addAgentMessage(errorAgent));
                dispatch(planFailedFinal());
                dispatch(requestSettled());
                processingStartedAtRef.current = null;
                dispatch(clearStreamingAnswer());
                // The turn is over, so nothing is in flight (#77, ADR-027).
                // This used to lock the box, which left the failed chat — the
                // one most worth resuming — the one chat that could not be.
                dispatch(setSubmittingChatDisableInput(false));
                scrollToBottom();
                showToast(errorContent, 'error');
                webSocketService.disconnect();
            },
        );
        return unsub;
    }, [dispatch, scrollToBottom, showToast, formatErrorMessage]);

    // ── TIMEOUT_NOTIFICATION ──────────────────────────────────────
    useEffect(() => {
        const unsub = webSocketService.on(
            WebsocketMessageType.TIMEOUT_NOTIFICATION,
            (msg: any) => {
                const message = msg?.data?.message || msg?.message ||
                    'Session timed out. Please go back to home and try again.';
                dispatch(setTimeoutMessage(message));
                dispatch(setShowTimeoutDialog(true));
                dispatch(requestSettled());
                dispatch(setShowProcessingPlanSpinner(false));
                dispatch(setShowApprovalButtons(false));
                webSocketService.disconnect();
            },
        );
        return unsub;
    }, [dispatch]);

    // ── AGENT_MESSAGE ─────────────────────────────────────────────
    useEffect(() => {
        const unsub = webSocketService.on(
            WebsocketMessageType.AGENT_MESSAGE,
            (agentMessage: any) => {
                // Only process agent messages after the user has approved the plan
                if (!planApproved) return;

                const agentMessageData = agentMessage.data as AgentMessageData;
                if (agentMessageData) {
                    agentMessageData.content = PlanDataService.simplifyHumanClarification(
                        agentMessageData?.content,
                    );
                    dispatch(addAgentMessage(agentMessageData));
                    dispatch(setShowProcessingPlanSpinner(true));
                    scrollToBottom();
                    persistAgentMessage(agentMessageData, planData, dispatch);
                }
            },
        );
        return unsub;
    }, [dispatch, scrollToBottom, planData, planApproved]);

    // ── WebSocket connect ─────────────────────────────────────────
    /*
      The chat page's connect, which is now the *second* one (ADR-021). The
      first is initiated by `HomeInput` on the `createPlan` response, because
      the backend schedules the orchestration before that response returns and
      everything it emits in the meantime is pushed at a socket that does not
      exist (#63). This one serves the case that has no response to hang off —
      a direct load or a reload of /chat/:id — and is a no-op when the socket
      for this plan is already open or still handshaking.
    */
    useEffect(() => {
        if (!planId || !continueWithWebsocketFlow) return;
        socketOwnedForRef.current = planId;
        connectWebSocket(planId);
    }, [planId, continueWithWebsocketFlow]);

    // ── WebSocket subscriptions ───────────────────────────────────
    useEffect(() => {
        const handleConnectionChange = (connected: boolean) => {
            dispatch(setWsConnected(connected));
            // Plumbing. It moves the phase on and says nothing of its own, so
            // the surface holds the last true statement (#64, ADR-023).
            if (connected) dispatch(socketConnected());
        };

        const handleStreamingMessage = (message: StreamMessage) => {
            if (message.data?.plan_id) {
                dispatch(addStreamingMessage(message.data));
            }
        };

        const unsubConnection = webSocketService.on('connection_status', (msg) =>
            handleConnectionChange(msg.data?.connected || false),
        );
        const unsubStreaming = webSocketService.on(
            WebsocketMessageType.AGENT_MESSAGE,
            handleStreamingMessage,
        );
        const unsubApproval = webSocketService.on(WebsocketMessageType.PLAN_APPROVAL_RESPONSE, () => {});
        const unsubApprovalReq = webSocketService.on(WebsocketMessageType.PLAN_APPROVAL_REQUEST, () => {});

        return () => {
            unsubConnection();
            unsubStreaming();
            unsubApproval();
            unsubApprovalReq();
        };
    }, [dispatch]);

    // ── WebSocket disconnect ──────────────────────────────────────
    /*
      The socket belongs to the chat page for as long as the chat page is on
      screen, whether the page opened it or adopted one opened on the
      `createPlan` response (ADR-021). It cannot be owned by
      `continueWithWebsocketFlow`, which only turns true once the plan GET has
      landed: a presenter who leaves before it does used to leave an adopted
      socket open with nothing to close it.

      Setup and cleanup are symmetric on purpose. React 18 StrictMode runs
      setup, cleanup, setup — so a cleanup that disconnects a socket no setup
      reopens closes the adopted socket on arrival, and #63 comes straight back
      on the dev server. `socketOwnedForRef` is what survives that teardown:
      once this page owns a socket for a plan it re-establishes it, and a
      completed plan that never had one still gets none.
    */
    useEffect(() => {
        if (!planId) return;

        if (socketOwnedForRef.current === planId || webSocketService.isServing(planId)) {
            socketOwnedForRef.current = planId;
            connectWebSocket(planId);
        }

        return () => {
            webSocketService.disconnect();
        };
    }, [planId]);
}

export default usePlanWebSocket;