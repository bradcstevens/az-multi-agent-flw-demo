import React, { useState } from 'react';
import {
    Button,
} from '@fluentui/react-components';
import { ChevronRightRegular, ChevronDownRegular, CheckmarkCircle20Regular, ArrowTurnDownRightRegular } from '@fluentui/react-icons';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";

const renderBufferMessage = (streamingMessageBuffer: string) => {
    const [isExpanded, setIsExpanded] = useState(false);

    if (!streamingMessageBuffer || streamingMessageBuffer.trim() === "") return null;

    const previewText = streamingMessageBuffer.length > 500
        ? streamingMessageBuffer.substring(0, 500) + "..."
        : streamingMessageBuffer;

    return (
        <div style={{
            backgroundColor: 'var(--colorNeutralBackground2)',
            border: '1px solid var(--colorNeutralStroke1)',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '16px'
        }}>

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
                        color: 'var(--colorNeutralForeground1)',
                        fontSize: '20px',
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
                    // icon={isExpanded ? <ChevronDownRegular /> : <ChevronRightRegular />}
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
                        >
                            {previewText}
                        </ReactMarkdown>

                    </div>
                </div>
            )}

            {isExpanded && (
                <div style={{
                    // backgroundColor: 'var(--colorNeutralBackground1)',
                    // border: '1px solid var(--colorNeutralStroke1)',
                    // borderRadius: '6px',
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
    );
};

export default renderBufferMessage;