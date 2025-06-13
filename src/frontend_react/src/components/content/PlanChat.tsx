import HeaderTools from "@/coral/components/Header/HeaderTools";
import { Copy, Send } from "@/coral/imports/bundleicons";
import ChatInput from "@/coral/modules/ChatInput";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import { PlanChatProps } from "@/models";
import {
  Body1,
  Button,
  Tag,
  ToolbarDivider
} from "@fluentui/react-components";
import {
  HeartRegular,
} from "@fluentui/react-icons";
import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import "../../styles/PlanChat.css";
import "../../styles/Chat.css";
import "../../styles/prism-material-oceanic.css";

const PlanChat: React.FC<PlanChatProps> = ({
  planData,
  OnChatSubmit
}) => {
  const messages = planData?.messages || [];
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [inputHeight, setInputHeight] = useState(0);
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>(undefined);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  const sendMessage = async () => {};

  const scrollToBottom = () => {};

  return (
    <div className="chat-container">
      <div className="messages" ref={messagesContainerRef}>
        <div className="message-wrapper">
          {messages.map((msg, index) => {
            const isHuman = msg.role === "user" || msg.role === "human";

            return (
              <div key={index} className={`message ${msg.role}`}>
                {!isHuman && (
                  <div className="plan-chat-header">
                    <div className="plan-chat-speaker">
                      <span className="speaker-name">HR Agent</span>
                      <Tag size="extra-small" shape="rounded" appearance="filled" className="bot-tag">BOT</Tag>
                    </div>
                  </div>
                )}

                <Body1>
                  <div className="plan-chat-message-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypePrism]}>
                      {msg.content || ""}
                    </ReactMarkdown>

                    {!isHuman && (
                      <div className="assistant-footer">
                        <div className="assistant-actions">
                          <Button
                            onClick={() => msg.content && navigator.clipboard.writeText(msg.content)}
                            title="Copy Response"
                            appearance="subtle"
                            style={{ height: 28, width: 28 }}
                            icon={<Copy />}
                          />
                          <Tag size="extra-small">Sample data for demonstration purposes only.</Tag>
                        </div>
                      </div>
                    )}
                  </div>
                </Body1>
              </div>
            );
          })}
        </div>

        {isTyping && (
          <div className="typing-indicator">
            <span>Thinking...</span>
          </div>
        )}
      </div>

      {showScrollButton && (
        <Tag
          onClick={scrollToBottom}
          className="scroll-to-bottom plan-chat-scroll-button"
          shape="circular"
          style={{ bottom: inputHeight }}
        >
          Back to bottom
        </Tag>
      )}

      <div ref={inputContainerRef} className="plan-chat-input-container">
        <div className="plan-chat-input-wrapper">
          <ChatInput
            value={input}
            onChange={setInput}
            onEnter={sendMessage}
          >
            <Button
              appearance="transparent"
              onClick={sendMessage}
              icon={<Send />}
              disabled={!planData?.hasHumanClarificationRequest || isTyping || !input.trim()}
            />
          </ChatInput>
        </div>
      </div>
    </div>
  );
};

export default PlanChat;
