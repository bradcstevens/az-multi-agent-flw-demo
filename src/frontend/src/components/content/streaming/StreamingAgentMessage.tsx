import { AgentMessageData } from "@/models";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
// Render AI thinking/planning state
const renderAgentMessages = (agentMessages: AgentMessageData[]) => {
    if (!agentMessages || agentMessages.length === 0) return null;

    return (
        <div
        // style={{
        //     height: 200,
        //     maxHeight: 200,
        //     overflowY: 'auto',     // or 'hidden' if you don't want scrolling
        //     overflowX: 'hidden',
        //     flex: '0 0 200px'      // prevents flex parents from stretching it
        // }}

        >
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