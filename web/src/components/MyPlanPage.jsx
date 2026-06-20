import { useMemo, useState } from "react";
import "./MyPlanPage.css";

// Mock data for the hourly traffic stats
const MOCK_STATS = [
  { p: 120, c: -2 },
  { p: 80, c: 0 },
  { p: 40, c: 1 },
  { p: 20, c: 0 },
  { p: 30, c: 5 },
  { p: 90, c: 12 },
  { p: 300, c: -10 },
  { p: 600, c: -25 },
  { p: 900, c: -40 },
  { p: 1300, c: -80 },
  { p: 1600, c: -120 },
  { p: 1550, c: -50 },
  { p: 1400, c: -10 },
  { p: 1200, c: 15 },
  { p: 1300, c: 20 },
  { p: 1500, c: -30 },
  { p: 1950, c: -180, isMe: true }, // 16:00 - user's planned time
  { p: 1800, c: -90 },
  { p: 1400, c: 30 },
  { p: 950, c: 110 },
  { p: 600, c: 150 },
  { p: 400, c: 40 },
  { p: 250, c: 10 },
  { p: 180, c: 5 },
];

function HourCell({ hour, data }) {
  const barColor =
    data.p > 1500 ? "#f43f5e" : data.p > 800 ? "#f59e0b" : "#10b981";
  const height = (data.p / 2000) * 100;

  return (
    <div className={`hour-cell ${data.isMe ? "my-plan-slot" : ""}`}>
      {data.isMe && <span className="my-tag">My Plan</span>}
      <div
        className={`text-lg font-mono font-bold mb-1 ${
          data.p > 1500 ? "text-rose-500" : "text-slate-300"
        }`}
      >
        {data.p}
      </div>
      <div className="bar-bg">
        <div
          className="bar-fill"
          style={{ height: `${height}%`, backgroundColor: barColor }}
        />
      </div>
      <div
        className={`font-mono font-bold text-xs ${
          data.c > 0 ? "trend-up" : "trend-down"
        }`}
      >
        {data.c > 0 ? "↑" : "↓"}
        {Math.abs(data.c)}
      </div>
    </div>
  );
}

export default function MyPlanPage() {
  const [myPlanHour] = useState(16);
  const [suggestedHour] = useState(20);

  const stats = useMemo(() => {
    return MOCK_STATS.map((item, index) => ({
      ...item,
      isMe: index === myPlanHour,
    }));
  }, [myPlanHour]);

  const mySlot = stats[myPlanHour];
  const suggestedSlot = stats[suggestedHour];
  const timeSaved = Math.round((mySlot.p - suggestedSlot.p) / 40);

  return (
    <div className="myplan-page">
      {/* Top: Personal Trip Status Bar */}
      <section className="status-section">
        <div className="status-main">
          {/* Decorative background */}
          <div className="status-decoration">
            <svg width="200" height="200" fill="white">
              <circle cx="100" cy="100" r="100" />
            </svg>
          </div>

          <div className="status-content">
            <div className="avatar-container">
              <div className="avatar">
                <span className="avatar-icon">🚗</span>
              </div>
              <span className="status-indicator"></span>
            </div>
            <div className="status-text">
              <h2 className="status-title">
                My Current Plan:{" "}
                <span className="highlight-time">Today {myPlanHour}:00</span>
              </h2>
              <p className="status-subtitle">
                📍 A8 Munich → Salzburg · Predicted delay:{" "}
                <span className="delay-time">45 min</span>
              </p>
            </div>
          </div>

          <div className="status-rank">
            <div className="rank-label">Current Time Slot Rank</div>
            <div className="rank-value">No. 2 / 24</div>
            <div className="rank-warning">Peak congestion period</div>
          </div>
        </div>

        <div className="achievement-card">
          <p className="achievement-label">Congestion Avoided</p>
          <h3 className="achievement-value">Saved 35 min</h3>
          <div className="achievement-badge">Better than 88% of users</div>
        </div>
      </section>

      {/* Real-time Dashboard */}
      <div className="dashboard">
        <div className="dashboard-header">
          <div>
            <h3 className="dashboard-title">Traffic Flow Monitor</h3>
            <p className="dashboard-subtitle">
              Yellow highlighted area shows your planned departure time
            </p>
          </div>
          <div className="dashboard-tags">
            <span className="tag-date">2026.07.25</span>
            <span className="tag-status">Live Data</span>
          </div>
        </div>

        <div className="data-grid-container">
          <div className="data-grid">
            {/* Time axis header */}
            <div className="hour-cell header-cell">TIME</div>
            {Array.from({ length: 24 }, (_, i) => (
              <div key={`header-${i}`} className="hour-cell header-cell">
                {i}:00
              </div>
            ))}

            {/* Data row */}
            <div className="hour-cell row-label">Traffic</div>
            {stats.map((data, hour) => (
              <HourCell key={hour} hour={hour} data={data} />
            ))}
          </div>
        </div>
      </div>

      {/* Bottom: One-click Reschedule Suggestion */}
      <div className="suggestion-bar">
        <div className="suggestion-content">
          <div className="suggestion-info">
            <div className="suggestion-badge">
              ✨ <strong>Better Option Found!</strong>
            </div>
            <p className="suggestion-text">
              Switch to{" "}
              <span className="suggested-time">{suggestedHour}:00</span> to save{" "}
              <span className="time-saved">{timeSaved} min</span> of waiting.{" "}
              <span className="others-count">150 people</span> just switched to
              this time slot.
            </p>
          </div>
          <div className="suggestion-actions">
            <button className="btn-ignore">Ignore</button>
            <button className="btn-accept">
              Switch to {suggestedHour}:00
            </button>
          </div>
        </div>
      </div>

      {/* Spacer to prevent content being hidden by fixed bar */}
      <div className="bottom-spacer"></div>
    </div>
  );
}
