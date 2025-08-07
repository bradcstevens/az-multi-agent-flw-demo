import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Button,
    Spinner,
    Toast,
    ToastTitle,
    ToastBody,
    useToastController,
    Toaster
} from '@fluentui/react-components';
import {
    Add20Regular,
    ErrorCircle20Regular,
    Sparkle20Filled
} from '@fluentui/react-icons';
import '../styles/PlanPage.css';
import CoralShellColumn from '../coral/components/Layout/CoralShellColumn';
import CoralShellRow from '../coral/components/Layout/CoralShellRow';
import Content from '../coral/components/Content/Content';
import HomeInput from '@/components/content/HomeInput';
import { NewTaskService } from '../services/NewTaskService';
import PlanPanelLeft from '@/components/content/PlanPanelLeft';
import ContentToolbar from '@/coral/components/Content/ContentToolbar';
import { TaskService } from '../services/TaskService';
import { TeamConfig } from '../models/Team';

/**
 * HomePage component - displays task lists and provides navigation
 * Accessible via the route "/"
 */
const HomePage: React.FC = () => {
    const navigate = useNavigate();
    const { dispatchToast } = useToastController("toast");
    const [selectedTeam, setSelectedTeam] = useState<TeamConfig | null>(null);

    /**
    * Handle new task creation from the "New task" button
    * Resets textarea to empty state on HomePage
    */
    const handleNewTaskButton = useCallback(() => {
        NewTaskService.handleNewTaskFromHome();
    }, []);

    /**
     * Handle team selection from the Settings button
     */
    const handleTeamSelect = useCallback((team: TeamConfig) => {
        setSelectedTeam(team);
        dispatchToast(
            <Toast>
                <ToastTitle>Team Selected</ToastTitle>
                <ToastBody>
                    {team.name} team has been selected with {team.agents.length} agents
                </ToastBody>
            </Toast>,
            { intent: "success" }
        );
    }, [dispatchToast]);

    /**
     * Handle new task creation from input submission
     * Creates a plan and navigates to the create plan page
     */
    const handleNewTask = useCallback(async (taskName: string) => {
        if (taskName.trim()) {
            try {
                const response = await TaskService.createPlan(taskName.trim());
                
                if (response.plan_id && response.plan_id !== null) {
                    dispatchToast(
                        <Toast>
                            <ToastTitle>Plan Created!</ToastTitle>
                            <ToastBody>
                                Successfully created plan for: {taskName}
                                {selectedTeam && ` using ${selectedTeam.name} team`}
                            </ToastBody>
                        </Toast>,
                        { intent: "success" }
                    );
                    navigate(`/plan/${response.plan_id}/create`);
                } else {
                    dispatchToast(
                        <Toast>
                            <ToastTitle>
                                <ErrorCircle20Regular />
                                Failed to create plan
                            </ToastTitle>
                            <ToastBody>Unable to create plan. Please try again.</ToastBody>
                        </Toast>,
                        { intent: "error" }
                    );
                }
            } catch (error: any) {
                console.error('Error creating plan:', error);
                dispatchToast(
                    <Toast>
                        <ToastTitle>
                            <ErrorCircle20Regular />
                            Error creating plan
                        </ToastTitle>
                        <ToastBody>{error.message || 'Something went wrong'}</ToastBody>
                    </Toast>,
                    { intent: "error" }
                );
            }
        }
    }, [navigate, dispatchToast, selectedTeam]);

    return (
        <>
            <Toaster toasterId="toast" />
            <CoralShellColumn>
                <CoralShellRow>
                    <PlanPanelLeft
                        onNewTaskButton={handleNewTaskButton}
                        onTeamSelect={handleTeamSelect}
                        selectedTeam={selectedTeam}
                    />
                    <Content>
                        <ContentToolbar
                            panelTitle={"Multi-Agent Planner"}
                        ></ContentToolbar>
                        <HomeInput
                            onInputSubmit={handleNewTask}
                            onQuickTaskSelect={handleNewTask}
                            selectedTeam={selectedTeam}
                        />
                    </Content>

                </CoralShellRow>
            </CoralShellColumn>
        </>
    );
};

export default HomePage;