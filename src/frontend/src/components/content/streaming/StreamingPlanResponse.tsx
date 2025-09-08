import { MPlanData } from "@/models";
import { 
    Button, 
    Text, 
    Title3, 
    Body1, 
    Caption1,
    Badge,
    makeStyles,
    tokens
} from "@fluentui/react-components";
import { 
    BotRegular, 
    Copy20Regular, 
    InfoRegular, 
    ClockRegular,
    CheckmarkCircle20Regular 
} from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import React, { useState } from 'react';

// FluentUI styles using design tokens with 14px max font size
const useStyles = makeStyles({
    container: {
        maxWidth: '800px',
        margin: '0 auto',
        padding: `${tokens.spacingVerticalXXL} ${tokens.spacingHorizontalXL}`,
        backgroundColor: tokens.colorNeutralBackground1,
        fontFamily: tokens.fontFamilyBase
    },
    agentHeader: {
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacingHorizontalM,
        marginBottom: tokens.spacingVerticalXL,
        padding: tokens.spacingVerticalM,
        backgroundColor: tokens.colorNeutralBackground2,
        borderRadius: tokens.borderRadiusMedium
    },
    agentAvatar: {
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        backgroundColor: tokens.colorBrandForeground1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
    },
    agentInfo: {
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacingHorizontalM,
        flex: 1
    },
    agentName: {
        fontSize: '14px',
        fontWeight: tokens.fontWeightSemibold,
        color: tokens.colorNeutralForeground1,
        lineHeight: tokens.lineHeightBase400
    },
    botBadge: {
        border: 'none',
        fontSize: '11px',
        fontWeight: tokens.fontWeightSemibold,
        textTransform: 'uppercase',
        letterSpacing: '0.5px'
    },
    factsSection: {
        marginBottom: tokens.spacingVerticalXL,
        marginLeft: `calc(32px + ${tokens.spacingHorizontalM} + ${tokens.spacingVerticalM})`,
        backgroundColor: tokens.colorNeutralBackground2,
        border: `1px solid ${tokens.colorNeutralStroke1}`,
        borderRadius: '8px',
        padding: '16px'
    },
    factsHeader: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px'
    },
    factsHeaderLeft: {
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
    },
    factsTitle: {
        fontWeight: '500',
        color: tokens.colorNeutralForeground1,
        fontSize: '14px',
        lineHeight: '20px'
    },
    factsButton: {
        backgroundColor: tokens.colorNeutralBackground3,
        border: `1px solid ${tokens.colorNeutralStroke2}`,
        borderRadius: '16px',
        padding: '4px 12px',
        fontSize: '12px'
    },
    factsPreview: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: '8px',
        marginLeft: '32px'
    },
    factsContent: {
        padding: '12px',
        marginTop: '8px',
        fontSize: '14px',
        lineHeight: '1.4'
    },
    stepsList: {
        marginBottom: tokens.spacingVerticalXXL,
        marginLeft: `calc(32px + ${tokens.spacingHorizontalM} + ${tokens.spacingVerticalM})`
    },
    stepItem: {
        marginBottom: tokens.spacingVerticalL,
        display: 'flex',
        alignItems: 'flex-start',
        gap: tokens.spacingHorizontalS
    },
    stepNumber: {
        fontSize: '14px',
        fontWeight: tokens.fontWeightSemibold,
        color: tokens.colorNeutralForeground1,
        minWidth: '24px',
        flexShrink: 0,
        marginTop: '2px'
    },
    stepHeading: {
        marginBottom: tokens.spacingVerticalM,
        marginLeft: `calc(32px + ${tokens.spacingHorizontalM} + ${tokens.spacingVerticalM})`,
        fontSize: '14px',
        fontWeight: tokens.fontWeightSemibold,
        color: tokens.colorNeutralForeground1,
        lineHeight: '1.5'
    },
    stepText: {
        fontSize: '14px',
        color: tokens.colorNeutralForeground1,
        lineHeight: '1.5',
        flex: 1,
        wordWrap: 'break-word',
        overflowWrap: 'break-word'
    },
    instructionText: {
        marginBottom: tokens.spacingVerticalXL,
        color: tokens.colorNeutralForeground2,
        fontSize: '14px',
        lineHeight: tokens.lineHeightBase400,
        textAlign: 'left',
        marginLeft: `calc(32px + ${tokens.spacingHorizontalM} + ${tokens.spacingVerticalM})`
    },
    buttonContainer: {
        display: 'flex',
        gap: tokens.spacingHorizontalM,
        paddingTop: tokens.spacingVerticalM,
        alignItems: 'center',
        justifyContent: 'flex-start',
        marginLeft: `calc(32px + ${tokens.spacingHorizontalM} + ${tokens.spacingVerticalM})`
    }
});

// Function to get agent name from backend data
const getAgentDisplayName = (planApprovalRequest: MPlanData | null): string => {
    if (planApprovalRequest?.steps?.length) {
        const firstAgent = planApprovalRequest.steps.find(step => step.agent)?.agent;
        if (firstAgent) {
            return firstAgent.replace(/Agent$/, '').replace(/([A-Z])/g, ' $1').trim();
        }
    }
    return 'Assistant';
};

// Dynamically extract content from whatever fields contain data
const extractDynamicContent = (planApprovalRequest: MPlanData): { 
    factsContent: string; 
    planSteps: Array<{ type: 'heading' | 'substep'; text: string }> 
} => {
    if (!planApprovalRequest) return { factsContent: '', planSteps: [] };

    let factsContent = '';
    let planSteps: Array<{ type: 'heading' | 'substep'; text: string }> = [];

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

    // Extract plan steps from multiple possible sources
    if (planApprovalRequest.steps && planApprovalRequest.steps.length > 0) {
        planApprovalRequest.steps.forEach(step => {
            // Use whichever action field has content
            const action = step.action || step.cleanAction || '';
            if (action.trim()) {
                // Check if it ends with colon (heading) or is a regular step
                if (action.trim().endsWith(':')) {
                    planSteps.push({ type: 'heading', text: action.trim() });
                } else {
                    planSteps.push({ type: 'substep', text: action.trim() });
                }
            }
        });
    }

    // If no steps found in steps array, try to extract from other fields
    if (planSteps.length === 0) {
        // Look in user_request or facts for plan content
        const searchContent = planApprovalRequest.user_request || planApprovalRequest.facts || '';
        const lines = searchContent.split('\n');
        
        for (const line of lines) {
            const trimmedLine = line.trim();
            
            // Skip empty lines and section headers
            if (!trimmedLine || 
                trimmedLine.toLowerCase().includes('plan created') ||
                trimmedLine.toLowerCase().includes('user request') ||
                trimmedLine.toLowerCase().includes('team assembly') ||
                trimmedLine.toLowerCase().includes('fact sheet')) {
                continue;
            }
            
            // Look for bullet points, dashes, or numbered items
            if (trimmedLine.match(/^[-•*]\s+/) || 
                trimmedLine.match(/^\d+\.\s+/) ||
                trimmedLine.match(/^[a-zA-Z][\w\s]*:$/)) {
                
                // Remove bullet/number prefixes for clean display
                let cleanText = trimmedLine
                    .replace(/^[-•*]\s+/, '')
                    .replace(/^\d+\.\s+/, '')
                    .trim();
                
                if (cleanText.length > 3) {
                    // Determine if it's a heading (ends with colon) or substep
                    if (cleanText.endsWith(':')) {
                        planSteps.push({ type: 'heading', text: cleanText });
                    } else {
                        planSteps.push({ type: 'substep', text: cleanText });
                    }
                }
            }
        }
    }

    return { factsContent, planSteps };
};

// Process facts for preview
const getFactsPreview = (content: string): string => {
    if (!content) return '';
    return content.length > 200 ? content.substring(0, 200) + "..." : content;
};

// FluentUI-based plan response component
const renderPlanResponse = (
    planApprovalRequest: MPlanData | null, 
    handleApprovePlan: () => void, 
    handleRejectPlan: () => void, 
    processingApproval: boolean, 
    showApprovalButtons: boolean
) => {
    const styles = useStyles();
    const [isFactsExpanded, setIsFactsExpanded] = useState(false);
    
    if (!planApprovalRequest) return null;

    const agentName = getAgentDisplayName(planApprovalRequest);
    const { factsContent, planSteps } = extractDynamicContent(planApprovalRequest);
    const factsPreview = getFactsPreview(factsContent);

    let stepCounter = 0;

    return (
        <div className={styles.container}>
            {/* Agent Header */}
            <div className={styles.agentHeader}>
                <div className={styles.agentAvatar}>
                    <BotRegular style={{ fontSize: '16px', color: tokens.colorNeutralForeground2 }} />
                </div>
                <div className={styles.agentInfo}>
                    <Text className={styles.agentName}>
                        {agentName}
                    </Text>
                    <Badge 
                        appearance="filled" 
                        size="small"
                        className={styles.botBadge}
                    >
                        BOT
                    </Badge>
                </div>
            </div>

            {/* Facts Section */}
            {factsContent && (
                <div className={styles.factsSection}>
                    <div className={styles.factsHeader}>
                        <div className={styles.factsHeaderLeft}>
                            <CheckmarkCircle20Regular style={{
                                color: tokens.colorNeutralForeground2,
                                fontSize: '20px',
                                width: '20px',
                                height: '20px',
                                flexShrink: 0
                            }} />
                            <span className={styles.factsTitle}>
                                Analysis & Context
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
                            <div style={{
                                color: tokens.colorNeutralForeground2,
                                fontSize: '14px',
                                lineHeight: '1.4'
                            }}>
                                {factsPreview}
                            </div>
                        </div>
                    )}
                    
                    {isFactsExpanded && (
                        <div className={styles.factsContent}>
                            <div style={{ whiteSpace: 'pre-wrap' }}>
                                {factsContent}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Plan Steps - Better formatting like the image */}
            {planSteps.length > 0 && (
                <div className={styles.stepsList}>
                    {planSteps.map((step, index) => {
                        if (step.type === 'heading') {
                            return (
                                <div key={index} className={styles.stepHeading}>
                                    {step.text}
                                </div>
                            );
                        } else {
                            stepCounter++;
                            return (
                                <div key={index} className={styles.stepItem}>
                                    <div className={styles.stepNumber}>
                                        {stepCounter}.
                                    </div>
                                    <div className={styles.stepText}>
                                        {step.text}
                                    </div>
                                </div>
                            );
                        }
                    })}
                </div>
            )}

            {/* Instruction Text */}
            <Body1 className={styles.instructionText}>
                If the plan looks good we can move forward with the first step.
            </Body1>

            {/* Action Buttons */}
            {showApprovalButtons && (
                <div className={styles.buttonContainer}>
                    <Button
                        appearance="primary"
                        size="medium"
                        onClick={handleApprovePlan}
                        disabled={processingApproval}
                        style={{ fontSize: '14px' }}
                    >
                        {processingApproval ? 'Processing...' : 'Approve Task Plan'}
                    </Button>
                    <Button
                        appearance="secondary"
                        size="medium"
                        onClick={handleRejectPlan}
                        disabled={processingApproval}
                        style={{ fontSize: '14px' }}
                    >
                        Cancel
                    </Button>
                </div>
            )}
        </div>
    );
};

export default renderPlanResponse;