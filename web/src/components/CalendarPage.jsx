import { useMemo, useState } from "react";

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
const ROADS = {
  a8: {
    id: "a8",
    name: "A8",
    directions: [
      { label: "Munich → Salzburg", shortLabel: "→ SBG", seed: 0 },
      { label: "Salzburg → Munich", shortLabel: "→ MUC", seed: 1 },
    ],
  },
  a93: {
    id: "a93",
    name: "A93",
    directions: [
      { label: "Rosenheim → Kufstein", shortLabel: "→ KUF", seed: 2 },
      { label: "Kufstein → Rosenheim", shortLabel: "→ ROS", seed: 3 },
    ],
  },
};

function demoTrafficStatus(year, month, day, roadIndex) {
  const value =
    Math.sin(year * 13.17 + month * 7.31 + day * 3.77 + roadIndex * 11.93) *
    10000;
  const weekend = new Date(year, month, day).getDay() % 6 === 0;
  const seasonalPeak = month === 6 || month === 7 || month === 11;
  const score = Math.abs(Math.floor(value)) % 100;
  return score + (weekend ? 18 : 0) + (seasonalPeak ? 8 : 0) > 58
    ? "heavy"
    : "smooth";
}

function buildMonth(year, month, road) {
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const mondayOffset = (firstDay.getDay() + 6) % 7;

  return Array.from({ length: 42 }, (_, index) => {
    const day = index - mondayOffset + 1;
    if (day < 1 || day > daysInMonth) return null;

    return {
      day,
      date: new Date(year, month, day),
      directions: road.directions.map((direction) =>
        demoTrafficStatus(year, month, day, direction.seed),
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

export default function CalendarPage() {
  const today = new Date();
  const initialYear = YEARS.includes(today.getFullYear())
    ? today.getFullYear()
    : 2026;
  const [year, setYear] = useState(initialYear);
  const [month, setMonth] = useState(
    YEARS.includes(today.getFullYear()) ? today.getMonth() : 5,
  );
  const [roadId, setRoadId] = useState("a8");
  const [selectedDay, setSelectedDay] = useState(null);
  const road = ROADS[roadId];

  const days = useMemo(() => buildMonth(year, month, road), [year, month, road]);

  const moveMonth = (offset) => {
    const next = new Date(year, month + offset, 1);
    const nextYear = next.getFullYear();

    if (!YEARS.includes(nextYear)) return;

    setYear(nextYear);
    setMonth(next.getMonth());
    setSelectedDay(null);
  };

  const selected = selectedDay
    ? days.find((item) => item?.day === selectedDay)
    : null;

  return (
    <section className="calendar-page page-container">
      <div className="page-heading">
        <div>
          <span className="eyebrow">TRAFFIC OUTLOOK · 2023–2029</span>
          <h1>When will the road get busy?</h1>
          <p>
            Choose a highway to compare average congestion in both directions.
          </p>
        </div>

        <div className="legend-card" aria-label="Traffic legend">
          <span className="legend-title">Daily average</span>
          <span className="legend-item">
            <i className="legend-dot smooth" />
            Smooth
          </span>
          <span className="legend-item">
            <i className="legend-dot heavy" />
            Heavy
          </span>
        </div>
      </div>

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
                <select
                  value={year}
                  onChange={(event) => {
                    setYear(Number(event.target.value));
                    setSelectedDay(null);
                  }}
                  aria-label="Select year"
                >
                  {YEARS.map((availableYear) => (
                    <option value={availableYear} key={availableYear}>
                      {availableYear}
                    </option>
                  ))}
                </select>
                <select
                  value={month}
                  onChange={(event) => {
                    setMonth(Number(event.target.value));
                    setSelectedDay(null);
                  }}
                  aria-label="Select month"
                >
                  {MONTHS.map((monthName, monthIndex) => (
                    <option value={monthIndex} key={monthName}>
                      {monthName}
                    </option>
                  ))}
                </select>
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
          </div>

          <div className="road-control">
            <span className="control-label">Selected highway</span>
            <div className="road-selector" aria-label="Select highway">
              {Object.values(ROADS).map((availableRoad) => (
                <button
                  className={availableRoad.id === roadId ? "active" : ""}
                  type="button"
                  key={availableRoad.id}
                  onClick={() => {
                    setRoadId(availableRoad.id);
                    setSelectedDay(null);
                  }}
                  aria-pressed={availableRoad.id === roadId}
                >
                  {availableRoad.name}
                </button>
              ))}
            </div>
            <div className="direction-key">
              {road.directions.map((direction, index) => (
                <span key={direction.label}>
                  <b>{index + 1}</b>
                  {direction.label}
                </span>
              ))}
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
                }`}
                key={item.date.toISOString()}
                onClick={() => setSelectedDay(item.day)}
                aria-label={`${MONTHS[month]} ${item.day}, ${year}. ${road.directions[0].label} ${item.directions[0]}, ${road.directions[1].label} ${item.directions[1]}.`}
              >
                <span className="day-number">{item.day}</span>
                <span className="traffic-bars" aria-hidden="true">
                  <i className={item.directions[0]} />
                  <i className={item.directions[1]} />
                </span>
                <span className="mobile-road-labels">
                  <small>1</small>
                  <small>2</small>
                </span>
              </button>
            ) : (
              <div className="day-cell empty" key={`empty-${index}`} />
            ),
          )}
        </div>

        <div className={`selection-summary ${selected ? "visible" : ""}`}>
          {selected ? (
            <>
              <div>
                <span>Selected date</span>
                <strong>
                  {MONTHS[month]} {selected.day}, {year}
                </strong>
              </div>
              <div className="summary-routes">
                {road.directions.map((direction, index) => (
                  <span key={direction.label}>
                    <b className={`route-badge ${road.id}`}>{road.name}</b>
                    <span className="direction-name">{direction.label}</span>
                    <i
                      className={`legend-dot ${selected.directions[index]}`}
                    />
                    {selected.directions[index] === "smooth"
                      ? "Smooth"
                      : "Heavy"}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <p>Select a date to inspect both directions of {road.name}.</p>
          )}
        </div>
      </div>
    </section>
  );
}
