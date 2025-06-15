/**
 * PlanChat.tsx
 * ---------------------------------------
 * TEMP FRONTEND INJECTION FOR USER CHAT BUBBLES
 *
 * This version adds placeholder "user" messages between bot messages
 * for UI layout/design purposes only.
 *
 * All placeholder injection logic is clearly marked, easy to remove.
 * Simply delete the `injectUserPlaceholders()` call and use raw `planData.messages`.
 */

import HeaderTools from "@/coral/components/Header/HeaderTools";
import { Copy, Send } from "@/coral/imports/bundleicons";
import ChatInput from "@/coral/modules/ChatInput";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import { PlanChatProps } from "@/models";
import { Body1, Button, Spinner, Tag } from "@fluentui/react-components";
import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import "../../styles/PlanChat.css";
import "../../styles/Chat.css";
import "../../styles/prism-material-oceanic.css";
import { TaskService } from "@/services/TaskService";

/**
 * TEMPORARY DEV FUNCTION:
 * Injects empty human messages between bot messages
 * Used for front-end chat UI preview only
 */
const injectUserPlaceholders = (rawMessages: any[]) => {
  if (!rawMessages.length) return [];

  const result = [];
  for (let i = 0; i < rawMessages.length; i++) {
    const current = rawMessages[i];
    result.push(current);

    const next = rawMessages[i + 1];
    const currentIsBot = !current.source.includes("human");
    const nextIsBot = next && !next.source.includes("human");

    // If two bots in a row, insert user bubble
    if (currentIsBot && nextIsBot) {
      result.push({
        source: `human_placeholder_${i}`,
        content: "", // Leave blank so it's easy to style separately
      });
    }
  }
  return result;
};

const PlanChat: React.FC<PlanChatProps> = ({
  planData,
  input,
  loading,
  OnChatSubmit,
}) => {
  // 👇 Use modified placeholder-injected message list for layout preview
  const rawMessages = planData?.messages || [];
  const messages = injectUserPlaceholders(rawMessages); // 👈 Remove this call when backend data is live

  const [inputValue, setInput] = useState(input);
  const [isTyping, setIsTyping] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [inputHeight, setInputHeight] = useState(0);
  const [currentConversationId, setCurrentConversationId] = useState<
    string | undefined
  >(undefined);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  const sendMessage = async () => {
    // Placeholder for message send logic
  };

  const scrollToBottom = () => {
    // Placeholder for scroll behavior
  };

  if (!planData) return <Spinner size="large" />;

  return (
    <div className="chat-container">
      <div className="messages" ref={messagesContainerRef}>
        <div className="message-wrapper">
          {messages.map((msg, index) => {
            const isHuman = msg.source.includes("human");

            return (
              <div
                key={index}
                className={`message ${isHuman ? "user" : "assistant"}`}
              >
                {/* 🧠 Assistant header + label */}
                {!isHuman && (
                  <div className="plan-chat-header">
                    <div className="plan-chat-speaker">
                      <span className="speaker-name">
                        {TaskService.cleanTextToSpaces(msg.source)}
                      </span>
                      <Tag
                        size="extra-small"
                        shape="rounded"
                        appearance="filled"
                        className="bot-tag"
                      >
                        BOT
                      </Tag>
                    </div>
                  </div>
                )}

                <Body1>
                  <div className="plan-chat-message-content">
                    {/* 📄 If message has content, render Markdown */}
                    {msg.content ? (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypePrism]}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    ) : (
                      // 🧪 PLACEHOLDER UI for empty user messages
                      isHuman && (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypePrism]}
                        >
                          This is a placeholder user message.
                          {/*
                        SWAP THIS
                        const messages = injectUserPlaceholders(rawMessages);
                        WITH
                        const messages = rawMessages;
                        */}
                        </ReactMarkdown>
                      )
                    )}

                    {/* 🛠️ Assistant footer with Copy button */}
                    {!isHuman && msg.content && (
                      <div className="assistant-footer">
                        <div className="assistant-actions">
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
                          <Tag size="extra-small">
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

        {/* 🤖 Typing indicator while AI is generating */}
        {isTyping && (
          <div className="typing-indicator">
            <span>Thinking...</span>
          </div>
        )}
      </div>

      {/* ⬇️ Back-to-bottom bubble when not scrolled */}
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

      {/* 💬 Input field with Send button */}
      <div ref={inputContainerRef} className="plan-chat-input-container">
        <div className="plan-chat-input-wrapper">
          <ChatInput
            value={inputValue}
            onChange={setInput}
            onEnter={() => OnChatSubmit(inputValue)}
            disabledChat={!planData.enableChat}
            placeholder="Add more info to this task..."
          >
            <Button
              appearance="transparent"
              onClick={sendMessage}
              icon={<Send />}
              disabled={!planData?.enableChat || isTyping || !input.trim()}
            />
          </ChatInput>
        </div>
      </div>
    </div>
  );
};

export default PlanChat;
