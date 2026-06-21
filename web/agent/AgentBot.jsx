import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import agentImage from "./assets/bot.webp";
import "./AgentBot.css";

const ROLE_STORAGE_KEY = `alpineflow-agent-role:${import.meta.env.VITE_AGENT_SESSION_ID}`;
const POSITION_STORAGE_KEY = "alpineflow-agent-position";
const CHAT_STORAGE_KEY_PREFIX = "alpineflow-agent-chat:";
const HISTORY_STORAGE_KEY_PREFIX = "alpineflow-agent-history:";
const MAX_STORED_MESSAGES = 200;
const MAX_HISTORY_CONVERSATIONS = 20;
const AVATAR_SIZE = 92;
const EDGE_GAP = 18;

const ROLES = [
  {
    id: "traveler",
    label: "Traveler",
    emoji: "🧳",
    description: "Plan a smoother personal trip.",
    welcome:
      "Hi! I’m your travel companion. I can help you compare busy days and find a calmer departure window.",
  },
  {
    id: "resident",
    label: "Resident",
    emoji: "🏠",
    description: "Understand local traffic impact.",
    welcome:
      "Hello! I’ll help you keep an eye on nearby traffic pressure and avoid the busiest local periods.",
  },
  {
    id: "logistics",
    label: "Logistics",
    emoji: "🚚",
    description: "Reduce delivery delay risk.",
    welcome:
      "Welcome! I’ll help you identify risky traffic windows and think through more reliable transport timing.",
  },
  {
    id: "tourism",
    label: "Tourism",
    emoji: "🏨",
    description: "Prepare for visitor peaks.",
    welcome:
      "Hi there! I’ll help you understand likely visitor traffic peaks and prepare for high-demand periods.",
  },
  {
    id: "authority",
    label: "Authority",
    emoji: "🚦",
    description: "Review corridor pressure.",
    welcome:
      "Welcome. I’ll support your traffic overview with corridor risks, peak windows, and operational context.",
  },
];

function readStoredRole() {
  for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
    const key = window.localStorage.key(index);
    if (
      key?.startsWith("alpineflow-agent-role:dev-") &&
      key !== ROLE_STORAGE_KEY
    ) {
      window.localStorage.removeItem(key);
    }
  }

  const storedRole = window.localStorage.getItem(ROLE_STORAGE_KEY);
  return ROLES.some((role) => role.id === storedRole) ? storedRole : null;
}

function readStoredPosition() {
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(POSITION_STORAGE_KEY),
    );
    if (Number.isFinite(stored?.x) && Number.isFinite(stored?.y)) {
      return stored;
    }
  } catch {
    // Ignore malformed local storage and use the default position.
  }
  return null;
}

function clampPosition(position) {
  return {
    x: Math.min(
      Math.max(EDGE_GAP, position.x),
      Math.max(EDGE_GAP, window.innerWidth - AVATAR_SIZE - EDGE_GAP),
    ),
    y: Math.min(
      Math.max(EDGE_GAP, position.y),
      Math.max(EDGE_GAP, window.innerHeight - AVATAR_SIZE - EDGE_GAP),
    ),
  };
}

function defaultPosition() {
  return clampPosition({
    x: window.innerWidth - AVATAR_SIZE - 28,
    y: window.innerHeight - AVATAR_SIZE - 28,
  });
}

function RolePicker({ onSelect, currentRole }) {
  return (
    <div className="agent-role-picker">
      <div className="agent-panel-intro">
        <span>CHOOSE YOUR VIEW</span>
        <h2>How can I help you?</h2>
        <p>Select a role so the assistant can tailor its responses.</p>
      </div>

      <div className="agent-role-list">
        {ROLES.map((role) => (
          <button
            className={currentRole === role.id ? "selected" : ""}
            type="button"
            key={role.id}
            onClick={() => onSelect(role.id)}
          >
            <span className="agent-role-emoji">{role.emoji}</span>
            <span>
              <strong>{role.label}</strong>
              <small>{role.description}</small>
            </span>
            <span className="agent-role-arrow">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function createSessionId() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function chatStorageKey(roleId) {
  return `${CHAT_STORAGE_KEY_PREFIX}${roleId}`;
}

function historyStorageKey(roleId) {
  return `${HISTORY_STORAGE_KEY_PREFIX}${roleId}`;
}

function normalizeMessages(messages) {
  return Array.isArray(messages)
    ? messages
        .filter(
          (message) =>
            (message?.role === "user" || message?.role === "assistant") &&
            typeof message.content === "string",
        )
        .map((message) => ({
          id:
            typeof message.id === "string"
              ? message.id
              : createSessionId(),
          role: message.role,
          content: message.content,
          createdAt:
            typeof message.createdAt === "string"
              ? message.createdAt
              : null,
        }))
    : [];
}

function titleFromMessages(messages) {
  const firstUserMessage = messages.find((message) => message.role === "user");
  const title = firstUserMessage?.content?.trim() || "Untitled chat";
  return title.length > 52 ? `${title.slice(0, 52)}…` : title;
}

function formatHistoryTime(value) {
  if (!value) return "";
  try {
    return new Intl.DateTimeFormat("en", {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return "";
  }
}

function readStoredHistory(roleId) {
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(historyStorageKey(roleId)),
    );
    return Array.isArray(stored)
      ? stored
          .map((conversation) => {
            const messages = normalizeMessages(conversation?.messages);
            if (!messages.length) return null;
            const sessionId =
              typeof conversation?.sessionId === "string" &&
              conversation.sessionId
                ? conversation.sessionId
                : createSessionId();

            return {
              id:
                typeof conversation?.id === "string"
                  ? conversation.id
                  : sessionId,
              sessionId,
              title:
                typeof conversation?.title === "string" &&
                conversation.title
                  ? conversation.title
                  : titleFromMessages(messages),
              messages,
              createdAt:
                typeof conversation?.createdAt === "string"
                  ? conversation.createdAt
                  : messages[0]?.createdAt || new Date().toISOString(),
              updatedAt:
                typeof conversation?.updatedAt === "string"
                  ? conversation.updatedAt
                  : messages.at(-1)?.createdAt || new Date().toISOString(),
            };
          })
          .filter(Boolean)
      : [];
  } catch {
    return [];
  }
}

function readStoredConversation(roleId) {
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(chatStorageKey(roleId)),
    );
    const messages = normalizeMessages(stored?.messages);

    return {
      sessionId:
        typeof stored?.sessionId === "string" && stored.sessionId
          ? stored.sessionId
          : createSessionId(),
      messages,
    };
  } catch {
    return {
      sessionId: createSessionId(),
      messages: [],
    };
  }
}

function ChatPanel({ role, onChangeRole, onBusyChange }) {
  const bodyRef = useRef(null);
  const [storedConversation] = useState(() =>
    readStoredConversation(role.id),
  );
  const [sessionId, setSessionId] = useState(storedConversation.sessionId);
  const [messages, setMessages] = useState(storedConversation.messages);
  const [history, setHistory] = useState(() => readStoredHistory(role.id));
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [modeNotice, setModeNotice] = useState("");

  useEffect(() => {
    onBusyChange?.(isLoading);
    return () => onBusyChange?.(false);
  }, [isLoading, onBusyChange]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        chatStorageKey(role.id),
        JSON.stringify({
          sessionId,
          messages: messages.slice(-MAX_STORED_MESSAGES),
        }),
      );
    } catch {
      // Ignore storage quota/privacy errors; the active chat still works.
    }
  }, [messages, role.id, sessionId]);

  useEffect(() => {
    if (!messages.length) return;

    const now = new Date().toISOString();
    setHistory((current) => {
      const nextConversation = {
        id: sessionId,
        sessionId,
        title: titleFromMessages(messages),
        messages: messages.slice(-MAX_STORED_MESSAGES),
        createdAt: current.find((item) => item.sessionId === sessionId)?.createdAt || messages[0]?.createdAt || now,
        updatedAt: now,
      };
      return [
        nextConversation,
        ...current.filter((item) => item.sessionId !== sessionId),
      ].slice(0, MAX_HISTORY_CONVERSATIONS);
    });
  }, [messages, sessionId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        historyStorageKey(role.id),
        JSON.stringify(history),
      );
    } catch {
      // Ignore storage errors; active chat still remains available.
    }
  }, [history, role.id]);

  useEffect(() => {
    bodyRef.current?.scrollTo({
      top: bodyRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isLoading, error]);

  useEffect(() => {
    if (!modeNotice) return undefined;
    const timer = window.setTimeout(() => setModeNotice(""), 2600);
    return () => window.clearTimeout(timer);
  }, [modeNotice]);

  const clearRemoteSession = (id = sessionId) =>
    fetch(`/api/chat/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }).catch(() => {
      // The local UI can still reset if the backend has already restarted.
    });

  const resetConversation = () => {
    void clearRemoteSession();
    window.localStorage.removeItem(chatStorageKey(role.id));
    setSessionId(createSessionId());
    setMessages([]);
    setIsHistoryOpen(false);
    setDraft("");
    setError("");
  };

  const restoreConversation = (conversation) => {
    if (!conversation || isLoading) return;
    setSessionId(conversation.sessionId || createSessionId());
    setMessages(normalizeMessages(conversation.messages));
    setDraft("");
    setError("");
    setIsHistoryOpen(false);
  };

  const deleteHistoryItem = (conversationId) => {
    setHistory((current) =>
      current.filter((conversation) => conversation.id !== conversationId),
    );
  };

  const requestRoleChange = () => {
    if (isLoading) {
      setModeNotice("Please wait until the current answer is finished before changing mode.");
      return;
    }
    setModeNotice("");
    onChangeRole();
  };

  const sendMessage = async (event) => {
    event.preventDefault();
    const query = draft.trim();
    if (!query || isLoading) return;

    setDraft("");
    setError("");
    setMessages((current) => [
      ...current,
      {
        id: createSessionId(),
        role: "user",
        content: query,
        createdAt: new Date().toISOString(),
      },
    ]);
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          user_type: role.id,
          session_id: sessionId,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "The planning agent is unavailable.");
      }

      if (payload.session_id) setSessionId(payload.session_id);
      setMessages((current) => [
        ...current,
        {
          id: createSessionId(),
          role: "assistant",
          content: payload.message || payload.advice || "No response returned.",
          createdAt: new Date().toISOString(),
        },
      ]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The planning agent is unavailable.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="agent-chat">
      <div className="agent-chat-header">
        <div className="agent-chat-avatar">{role.emoji}</div>
        <div>
          <span>TRAFFIC ASSISTANT</span>
          <strong>{role.label} mode</strong>
        </div>
        <div className="agent-header-actions">
          <button
            type="button"
            onClick={() => setIsHistoryOpen((current) => !current)}
          >
            History
          </button>
          <button type="button" onClick={requestRoleChange}>
            Change role
          </button>
        </div>
      </div>

      {modeNotice && <div className="agent-mode-notice">{modeNotice}</div>}

      <div className="agent-chat-body" ref={bodyRef} aria-live="polite">
        {isHistoryOpen && (
          <div className="agent-history-panel">
            <div className="agent-history-heading">
              <span>Conversation history</span>
              <button type="button" onClick={() => setIsHistoryOpen(false)}>
                Close
              </button>
            </div>

            {history.length ? (
              <div className="agent-history-list">
                {history.map((conversation) => (
                  <div className="agent-history-item" key={conversation.id}>
                    <button
                      type="button"
                      onClick={() => restoreConversation(conversation)}
                      disabled={isLoading}
                    >
                      <strong>{conversation.title}</strong>
                      <small>
                        {conversation.messages.length} messages ·{" "}
                        {formatHistoryTime(conversation.updatedAt)}
                      </small>
                    </button>
                    <button
                      type="button"
                      aria-label="Delete history item"
                      onClick={() => deleteHistoryItem(conversation.id)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p>No saved conversations yet.</p>
            )}
          </div>
        )}

        <div className="agent-message assistant">
          <img src={agentImage} alt="" />
          <div className="agent-message-content">
            <p>{role.welcome}</p>
          </div>
        </div>

        {messages.map((message) => (
          <div className={`agent-message ${message.role}`} key={message.id}>
            {message.role === "assistant" && <img src={agentImage} alt="" />}
            <div className="agent-message-content">
              {message.role === "assistant" ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              ) : (
                <p>{message.content}</p>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="agent-message assistant">
            <img src={agentImage} alt="" />
            <div className="agent-message-content agent-typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}

        {error && (
          <div className="agent-error">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")}>
              Dismiss
            </button>
          </div>
        )}
      </div>

      <div className="agent-chat-actions">
        <span>Follow-ups remember your current plan.</span>
        <button type="button" onClick={resetConversation}>
          New chat
        </button>
      </div>

      <form className="agent-composer" onSubmit={sendMessage}>
        <input
          type="text"
          placeholder="Ask about your journey…"
          aria-label="Chat message"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !draft.trim()}
          aria-label="Send message"
        >
          ↑
        </button>
      </form>
    </div>
  );
}

export default function AgentBot() {
  const dragState = useRef(null);
  const isAgentBusyRef = useRef(false);
  const roleIdRef = useRef(null);
  const [roleId, setRoleId] = useState(readStoredRole);
  const [isOpen, setIsOpen] = useState(false);
  const [isChoosingRole, setIsChoosingRole] = useState(!roleId);
  const [isAgentBusy, setIsAgentBusy] = useState(false);
  const [position, setPosition] = useState(
    () => readStoredPosition() ?? defaultPosition(),
  );
  const selectedRole = ROLES.find((role) => role.id === roleId) ?? null;

  useEffect(() => {
    isAgentBusyRef.current = isAgentBusy;
  }, [isAgentBusy]);

  useEffect(() => {
    roleIdRef.current = roleId;
  }, [roleId]);

  useEffect(() => {
    const keepInsideViewport = () => {
      setPosition((current) => clampPosition(current));
    };
    window.addEventListener("resize", keepInsideViewport);
    return () => window.removeEventListener("resize", keepInsideViewport);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(
      POSITION_STORAGE_KEY,
      JSON.stringify(position),
    );
  }, [position]);

  const panelStyle = useMemo(() => {
    const panelWidth = Math.min(430, window.innerWidth - 24);
    const panelHeight = isChoosingRole ? 510 : 540;
    const openOnLeft =
      position.x + AVATAR_SIZE + 14 + panelWidth > window.innerWidth;
    const left = openOnLeft
      ? position.x - panelWidth - 14
      : position.x + AVATAR_SIZE + 14;
    const top = Math.min(
      Math.max(12, position.y + AVATAR_SIZE - panelHeight),
      Math.max(12, window.innerHeight - panelHeight - 12),
    );

    return {
      width: panelWidth,
      left: Math.max(12, left),
      top,
    };
  }, [isChoosingRole, position]);

  const selectRole = (nextRole) => {
    if (isAgentBusy) return;
    window.localStorage.setItem(ROLE_STORAGE_KEY, nextRole);
    setRoleId(nextRole);
    setIsChoosingRole(false);
  };

  const togglePanel = () => {
    setIsOpen((open) => {
      if (open && isAgentBusy) return true;
      const nextOpen = !open;
      if (nextOpen) setIsChoosingRole(!roleId);
      return nextOpen;
    });
  };

  const openRolePicker = () => {
    if (isAgentBusy) return;
    setIsChoosingRole(true);
  };

  const onPointerDown = (event) => {
    event.preventDefault();
    dragState.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: position.x,
      originY: position.y,
      moved: false,
    };
  };

  useEffect(() => {
    const onWindowPointerMove = (event) => {
      const drag = dragState.current;
      if (!drag || drag.pointerId !== event.pointerId) return;

      const deltaX = event.clientX - drag.startX;
      const deltaY = event.clientY - drag.startY;
      if (Math.abs(deltaX) + Math.abs(deltaY) > 5) drag.moved = true;

      setPosition(
        clampPosition({
          x: drag.originX + deltaX,
          y: drag.originY + deltaY,
        }),
      );
    };

    const onWindowPointerUp = (event) => {
      const drag = dragState.current;
      if (!drag || drag.pointerId !== event.pointerId) return;
      dragState.current = null;
      if (!drag.moved) {
        setIsOpen((open) => {
          if (open && isAgentBusyRef.current) return true;
          const nextOpen = !open;
          if (nextOpen) setIsChoosingRole(!roleIdRef.current);
          return nextOpen;
        });
      }
    };

    window.addEventListener("pointermove", onWindowPointerMove);
    window.addEventListener("pointerup", onWindowPointerUp);
    window.addEventListener("pointercancel", onWindowPointerUp);

    return () => {
      window.removeEventListener("pointermove", onWindowPointerMove);
      window.removeEventListener("pointerup", onWindowPointerUp);
      window.removeEventListener("pointercancel", onWindowPointerUp);
    };
  }, []);

  return (
    <div className="agent-layer">
      {isOpen && (
        <section
          className="agent-panel"
          style={panelStyle}
          aria-label="Traffic assistant"
        >
          {isChoosingRole || !selectedRole ? (
            <RolePicker onSelect={selectRole} currentRole={roleId} />
          ) : (
            <ChatPanel
              key={selectedRole.id}
              role={selectedRole}
              onChangeRole={openRolePicker}
              onBusyChange={setIsAgentBusy}
            />
          )}
        </section>
      )}

      <button
        className={`agent-mascot ${isOpen ? "open" : ""}`}
        type="button"
        style={{ left: position.x, top: position.y }}
        onPointerDown={onPointerDown}
        onPointerCancel={() => {
          dragState.current = null;
        }}
        aria-label={isOpen ? "Close traffic assistant" : "Open traffic assistant"}
        title={isAgentBusy ? "Generating answer..." : "Drag me or click to chat"}
      >
        <span className="agent-online-dot" />
        <img src={agentImage} alt="Traffic assistant" draggable="false" />
      </button>
    </div>
  );
}
