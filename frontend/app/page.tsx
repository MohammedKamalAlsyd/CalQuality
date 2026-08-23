"use client";

import React, {
  useState,
  useEffect,
  useRef,
  useSyncExternalStore,
} from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ConfigProvider,
  Layout,
  Select,
  Button,
  Card,
  Typography,
  Flex,
  Avatar,
  Spin,
  Collapse,
  Tooltip,
} from "antd";
import { Bubble, Sender } from "@ant-design/x";
import {
  RobotOutlined,
  UserOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CodeSandboxOutlined,
  ClearOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  SendOutlined,
} from "@ant-design/icons";

const { Header, Content } = Layout;
const { Text, Title } = Typography;

const generateId = (prefix: string) =>
  `${prefix}_${Math.random().toString(36).substr(2, 9)}`;

// --- Linter-Safe Mount Hook (Avoids Cascading Renders) ---
const emptySubscribe = () => () => {};
function useIsMounted() {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );
}

// --- Types ---
type ActionPayload = {
  tool_call_id: string;
  details: {
    action_type: string;
    target_id: string;
    reason: string;
    account_id?: string;
    metadata?: Record<string, unknown>;
  };
};

type ToolData = {
  name: string;
  content: string;
};

type Message = {
  id: string;
  role: "user" | "ai";
  text: string;
  requiresAction?: boolean;
  actionPayload?: ActionPayload; // 🔒 FIX 1: Strongly typed instead of any
  isConfirmed?: boolean;
  usedTools?: ToolData[];
};

// --- Mock Data ---
const USERS = [
  { id: "ACCT-001", name: "Northstar Logistics", role: "Enterprise" },
  { id: "ACCT-002", name: "LumenWorks", role: "Growth" },
  { id: "INTERNAL_OPS", name: "Internal Operations", role: "Admin" },
];

// --- DYNAMIC ROLE-BASED PROMPTS ---
const PROMPTS_BY_ROLE: Record<string, string[]> = {
  "ACCT-001": [
    "Can Northstar cancel ORD-1001 without a cancellation fee? Explain why.",
    "What is the status of order ORD-1001?",
    "Please escalate ticket TKT-501 due to severe system outage.",
  ],
  "ACCT-002": [
    "Why did bulk upload fail for 4,200 rows?",
    "My pickup for ORD-2002 was missed by the carrier. Do I get a credit?",
    "What is the status of ORD-2001?",
  ],
  INTERNAL_OPS: [
    "Show me the details of ticket TKT-505.",
    "What is the standard SLA for P1 tickets on Enterprise plans?",
    "Which accounts are currently experiencing upload issues?",
  ],
};

export default function TealSilverChat() {
  const isMounted = useIsMounted(); // 🔒 FIX 2: SSR hydration safe hook
  const [currentUser, setCurrentUser] = useState(USERS[0]);
  const [threadId, setThreadId] = useState<string>(() => generateId("sess"));
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const switchUser = (userId: string) => {
    const user = USERS.find((u) => u.id === userId)!;
    setCurrentUser(user);
    clearChat();
  };

  const clearChat = () => {
    setMessages([]);
    setThreadId(generateId("sess"));
    setInputText("");
  };

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = { id: generateId("msg"), role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsLoading(true);

    try {
      const { data } = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/chat`,
        {
          message: text,
          account_id: currentUser.id,
          thread_id: threadId,
        },
      );

      const aiMsg: Message = {
        id: generateId("msg"),
        role: "ai",
        text: data.response_text,
        requiresAction: data.requires_action,
        actionPayload: data.action_payload,
        usedTools: data.used_tools,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId("err"),
          role: "ai",
          text: "❌ Connection Error to Backend.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async (
    msgId: string,
    toolCallId: string,
    isConfirmed: boolean,
  ) => {
    setIsLoading(true);
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, isConfirmed: true } : m)),
    );

    try {
      const { data } = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/confirm_action`,
        {
          thread_id: threadId,
          account_id: currentUser.id,
          tool_call_id: toolCallId,
          is_confirmed: isConfirmed,
        },
      );

      setMessages((prev) => [
        ...prev,
        { id: generateId("msg"), role: "ai", text: data.response_text },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: generateId("err"), role: "ai", text: "❌ Action Failed." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isMounted) return null;
  const isChatEmpty = messages.length === 0;
  const currentPrompts = PROMPTS_BY_ROLE[currentUser.id] || [];

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#0d9488",
          colorBgBase: "#f8fafc",
          colorBorder: "#cbd5e1",
          borderRadius: 12,
          fontFamily: "Inter, sans-serif",
        },
      }}
    >
      <Layout style={{ height: "100vh", background: "#f1f5f9" }}>
        {/* DYNAMIC HEADER */}
        {!isChatEmpty && (
          <Header
            style={{
              background: "#ffffff",
              borderBottom: "1px solid #e2e8f0",
              padding: "0 24px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              height: 64,
            }}
          >
            <Flex align="center" gap="small">
              <Avatar
                style={{ backgroundColor: "#0d9488" }}
                icon={<CodeSandboxOutlined />}
              />
              <Title level={5} style={{ margin: 0, color: "#0f172a" }}>
                ParcelPilot
              </Title>
            </Flex>

            <Flex align="center" gap="middle">
              <Select
                value={currentUser.id}
                onChange={switchUser}
                style={{ width: 220 }}
                options={USERS.map((u) => ({
                  label: `${u.name} (${u.role})`,
                  value: u.id,
                }))}
              />
              <Tooltip title="Clear Chat">
                <Button
                  type="text"
                  icon={<ClearOutlined />}
                  onClick={clearChat}
                />
              </Tooltip>
            </Flex>
          </Header>
        )}

        <Content
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: isChatEmpty ? "center" : "flex-start",
            height: "100%",
          }}
        >
          {/* EMPTY STATE - CENTERED */}
          {isChatEmpty && (
            <Flex
              vertical
              align="center"
              gap="large"
              style={{ width: "100%", maxWidth: 750, padding: "0 24px" }}
            >
              <Flex
                vertical
                align="center"
                gap="small"
                style={{ marginBottom: 20 }}
              >
                <Avatar
                  size={64}
                  style={{ backgroundColor: "#0d9488" }}
                  icon={<CodeSandboxOutlined />}
                />
                <Title level={2} style={{ margin: 0, color: "#0f172a" }}>
                  ParcelPilot AI
                </Title>
                <Text type="secondary" style={{ fontSize: 16 }}>
                  Operational Intelligence Agent
                </Text>
              </Flex>

              <Flex
                align="center"
                gap="small"
                style={{
                  marginBottom: 10,
                  background: "#e2e8f0",
                  padding: "6px 16px",
                  borderRadius: 20,
                }}
              >
                <Text
                  type="secondary"
                  strong
                  style={{ fontSize: 12, textTransform: "uppercase" }}
                >
                  Operating As:
                </Text>
                <Select
                  variant="outlined"
                  value={currentUser.id}
                  onChange={switchUser}
                  style={{ width: 200, fontWeight: 600 }}
                  options={USERS.map((u) => ({ label: u.name, value: u.id }))}
                />
              </Flex>

              <Sender
                value={inputText}
                onChange={setInputText}
                onSubmit={sendMessage}
                loading={isLoading}
                placeholder={`Ask anything about ${currentUser.name}'s account...`}
                style={{
                  boxShadow: "0 10px 25px rgba(15, 23, 42, 0.08)",
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  width: "100%",
                }}
              />

              {/* FULLY VISIBLE PROMPT GRID */}
              <Flex
                wrap="wrap"
                justify="center"
                gap="small"
                style={{ marginTop: 24, width: "100%" }}
              >
                {currentPrompts.map((prompt, i) => (
                  <Button
                    key={i}
                    onClick={() => sendMessage(prompt)}
                    style={{
                      background: "#ffffff",
                      color: "#334155",
                      border: "1px solid #cbd5e1",
                      borderRadius: 20,
                      padding: "4px 16px",
                      height: "auto",
                    }}
                    icon={<SendOutlined style={{ color: "#0d9488" }} />}
                  >
                    {prompt}
                  </Button>
                ))}
              </Flex>
            </Flex>
          )}

          {/* ACTIVE CHAT WINDOW */}
          {!isChatEmpty && (
            <div
              style={{
                flex: 1,
                width: "100%",
                maxWidth: 850,
                overflowY: "auto",
                padding: "30px 24px",
              }}
            >
              <Flex vertical gap="large" style={{ width: "100%" }}>
                {messages.map((msg) => (
                  <Bubble
                    key={msg.id}
                    placement={msg.role === "user" ? "end" : "start"}
                    content={
                      <div>
                        <div
                          className="markdown-body"
                          style={{
                            fontSize: 15,
                            lineHeight: 1.6,
                            color: "#1e293b",
                          }}
                        >
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.text}
                          </ReactMarkdown>
                        </div>

                        {/* REAL TOOL SNIPPETS */}
                        {msg.usedTools && msg.usedTools.length > 0 && (
                          <Collapse
                            size="small"
                            ghost
                            style={{
                              marginTop: 12,
                              background: "#f8fafc",
                              borderRadius: 8,
                              border: "1px solid #e2e8f0",
                            }}
                            items={[
                              {
                                key: "1",
                                label: (
                                  <Text
                                    type="secondary"
                                    style={{ fontSize: 12 }}
                                  >
                                    <DatabaseOutlined /> View Internal Agent
                                    Reasoning & Data Sources
                                  </Text>
                                ),
                                children: (
                                  <Flex vertical gap="small">
                                    {msg.usedTools.map((tool, idx) => (
                                      <div
                                        key={idx}
                                        style={{
                                          background: "#ffffff",
                                          border: "1px solid #e2e8f0",
                                          padding: 12,
                                          borderRadius: 8,
                                        }}
                                      >
                                        <Text
                                          strong
                                          style={{
                                            fontSize: 12,
                                            color: "#0d9488",
                                            textTransform: "uppercase",
                                          }}
                                        >
                                          {tool.name === "search_documents" ? (
                                            <FileTextOutlined />
                                          ) : (
                                            <DatabaseOutlined />
                                          )}{" "}
                                          {tool.name}
                                        </Text>
                                        <pre
                                          style={{
                                            margin: "8px 0 0 0",
                                            whiteSpace: "pre-wrap",
                                            fontSize: 11,
                                            color: "#475569",
                                            maxHeight: 200,
                                            overflowY: "auto",
                                          }}
                                        >
                                          {tool.content}
                                        </pre>
                                      </div>
                                    ))}
                                  </Flex>
                                ),
                              },
                            ]}
                          />
                        )}

                        {/* ACTION CARD */}
                        {msg.requiresAction &&
                          msg.actionPayload &&
                          !msg.isConfirmed && (
                            <Card
                              size="small"
                              title={
                                <>
                                  <ThunderboltOutlined
                                    style={{ color: "#0d9488" }}
                                  />{" "}
                                  Authorization Required
                                </>
                              }
                              style={{
                                marginTop: 16,
                                borderColor: "#5eead4",
                                background: "#f0fdfa",
                              }}
                            >
                              <Text strong style={{ color: "#115e59" }}>
                                {msg.actionPayload.details.reason}
                              </Text>
                              <pre
                                style={{
                                  background: "#ffffff",
                                  border: "1px solid #ccfbf1",
                                  padding: 12,
                                  borderRadius: 8,
                                  fontSize: 13,
                                  overflowX: "auto",
                                  marginTop: 12,
                                }}
                              >
                                {JSON.stringify(
                                  msg.actionPayload.details,
                                  null,
                                  2,
                                )}
                              </pre>
                              <Flex gap="small" style={{ marginTop: 16 }}>
                                <Button
                                  type="primary"
                                  style={{ background: "#0d9488" }}
                                  icon={<CheckCircleOutlined />}
                                  onClick={() =>
                                    handleConfirm(
                                      msg.id,
                                      msg.actionPayload!.tool_call_id,
                                      true,
                                    )
                                  }
                                >
                                  Confirm Action
                                </Button>
                                <Button
                                  danger
                                  icon={<CloseCircleOutlined />}
                                  onClick={() =>
                                    handleConfirm(
                                      msg.id,
                                      msg.actionPayload!.tool_call_id,
                                      false,
                                    )
                                  }
                                >
                                  Reject
                                </Button>
                              </Flex>
                            </Card>
                          )}
                      </div>
                    }
                    avatar={
                      msg.role === "user" ? (
                        <Avatar
                          icon={<UserOutlined />}
                          style={{ background: "#64748b" }}
                        />
                      ) : (
                        <Avatar
                          icon={<RobotOutlined />}
                          style={{ background: "#0d9488" }}
                        />
                      )
                    }
                    styles={{
                      content: {
                        background: msg.role === "user" ? "#e2e8f0" : "#ffffff",
                        boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
                        border: "1px solid #e2e8f0",
                        maxWidth: "650px",
                      },
                    }}
                  />
                ))}

                {isLoading && (
                  <Bubble
                    placement="start"
                    content={<Spin size="small" style={{ margin: "0 10px" }} />}
                    avatar={
                      <Avatar
                        icon={<RobotOutlined />}
                        style={{ background: "#0d9488" }}
                      />
                    }
                    styles={{
                      content: {
                        background: "#ffffff",
                        border: "1px solid #e2e8f0",
                      },
                    }}
                  />
                )}
                <div ref={scrollRef} />
              </Flex>
            </div>
          )}

          {/* SENDER INPUT */}
          {!isChatEmpty && (
            <div
              style={{
                width: "100%",
                maxWidth: 850,
                padding: "20px 24px 40px",
                background:
                  "linear-gradient(to top, #f1f5f9 80%, rgba(241,245,249,0))",
              }}
            >
              <Sender
                value={inputText}
                onChange={setInputText}
                onSubmit={sendMessage}
                loading={isLoading}
                placeholder={`Message Agent as ${currentUser.name}...`}
                style={{
                  boxShadow: "0 10px 25px rgba(15, 23, 42, 0.05)",
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                }}
              />
            </div>
          )}
        </Content>
      </Layout>
    </ConfigProvider>
  );
}
