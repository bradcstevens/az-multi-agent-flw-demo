import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Button,
    Text,
    Spinner,
    Toast,
    ToastTitle,
    ToastBody,
    useToastController,
    Toaster
} from '@fluentui/react-components';
import {
    Add20Regular,
    CheckmarkCircle20Regular,
    ErrorCircle20Regular
} from '@fluentui/react-icons';
import '../styles/PlanPage.css';
import CoralShellColumn from '../coral/components/Layout/CoralShellColumn';
import CoralShellRow from '../coral/components/Layout/CoralShellRow';
import Content from '../coral/components/Content/Content';
import PanelLeft from '../coral/components/Panels/PanelLeft';
import PanelLeftToolbar from '../coral/components/Panels/PanelLeftToolbar';
import TaskList from '../components/content/TaskList';
import { useGetPlans } from '../hooks';
import { PlanWithSteps, PlanStatus } from '../models';
import { Task } from '../models/taskList';
import { apiService } from '../api/apiService';
import { TaskService } from '../services';

/**
 * HomePage component - displays task lists and provides navigation
 * Accessible via the route "/"
 */
const HomePage: React.FC = () => {
    const navigate = useNavigate();
    const { dispatchToast } = useToastController('toast');

    // State for task lists
    const [inProgressTasks, setInProgressTasks] = useState<Task[]>([]);
    const [completedTasks, setCompletedTasks] = useState<Task[]>([]);

    // API hook for fetching plans
    const {
        data: plans,
        loading: plansLoading,
        error: plansError,
        execute: fetchPlans, } = useGetPlans();

    /**
     * Load plans data and update task lists
     */
    const loadPlansData = useCallback(async (showToast = false) => {
        try {
            await fetchPlans();
            if (showToast) {
                dispatchToast(
                    <Toast>
                        <ToastTitle>
                            <CheckmarkCircle20Regular />
                            Tasks refreshed successfully
                        </ToastTitle>
                    </Toast>,
                    { intent: 'success' }
                );
            }
        } catch (error) {
            console.error('Failed to load plans:', error);
            if (showToast) {
                dispatchToast(
                    <Toast>
                        <ToastTitle>
                            <ErrorCircle20Regular />
                            Failed to refresh tasks
                        </ToastTitle>
                        <ToastBody>
                            {error instanceof Error ? error.message : 'An unknown error occurred'}
                        </ToastBody>
                    </Toast>,
                    { intent: 'error' }
                );
            }
        }
    }, [fetchPlans, dispatchToast]);

    /**
     * Handle new task creation - placeholder for future implementation
     */
    const handleNewTask = useCallback((taskName: string) => {
        console.log('Creating new task:', taskName);
        // TODO: Implement task creation functionality
        // This would typically involve:
        // 1. Opening a modal or navigation to task creation form
        // 2. Calling apiService.submitInputTask() with user input
        // 3. Refreshing the task lists after creation

        dispatchToast(
            <Toast>
                <ToastTitle>New Task</ToastTitle>
                <ToastBody>Task creation functionality coming soon</ToastBody>
            </Toast>,
            { intent: 'info' }
        );
    }, [dispatchToast]);

    /**
     * Handle task selection - navigate to task details
     */
    const handleTaskSelect = useCallback((taskId: string) => {
        console.log('Selected task ID:', taskId);

        // Find the plan by session_id to get the plan_id
        const selectedPlan = plans?.find(plan => plan.session_id === taskId);
        if (selectedPlan) {
            navigate(`/plan/${selectedPlan.id}`);
        } else {
            dispatchToast(
                <Toast>
                    <ToastTitle>
                        <ErrorCircle20Regular />
                        Task not found
                    </ToastTitle>
                    <ToastBody>Unable to locate the selected task</ToastBody>
                </Toast>,
                { intent: 'error' }
            );
        }
    }, [plans, navigate, dispatchToast]);    // Transform plans data when it changes
    useEffect(() => {
        if (plans) {
            const { inProgress, completed } = TaskService.transformPlansToTasks(plans);
            setInProgressTasks(inProgress);
            setCompletedTasks(completed);
        }
    }, [plans]);

    // Initial data load
    useEffect(() => {
        loadPlansData();
    }, [loadPlansData]);

    // Handle API errors
    useEffect(() => {
        if (plansError) {
            dispatchToast(
                <Toast>
                    <ToastTitle>
                        <ErrorCircle20Regular />
                        Failed to load tasks
                    </ToastTitle>
                    <ToastBody>
                        {plansError.message}
                    </ToastBody>
                </Toast>,
                { intent: 'error' }
            );
        }
    }, [plansError, dispatchToast]);

    return (
        <>
            <Toaster toasterId="toast" />
            <CoralShellColumn>
                <CoralShellRow>
                    <div style={{ flexShrink: 0, display: "flex", overflow: "hidden" }}>
                        <PanelLeft
                            panelWidth={280}
                            panelResize={true}>
                            <PanelLeftToolbar panelTitle="Tasks" panelIcon={null}>
                                <Button
                                    icon={<Add20Regular />}
                                    onClick={() => handleNewTask("New task")}
                                    disabled={plansLoading}
                                >
                                    New task
                                </Button>
                            </PanelLeftToolbar>
                            {plansLoading && (!inProgressTasks.length && !completedTasks.length) ? (
                                <div style={{ padding: '20px', textAlign: 'center' }}>
                                    <Spinner size="medium" label="Loading tasks..." />
                                </div>
                            ) : (
                                <TaskList
                                    inProgressTasks={inProgressTasks}
                                    completedTasks={completedTasks}
                                    onTaskSelect={handleTaskSelect}
                                />
                            )}
                        </PanelLeft>
                        <Content>
                            <div style={{ padding: '20px' }}>
                                <Text size={600} weight="semibold">
                                    Welcome to MACAE
                                </Text>
                                <Text as="p" style={{ marginTop: '10px' }}>
                                    Select a task from the sidebar to view its details, or create a new task to get started.
                                </Text>

                                {/* Task statistics */}
                                <div style={{ marginTop: '20px', display: 'flex', gap: '20px' }}>
                                    <div>
                                        <Text size={400} weight="semibold">
                                            {inProgressTasks.length}
                                        </Text>
                                        <Text as="p" size={200}>
                                            In Progress
                                        </Text>
                                    </div>
                                    <div>
                                        <Text size={400} weight="semibold">
                                            {completedTasks.length}
                                        </Text>
                                        <Text as="p" size={200}>
                                            Completed
                                        </Text>
                                    </div>
                                </div>

                                {/* Refresh button */}
                                <Button
                                    style={{ marginTop: '20px' }}
                                    disabled={plansLoading}
                                    onClick={() => loadPlansData(true)}
                                >
                                    {plansLoading ? <Spinner size="tiny" /> : 'Refresh Tasks'}
                                </Button>
                            </div>
                        </Content>
                    </div>
                </CoralShellRow>
            </CoralShellColumn>
        </>
    );
};

export default HomePage;