export const TRAFFIC_LEVELS = {
  smooth: {
    label: "Smooth",
    color: "#45aa72",
  },
  busy: {
    label: "Busy",
    color: "#e7b93f",
  },
  heavy: {
    label: "Heavy",
    color: "#ef554a",
  },
};

export const ROAD_DIRECTIONS = {
  A8: ["Munich → Salzburg", "Salzburg → Munich"],
  A93: ["Rosenheim → Kufstein", "Kufstein → Rosenheim"],
};

export const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

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

  if (score >= 70) return "heavy";
  if (score >= 42) return "busy";
  return "smooth";
}

export function getDailyStatus(dateKey, road, direction) {
  const [year, month, day] = dateKey.split("-").map(Number);
  const weekday = new Date(year, month - 1, day).getDay();
  const isWeekend = weekday === 0 || weekday === 6;
  const isPeakSeason = month === 2 || (month >= 6 && month <= 9) || month === 12;
  const seed = stringSeed(`${dateKey}-${road}-${direction}-daily`);
  let score = seed % 82;
  score += isWeekend ? 7 : 0;
  score += isPeakSeason ? 7 : 0;

  if (score >= 72) return "heavy";
  if (score >= 39) return "busy";
  return "smooth";
}

export function statusLabel(status) {
  return TRAFFIC_LEVELS[status]?.label ?? status;
}
