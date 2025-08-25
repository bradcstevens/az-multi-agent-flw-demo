import HeaderTools from "@/coral/components/Header/HeaderTools";
import { Copy, Send } from "@/coral/imports/bundleicons";
import ChatInput from "@/coral/modules/ChatInput";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import { AgentType, PlanChatProps, role } from "@/models";
import { StreamingPlanUpdate } from "@/services/WebSocketService";
import {
  Body1,
  Button,
  Spinner,
  Tag,
  ToolbarDivider,
} from "@fluentui/react-components";
import { DiamondRegular, HeartRegular } from "@fluentui/react-icons";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import "../../styles/PlanChat.css";
import "../../styles/Chat.css";
import "../../styles/prism-material-oceanic.css";
import { TaskService } from "@/services/TaskService";
import InlineToaster from "../toast/InlineToaster";
import ContentNotFound from "../NotFound/ContentNotFound";

const PlanChat: React.FC<PlanChatProps> = ({
  planData,
  input,
  loading,
  setInput,
  submittingChatDisableInput,
  OnChatSubmit,
  streamingMessages = [],
  wsConnected = false,
}) => {
  const messages = planData?.messages || [];
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [inputHeight, setInputHeight] = useState(0);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  // Debug logging
  console.log('PlanChat - planData:', planData);
  console.log('PlanChat - messages:', messages);
  console.log('PlanChat - messages.length:', messages.length);

  // Scroll to Bottom useEffect

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessages]);

  //Scroll to Bottom Buttom

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      setShowScrollButton(scrollTop + clientHeight < scrollHeight - 100);
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (inputContainerRef.current) {
      setInputHeight(inputContainerRef.current.offsetHeight);
    }
  }, [input]); // or [inputValue, submittingChatDisableInput]

  const scrollToBottom = () => {
    messagesContainerRef.current?.scrollTo({
      top: messagesContainerRef.current.scrollHeight,
      behavior: "smooth",
    });
    setShowScrollButton(false);
  };

  if (!planData)
    return (
      <ContentNotFound subtitle="The requested page could not be found." />
    );

  // If no messages exist, show the initial task as the first message
  const displayMessages = messages.length > 0 ? messages : [
    {
      source: AgentType.HUMAN,
      content: planData.plan?.initial_goal || "Task started",
      timestamp: planData.plan?.timestamp || new Date().toISOString()
    }
  ];

  // Merge streaming messages with existing messages
  const allMessages = [...displayMessages];
  
  // Add streaming messages as assistant messages
  streamingMessages.forEach(streamMsg => {
    if (streamMsg.content) {
      allMessages.push({
        source: streamMsg.agent_name || 'AI Assistant',
        content: streamMsg.content,
        timestamp: new Date().toISOString(),
        streaming: true,
        status: streamMsg.status,
        message_type: streamMsg.message_type
      });
    }
  });

  console.log('PlanChat - all messages including streaming:', allMessages);

  return (
    <div className="chat-container">
      <div className="messages" ref={messagesContainerRef}>
        {/* WebSocket Connection Status */}
        {wsConnected && (
          <div className="connection-status">
            <Tag
              appearance="filled"
              color="success"
              size="extra-small"
              icon={<DiamondRegular />}
            >
              Real-time updates active
            </Tag>
          </div>
        )}
        
        <div className="message-wrapper">
          {allMessages.map((msg, index) => {
            const isHuman = msg.source === AgentType.HUMAN;

            return (
              <div
                key={index}
                className={`message ${isHuman ? role.user : role.assistant} ${(msg as any).streaming ? 'streaming-message' : ''}`}
              >
                {!isHuman && (
                  <div className="plan-chat-header">
                    <div className="plan-chat-speaker">
                      <Body1 className="speaker-name">
                        {TaskService.cleanTextToSpaces(msg.source)}
                      </Body1>
                      <Tag
                        size="extra-small"
                        shape="rounded"
                        appearance="brand"
                        className="bot-tag"
                      >
                        BOT
                      </Tag>
                      {(msg as any).streaming && (
                        <Tag
                          size="extra-small"
                          shape="rounded"
                          appearance="outline"
                          icon={<Spinner size="extra-tiny" />}
                        >
                          {(msg as any).message_type === 'thinking' ? 'Thinking...' : 
                           (msg as any).message_type === 'action' ? 'Acting...' : 
                           (msg as any).status === 'in_progress' ? 'Working...' : 'Live'}
                        </Tag>
                      )}
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
      </div>

      {showScrollButton && (
        <Tag
          onClick={scrollToBottom}
          className="scroll-to-bottom plan-chat-scroll-button"
          shape="circular"
          style={{
            bottom: inputHeight,
            position: "absolute", // ensure this or your class handles it
            right: 16, // optional, for right alignment
            zIndex: 5,
          }}
        >
          Back to bottom
        </Tag>
      )}
      <InlineToaster />
      <div ref={inputContainerRef} className="plan-chat-input-container">
        <div className="plan-chat-input-wrapper">
          <ChatInput
            value={input}
            onChange={setInput}
            onEnter={() => OnChatSubmit(input)}
            disabledChat={
              planData?.enableChat ? submittingChatDisableInput : true
            }
            placeholder="Add more info to this task..."
          >
            <Button
              appearance="transparent"
              onClick={() => OnChatSubmit(input)}
              icon={<Send />}
              disabled={
                planData?.enableChat ? submittingChatDisableInput : true
              }
            />
          </ChatInput>
        </div>
      </div>
    </div>
  );
};

export default PlanChat;
