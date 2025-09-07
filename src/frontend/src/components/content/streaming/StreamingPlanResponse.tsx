import { MPlanData } from "@/models";
import { Button, Spinner, Tag } from "@fluentui/react-components";
import { BotRegular, CheckmarkRegular, DismissRegular } from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
// Render the complete plan with all information
const renderPlanResponse = (planApprovalRequest: MPlanData | null, handleApprovePlan: () => void, handleRejectPlan: () => void, processingApproval: boolean,) => {
    if (!planApprovalRequest) return null;

    return (
        <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '16px',
            marginBottom: '32px',
            padding: '0 24px'
        }}>
            {/* AI Avatar */}
            <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: 'var(--colorNeutralBackground3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
            }}>
                <BotRegular style={{ fontSize: '16px', color: 'var(--colorNeutralForeground2)' }} />
            </div>

            {/* Plan Content */}
            <div style={{ flex: 1, maxWidth: 'calc(100% - 48px)' }}>

                {/* Plan Header */}
                <div style={{
                    marginBottom: '24px',
                    borderBottom: '1px solid var(--colorNeutralStroke2)',
                    paddingBottom: '16px'
                }}>
                    <h3 style={{
                        margin: '0 0 8px 0',
                        fontSize: '20px',
                        fontWeight: '600',
                        color: 'var(--colorNeutralForeground1)'
                    }}>
                        📋 Plan Generated
                    </h3>
                    <div style={{
                        display: 'flex',
                        gap: '12px',
                        alignItems: 'center',
                        fontSize: '14px',
                        color: 'var(--colorNeutralForeground2)'
                    }}>
                        <span>Plan ID: {planApprovalRequest.id}</span>
                        <Tag size="extra-small" appearance="outline">
                            {planApprovalRequest.status?.replace(/^.*'([^']*)'.*$/, '$1') || planApprovalRequest.status || 'PENDING_APPROVAL'}
                        </Tag>
                    </div>
                </div>

                {/* Analysis Section */}
                {planApprovalRequest.facts && (
                    <div style={{ marginBottom: '28px' }}>
                        <h4 style={{
                            margin: '0 0 12px 0',
                            fontSize: '16px',
                            fontWeight: '600',
                            color: 'var(--colorNeutralForeground1)'
                        }}>
                            🔍 Analysis & Context
                        </h4>
                        <div style={{
                            padding: '20px',
                            backgroundColor: 'var(--colorNeutralBackground2)',
                            borderRadius: '12px',
                            border: '1px solid var(--colorNeutralStroke2)',
                            fontSize: '15px',
                            lineHeight: '1.6'
                        }}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {planApprovalRequest.facts}
                            </ReactMarkdown>
                        </div>
                    </div>
                )}

                {/* Action Steps */}
                {planApprovalRequest.steps && planApprovalRequest.steps.length > 0 && (
                    <div style={{ marginBottom: '28px' }}>
                        <h4 style={{
                            margin: '0 0 16px 0',
                            fontSize: '16px',
                            fontWeight: '600',
                            color: 'var(--colorNeutralForeground1)'
                        }}>
                            📝 Action Plan ({planApprovalRequest.steps.length} steps)
                        </h4>
                        <div style={{
                            backgroundColor: 'var(--colorNeutralBackground1)',
                            borderRadius: '12px',
                            border: '1px solid var(--colorNeutralStroke2)',
                            overflow: 'hidden'
                        }}>
                            {planApprovalRequest.steps.map((step, index) => (
                                <div
                                    key={index}
                                    style={{
                                        padding: '20px',
                                        borderBottom: index < planApprovalRequest.steps.length - 1 ? '1px solid var(--colorNeutralStroke2)' : 'none',
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: '16px'
                                    }}
                                >
                                    <div style={{
                                        width: '28px',
                                        height: '28px',
                                        borderRadius: '50%',
                                        backgroundColor: 'var(--colorBrandBackground)',
                                        color: 'white',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '14px',
                                        fontWeight: '600',
                                        flexShrink: 0
                                    }}>
                                        {step.id}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <div style={{
                                            fontSize: '15px',
                                            lineHeight: '1.6',
                                            marginBottom: step.agent && step.agent !== 'System' ? '8px' : '0'
                                        }}>
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {step.cleanAction || step.action}
                                            </ReactMarkdown>
                                        </div>
                                        {step.agent && step.agent !== 'System' && (
                                            <Tag size="small" appearance="brand">
                                                {step.agent}
                                            </Tag>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Team Assignment */}
                {planApprovalRequest.team && planApprovalRequest.team.length > 0 && (
                    <div style={{ marginBottom: '28px' }}>
                        <h4 style={{
                            margin: '0 0 12px 0',
                            fontSize: '16px',
                            fontWeight: '600',
                            color: 'var(--colorNeutralForeground1)'
                        }}>
                            👥 Assigned Team
                        </h4>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            {planApprovalRequest.team.map((member, index) => (
                                <Tag key={index} size="medium" appearance="brand">
                                    {member}
                                </Tag>
                            ))}
                        </div>
                    </div>
                )}

                {/* Agent Capabilities */}
                {planApprovalRequest.context?.participant_descriptions &&
                    Object.keys(planApprovalRequest.context.participant_descriptions).length > 0 && (
                        <div style={{ marginBottom: '28px' }}>
                            <h4 style={{
                                margin: '0 0 12px 0',
                                fontSize: '16px',
                                fontWeight: '600',
                                color: 'var(--colorNeutralForeground1)'
                            }}>
                                Agent Capabilities
                            </h4>
                            <div style={{
                                padding: '16px',
                                backgroundColor: 'var(--colorNeutralBackground2)',
                                borderRadius: '12px',
                                border: '1px solid var(--colorNeutralStroke2)',
                                fontSize: '14px'
                            }}>
                                {Object.entries(planApprovalRequest.context.participant_descriptions).map(([agent, description]) => (
                                    <div key={agent} style={{ marginBottom: '12px' }}>
                                        <div style={{ fontWeight: '600', marginBottom: '4px' }}>{agent}:</div>
                                        <div style={{ color: 'var(--colorNeutralForeground2)' }}>{description}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}


                {/* Action Buttons - Separate section */}
                <div style={{
                    display: 'flex',
                    gap: '12px',
                    alignItems: 'center',
                    padding: '20px',
                    backgroundColor: 'var(--colorNeutralBackground2)',
                    borderRadius: '12px',
                    border: '1px solid var(--colorNeutralStroke2)',
                    marginTop: '20px'
                }}>
                    <div style={{
                        flex: 1,
                        fontSize: '14px',
                        color: 'var(--colorNeutralForeground2)'
                    }}>
                        <span>Ready for approval</span>

                    </div>

                    <Button
                        appearance="primary"
                        icon={processingApproval ? <Spinner size="extra-tiny" /> : <CheckmarkRegular />}
                        onClick={handleApprovePlan}
                        disabled={processingApproval}
                        size="medium"
                        style={{ minWidth: '140px' }}
                    >
                        {processingApproval ? 'Processing...' : 'Approve'}
                    </Button>
                    <Button
                        appearance="outline"
                        icon={<DismissRegular />}
                        onClick={handleRejectPlan}
                        disabled={processingApproval}
                        size="medium"
                        style={{ minWidth: '100px' }}
                    >
                        Cancel
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default renderPlanResponse;