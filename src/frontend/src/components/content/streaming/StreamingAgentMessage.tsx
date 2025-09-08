import { AgentMessageData } from "@/models";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";

interface StreamingAgentMessageProps {
  agentMessages: AgentMessageData[];
}

const StreamingAgentMessage = ({ agentMessages }: StreamingAgentMessageProps) => {
  if (!agentMessages?.length) return null;

  // Filter out messages with empty content
  const validMessages = agentMessages.filter(msg => msg.raw_content?.trim());

  if (!validMessages.length) return null;

  return (
    <div className="streaming-agent-messages">
      {validMessages.map((message, index) => (
        <div key={`${message.agent}-${message.timestamp}-${index}`} className="agent-message">
          <div className="agent-name">
            <strong>{message.agent}</strong>:
          </div>
          <div className="agent-content">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypePrism]}
            >
              {message.raw_content.trim()}
            </ReactMarkdown>
          </div>
        </div>
      ))}
    </div>
  );
};

export default StreamingAgentMessage;