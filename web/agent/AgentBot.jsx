import { useEffect, useMemo, useRef, useState } from "react";
import agentImage from "./assets/bot.webp";
import "./AgentBot.css";

const ROLE_STORAGE_KEY = `alpineflow-agent-role:${import.meta.env.VITE_AGENT_SESSION_ID}`;
const POSITION_STORAGE_KEY = "alpineflow-agent-position";
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

function ChatPanel({ role, onChangeRole }) {
  return (
    <div className="agent-chat">
      <div className="agent-chat-header">
        <div className="agent-chat-avatar">{role.emoji}</div>
        <div>
          <span>TRAFFIC ASSISTANT</span>
          <strong>{role.label} mode</strong>
        </div>
        <button type="button" onClick={onChangeRole}>
          Change role
        </button>
      </div>

      <div className="agent-chat-body">
        <div className="agent-message assistant">
          <img src={agentImage} alt="" />
          <p>{role.welcome}</p>
        </div>
        <div className="agent-coming-soon">
          <span>✦</span>
          Full agent capabilities will be connected here next.
        </div>
      </div>

      <form
        className="agent-composer"
        onSubmit={(event) => event.preventDefault()}
      >
        <input
          type="text"
          placeholder="Ask about your journey…"
          aria-label="Chat message"
          disabled
        />
        <button type="submit" disabled aria-label="Send message">
          ↑
        </button>
      </form>
    </div>
  );
}

export default function AgentBot() {
  const dragState = useRef(null);
  const [roleId, setRoleId] = useState(readStoredRole);
  const [isOpen, setIsOpen] = useState(false);
  const [isChoosingRole, setIsChoosingRole] = useState(!roleId);
  const [position, setPosition] = useState(
    () => readStoredPosition() ?? defaultPosition(),
  );
  const selectedRole = ROLES.find((role) => role.id === roleId) ?? null;

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
    const panelWidth = Math.min(354, window.innerWidth - 24);
    const panelHeight = isChoosingRole ? 510 : 438;
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
    window.localStorage.setItem(ROLE_STORAGE_KEY, nextRole);
    setRoleId(nextRole);
    setIsChoosingRole(false);
  };

  const togglePanel = () => {
    setIsOpen((open) => {
      const nextOpen = !open;
      if (nextOpen) setIsChoosingRole(!roleId);
      return nextOpen;
    });
  };

  const onPointerDown = (event) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragState.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: position.x,
      originY: position.y,
      moved: false,
    };
  };

  const onPointerMove = (event) => {
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

  const onPointerUp = (event) => {
    const drag = dragState.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragState.current = null;
    if (!drag.moved) togglePanel();
  };

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
              role={selectedRole}
              onChangeRole={() => setIsChoosingRole(true)}
            />
          )}
        </section>
      )}

      <button
        className={`agent-mascot ${isOpen ? "open" : ""}`}
        type="button"
        style={{ left: position.x, top: position.y }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => {
          dragState.current = null;
        }}
        aria-label={isOpen ? "Close traffic assistant" : "Open traffic assistant"}
        title="Drag me or click to chat"
      >
        <span className="agent-online-dot" />
        <img src={agentImage} alt="Traffic assistant" draggable="false" />
      </button>
    </div>
  );
}
