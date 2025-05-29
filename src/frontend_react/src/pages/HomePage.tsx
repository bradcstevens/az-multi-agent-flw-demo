import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Button,
    Text,
    Card,
    CardHeader
} from '@fluentui/react-components';
import {
    ArrowLeft24Regular,
    ErrorCircle24Regular
} from '@fluentui/react-icons';
import PlanView from '../components/PlanView';
import '../styles/PlanPage.css';
import CoralShellColumn from '../coral/components/Layout/CoralShellColumn';
import CoralShellRow from '../coral/components/Layout/CoralShellRow';
import Content from '../coral/components/Content/Content';

/**
 * Page component for displaying a specific plan
 * Accessible via the route /plan/{plan_id}
 */
const HomePage: React.FC = () => {
    const { planId } = useParams<{ planId: string }>();
    const navigate = useNavigate();

    // Handle back navigation
    const handleBackClick = () => {
        navigate(-1);
    };

    // Show error if no planId is provided


    return (
        <CoralShellColumn>
            <CoralShellRow>
                <Content>

                </Content>

            </CoralShellRow>
        </CoralShellColumn>
    );
};

export default HomePage;