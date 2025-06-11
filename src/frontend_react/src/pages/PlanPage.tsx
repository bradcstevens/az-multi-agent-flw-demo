import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Button,
    Text,
    Card,
    CardHeader,
    useToastController,
    Spinner,
    Badge
} from '@fluentui/react-components';
import {
    Add20Regular,
    ArrowLeft24Regular,
    ErrorCircle24Regular,
    Person24Regular,
    CheckmarkCircle24Regular,
    AlertUrgent24Regular,
    Sparkle20Filled
} from '@fluentui/react-icons';
import '../styles/PlanPage.css';
import CoralShellColumn from '../coral/components/Layout/CoralShellColumn';
import CoralShellRow from '../coral/components/Layout/CoralShellRow';
import Content from '../coral/components/Content/Content';
import { NewTaskService } from '../services/NewTaskService';
import { PlanDataService } from '../services/PlanDataService';
import { Step, ProcessedPlanData } from '@/models';
import PlanPanelLeft from '@/components/content/PlanPanelLeft';
import ContentToolbar from '@/coral/components/Content/ContentToolbar';
import PlanChat from '@/components/content/PlanChat';
import PlanPanelRight from '@/components/content/PlanPanelRight';

/**
 * Page component for displaying a specific plan
 * Accessible via the route /plan/{plan_id}
 */
const PlanPage: React.FC = () => {
    const { planId } = useParams<{ planId: string }>();
    const navigate = useNavigate();

    // State for plan data
    const [planData, setPlanData] = useState<ProcessedPlanData | any>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<Error | null>(null);

    /**
     * Fetch plan data when component mounts or planId changes
     */
    const loadPlanData = useCallback(async () => {
        if (!planId) return;

        try {
            setLoading(true);
            setError(null);

            const data = await PlanDataService.fetchPlanData(planId);
            console.log('Fetched plan data:', data);
            setPlanData(data);
        } catch (err) {
            console.error('Failed to load plan data:', err);
            setError(err instanceof Error ? err : new Error('Failed to load plan data'));
        } finally {
            setLoading(false);
        }
    }, [planId]);

    // Accept chat input and submit clarification
    const handleOnchatSubmit = useCallback(
        async (chatInput: string) => {
            if (!planData?.plan) return;
            try {
                await PlanDataService.submitClarification(
                    planData.plan.id, // plan_id
                    planData.plan.session_id, // session_id
                    chatInput // human_clarification
                );
                await loadPlanData();
            } catch (error) {
                console.error('Failed to submit clarification:', error);
            }
        },
        [planData, loadPlanData]
    );

    // Move handlers here to fix dependency order
    const handleApproveStep = useCallback(async (step: Step) => {
        try {
            await PlanDataService.approveStep(step);
            await loadPlanData();
        } catch (error) {
            console.error('Failed to approve step:', error);
        }
    }, [loadPlanData]);

    const handleRejectStep = useCallback(async (step: Step) => {
        try {
            await PlanDataService.rejectStep(step);
            await loadPlanData();
        } catch (error) {
            console.error('Failed to reject step:', error);
        }
    }, [loadPlanData]);

    // Load plan data on mount and when planId changes
    useEffect(() => {
        loadPlanData();
    }, [loadPlanData]);

    const handleNewTaskButton = () => {
        // Use NewTaskService to handle navigation to homepage and reset textarea
        NewTaskService.handleNewTaskFromPlan(navigate);
    };    // Show error if no planId is provided
    if (!planId) {
        return (
            <div style={{ padding: '20px' }}>
                <Text>Error: No plan ID provided</Text>
            </div>
        );
    }

    return (
        <CoralShellColumn>
            <CoralShellRow>
                <PlanPanelLeft onNewTaskButton={handleNewTaskButton} />
                <Content>
                    {loading && <Spinner />}
                    {!loading && (
                        <>
                            <ContentToolbar
                                panelTitle={planData?.plan?.initial_goal || 'Plan Details'}
                                panelIcon={<Sparkle20Filled />}
                            ></ContentToolbar>
                            <PlanChat
                                planData={planData}
                                OnChatSubmit={handleOnchatSubmit}
                            />
                        </>
                    )}
                </Content>

                <PlanPanelRight
                    planData={planData}
                    OnApproveStep={handleApproveStep}
                    OnRejectStep={handleRejectStep}
                />
            </CoralShellRow>
        </CoralShellColumn>
    );


};

export default PlanPage;