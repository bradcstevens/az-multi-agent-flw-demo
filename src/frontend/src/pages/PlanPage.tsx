import React, { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spinner, Text } from "@fluentui/react-components";
import { PlanDataService } from "../services/PlanDataService";
import { ProcessedPlanData, PlanWithSteps, WebsocketMessageType, MPlanData } from "../models";
import PlanChat from "../components/content/PlanChat";
import PlanPanelRight from "../components/content/PlanPanelRight";
import PlanPanelLeft from "../components/content/PlanPanelLeft";
import CoralShellColumn from "../coral/components/Layout/CoralShellColumn";
import CoralShellRow from "../coral/components/Layout/CoralShellRow";
import Content from "../coral/components/Content/Content";
import ContentToolbar from "../coral/components/Content/ContentToolbar";
import {
    useInlineToaster,
} from "../components/toast/InlineToaster";
import Octo from "../coral/imports/Octopus.png";
import PanelRightToggles from "../coral/components/Header/PanelRightToggles";
import { TaskListSquareLtr } from "../coral/imports/bundleicons";
import LoadingMessage, { loadingMessages } from "../coral/components/LoadingMessage";
import { RAIErrorCard, RAIErrorData } from "../components/errors";
import { TeamConfig } from "../models/Team";
import { TeamService } from "../services/TeamService";
import webSocketService from "../services/WebSocketService";
import { APIService } from "../api/apiService";
import { StreamMessage, StreamingPlanUpdate } from "../models";

import "../styles/PlanPage.css"

// Create API service instance
const apiService = new APIService();

/**
 * Page component for displaying a specific plan
 * Accessible via the route /plan/{plan_id}
 */
const PlanPage: React.FC = () => {
    const { planId } = useParams<{ planId: string }>();
    const navigate = useNavigate();
    const { showToast, dismissToast } = useInlineToaster();
    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const [input, setInput] = useState("");
    const [planData, setPlanData] = useState<ProcessedPlanData | any>(null);
    const [allPlans, setAllPlans] = useState<ProcessedPlanData[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [submittingChatDisableInput, setSubmitting] = useState<boolean>(false);
    const [error, setError] = useState<Error | null>(null);
    const [processingSubtaskId, setProcessingSubtaskId] = useState<string | null>(
        null
    );
    const [planApprovalRequest, setPlanApprovalRequest] = useState<MPlanData | null>(null);
    const [reloadLeftList, setReloadLeftList] = useState(true);
    const [waitingForPlan, setWaitingForPlan] = useState(true);
    // WebSocket connection state
    const [wsConnected, setWsConnected] = useState(false);
    const [streamingMessages, setStreamingMessages] = useState<StreamingPlanUpdate[]>([]);

    // RAI Error state
    const [raiError, setRAIError] = useState<RAIErrorData | null>(null);

    // Team config state
    const [teamConfig, setTeamConfig] = useState<TeamConfig | null>(null);
    const [loadingTeamConfig, setLoadingTeamConfig] = useState(true);

    // Plan approval state - track when plan is approved
    const [planApproved, setPlanApproved] = useState(false);

    const [loadingMessage, setLoadingMessage] = useState<string>(loadingMessages[0]);

    // Use ref to store the function to avoid stale closure issues
    const loadPlanDataRef = useRef<() => Promise<ProcessedPlanData[]>>();
    // Auto-scroll helper
    const scrollToBottom = useCallback(() => {
        setTimeout(() => {
            if (messagesContainerRef.current) {
                messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
            }
        }, 100);
    }, []);

    useEffect(() => {
        const unsubscribe = webSocketService.on(WebsocketMessageType.PLAN_APPROVAL_REQUEST, (approvalRequest: any) => {
            console.log('📋 Plan received:', approvalRequest);

            let mPlanData: MPlanData | null = null;

            // Handle the different message structures
            if (approvalRequest.parsedData) {
                // Direct parsedData property
                mPlanData = approvalRequest.parsedData;
            } else if (approvalRequest.data && typeof approvalRequest.data === 'object') {
                // Data property with nested object
                if (approvalRequest.data.parsedData) {
                    mPlanData = approvalRequest.data.parsedData;
                } else {
                    // Try to parse the data object directly
                    mPlanData = approvalRequest.data;
                }
            } else if (approvalRequest.rawData) {
                // Parse the raw data string
                mPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest.rawData);
            } else {
                // Try to parse the entire object
                mPlanData = PlanDataService.parsePlanApprovalRequest(approvalRequest);
            }

            if (mPlanData) {
                console.log('✅ Parsed plan data:', mPlanData);
                setPlanApprovalRequest(mPlanData);
                setWaitingForPlan(false);
                // onPlanReceived?.(mPlanData);
                scrollToBottom();
            } else {
                console.error('❌ Failed to parse plan data', approvalRequest);
            }
        });

        return () => unsubscribe();
    }, [scrollToBottom]); //onPlanReceived, scrollToBottom
    // Loading message rotation effect
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (loading) {
            let index = 0;
            interval = setInterval(() => {
                index = (index + 1) % loadingMessages.length;
                setLoadingMessage(loadingMessages[index]);
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [loading]);

    // WebSocket connection with proper error handling and v3 backend compatibility
    useEffect(() => {
        if (planId && !loading) {
            console.log('🔌 Connecting WebSocket:', { planId });

            const connectWebSocket = async () => {
                try {
                    await webSocketService.connect(planId);
                    console.log('✅ WebSocket connected successfully');
                } catch (error) {
                    console.error('❌ WebSocket connection failed:', error);
                    // Continue without WebSocket - the app should still work
                }
            };

            connectWebSocket();

            const handleConnectionChange = (connected: boolean) => {
                setWsConnected(connected);
                console.log('🔗 WebSocket connection status:', connected);
            };

            const handleStreamingMessage = (message: StreamMessage) => {
                console.log('📨 Received streaming message:', message);
                if (message.data && message.data.plan_id) {
                    setStreamingMessages(prev => [...prev, message.data]);
                }
            };

            const handlePlanApprovalResponse = (message: StreamMessage) => {
                console.log('✅ Plan approval response received:', message);
                if (message.data && message.data.approved) {
                    setPlanApproved(true);
                }
            };

            const handlePlanApprovalRequest = (message: StreamMessage) => {
                console.log('📥 Plan approval request received:', message);
                // This is handled by PlanChat component through its own listener
            };

            // Subscribe to all relevant v3 backend events
            const unsubscribeConnection = webSocketService.on('connection_status', (message) => {
                handleConnectionChange(message.data?.connected || false);
            });

            const unsubscribeStreaming = webSocketService.on(WebsocketMessageType.AGENT_MESSAGE, handleStreamingMessage);
            const unsubscribePlanApproval = webSocketService.on(WebsocketMessageType.PLAN_APPROVAL_RESPONSE, handlePlanApprovalResponse);
            const unsubscribePlanApprovalRequest = webSocketService.on(WebsocketMessageType.PLAN_APPROVAL_REQUEST, handlePlanApprovalRequest);
            const unsubscribeParsedPlanApprovalRequest = webSocketService.on(WebsocketMessageType.PLAN_APPROVAL_REQUEST, handlePlanApprovalRequest);

            return () => {
                console.log('🔌 Cleaning up WebSocket connections');
                unsubscribeConnection();
                unsubscribeStreaming();
                unsubscribePlanApproval();
                unsubscribePlanApprovalRequest();
                unsubscribeParsedPlanApprovalRequest();
                webSocketService.disconnect();
            };
        }
    }, [planId, loading]);

    useEffect(() => {

        const loadTeamConfig = async () => {
            try {
                setLoadingTeamConfig(true);
                const teams = await TeamService.getUserTeams();
                // Get the first team as default config, or you can implement logic to get current team
                const config = teams.length > 0 ? teams[0] : null;
                setTeamConfig(config);
            } catch (error) {
                console.error('Failed to load team config:', error);
                // Don't show error for team config loading - it's optional
            } finally {
                setLoadingTeamConfig(false);
            }
        };

        loadTeamConfig();
    }, []);

    // Helper function to convert PlanWithSteps to ProcessedPlanData
    const convertToProcessedPlanData = (planWithSteps: PlanWithSteps): ProcessedPlanData => {
        return PlanDataService.processPlanData(planWithSteps, []);
    };

    // Create loadPlanData function with useCallback to memoize it
    const loadPlanData = useCallback(
        async (useCache = true): Promise<ProcessedPlanData[]> => {
            if (!planId) return [];

            setLoading(true);
            setError(null);

            try {
                let actualPlanId = planId;
                let planResult: ProcessedPlanData | null = null;

                if (actualPlanId && !planResult) {
                    console.log("Fetching plan with ID:", actualPlanId);
                    planResult = await PlanDataService.fetchPlanData(actualPlanId, useCache);
                    console.log("Plan data loaded successfully");
                }

                const allPlansWithSteps = await apiService.getPlans();
                const allPlansData = allPlansWithSteps.map(convertToProcessedPlanData);
                setAllPlans(allPlansData);

                if (planResult?.plan?.id && planResult.plan.id !== actualPlanId) {
                    console.log('Plan ID mismatch detected, redirecting...', {
                        requested: actualPlanId,
                        actual: planResult.plan.id
                    });
                    navigate(`/plan/${planResult.plan.id}`, { replace: true });
                }

                setPlanData(planResult);
                return allPlansData;
            } catch (err) {
                console.log("Failed to load plan data:", err);
                setError(
                    err instanceof Error ? err : new Error("Failed to load plan data")
                );
                return [];
            } finally {
                setLoading(false);
            }
        },
        [planId, navigate]
    );

    // Update the ref whenever loadPlanData changes
    useEffect(() => {
        loadPlanDataRef.current = loadPlanData;
    }, [loadPlanData]);

    // Chat submission handler - updated for v3 backend compatibility
    const handleOnchatSubmit = useCallback(
        async (chatInput: string) => {
            if (!chatInput.trim()) {
                showToast("Please enter a clarification", "error");
                return;
            }
            setInput("");
            setRAIError(null); // Clear any previous RAI errors
            if (!planData?.plan) return;
            setSubmitting(true);
            let id = showToast("Submitting clarification", "progress");

            try {
                // Use legacy method for non-v3 backends
                await PlanDataService.submitClarification(
                    planData.plan.id,
                    planData.plan.session_id,
                    chatInput
                );


                setInput("");
                dismissToast(id);
                showToast("Clarification submitted successfully", "success");
                await loadPlanData(false);
            } catch (error: any) {
                dismissToast(id);

                // Enhanced error handling for v3 backend
                let errorDetail = null;
                try {
                    // Try to parse the error detail if it's a string
                    if (typeof error?.response?.data?.detail === 'string') {
                        errorDetail = JSON.parse(error.response.data.detail);
                    } else {
                        errorDetail = error?.response?.data?.detail;
                    }
                } catch (parseError) {
                    // If parsing fails, use the original error
                    errorDetail = error?.response?.data?.detail;
                }

                // Handle RAI validation errors with better UX
                if (errorDetail?.error_type === 'RAI_VALIDATION_FAILED') {
                    const raiErrorData: RAIErrorData = {
                        error_type: 'RAI_VALIDATION_FAILED',
                        message: 'Content Policy Violation',
                        description: errorDetail.message || 'Your input contains content that violates our content policy.',
                        suggestions: errorDetail.suggestions || [
                            'Please rephrase your message using professional language',
                            'Avoid potentially harmful or inappropriate content',
                            'Focus on business-appropriate requests'
                        ],
                        user_action: 'Please modify your input and try again.'
                    };
                    setRAIError(raiErrorData);
                } else {
                    // Handle other types of errors
                    showToast(
                        error?.response?.data?.detail?.message ||
                        error?.response?.data?.detail ||
                        error?.message ||
                        "Failed to submit clarification",
                        "error"
                    );
                }
            } finally {
                setSubmitting(false);
            }
        },
        [planData?.plan, showToast, dismissToast, loadPlanData]
    );


    // ✅ Handlers for PlanPanelLeft
    const handleNewTaskButton = useCallback(() => {
        navigate("/", { state: { focusInput: true } });
    }, [navigate]);



    const resetReload = useCallback(() => {
        setReloadLeftList(false);
    }, []);

    useEffect(() => {
        const initializePlanLoading = async () => {
            if (!planId) return;

            try {
                await loadPlanData(true);
            } catch (err) {
                console.error("Failed to initialize plan loading:", err);
            }
        };

        initializePlanLoading();
    }, [planId, loadPlanData]);

    if (error) {
        return (
            <CoralShellColumn>
                <CoralShellRow>
                    <Content>
                        <div style={{
                            textAlign: "center",
                            padding: "40px 20px",
                            color: 'var(--colorNeutralForeground2)'
                        }}>
                            <Text size={500}>
                                {error.message || "An error occurred while loading the plan"}
                            </Text>
                        </div>
                    </Content>
                </CoralShellRow>
            </CoralShellColumn>
        );
    }

    return (
        <CoralShellColumn>
            <CoralShellRow>
                {/* ✅ RESTORED: PlanPanelLeft for navigation */}
                <PlanPanelLeft
                    reloadTasks={reloadLeftList}
                    onNewTaskButton={handleNewTaskButton}
                    restReload={resetReload}
                    onTeamSelect={() => { }}
                    onTeamUpload={async () => { }}
                    isHomePage={false}
                    selectedTeam={teamConfig}
                />

                <Content>
                    {loading || !planData ? (
                        <>
                            <div style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "12px",
                                justifyContent: "center",
                                padding: "20px",
                            }}>
                                <Spinner size="medium" />
                                <Text>Loading plan data...</Text>
                            </div>
                            <LoadingMessage
                                loadingMessage={loadingMessage}
                                iconSrc={Octo}
                            />
                        </>
                    ) : (
                        <>
                            <ContentToolbar
                                panelTitle="Multi-Agent Planner"
                            >
                                <PanelRightToggles>
                                    <TaskListSquareLtr />
                                </PanelRightToggles>
                            </ContentToolbar>

                            {/* Show RAI error if present */}
                            {raiError && (
                                <div style={{ padding: '16px 24px 0' }}>
                                    <RAIErrorCard
                                        error={raiError}
                                        onRetry={() => {
                                            setRAIError(null);
                                        }}
                                        onDismiss={() => setRAIError(null)}
                                    />
                                </div>
                            )}

                            <PlanChat
                                planData={planData}
                                OnChatSubmit={handleOnchatSubmit}
                                loading={loading}
                                setInput={setInput}
                                submittingChatDisableInput={submittingChatDisableInput}
                                input={input}
                                streamingMessages={streamingMessages}
                                wsConnected={wsConnected}
                                onPlanApproval={(approved) => setPlanApproved(approved)}
                                planApprovalRequest={planApprovalRequest}
                                waitingForPlan={waitingForPlan}
                                messagesContainerRef={messagesContainerRef}
                            />
                        </>
                    )}
                </Content>

                <PlanPanelRight
                    planData={planData}
                    submittingChatDisableInput={submittingChatDisableInput}
                    processingSubtaskId={processingSubtaskId}
                    loading={loading}
                    streamingMessages={streamingMessages}
                    planApproved={planApproved}
                    planApprovalRequest={planApprovalRequest}
                />
            </CoralShellRow>
        </CoralShellColumn>
    );
};

export default PlanPage;