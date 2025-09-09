import { AgentMessageData, AgentMessageType, role } from "@/models";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import { Body1, Button, Tag } from "@fluentui/react-components";
import { TaskService } from "@/services";
import { Copy } from "@/coral/imports/bundleicons";
import { DiamondRegular, HeartRegular } from "@fluentui/react-icons";


const StreamingAgentMessage = (agentMessages: AgentMessageData[]) => {
  if (!agentMessages?.length) return null;

  // Filter out messages with empty content
  const validMessages = agentMessages.filter(msg => msg.content?.trim());
  const messages = validMessages;
  if (!validMessages.length) return null;

  return (


    <div className="message-wrapper">
      {messages.map((msg, index) => {
        const isHuman = msg.agent_type === AgentMessageType.HUMAN_AGENT;

        return (
          <div
            key={index}
            className={`message ${isHuman ? role.user : role.assistant}`}
          >
            {!isHuman && (
              <div className="plan-chat-header">
                <div className="plan-chat-speaker">
                  <Body1 className="speaker-name">
                    {TaskService.cleanTextToSpaces(msg.agent)}
                  </Body1>
                  <Tag
                    size="extra-small"
                    shape="rounded"
                    appearance="brand"
                    className="bot-tag"
                  >
                    BOT
                  </Tag>
                </div>
              </div>
            )}

            <Body1>
              <div className="plan-chat-message-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypePrism]}
                >
                  {TaskService.cleanHRAgent(msg.content) || ""}
                </ReactMarkdown>

                {!isHuman && (
                  <div className="assistant-footer">
                    <div className="assistant-actions">
                      <div>
                        <Button
                          onClick={() =>
                            msg.content &&
                            navigator.clipboard.writeText(msg.content)
                          }
                          title="Copy Response"
                          appearance="subtle"
                          style={{ height: 28, width: 28 }}
                          icon={<Copy />}
                        />
                      </div>

                      <Tag
                        icon={<DiamondRegular />}
                        appearance="filled"
                        size="extra-small"
                      >
                        Sample data for demonstration purposes only.
                      </Tag>
                    </div>
                  </div>
                )}
              </div>
            </Body1>
          </div>
        );
      })}
    </div>

  );
};

export default StreamingAgentMessage;