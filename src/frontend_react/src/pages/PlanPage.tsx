import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Button,
    Text,
    Card,
    CardHeader,
    useToastController,
    Spinner
} from '@fluentui/react-components';
import {
    Add20Regular,
    ArrowLeft24Regular,
    ErrorCircle24Regular
} from '@fluentui/react-icons';
import '../styles/PlanPage.css';
import CoralShellColumn from '../coral/components/Layout/CoralShellColumn';
import CoralShellRow from '../coral/components/Layout/CoralShellRow';
import Content from '../coral/components/Content/Content';
import PanelLeft from '../coral/components/Panels/PanelLeft';
import PanelLeftToolbar from '../coral/components/Panels/PanelLeftToolbar';
import TaskList from '../components/content/TaskList';
import { NewTaskService } from '../services/NewTaskService';
import { PlanWithSteps, Task } from '@/models';
import { apiService } from '@/api';
import PlanPanelLeft from '@/components/content/PlanPanelLeft';

/**
 * Page component for displaying a specific plan
 * Accessible via the route /plan/{plan_id}
 */
const PlanPage: React.FC = () => {
    const { planId } = useParams<{ planId: string }>();
    const navigate = useNavigate();




    const handleNewTaskButton = () => {
        // Use NewTaskService to handle navigation to homepage and reset textarea
        NewTaskService.handleNewTaskFromPlan(navigate);
    };

    // Show error if no planId is provided
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
                <PlanPanelLeft
                    onNewTaskButton={handleNewTaskButton}
                />
                <Content>

                </Content>

            </CoralShellRow>
        </CoralShellColumn>
    );
};

export default PlanPage;