import HeaderTools from "@/coral/components/Header/HeaderTools";
import { Send } from "@/coral/imports/bundleicons";
import ChatInput from "@/coral/modules/ChatInput";
import remarkGfm from "remark-gfm";
import rehypePrism from "rehype-prism";
import { PlanChatProps } from "@/models";
import { Body1, Button, Tag, ToolbarDivider } from "@fluentui/react-components";
import { ChatDismiss20Regular, HeartRegular } from "@fluentui/react-icons";
import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import "../../styles/PlanChat.css"; // Assuming you have a CSS file for additional styles
import "../../styles/Chat.css"; // Assuming you have a CSS file for additional styles
import "../../styles/prism-material-oceanic.css"
const PlanChat: React.FC<PlanChatProps> = ({
    planData,
    OnChatSubmit
}) => {
    const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
    const [input, setInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [showScrollButton, setShowScrollButton] = useState(false);
    const [inputHeight, setInputHeight] = useState(0);
    const [currentConversationId, setCurrentConversationId] = useState<string | undefined>(undefined);

    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const inputContainerRef = useRef<HTMLDivElement>(null);
    const sendMessage = async () => {
    };
    const scrollToBottom = () => {
    };
    const clearChat = async () => {
        setMessages([]);
        setInput("");
        setCurrentConversationId(undefined);
    };
    return (
        <div className="chat-container">
            <div className="messages" ref={messagesContainerRef}>
                <div className="message-wrapper">
                    {messages.map((msg, index) => (<div key={index} className={`message ${msg.role}`}>
                        <Body1>
                            <div className="plan-chat-message-content">
                                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypePrism]}>
                                    {msg.content}
                                </ReactMarkdown>
                                {/* {msg.role === "assistant" && (
                                    <div className="assistant-footer">
                                        <div className="assistant-actions">
                                            <Button
                                                onClick={() => handleCopy(msg.content)}
                                                title="Copy Response"
                                                appearance="subtle"
                                                style={{ height: 28, width: 28 }}
                                                icon={<Copy />}
                                            />
                                            <Button
                                                onClick={() => console.log("Heart clicked for response:", msg.content)}
                                                title="Like"
                                                appearance="subtle"
                                                style={{ height: 28, width: 28 }}
                                                icon={<HeartRegular />}
                                            />
                                        </div>
                                    </div>
                                )} */}
                            </div>
                        </Body1>
                    </div>
                    ))}</div>


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
                            disabled={planData.hasHumanClarificationRequest && (isTyping || !input.trim())}
                        />

                        {messages.length > 0 && (
                            <HeaderTools>
                                <ToolbarDivider />
                                <Button

                                    onClick={clearChat}
                                    appearance="transparent"
                                    icon={<ChatDismiss20Regular />}
                                    disabled={isTyping || messages.length === 0} />

                            </HeaderTools>

                        )}

                    </ChatInput>
                </div>

            </div>


        </div>
    );
};

export default PlanChat;
