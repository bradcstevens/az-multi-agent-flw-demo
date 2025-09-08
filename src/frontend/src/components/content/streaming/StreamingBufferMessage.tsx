import {
    Accordion,
    AccordionItem,
    AccordionHeader,
    AccordionPanel,
} from '@fluentui/react-components';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import { useState } from "react";
// Render AI thinking/planning state
const renderBufferMessage = (streamingMessageBuffer: string) => {
    if (!streamingMessageBuffer || streamingMessageBuffer.trim() === "") return null;
    return (
        <Accordion collapsible defaultOpenItems="one">
            <AccordionItem value="one">

                <AccordionPanel>
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypePrism]}
                    >
                        {streamingMessageBuffer}
                    </ReactMarkdown>
                </AccordionPanel>
            </AccordionItem>
        </Accordion>

    );
};

export default renderBufferMessage;