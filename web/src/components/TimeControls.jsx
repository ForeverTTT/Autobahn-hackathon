import { useEffect, useRef, useState } from "react";
import { formatHourRange, HOURS } from "../lib/trafficData";

// Custom date / hour controls so the dropdowns are always English and match
// the app UI (the native <input type="date"> picker follows the OS locale and
// can't be styled).

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
const WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

const pad = (n) => String(n).padStart(2, "0");
const toKey = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;

function useClickOutside(ref, onClose, open) {
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose, ref]);
}

export function DateField({
  value,
  min = "2023-01-01",
  max = "2029-12-31",
  onChange,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false), open);

  const [vy, setVy] = useState(Number(value.slice(0, 4)));
  const [vm, setVm] = useState(Number(value.slice(5, 7)) - 1);

  useEffect(() => {
    if (open) {
      setVy(Number(value.slice(0, 4)));
      setVm(Number(value.slice(5, 7)) - 1);
    }
  }, [open, value]);

  const minY = Number(min.slice(0, 4));
  const maxY = Number(max.slice(0, 4));

  const startOffset = (new Date(vy, vm, 1).getDay() + 6) % 7; // Monday-first
  const daysIn = new Date(vy, vm + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startOffset; i += 1) cells.push(null);
  for (let d = 1; d <= daysIn; d += 1) cells.push(d);

  const prevDisabled = vy < minY || (vy === minY && vm <= 0);
  const nextDisabled = vy > maxY || (vy === maxY && vm >= 11);

  const go = (delta) => {
    let m = vm + delta;
    let y = vy;
    if (m < 0) {
      m = 11;
      y -= 1;
    } else if (m > 11) {
      m = 0;
      y += 1;
    }
    if (y < minY || y > maxY) return;
    setVy(y);
    setVm(m);
  };

  return (
    <div className="tc-field" ref={ref}>
      <button
        type="button"
        className="tc-trigger"
        onClick={() => setOpen((o) => !o)}
      >
        {value}
      </button>
      {open && (
        <div className="tc-popover tc-cal">
          <div className="tc-cal-head">
            <button type="button" onClick={() => go(-1)} disabled={prevDisabled}>
              ‹
            </button>
            <span>
              {MONTHS[vm]} {vy}
            </span>
            <button type="button" onClick={() => go(1)} disabled={nextDisabled}>
              ›
            </button>
          </div>
          <div className="tc-weekdays">
            {WEEKDAYS.map((w) => (
              <span key={w}>{w}</span>
            ))}
          </div>
          <div className="tc-days">
            {cells.map((d, i) =>
              d === null ? (
                <span key={`e${i}`} className="tc-empty" />
              ) : (
                <button
                  key={d}
                  type="button"
                  className={`tc-day${toKey(vy, vm, d) === value ? " sel" : ""}`}
                  onClick={() => {
                    onChange(toKey(vy, vm, d));
                    setOpen(false);
                  }}
                >
                  {d}
                </button>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function SelectMenu({ value, options, onChange, ariaLabel, minWidth }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false), open);
  const current = options.find((o) => o.value === value);

  return (
    <div className="tc-field" ref={ref}>
      <button
        type="button"
        className="tc-trigger tc-trigger--select"
        style={minWidth ? { minWidth } : undefined}
        aria-label={ariaLabel}
        onClick={() => setOpen((o) => !o)}
      >
        {current?.label ?? value}
        <svg className="tc-caret" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="m6 9 6 6 6-6"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && (
        <div className="tc-popover tc-menu">
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              className={`tc-hour${o.value === value ? " sel" : ""}`}
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function HourField({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false), open);

  return (
    <div className="tc-field" ref={ref}>
      <button
        type="button"
        className="tc-trigger"
        onClick={() => setOpen((o) => !o)}
      >
        {formatHourRange(value)}
      </button>
      {open && (
        <div className="tc-popover tc-hours">
          {HOURS.map((h) => (
            <button
              key={h}
              type="button"
              className={`tc-hour${h === value ? " sel" : ""}`}
              onClick={() => {
                onChange(h);
                setOpen(false);
              }}
            >
              {formatHourRange(h)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
