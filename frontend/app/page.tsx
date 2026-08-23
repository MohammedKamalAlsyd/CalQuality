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
  Alert,
  Tag,
  Modal,
  Table,
  Badge,
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
  WarningOutlined,
  DashboardOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";

const { Header, Content } = Layout;
const { Text, Title } = Typography;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const generateId = (prefix: string) =>
  `${prefix}_${Math.random().toString(36).substring(2, 11)}`;

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
  actionPayload?: ActionPayload;
  isConfirmed?: boolean;
  actionResultStatus?: "success" | "cancelled" | "failed";
  usedTools?: ToolData[];
};

type ChatSession = {
  threadId: string;
  messages: Message[];
};

type Anomaly = {
  key: string;
  type: string;
  severity: "high" | "medium" | "low";
  affected_accounts: string[];
  description: string;
  suggested_action: string;
};

// --- Mock User Contexts ---
const USERS = [
  { id: "ACCT-001", name: "Northstar Logistics", role: "Enterprise" },
  { id: "ACCT-002", name: "LumenWorks", role: "Growth" },
  { id: "INTERNAL_OPS", name: "Internal Operations", role: "Admin / Ops" },
];

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
    "Which accounts have experienced SLA breaches relative to the 2026-08-16 snapshot?",
    "Show me all unassigned P1 tickets across all carriers.",
    "Which carrier has the highest late pickup rate in the system?",
  ],
};

export default function ParcelPilotAgentChat() {
  const isMounted = useIsMounted();
  const [currentUser, setCurrentUser] = useState(USERS[0]);

  // Load / Save Sessions in LocalStorage
  const [sessions, setSessions] = useState<Record<string, ChatSession>>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("parcelpilot_sessions");
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch {
          // fallback
        }
      }
    }
    const initial: Record<string, ChatSession> = {};
    USERS.forEach((u) => {
      initial[u.id] = { threadId: generateId("sess"), messages: [] };
    });
    return initial;
  });

  useEffect(() => {
    if (isMounted) {
      localStorage.setItem("parcelpilot_sessions", JSON.stringify(sessions));
    }
  }, [sessions, isMounted]);

  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [confirmingMsgId, setConfirmingMsgId] = useState<string | null>(null);

  // Anomaly Modal State (Problem 1)
  const [isAnomalyModalOpen, setIsAnomalyModalOpen] = useState(false);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loadingAnomalies, setLoadingAnomalies] = useState(false);
  const [anomalyError, setAnomalyError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [sessions, isLoading, confirmingMsgId]);

  const activeSession = sessions[currentUser.id] || {
    threadId: generateId("sess"),
    messages: [],
  };
  const messages = activeSession.messages;

  const setMessages = (updater: (prev: Message[]) => Message[]) => {
    setSessions((prev) => ({
      ...prev,
      [currentUser.id]: {
        ...prev[currentUser.id],
        messages: updater(prev[currentUser.id]?.messages || []),
      },
    }));
  };

  const switchUser = (userId: string) => {
    const user = USERS.find((u) => u.id === userId)!;
    setCurrentUser(user);
    setInputText("");
  };

  const clearChat = () => {
    setSessions((prev) => ({
      ...prev,
      [currentUser.id]: { threadId: generateId("sess"), messages: [] },
    }));
  };

  const fetchAnomalies = async () => {
    setIsAnomalyModalOpen(true);
    setLoadingAnomalies(true);
    setAnomalyError(null);

    try {
      const { data } = await axios.get(`${API_BASE}/ops/anomalies`, {
        timeout: 10000,
      });
      setAnomalies(data.anomalies || []);
    } catch (error: unknown) {
      console.error("❌ Failed to fetch anomalies from backend:", error);
      let errMsg = "Failed to load real-time operational anomalies.";
      if (axios.isAxiosError(error)) {
        errMsg = error.response?.data?.detail || error.message || errMsg;
      }
      setAnomalyError(errMsg);
      setAnomalies([]);
    } finally {
      setLoadingAnomalies(false);
    }
  };

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = { id: generateId("msg"), role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsLoading(true);

    try {
      const { data } = await axios.post(
        `${API_BASE}/chat`,
        {
          message: text,
          account_id: currentUser.id,
          thread_id: activeSession.threadId,
        },
        { timeout: 60000 },
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
    } catch (error: unknown) {
      let errorMessage =
        "❌ Connection Error or Timeout. Please verify backend is running.";

      if (axios.isAxiosError(error) && error.response) {
        if (error.response.status === 403 || error.response.status === 401) {
          errorMessage =
            "🚫 **Access Denied:** You are not authorized to view records or policies outside your assigned account context.";
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: generateId("err"),
          role: "ai",
          text: errorMessage,
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
    setConfirmingMsgId(msgId);

    try {
      const { data } = await axios.post(
        `${API_BASE}/confirm_action`,
        {
          thread_id: activeSession.threadId,
          account_id: currentUser.id,
          tool_call_id: toolCallId,
          is_confirmed: isConfirmed,
        },
        { timeout: 60000 },
      );

      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? {
                ...m,
                isConfirmed: true,
                actionResultStatus: isConfirmed ? "success" : "cancelled",
              }
            : m,
        ),
      );

      setMessages((prev) => [
        ...prev,
        {
          id: generateId("msg"),
          role: "ai",
          text: data.response_text,
          usedTools: data.used_tools,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId("err"),
          role: "ai",
          text: "❌ Action confirmation request failed. Please try again.",
        },
      ]);
    } finally {
      setConfirmingMsgId(null);
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
          borderRadius: 10,
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        },
      }}
    >
      <Layout style={{ height: "100vh", background: "#f1f5f9" }}>
        {/* APP HEADER */}
        <Header
          style={{
            background: "#ffffff",
            borderBottom: "1px solid #e2e8f0",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            height: 70,
            lineHeight: "normal",
          }}
        >
          <Flex align="center" gap="middle">
            <Avatar
              size={44}
              style={{
                backgroundColor: "#0d9488",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 2px 8px rgba(13, 148, 136, 0.25)",
              }}
              icon={<CodeSandboxOutlined style={{ fontSize: 24 }} />}
            />

            <Flex vertical justify="center" gap={2}>
              <Title
                level={4}
                style={{
                  margin: 0,
                  color: "#0f172a",
                  fontWeight: 700,
                  fontSize: 18,
                  lineHeight: 1.2,
                }}
              >
                ParcelPilot Support AI
              </Title>
              <Flex align="center" gap={4}>
                <ClockCircleOutlined
                  style={{ fontSize: 11, color: "#64748b" }}
                />
                <Text type="secondary" style={{ fontSize: 12, lineHeight: 1 }}>
                  Snapshot:{" "}
                  <strong style={{ color: "#334155" }}>
                    2026-08-16 11:00 IST
                  </strong>
                </Text>
              </Flex>
            </Flex>
          </Flex>

          <Flex align="center" gap="small">
            {currentUser.id === "INTERNAL_OPS" && (
              <Button
                type="primary"
                ghost
                icon={<DashboardOutlined />}
                onClick={fetchAnomalies}
              >
                Proactive Issue Monitor
              </Button>
            )}

            <Select
              value={currentUser.id}
              onChange={switchUser}
              style={{ width: 240 }}
              options={USERS.map((u) => ({
                label: `${u.name} (${u.role})`,
                value: u.id,
              }))}
            />

            <Tooltip title="Clear Chat History">
              <Button
                type="text"
                icon={<ClearOutlined />}
                onClick={clearChat}
              />
            </Tooltip>
          </Flex>
        </Header>

        <Content
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: isChatEmpty ? "center" : "flex-start",
            height: "calc(100vh - 70px)",
            overflow: "hidden",
          }}
        >
          {/* EMPTY STATE */}
          {isChatEmpty && (
            <Flex
              vertical
              align="center"
              gap="large"
              style={{ width: "100%", maxWidth: 750, padding: "0 24px" }}
            >
              <Flex vertical align="center" gap="small">
                <Avatar
                  size={56}
                  style={{ backgroundColor: "#0d9488" }}
                  icon={<CodeSandboxOutlined />}
                />
                <Title level={3} style={{ margin: 0, color: "#0f172a" }}>
                  How can I help you today?
                </Title>
                <Text type="secondary">
                  Logged in as <Tag color="cyan">{currentUser.name}</Tag> (
                  {currentUser.role})
                </Text>
              </Flex>

              {currentUser.id === "INTERNAL_OPS" && (
                <Alert
                  message="Internal Ops Anomaly Detection Active"
                  description="System detected repeated pickup failures across carrier routes near 2026-08-16 11:00."
                  type="warning"
                  showIcon
                  icon={<WarningOutlined />}
                  style={{ width: "100%", border: "1px solid #fde047" }}
                  action={
                    <Button
                      size="small"
                      type="primary"
                      danger
                      onClick={fetchAnomalies}
                    >
                      View Anomalies
                    </Button>
                  }
                />
              )}

              <Sender
                value={inputText}
                onChange={setInputText}
                onSubmit={sendMessage}
                loading={isLoading}
                placeholder={`Ask a question as ${currentUser.name}...`}
                style={{
                  boxShadow: "0 10px 25px rgba(15, 23, 42, 0.06)",
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  width: "100%",
                }}
              />

              <Flex
                wrap="wrap"
                justify="center"
                gap="small"
                style={{ width: "100%" }}
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
                      padding: "4px 14px",
                      height: "auto",
                      fontSize: 13,
                    }}
                    icon={<SendOutlined style={{ color: "#0d9488" }} />}
                  >
                    {prompt}
                  </Button>
                ))}
              </Flex>
            </Flex>
          )}

          {/* ACTIVE CHAT */}
          {!isChatEmpty && (
            <div
              style={{
                flex: 1,
                width: "100%",
                maxWidth: 850,
                overflowY: "auto",
                padding: "24px 20px",
              }}
            >
              <Flex vertical gap="middle" style={{ width: "100%" }}>
                {messages.map((msg) => (
                  <Bubble
                    key={msg.id}
                    placement={msg.role === "user" ? "end" : "start"}
                    content={
                      <div>
                        {/* Markdown with Scrollable Table Container */}
                        <div
                          className="markdown-body"
                          style={{
                            fontSize: 14.5,
                            lineHeight: 1.6,
                            color: "#1e293b",
                            overflowX: "auto",
                          }}
                        >
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.text}
                          </ReactMarkdown>
                        </div>

                        {/* TOOL USAGE & SOURCES */}
                        {msg.usedTools && msg.usedTools.length > 0 && (
                          <Collapse
                            size="small"
                            ghost
                            style={{
                              marginTop: 10,
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
                                    <DatabaseOutlined /> Tools Executed & Policy
                                    Sources ({msg.usedTools.length})
                                  </Text>
                                ),
                                children: (
                                  <Flex vertical gap="small">
                                    {msg.usedTools.map((tool, idx) => {
                                      const isDoc =
                                        tool.name.includes("document") ||
                                        tool.name.includes("search");

                                      return (
                                        <div
                                          key={idx}
                                          style={{
                                            background: "#ffffff",
                                            border: "1px solid #e2e8f0",
                                            padding: 10,
                                            borderRadius: 6,
                                          }}
                                        >
                                          <Flex
                                            justify="space-between"
                                            align="center"
                                            style={{ marginBottom: 4 }}
                                          >
                                            <Text
                                              strong
                                              style={{
                                                fontSize: 12,
                                                color: "#0d9488",
                                              }}
                                            >
                                              {isDoc ? (
                                                <FileTextOutlined />
                                              ) : (
                                                <DatabaseOutlined />
                                              )}{" "}
                                              {tool.name}
                                            </Text>
                                            <Tag
                                              color={isDoc ? "blue" : "purple"}
                                              style={{ fontSize: 10 }}
                                            >
                                              {isDoc
                                                ? "Vector Search"
                                                : "Structured SQL"}
                                            </Tag>
                                          </Flex>
                                          <pre
                                            style={{
                                              margin: 0,
                                              whiteSpace: "pre-wrap",
                                              fontSize: 11,
                                              color: "#475569",
                                              maxHeight: 180,
                                              overflowY: "auto",
                                              background: "#f8fafc",
                                              padding: 8,
                                              borderRadius: 4,
                                            }}
                                          >
                                            {tool.content}
                                          </pre>
                                        </div>
                                      );
                                    })}
                                  </Flex>
                                ),
                              },
                            ]}
                          />
                        )}

                        {/* STATE-CHANGING ACTION AUTHORIZATION CARD */}
                        {msg.requiresAction && msg.actionPayload && (
                          <Card
                            size="small"
                            title={
                              <Flex justify="space-between" align="center">
                                <span>
                                  <ThunderboltOutlined
                                    style={{ color: "#0d9488" }}
                                  />{" "}
                                  Authorization Required
                                </span>
                                {msg.isConfirmed ? (
                                  msg.actionResultStatus === "success" ? (
                                    <Tag color="success">Executed</Tag>
                                  ) : (
                                    <Tag color="default">Cancelled</Tag>
                                  )
                                ) : (
                                  <Tag color="warning">
                                    Pending Confirmation
                                  </Tag>
                                )}
                              </Flex>
                            }
                            style={{
                              marginTop: 14,
                              borderColor: msg.isConfirmed
                                ? "#cbd5e1"
                                : "#5eead4",
                              background: msg.isConfirmed
                                ? "#f8fafc"
                                : "#f0fdfa",
                            }}
                          >
                            <Text strong style={{ color: "#0f766e" }}>
                              {msg.actionPayload.details.reason}
                            </Text>

                            <pre
                              style={{
                                background: "#ffffff",
                                border: "1px solid #ccfbf1",
                                padding: 10,
                                borderRadius: 6,
                                fontSize: 12,
                                overflowX: "auto",
                                marginTop: 10,
                              }}
                            >
                              {JSON.stringify(
                                msg.actionPayload.details,
                                null,
                                2,
                              )}
                            </pre>

                            {!msg.isConfirmed && (
                              <Flex gap="small" style={{ marginTop: 12 }}>
                                <Button
                                  type="primary"
                                  style={{ background: "#0d9488" }}
                                  icon={<CheckCircleOutlined />}
                                  loading={confirmingMsgId === msg.id}
                                  onClick={() =>
                                    handleConfirm(
                                      msg.id,
                                      msg.actionPayload!.tool_call_id,
                                      true,
                                    )
                                  }
                                >
                                  Authorize & Execute
                                </Button>
                                <Button
                                  danger
                                  icon={<CloseCircleOutlined />}
                                  disabled={confirmingMsgId !== null}
                                  onClick={() =>
                                    handleConfirm(
                                      msg.id,
                                      msg.actionPayload!.tool_call_id,
                                      false,
                                    )
                                  }
                                >
                                  Reject Action
                                </Button>
                              </Flex>
                            )}
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
                        boxShadow: "0 2px 8px rgba(15, 23, 42, 0.04)",
                        border: "1px solid #e2e8f0",
                        maxWidth: "680px",
                      },
                    }}
                  />
                ))}

                {isLoading && (
                  <Bubble
                    placement="start"
                    content={
                      <Spin
                        size="small"
                        style={{ margin: "0 10px" }}
                        tip="Evaluating policies and data..."
                      />
                    }
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

          {/* SENDER INPUT BAR */}
          {!isChatEmpty && (
            <div
              style={{
                width: "100%",
                maxWidth: 850,
                padding: "16px 20px 24px",
                background:
                  "linear-gradient(to top, #f1f5f9 85%, rgba(241,245,249,0))",
              }}
            >
              <Sender
                value={inputText}
                onChange={setInputText}
                onSubmit={sendMessage}
                loading={isLoading}
                placeholder={`Message Agent as ${currentUser.name}...`}
                style={{
                  boxShadow: "0 8px 20px rgba(15, 23, 42, 0.06)",
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                }}
              />
            </div>
          )}
        </Content>

        {/* PROACTIVE ANOMALY DETECTION MODAL (Problem 1 Requirement) */}
        <Modal
          title={
            <Flex align="center" gap="small">
              <DashboardOutlined style={{ color: "#0d9488" }} />
              <span>Proactive Issue & Anomaly Monitor (Internal Ops View)</span>
            </Flex>
          }
          open={isAnomalyModalOpen}
          onOk={() => setIsAnomalyModalOpen(false)}
          onCancel={() => setIsAnomalyModalOpen(false)}
          width={800}
          footer={[
            <Button
              key="close"
              type="primary"
              onClick={() => setIsAnomalyModalOpen(false)}
            >
              Done
            </Button>,
          ]}
        >
          <Text type="secondary">
            Scanned structured operational data relative to snapshot{" "}
            <strong>2026-08-16 11:00 IST</strong>.
          </Text>

          {/* ERROR ALERT DISPLAY */}
          {anomalyError && (
            <Alert
              message="Failed to Fetch Anomalies"
              description={anomalyError}
              type="error"
              showIcon
              style={{ marginTop: 12, marginBottom: 12 }}
              action={
                <Button
                  size="small"
                  type="primary"
                  danger
                  icon={<ReloadOutlined />}
                  onClick={fetchAnomalies}
                >
                  Retry Scan
                </Button>
              }
            />
          )}

          <Table
            style={{ marginTop: 16 }}
            loading={loadingAnomalies}
            dataSource={anomalies}
            pagination={false}
            columns={[
              {
                title: "Severity",
                dataIndex: "severity",
                key: "severity",
                width: "120px",
                render: (sev: string) => (
                  <Badge
                    status={
                      sev === "high"
                        ? "error"
                        : sev === "medium"
                          ? "warning"
                          : "default"
                    }
                    text={<Text strong>{sev.toUpperCase()}</Text>}
                  />
                ),
              },
              {
                title: "Anomaly / Pattern",
                dataIndex: "type",
                key: "type",
                render: (text: string, row: Anomaly) => (
                  <div>
                    <Text strong>{text}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {row.description}
                    </Text>
                  </div>
                ),
              },
              {
                title: "Affected Accounts",
                dataIndex: "affected_accounts",
                key: "affected_accounts",
                render: (accounts: string[]) => (
                  <Flex gap="4px" wrap="wrap">
                    {accounts.map((a) => (
                      <Tag color="geekblue" key={a}>
                        {a}
                      </Tag>
                    ))}
                  </Flex>
                ),
              },
              {
                title: "Recommended Action",
                dataIndex: "suggested_action",
                key: "suggested_action",
                render: (action: string) => (
                  <Text style={{ fontSize: 12 }}>{action}</Text>
                ),
              },
            ]}
          />
        </Modal>
      </Layout>
    </ConfigProvider>
  );
}
