// Build public/factors.json for the Map-page GLOBAL radar from the REAL factor
// attribution in data_autobahn/forecast_2026_hourly.csv (the `reason` column:
// "Factor: x.x%；Factor: y.y%；…", Chinese-semicolon separated, 2026 only).
//
// Aggregates the 3 sensor sites of each corridor (road + travel direction) into
// one averaged % per factor per (day-of-2026, hour). Also records each factor's
// global max so the frontend can normalise per-axis (relative strength) while
// still showing the real %.
import { createReadStream, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";

const CSV = "../data_autobahn/forecast_2026_hourly.csv";
const OUT = "public/factors.json";

// canonical factor order (avg-descending) + short labels for the radar
const FACTORS = [
  ["Historical Traffic Baseline", "Baseline"],
  ["Date and Time Pattern", "Time"],
  ["Road Segment and Detector Attributes", "Road"],
  ["Holiday Effect", "Holiday"],
  ["Weather and Temperature", "Weather"],
  ["Special Events", "Event"],
  ["Construction Impact", "Construction"],
];
const LONG = FACTORS.map((f) => f[0]);
const LABELS = FACTORS.map((f) => f[1]);
const NF = FACTORS.length;
const idxOf = new Map(LONG.map((n, i) => [n, i]));

// frontend corridor key  <-  (road, CSV direction)
const corridorKey = (road, dir) => {
  if (road === "A8") return dir === "Sbg" ? "A8-1" : "A8-2";
  if (road === "A93") return dir === "Kff" ? "A93-1" : "A93-2";
  return null;
};

const DAYS = 365; // 2026 is not a leap year
const HOURS = 24;
const N = DAYS * HOURS;
const startUTC = Date.UTC(2026, 0, 1);
const dayIndex = (dateStr) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  return Math.round((Date.UTC(y, m - 1, d) - startUTC) / 86400000);
};

// corridors[key] = Float arrays: sum[idx*NF+f] and cnt[idx] (sites contributing)
const KEYS = ["A8-1", "A8-2", "A93-1", "A93-2"];
const sum = {};
const cnt = {};
for (const k of KEYS) {
  sum[k] = new Float64Array(N * NF);
  cnt[k] = new Int16Array(N);
}

const parseReason = (reason) => {
  const out = new Float64Array(NF);
  for (const part of reason.split("；")) {
    const p = part.trim();
    if (!p) continue;
    const sep = p.includes("：") ? "：" : ":";
    const at = p.lastIndexOf(sep);
    if (at < 0) continue;
    const name = p.slice(0, at).trim();
    const val = parseFloat(p.slice(at + 1).replace("%", "").trim());
    const fi = idxOf.get(name);
    if (fi !== undefined && Number.isFinite(val)) out[fi] = val;
  }
  return out;
};

const rl = createInterface({ input: createReadStream(CSV) });
let header = null;
let col = {};
let rows = 0;

for await (const line of rl) {
  if (!header) {
    header = line.split(",");
    header.forEach((h, i) => (col[h] = i));
    continue;
  }
  if (!line) continue;
  const f = line.split(",");
  const key = corridorKey(f[col.road], f[col.direction]);
  if (!key) continue;
  const di = dayIndex(f[col.date]);
  const hour = Number(f[col.hour]);
  const idx = di * HOURS + hour;
  if (idx < 0 || idx >= N) continue;
  const pct = parseReason(f[col.reason] ?? "");
  for (let fi = 0; fi < NF; fi += 1) sum[key][idx * NF + fi] += pct[fi];
  cnt[key][idx] += 1;
  rows += 1;
}

// average per site count, round to 1dp; track per-factor global max
const max = new Float64Array(NF);
const corridors = {};
for (const k of KEYS) {
  const arr = new Array(N);
  for (let i = 0; i < N; i += 1) {
    const c = cnt[k][i] || 1;
    const row = new Array(NF);
    for (let fi = 0; fi < NF; fi += 1) {
      const v = Math.round((sum[k][i * NF + fi] / c) * 10) / 10;
      row[fi] = v;
      if (v > max[fi]) max[fi] = v;
    }
    arr[i] = row;
  }
  corridors[k] = arr;
}

writeFileSync(
  OUT,
  JSON.stringify({
    start: "2026-01-01",
    days: DAYS,
    hours: HOURS,
    factors: LABELS,
    max: Array.from(max).map((v) => Math.round(v * 10) / 10),
    corridors,
  }),
);
console.log(
  `rows=${rows} factors=${LABELS.join(",")}\nmax%=${Array.from(max).map((v) => v.toFixed(1)).join(", ")}`,
);
// sanity: print 2026-06-20 08:00 A8-1
const idx = (dayIndex("2026-06-20")) * HOURS + 8;
console.log("A8-1 2026-06-20 08:00 =", corridors["A8-1"][idx]);
