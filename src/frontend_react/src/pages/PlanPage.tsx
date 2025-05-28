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

/**
 * Page component for displaying a specific plan
 * Accessible via the route /plan/{plan_id}
 */
const PlanPage: React.FC = () => {
    const { planId } = useParams<{ planId: string }>();
    const navigate = useNavigate();

    // Handle back navigation
    const handleBackClick = () => {
        navigate(-1);
    };

    // Show error if no planId is provided
    if (!planId) {
        return (
            <div className="plan-page-container">
                <div className="plan-page-error">
                    <Card>
                        <CardHeader
                            header={
                                <div className="error-header">
                                    <ErrorCircle24Regular />
                                    <Text weight="semibold">Invalid Plan ID</Text>
                                </div>
                            }
                        />
                        <div className="card-content">
                            <Text>No plan ID was provided in the URL. Please check the URL and try again.</Text>
                        </div>
                    </Card>
                </div>
            </div>
        );
    }

    return (
        <div className="plan-page-container">
            <div className="plan-page-header">
                <Button
                    className="back-button"
                    appearance="subtle"
                    icon={<ArrowLeft24Regular />}
                    onClick={handleBackClick}
                >
                    Back
                </Button>
                <Text className="page-title" size={800} weight="bold">
                    Plan Details
                </Text>
            </div>

            <div className="plan-page-content">
                <PlanView
                    sessionId="default" // TODO: Get from context/state management
                    planId={planId}
                />
            </div>
        </div>
    );
};

export default PlanPage;