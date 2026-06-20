export const TRAFFIC_LEVELS = {
  smooth: {
    label: "Smooth",
    color: "#45aa72",
  },
  light: {
    label: "Light",
    color: "#e7b93f",
  },
  moderate: {
    label: "Moderate",
    color: "#ee8a36",
  },
  heavy: {
    label: "Heavy",
    color: "#ef554a",
  },
  critical: {
    label: "Critical",
    color: "#981f2b",
  },
  unavailable: {
    label: "No forecast data",
    color: "#b7beb8",
  },
};

export const ROAD_DIRECTIONS = {
  A8: ["Munich → Salzburg", "Salzburg → Munich"],
  A93: ["Rosenheim → Kufstein", "Kufstein → Rosenheim"],
};

export const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

export async function fetchDailyTraffic(year, month, road, signal) {
  const params = new URLSearchParams({
    year: String(year),
    month: String(month + 1),
    road,
  });
  const response = await fetch(`/api/calendar/daily?${params}`, { signal });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || "Unable to load daily traffic scores.");
  }

  return response.json();
}

export function formatDateKey(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(
    2,
    "0",
  )}`;
}

export function formatHourRange(hour) {
  return `${String(hour).padStart(2, "0")}:00–${String(
    (hour + 1) % 24,
  ).padStart(2, "0")}:00`;
}

export function getDefaultDateKey() {
  const today = new Date();
  const year = today.getFullYear();

  if (year >= 2023 && year <= 2029) {
    return formatDateKey(year, today.getMonth(), today.getDate());
  }

  return "2026-06-20";
}

function stringSeed(value) {
  let seed = 0;
  for (let index = 0; index < value.length; index += 1) {
    seed = (seed * 31 + value.charCodeAt(index)) % 100003;
  }
  return seed;
}

export function getHourlyStatus(
  dateKey,
  road,
  direction,
  hour,
  segmentIndex = 0,
) {
  const [year, month, day] = dateKey.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const weekday = date.getDay();
  const isWeekend = weekday === 0 || weekday === 6;
  const isSummer = month >= 6 && month <= 9;
  const isWinterHoliday = month === 12 || month === 1;
  const outboundPeak =
    direction === 1 && ((hour >= 6 && hour <= 10) || (hour >= 14 && hour <= 17));
  const inboundPeak =
    direction === 2 && ((hour >= 15 && hour <= 20) || (hour >= 7 && hour <= 9));
  const commutePeak =
    !isWeekend && ((hour >= 7 && hour <= 9) || (hour >= 16 && hour <= 18));
  const nightRelief = hour <= 5 || hour >= 22;
  const seed = stringSeed(
    `${dateKey}-${road}-${direction}-${hour}-${segmentIndex}`,
  );

  let score = seed % 54;
  score += isWeekend ? 9 : 0;
  score += isSummer ? 10 : 0;
  score += isWinterHoliday ? 5 : 0;
  score += outboundPeak || inboundPeak ? 24 : 0;
  score += commutePeak ? 11 : 0;
  score += segmentIndex * 3;
  score -= nightRelief ? 20 : 0;

  if (score >= 80) return "critical";
  if (score >= 60) return "heavy";
  if (score >= 40) return "moderate";
  if (score >= 20) return "light";
  return "smooth";
}

export function statusLabel(status) {
  return TRAFFIC_LEVELS[status]?.label ?? status;
}
