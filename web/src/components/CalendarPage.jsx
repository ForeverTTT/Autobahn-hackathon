import { useEffect, useMemo, useState } from "react";
import {
  fetchDailyTraffic,
  formatDateKey,
  formatHourRange,
  getHourlyStatus,
  HOURS,
  ROAD_DIRECTIONS,
  statusLabel,
} from "../lib/trafficData";
import RouteArrow from "../../arrows/RouteArrow";
import { SelectMenu } from "./TimeControls";

const YEARS = Array.from({ length: 7 }, (_, index) => 2023 + index);
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ROADS = [
  { id: "A8", className: "a8" },
  { id: "A93", className: "a93" },
];
const STATUS_SCORE = {
  smooth: 0,
  light: 1,
  moderate: 2,
  heavy: 3,
  critical: 4,
};
const SCORE_STATUS = ["smooth", "light", "moderate", "heavy", "critical"];

function buildTrafficOverview(dateKey, road, direction) {
  return Array.from({ length: 6 }, (_, index) => {
    const startHour = index * 4;
    const statuses = Array.from({ length: 4 }, (_, hourOffset) =>
      getHourlyStatus(dateKey, road, direction, startHour + hourOffset),
    );
    const averageScore =
      statuses.reduce((total, status) => total + STATUS_SCORE[status], 0) /
      statuses.length;

    return {
      label: `${String(startHour).padStart(2, "0")}–${String(
        startHour + 4,
      ).padStart(2, "0")}`,
      status: SCORE_STATUS[Math.round(averageScore)],
    };
  });
}

function buildMonth(year, month, trafficDays) {
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const mondayOffset = (firstDay.getDay() + 6) % 7;
  const trafficByDate = new Map(
    trafficDays.map((item) => [item.date, item.directions]),
  );

  return Array.from({ length: 42 }, (_, index) => {
    const day = index - mondayOffset + 1;
    if (day < 1 || day > daysInMonth) return null;

    const dateKey = formatDateKey(year, month, day);
    const directionData = trafficByDate.get(dateKey) || [];
    return {
      day,
      dateKey,
      directions: [0, 1].map(
        (directionIndex) =>
          directionData[directionIndex]?.level || "unavailable",
      ),
      scores: [0, 1].map(
        (directionIndex) => directionData[directionIndex]?.score ?? null,
      ),
    };
  });
}

function ArrowIcon({ direction }) {
  return (
    <svg
      className={direction === "right" ? "arrow-right" : ""}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  );
}

export default function CalendarPage() {
  const today = new Date();
  const initialYear = YEARS.includes(today.getFullYear())
    ? today.getFullYear()
    : 2026;
  const [year, setYear] = useState(initialYear);
  const [month, setMonth] = useState(
    YEARS.includes(today.getFullYear()) ? today.getMonth() : 5,
  );
  const [road, setRoad] = useState("A8");
  const [selectedDay, setSelectedDay] = useState(null);
  const [detailDirection, setDetailDirection] = useState(1);
  const [trafficDays, setTrafficDays] = useState([]);
  const [trafficState, setTrafficState] = useState("loading");
  const todayKey = formatDateKey(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );

  useEffect(() => {
    const controller = new AbortController();
    setTrafficDays([]);
    setTrafficState("loading");

    fetchDailyTraffic(year, month, road, controller.signal)
      .then((payload) => {
        setTrafficDays(payload.days || []);
        setTrafficState("ready");
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        console.error(error);
        setTrafficState("error");
      });

    return () => controller.abort();
  }, [year, month, road]);

  const days = useMemo(
    () => buildMonth(year, month, trafficDays),
    [year, month, trafficDays],
  );
  const selected = selectedDay
    ? days.find((item) => item?.day === selectedDay)
    : null;
  const directions = ROAD_DIRECTIONS[road];
  const trafficOverview = useMemo(
    () =>
      selected
        ? buildTrafficOverview(selected.dateKey, road, detailDirection)
        : [],
    [selected?.dateKey, road, detailDirection],
  );

  const moveMonth = (offset) => {
    const next = new Date(year, month + offset, 1);
    const nextYear = next.getFullYear();
    if (!YEARS.includes(nextYear)) return;

    setYear(nextYear);
    setMonth(next.getMonth());
    setSelectedDay(null);
  };

  const goToToday = () => {
    if (!YEARS.includes(today.getFullYear())) return;
    setYear(today.getFullYear());
    setMonth(today.getMonth());
    setSelectedDay(null);
  };

  const toggleDay = (day) => {
    setSelectedDay((currentDay) => (currentDay === day ? null : day));
    if (selectedDay !== day) setDetailDirection(1);
  };

  const openHourOnMap = (hour) => {
    const params = new URLSearchParams({
      date: selected.dateKey,
      hour: String(hour),
      road,
      direction: String(detailDirection),
    });
    window.location.hash = `#/map?${params.toString()}`;
  };

  return (
    <>
      <section className="calendar-page page-container">
        <div className="calendar-card">
          <div className="calendar-toolbar">
            <div className="month-navigation">
              <button
                type="button"
                onClick={() => moveMonth(-1)}
                disabled={year === YEARS[0] && month === 0}
                aria-label="Previous month"
              >
                <ArrowIcon direction="left" />
              </button>
              <div className="date-selectors">
                <span>Selected month</span>
                <div className="date-select-row">
                  <SelectMenu
                    ariaLabel="Select year"
                    value={year}
                    minWidth={82}
                    options={YEARS.map((availableYear) => ({
                      value: availableYear,
                      label: String(availableYear),
                    }))}
                    onChange={(nextYear) => {
                      setYear(nextYear);
                      setSelectedDay(null);
                    }}
                  />
                  <SelectMenu
                    ariaLabel="Select month"
                    value={month}
                    minWidth={120}
                    options={MONTHS.map((monthName, monthIndex) => ({
                      value: monthIndex,
                      label: monthName,
                    }))}
                    onChange={(nextMonth) => {
                      setMonth(nextMonth);
                      setSelectedDay(null);
                    }}
                  />
                </div>
              </div>
              <button
                type="button"
                onClick={() => moveMonth(1)}
                disabled={year === YEARS.at(-1) && month === 11}
                aria-label="Next month"
              >
                <ArrowIcon direction="right" />
              </button>
              <button
                className="today-button"
                type="button"
                onClick={goToToday}
                disabled={!YEARS.includes(today.getFullYear())}
              >
                Today
              </button>
            </div>

            <div className="road-control">
              <span className="control-label">Selected highway</span>
              <div className="road-selector" aria-label="Select highway">
                {ROADS.map((availableRoad) => (
                  <button
                    className={availableRoad.id === road ? "active" : ""}
                    type="button"
                    key={availableRoad.id}
                    onClick={() => {
                      setRoad(availableRoad.id);
                      setSelectedDay(null);
                      setDetailDirection(1);
                    }}
                    aria-pressed={availableRoad.id === road}
                  >
                    {availableRoad.id}
                  </button>
                ))}
              </div>
              <div className="direction-key-row">
                <div className="direction-key">
                  <span className="dir-legend">
                    <span className="dir-legend-name">{directions[0]}</span>
                    <span className="dir-legend-name">{directions[1]}</span>
                  </span>
                </div>
                <div className="legend-inline" aria-label="Traffic legend">
                  <span className="legend-title">Traffic level</span>
                  <span className="legend-item">
                    <i className="legend-dot smooth" />
                    Smooth
                  </span>
                  <span className="legend-item">
                    <i className="legend-dot light" />
                    Light
                  </span>
                  <span className="legend-item">
                    <i className="legend-dot moderate" />
                    Moderate
                  </span>
                  <span className="legend-item">
                    <i className="legend-dot heavy" />
                    Heavy
                  </span>
                  <span className="legend-item">
                    <i className="legend-dot critical" />
                    Critical
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="calendar-grid weekday-row">
            {WEEKDAYS.map((weekday) => (
              <div key={weekday}>{weekday}</div>
            ))}
          </div>

          <div className="calendar-grid days-grid">
            {days.map((item, index) =>
              item ? (
                <button
                  type="button"
                  className={`day-cell ${
                    selectedDay === item.day ? "selected" : ""
                  } ${item.dateKey === todayKey ? "today" : ""}`}
                  key={item.dateKey}
                  onClick={() => toggleDay(item.day)}
                  aria-current={item.dateKey === todayKey ? "date" : undefined}
                  aria-label={`${MONTHS[month]} ${item.day}, ${year}. ${directions[0]} ${statusLabel(item.directions[0])}${item.scores[0] === null ? "" : `, score ${item.scores[0]}`}; ${directions[1]} ${statusLabel(item.directions[1])}${item.scores[1] === null ? "" : `, score ${item.scores[1]}`}.`}
                >
                  <span className="day-number">{item.day}</span>
                  <span
                    className={`calendar-route-shapes ${road.toLowerCase()}`}
                  >
                    <span
                      className="day-bar"
                      role="img"
                      aria-label={`${directions[0]}: ${statusLabel(item.directions[0])}; ${directions[1]}: ${statusLabel(item.directions[1])}`}
                    >
                      <i className={`day-bar-half ${item.directions[0]}`} />
                      <i className={`day-bar-half ${item.directions[1]}`} />
                    </span>
                  </span>
                </button>
              ) : (
                <div className="day-cell empty" key={`empty-${index}`} />
              ),
            )}
          </div>

          <div className="calendar-help">
            {trafficState === "loading" &&
              "Loading daily congestion scores…"}
            {trafficState === "error" &&
              "Daily scores could not be loaded. Start the backend on port 8000."}
            {trafficState === "ready" &&
              year < 2026 &&
              "Daily forecast data is available from 2026 to 2029."}
            {trafficState === "ready" &&
              year >= 2026 &&
              "Colors use the daily average score across the three stations in each direction."}
          </div>
        </div>
      </section>

      <aside
        className={`day-detail-drawer ${selected ? "open" : ""}`}
        aria-hidden={!selected}
      >
        {selected && (
          <>
            <div className="drawer-header">
              <div>
                <span className="panel-kicker">HOURLY TRAFFIC</span>
                <h2>
                  {MONTHS[month]} {selected.day}, {year}
                </h2>
                <p>{road} corridor forecast</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDay(null)}
                aria-label="Close hourly traffic"
              >
                <CloseIcon />
              </button>
            </div>

            <div className="drawer-direction">
              <span>Direction</span>
              <div>
                {directions.map((direction, index) => (
                  <button
                    className={detailDirection === index + 1 ? "active" : ""}
                    type="button"
                    key={direction}
                    onClick={() => setDetailDirection(index + 1)}
                  >
                    <RouteArrow
                      road={road}
                      direction={index + 1}
                      status="neutral"
                      label={direction}
                    />
                    {direction}
                  </button>
                ))}
              </div>
            </div>

            <div className="traffic-overview">
              <span className="traffic-overview-title">
                4-hour average traffic
              </span>
              <div className="traffic-overview-line">
                {trafficOverview.map((period) => (
                  <span
                    className={`traffic-overview-segment ${period.status}`}
                    key={period.label}
                    title={`${period.label}: ${statusLabel(period.status)}`}
                  />
                ))}
              </div>
              <div className="traffic-overview-labels">
                {trafficOverview.map((period) => (
                  <span key={period.label}>{period.label}</span>
                ))}
              </div>
            </div>

            <div className="hourly-list-heading">
              <span>Time</span>
              <span>Traffic condition</span>
            </div>

            <div className="hourly-list">
              {HOURS.map((hour) => {
                const status = getHourlyStatus(
                  selected.dateKey,
                  road,
                  detailDirection,
                  hour,
                );

                return (
                  <button
                    type="button"
                    className="hour-row"
                    key={hour}
                    onClick={() => openHourOnMap(hour)}
                    title="Open this hour on the map"
                  >
                    <span>{formatHourRange(hour)}</span>
                    <span className={`hour-status ${status}`}>
                      <i />
                      {statusLabel(status)}
                    </span>
                    <span className="hour-arrow">→</span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </aside>
    </>
  );
}
