import React, { useState } from 'react';
import {
    Button,
} from '@fluentui/react-components';
import { ChevronRightRegular, ChevronDownRegular, CheckmarkCircle20Regular, ArrowTurnDownRightRegular } from '@fluentui/react-icons';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";

const renderBufferMessage = (streamingMessageBuffer: string) => {
    const [isExpanded, setIsExpanded] = useState<boolean>(false);

    if (!streamingMessageBuffer || streamingMessageBuffer.trim() === "") return null;

    const start = Math.max(0, streamingMessageBuffer.length - 500);
    const previewText = start === 0
        ? streamingMessageBuffer
        : "..." + streamingMessageBuffer.substring(start);

    return (
        <div style={{
            maxWidth: '800px',
            margin: '0 auto 32px auto',
            padding: '0 24px'
        }}>
            <div style={{
                backgroundColor: 'var(--colorNeutralBackground2)',
                border: '1px solid var(--colorNeutralStroke2)',
                borderRadius: '8px',
                padding: '16px',
                fontSize: '14px',
                lineHeight: '1.5'
            }}>
                {/* Header */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: isExpanded ? '16px' : '8px'
                }}>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px'
                    }}>
                        <CheckmarkCircle20Regular style={{
                            fontSize: '20px',
                            color: 'var(--colorNeutralForeground1)',
                            width: '20px',
                            height: '20px',
                            flexShrink: 0
                        }} />
                        <span style={{
                            fontWeight: '500',
                            color: 'var(--colorNeutralForeground1)',
                            fontSize: '14px',
                            lineHeight: '20px'
                        }}>
                            AI Thinking Process
                        </span>
                    </div>

                    <Button
                        appearance="secondary"
                        size="small"
                        onClick={() => setIsExpanded(!isExpanded)}
                        style={{
                            backgroundColor: 'var(--colorNeutralBackground3)',
                            border: '1px solid var(--colorNeutralStroke2)',
                            borderRadius: '16px',
                            padding: '4px 12px',
                            fontSize: '14px'
                        }}
                    >
                        Details
                    </Button>
                </div>

                {/* Preview content when collapsed */}
                {!isExpanded && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '8px',
                        marginLeft: '32px'
                    }}>
                        <ArrowTurnDownRightRegular style={{
                            color: 'var(--colorNeutralForeground3)',
                            fontSize: '14px',
                            marginTop: '2px',
                            flexShrink: 0
                        }} />
                        <div style={{
                            color: 'var(--colorNeutralForeground2)',
                            fontSize: '14px',
                            lineHeight: '1.4'
                        }}>
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                rehypePlugins={[rehypePrism]}
                                components={{
                                    a: ({ node, ...props }) => (
                                        <a
                                            {...props}
                                            style={{
                                                color: 'var(--colorNeutralBrandForeground1)',
                                                textDecoration: 'none'
                                            }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.textDecoration = 'underline';
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.textDecoration = 'none';
                                            }}
                                        />
                                    )
                                }}
                            >
                                {previewText}
                            </ReactMarkdown>
                        </div>
                    </div>
                )}

                {/* Full content when expanded */}
                {isExpanded && (
                    <div style={{
                        padding: '12px',
                        marginTop: '8px'
                    }}>
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypePrism]}
                        >
                            {streamingMessageBuffer}
                        </ReactMarkdown>
                    </div>
                )}
            </div>
        </div>
    );
};

export default renderBufferMessage;