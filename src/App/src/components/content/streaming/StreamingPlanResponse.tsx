import { MPlanData } from "@/models";
import { 
    Button, 
    Text,  
    Body1, 
    Tag,
    makeStyles,
    tokens
} from "@fluentui/react-components";
import { 
    CheckmarkCircle20Regular 
} from "@fluentui/react-icons";
import React, { useState } from 'react';
import { getAgentIcon, getAgentDisplayNameWithSuffix } from '@/utils/agentIconUtils';
import { PLAN_ARRIVING } from '@/models/progressNarration';
import { SECTION_HEADING } from '@/models/headingOutline';
import { revisionSuggestionsFor, reviewablePlanSteps } from '@/models/reviewablePlan';

// Updated styles to match consistent spacing and remove brand colors from bot elements
const useStyles = makeStyles({
    container: {
        maxWidth: '800px',
        margin: '0 auto 32px auto',
        padding: '0 24px',
        fontFamily: tokens.fontFamilyBase
    },
    agentHeader: {
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        marginBottom: '8px'
    },
    agentAvatar: {
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        backgroundColor: 'var(--colorNeutralBackground3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
    },
    hiddenAvatar: {
        width: '32px',
        height: '32px',
        visibility: 'hidden',
        flexShrink: 0
    },
    agentInfo: {
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        flex: 1
    },
    agentName: {
        fontSize: '14px',
        fontWeight: '600',
        color: 'var(--colorNeutralForeground1)',
        lineHeight: '20px'
    },
    messageContainer: {
        backgroundColor: 'var(--colorNeutralBackground2)',
        padding: '12px 16px',
        borderRadius: '8px',
        fontSize: '14px',
        lineHeight: '1.5',
        wordWrap: 'break-word',
        marginLeft: '48px',
        boxSizing: 'border-box'
    },
    factsSection: {
        backgroundColor: 'var(--colorNeutralBackground2)',
        border: '1px solid var(--colorNeutralStroke2)',
        borderRadius: '8px',
        padding: '16px',
        marginBottom: '16px'
    },
    factsHeader: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '12px'
    },
    factsHeaderLeft: {
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
    },
    factsTitle: {
        fontWeight: '500',
        color: 'var(--colorNeutralForeground1)',
        fontSize: '14px',
        lineHeight: '20px'
    },
    factsButton: {
        backgroundColor: 'var(--colorNeutralBackground3)',
        border: '1px solid var(--colorNeutralStroke2)',
        borderRadius: '16px',
        padding: '4px 12px',
        fontSize: '14px',
        fontWeight: '500',
        cursor: 'pointer'
    },
    factsPreview: {
        fontSize: '14px',
        lineHeight: '1.4',
        color: 'var(--colorNeutralForeground2)',
        marginTop: '8px'
    },
    factsContent: {
        fontSize: '14px',
        lineHeight: '1.5',
        color: 'var(--colorNeutralForeground2)',
        marginTop: '8px',
        whiteSpace: 'pre-wrap'
    },
    planTitle: {
        marginBottom: '20px',
        fontSize: '18px',
        fontWeight: '600',
        color: 'var(--colorNeutralForeground1)',
        lineHeight: '24px'
    },
    stepsList: {
        marginBottom: '16px'
    },
    stepItem: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        marginBottom: '12px'
    },
    stepNumber: {
        minWidth: '24px',
        height: '24px',
        borderRadius: '50%',
        backgroundColor: 'var(--colorNeutralBackground3)',
        border: '1px solid var(--colorNeutralStroke2)',
        color: 'var(--colorNeutralForeground1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '12px',
        fontWeight: '600',
        flexShrink: 0,
        marginTop: '2px'
    },
    stepText: {
        fontSize: '14px',
        color: 'var(--colorNeutralForeground1)',
        lineHeight: '1.5',
        flex: 1,
        wordWrap: 'break-word',
        overflowWrap: 'break-word'
    },
    stepRole: {
        display: 'block',
        fontSize: '12px',
        fontWeight: '600',
        color: 'var(--colorNeutralForeground2)',
        lineHeight: '16px',
        marginBottom: '4px',
    },
    stepDetail: {
        display: 'block',
        color: 'var(--colorNeutralForeground2)',
        marginTop: '4px',
    },
    instructionText: {
        color: 'var(--colorNeutralForeground2)',
        fontSize: '14px',
        lineHeight: '1.5',
        marginBottom: '16px'
    },
    buttonContainer: {
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        marginTop: '20px'
    }
});

// Function to get agent name from backend data using the centralized utility
const getAgentDisplayNameFromPlan = (planApprovalRequest: MPlanData | null): string => {
    if (planApprovalRequest?.steps?.length) {
        const firstAgent = planApprovalRequest.steps.find(step => step.agent)?.agent;
        if (firstAgent) {
            return getAgentDisplayNameWithSuffix(firstAgent);
        }
    }
    return getAgentDisplayNameWithSuffix('Planning Agent');
};

const extractDynamicContent = (planApprovalRequest: MPlanData) => {
    if (!planApprovalRequest) return { factsContent: '', planSteps: [] };

    let factsContent = '';

    // Build facts content from available sources
    const factsSources: string[] = [];

    // Add team assembly if available
    if (planApprovalRequest.context?.participant_descriptions && 
        Object.keys(planApprovalRequest.context.participant_descriptions).length > 0) {
        let teamContent = 'Team Assembly:\n\n';
        Object.entries(planApprovalRequest.context.participant_descriptions).forEach(([agent, description]) => {
            teamContent += `${agent}: ${description}\n\n`;
        });
        factsSources.push(teamContent);
    }

    // Add facts field if it contains substantial content
    if (planApprovalRequest.facts && planApprovalRequest.facts.trim().length > 10) {
        factsSources.push(planApprovalRequest.facts.trim());
    }

    // Combine all facts sources
    factsContent = factsSources.join('\n---\n\n');

    return {
        factsContent,
        planSteps: reviewablePlanSteps(planApprovalRequest.steps).filter((step) => step.action.trim()),
    };
};

// Process facts for preview
const getFactsPreview = (content: string): string => {
    if (!content) return '';
    return content.length > 200 ? content.substring(0, 200) + "..." : content;
};

// FluentUI-based plan response component with consistent spacing and proper colors
const renderPlanResponse = (
    planApprovalRequest: MPlanData | null, 
    handleApprovePlan: () => void, 
    handleRejectPlan: (feedback: string) => void, 
    processingApproval: boolean, 
    showApprovalButtons: boolean
) => {
    const styles = useStyles();
    const [isFactsExpanded, setIsFactsExpanded] = useState(false);
    
    if (!planApprovalRequest) return null;

    const agentName = getAgentDisplayNameFromPlan(planApprovalRequest);
    const { factsContent, planSteps } = extractDynamicContent(planApprovalRequest);
    const factsPreview = getFactsPreview(factsContent);
    const [feedback, setFeedback] = useState('');
    const revision = planApprovalRequest.revision ?? 1;
    const feedbackHistory = planApprovalRequest.revision_feedback ?? [];
    const suggestions = revisionSuggestionsFor(planApprovalRequest.steps);

    // Check if this is a "creating plan" state
    const isCreatingPlan = !planSteps.length && !factsContent;

    let stepCounter = 0;

    return (
        <div className={styles.container}>
            {/* Agent Header */}
            <div className={styles.agentHeader}>
                {/* Hide avatar when creating plan */}
                {isCreatingPlan ? (
                    <div className={styles.hiddenAvatar}></div>
                ) : (
                    <div className={styles.agentAvatar}>
                        {getAgentIcon(agentName, null, planApprovalRequest)}
                    </div>
                )}
                <div className={styles.agentInfo}>
                    <Text className={styles.agentName}>
                        {agentName}
                    </Text>
                    {!isCreatingPlan && (
                        <Tag 
                            appearance="brand"
                        >
                            AI Agent
                        </Tag>
                    )}
                </div>
            </div>

            {/* Message Container */}
            <div className={styles.messageContainer}>
                {/* Facts Section */}
                {factsContent && (
                    <div className={styles.factsSection}>
                        <div className={styles.factsHeader}>
                            <div className={styles.factsHeaderLeft}>
                                <CheckmarkCircle20Regular style={{
                                    color: 'var(--colorPaletteGreenForeground1)',
                                    fontSize: '20px',
                                    width: '20px',
                                    height: '20px',
                                    flexShrink: 0
                                }} />
                                <span className={styles.factsTitle}>
                                    Analysis
                                </span>
                            </div>
                            
                            <Button 
                                appearance="secondary" 
                                size="small"
                                onClick={() => setIsFactsExpanded(!isFactsExpanded)}
                                className={styles.factsButton}
                            >
                                {isFactsExpanded ? 'Hide' : 'Details'}
                            </Button>
                        </div>
                        
                        {!isFactsExpanded && (
                            <div className={styles.factsPreview}>
                                {factsPreview}
                            </div>
                        )}
                        
                        {isFactsExpanded && (
                            <div className={styles.factsContent}>
                                {factsContent}
                            </div>
                        )}
                    </div>
                )}

                {/* Plan Title */}
                <Body1 as={SECTION_HEADING} className={styles.planTitle}>
                    Plan Overview
                </Body1>
                {isCreatingPlan && <div className={styles.planTitle}>{PLAN_ARRIVING}</div>}
                {!isCreatingPlan && (
                    <div className={styles.planTitle}>
                        {`Proposed Plan for ${planApprovalRequest.user_request || 'Task'}`}
                    </div>
                )}
                {!isCreatingPlan && (
                    <div className={styles.instructionText}>
                        <strong>Revision {revision}</strong>
                        {feedbackHistory.length > 0 && (
                            <div>
                                What you asked to change: {feedbackHistory.at(-1)}
                            </div>
                        )}
                    </div>
                )}

                {/* Plan Steps */}
                {planSteps.length > 0 && (
                    <ol className={styles.stepsList} style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                        {planSteps.map((step, index) => {
                            stepCounter++;
                            return (
                                <li key={index} className={styles.stepItem}>
                                    <div className={styles.stepNumber}>
                                        {stepCounter}
                                    </div>
                                    <div className={styles.stepText}>
                                        <Text className={styles.stepRole}>{step.role}</Text>
                                        <div>{step.action}</div>
                                        <Text className={styles.stepDetail}>{step.assigneeDescription}</Text>
                                        {step.waitingDescription && (
                                            <Text className={styles.stepDetail}>{step.waitingDescription}</Text>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ol>
                )}

                {/* Instruction Text */}
                {!isCreatingPlan && (
                    <Body1 className={styles.instructionText}>
                        If the plan looks good we can move forward with the first step.
                    </Body1>
                )}

                {/* Action Buttons */}
                {showApprovalButtons && !isCreatingPlan && (
                    <div className={styles.buttonContainer}>
                        <Button
                            appearance="primary"
                            size="medium"
                            onClick={handleApprovePlan}
                            disabled={processingApproval}
                        >
                            {processingApproval ? 'Processing...' : 'Approve Task Plan'}
                        </Button>
                        <Button
                            appearance="secondary"
                            size="medium"
                            onClick={() => handleRejectPlan(feedback)}
                            disabled={processingApproval || !feedback.trim()}
                        >
                            Send back with feedback
                        </Button>
                    </div>
                )}
                {showApprovalButtons && !isCreatingPlan && (
                    <div className={styles.buttonContainer}>
                        {suggestions.map((suggestion) => (
                            <Button
                                key={suggestion}
                                appearance="secondary"
                                size="small"
                                onClick={() => setFeedback(suggestion)}
                                disabled={processingApproval}
                            >
                                {suggestion}
                            </Button>
                        ))}
                    </div>
                )}
                {showApprovalButtons && !isCreatingPlan && (
                    <label>
                        What would you change?
                        <textarea
                            aria-label="What would you change?"
                            value={feedback}
                            onChange={(event) => setFeedback(event.target.value)}
                            disabled={processingApproval}
                        />
                    </label>
                )}
            </div>
        </div>
    );
};

export default renderPlanResponse;