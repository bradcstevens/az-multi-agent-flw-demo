import { AgentMessageData } from "@/models";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
// Render AI thinking/planning state
const renderAgentMessages = (agentMessages: AgentMessageData[]) => {
    if (!agentMessages || agentMessages.length === 0) return null;

    return (
        <div >
            {agentMessages.map((msg, index) => {
                const trimmed = msg.raw_content?.trim();
                if (!trimmed) return null; // skip if empty, null, or whitespace
                return (
                    <div key={index} style={{ marginBottom: '16px' }}>
                        <strong>{msg.agent}</strong>:
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypePrism]}
                        >
                            {trimmed}
                        </ReactMarkdown>
                    </div>
                );
            })}
        </div>
    );
};
export default renderAgentMessages;