import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DateField } from "./TimeControls";
import "./MyPlanPage.css";

// Base data for the hourly traffic stats
const BASE_STATS = [
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
  { p: 1950, c: -180 },
  { p: 1800, c: -90 },
  { p: 1400, c: 30 },
  { p: 950, c: 110 },
  { p: 600, c: 150 },
  { p: 400, c: 40 },
  { p: 250, c: 10 },
  { p: 180, c: 5 },
];

// Generate random fluctuation for live updates
function generateLiveStats(baseStats) {
  return baseStats.map((stat) => {
    const fluctuation = Math.floor(Math.random() * 30) - 15;
    const newP = Math.max(10, stat.p + fluctuation);
    const newC = Math.floor(Math.random() * 16) - 8;
    return { p: newP, c: newC };
  });
}

function LiveClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const hours = String(time.getHours()).padStart(2, "0");
  const minutes = String(time.getMinutes()).padStart(2, "0");
  const seconds = String(time.getSeconds()).padStart(2, "0");

  return (
    <div className="live-clock">
      <span className="clock-label">Last Update</span>
      <span className="clock-time">
        {hours}:{minutes}:<span className="clock-seconds">{seconds}</span>
      </span>
    </div>
  );
}

function LiveMonitorBar({ changedCount }) {
  return (
    <div className="live-monitor-bar">
      <div className="monitor-left">
        <span className="pulse-dot" />
        <div className="monitor-text">
          <h3>Real-time Schedule Monitor - A8 Munich → Salzburg</h3>
          <p>
            In the past hour,{" "}
            <span className="highlight-number">{changedCount.toLocaleString()}</span>{" "}
            people changed their travel plans
          </p>
        </div>
      </div>
      <LiveClock />
    </div>
  );
}

function HourCell({ hour, data, isSelected, isRecommended, onClick }) {
  const barColor =
    data.p > 1500
      ? "#ef554a"
      : data.p > 800
        ? "#ee8a36"
        : "#45aa72";
  const height = (data.p / 2000) * 100;

  return (
    <button
      type="button"
      className={`hour-cell hour-cell-btn ${isSelected ? "my-plan-slot" : ""} ${isRecommended ? "recommended-slot" : ""}`}
      onClick={() => onClick(hour)}
      title={`Click to select ${hour}:00 as departure time`}
    >
      {isSelected && <span className="my-tag">My Plan</span>}
      {isRecommended && !isSelected && (
        <span className="recommend-tag">Best</span>
      )}
      <div className={`cell-value ${data.p > 1500 ? "value-critical" : ""}`}>
        {data.p}
      </div>
      <div className="bar-bg">
        <div
          className="bar-fill"
          style={{ height: `${height}%`, backgroundColor: barColor }}
        />
      </div>
      <div className={`trend ${data.c > 0 ? "trend-up" : "trend-down"}`}>
        {data.c > 0 ? "↑" : "↓"}
        {Math.abs(data.c)}
      </div>
    </button>
  );
}

function ConfirmModal({ isOpen, onClose, onConfirm, fromHour, toHour, timeSaved }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">Change Departure Time?</h3>
        <div className="modal-body">
          <div className="time-change">
            <div className="time-from">
              <span className="time-label">Current</span>
              <span className="time-value">{fromHour}:00</span>
            </div>
            <span className="time-arrow">→</span>
            <div className="time-to">
              <span className="time-label">New</span>
              <span className="time-value">{toHour}:00</span>
            </div>
          </div>
          {timeSaved > 0 && (
            <p className="time-benefit">
              ✨ You'll save approximately{" "}
              <strong>{timeSaved} minutes</strong> of waiting time!
            </p>
          )}
          {timeSaved < 0 && (
            <p className="time-warning">
              ⚠️ This time slot has{" "}
              <strong>{Math.abs(timeSaved)} more minutes</strong> of expected delay.
            </p>
          )}
        </div>
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-confirm" onClick={onConfirm}>
            Confirm Change
          </button>
        </div>
      </div>
    </div>
  );
}

function Toast({ message, isVisible }) {
  return (
    <div className={`toast ${isVisible ? "toast-visible" : ""}`}>
      <span className="toast-icon">✓</span>
      {message}
    </div>
  );
}

export default function MyPlanPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [selectedDate, setSelectedDate] = useState("2026-07-25");
  const [myPlanHour, setMyPlanHour] = useState(16);
  const [pendingHour, setPendingHour] = useState(null);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [changedCount, setChangedCount] = useState(1284);
  const [liveStats, setLiveStats] = useState(BASE_STATS);

  // Live data updates every 2 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setLiveStats(generateLiveStats(BASE_STATS));
      // Randomly increment changed count
      if (Math.random() > 0.5) {
        setChangedCount((c) => c + Math.floor(Math.random() * 3) + 1);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Find recommended hour (lowest traffic)
  const recommendedHour = useMemo(() => {
    let minIndex = 0;
    let minValue = liveStats[0].p;
    liveStats.forEach((stat, index) => {
      if (stat.p < minValue) {
        minValue = stat.p;
        minIndex = index;
      }
    });
    return minIndex;
  }, [liveStats]);

  const stats = useMemo(() => {
    return liveStats.map((item, index) => ({
      ...item,
      isMe: index === myPlanHour,
    }));
  }, [myPlanHour, liveStats]);

  const mySlot = stats[myPlanHour];
  const recommendedSlot = stats[recommendedHour];

  // Calculate time saved if switching to recommended
  const timeSavedToRecommended = Math.round(
    (mySlot.p - recommendedSlot.p) / 40
  );

  // Calculate rank (1-24)
  const sortedByTraffic = [...stats]
    .map((s, i) => ({ ...s, hour: i }))
    .sort((a, b) => b.p - a.p);
  const currentRank =
    sortedByTraffic.findIndex((s) => s.hour === myPlanHour) + 1;

  // Handle hour cell click
  const handleHourClick = useCallback(
    (hour) => {
      if (hour === myPlanHour) return;
      setPendingHour(hour);
    },
    [myPlanHour]
  );

  // Confirm time change
  const confirmTimeChange = useCallback(() => {
    if (pendingHour === null) return;

    const oldHour = myPlanHour;
    setMyPlanHour(pendingHour);
    setPendingHour(null);

    // Show toast
    setToastMessage(`Departure changed from ${oldHour}:00 to ${pendingHour}:00`);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);

    // Increment changed count
    setChangedCount((c) => c + 1);
  }, [pendingHour, myPlanHour]);

  // Quick switch to recommended
  const switchToRecommended = useCallback(() => {
    if (recommendedHour === myPlanHour) return;
    setPendingHour(recommendedHour);
  }, [recommendedHour, myPlanHour]);

  // Calculate time saved for pending change
  const pendingTimeSaved =
    pendingHour !== null
      ? Math.round((stats[myPlanHour].p - stats[pendingHour].p) / 40)
      : 0;

  // Format date for display
  const formatDisplayDate = (dateStr) => {
    const date = new Date(dateStr);
    const options = { weekday: "short", month: "short", day: "numeric" };
    return date.toLocaleDateString("en-US", options);
  };

  return (
    <div className="myplan-page">
      {/* Toast notification */}
      <Toast message={toastMessage} isVisible={showToast} />

      {/* Confirm modal */}
      <ConfirmModal
        isOpen={pendingHour !== null}
        onClose={() => setPendingHour(null)}
        onConfirm={confirmTimeChange}
        fromHour={myPlanHour}
        toHour={pendingHour}
        timeSaved={pendingTimeSaved}
      />

      {/* Live Monitor Bar */}
      <LiveMonitorBar changedCount={changedCount} />

      {/* Top: Personal Trip Status Bar */}
      <section className="status-section">
        <div className="status-main">
          <div className="status-content">
            <div className="status-text">
              <h2 className="status-title">
                My Current Plan:{" "}
                <span className="highlight-time">
                  {formatDisplayDate(selectedDate)} {myPlanHour}:00
                </span>
              </h2>
              <p className="status-subtitle">
                📍 A8 Munich → Salzburg · Predicted delay:{" "}
                <span className="delay-time">
                  {Math.round(mySlot.p / 40)} min
                </span>
              </p>
            </div>
          </div>

          <div className="status-achievement">
            <div className="achievement-icon">🏆</div>
            <div className="achievement-info">
              <div className="achievement-title">Off-Peak Achievement</div>
              <div className="achievement-stats">
                <span className="avoided-count">Avoided <strong>{Math.round(changedCount * 0.8).toLocaleString()}</strong> people</span>
                <span className="percentile">Ahead of <strong>{Math.round((1 - currentRank / 24) * 100)}%</strong> of users</span>
              </div>
            </div>
          </div>
        </div>

        <div className="savings-card">
          <p className="savings-label">Potential Savings</p>
          <h3 className="savings-value">
            {timeSavedToRecommended > 0 ? `Save ${timeSavedToRecommended} min` : "Optimal!"}
          </h3>
          <div className="savings-badge">
            Switch to {recommendedHour}:00 for best results
          </div>
        </div>
      </section>

      {/* Real-time Dashboard */}
      <div className="dashboard">
        <div className="dashboard-header">
          <div>
            <h3 className="dashboard-title">Traffic Flow Monitor</h3>
            <p className="dashboard-subtitle">
              Click any time slot to change your departure time
            </p>
          </div>
          <div className="dashboard-controls">
            <DateField
              value={selectedDate}
              min="2026-01-01"
              max="2029-12-31"
              onChange={setSelectedDate}
            />
            <span className="tag-status">
              <span className="live-dot"></span>
              Live
            </span>
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
              <HourCell
                key={hour}
                hour={hour}
                data={data}
                isSelected={hour === myPlanHour}
                isRecommended={hour === recommendedHour}
                onClick={handleHourClick}
              />
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="grid-legend">
          <div className="legend-item">
            <span className="legend-color legend-green"></span>
            <span>Low (0-800)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color legend-orange"></span>
            <span>Medium (800-1500)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color legend-red"></span>
            <span>High (1500+)</span>
          </div>
          <div className="legend-item">
            <span className="legend-box legend-selected"></span>
            <span>Your selection</span>
          </div>
          <div className="legend-item">
            <span className="legend-box legend-recommended"></span>
            <span>Recommended</span>
          </div>
        </div>
      </div>

      {/* Bottom: One-click Reschedule Suggestion */}
      {myPlanHour !== recommendedHour && (
        <div className="suggestion-bar">
          <div className="suggestion-content">
            <div className="suggestion-info">
              <div className="suggestion-badge">
                ✨ <strong>Better Option Found!</strong>
              </div>
              <p className="suggestion-text">
                Switch to{" "}
                <span className="suggested-time">{recommendedHour}:00</span> to
                save{" "}
                <span className="time-saved">{timeSavedToRecommended} min</span>{" "}
                of waiting.{" "}
                <span className="others-count">{changedCount} people</span> already
                optimized their plans today.
              </p>
            </div>
            <div className="suggestion-actions">
              <button className="btn-ignore">Ignore</button>
              <button className="btn-accept" onClick={switchToRecommended}>
                Switch to {recommendedHour}:00
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Spacer to prevent content being hidden by fixed bar */}
      <div className="bottom-spacer"></div>
    </div>
  );
}
