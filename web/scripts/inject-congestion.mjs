// One-off: inject the REAL congestion_score (per site / date / hour) from
// data_autobahn/scored_traffic_2026_2029.csv into public/forecast.json as a
// `cong` array parallel to each site's kfz/sv arrays (same dayIndex*24+hour).
import { createReadStream, readFileSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";

const CSV = "../data_autobahn/scored_traffic_2026_2029.csv";
const JSON_PATH = "public/forecast.json";

const forecast = JSON.parse(readFileSync(JSON_PATH, "utf8"));
const N = forecast.days * forecast.hours; // 1461 * 24
const [sy, sm, sd] = forecast.start.split("-").map(Number);
const startUTC = Date.UTC(sy, sm - 1, sd);

// pre-fill every known site with a zeroed cong array
for (const site of Object.keys(forecast.sites)) {
  forecast.sites[site].cong = new Array(N).fill(0);
}

const dayIndex = (dateStr) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  return Math.round((Date.UTC(y, m - 1, d) - startUTC) / 86400000);
};

const rl = createInterface({ input: createReadStream(CSV) });
let header = null;
let col = {};
let filled = 0;
let skipped = 0;

for await (const line of rl) {
  if (!header) {
    header = line.split(",");
    header.forEach((h, i) => (col[h] = i));
    continue;
  }
  if (!line) continue;
  const f = line.split(",");
  const site = f[col.site_id];
  const entry = forecast.sites[site];
  if (!entry) {
    skipped += 1;
    continue;
  }
  const di = dayIndex(f[col.date]);
  const hour = Number(f[col.hour]);
  const idx = di * forecast.hours + hour;
  if (idx < 0 || idx >= N) {
    skipped += 1;
    continue;
  }
  entry.cong[idx] = Number(f[col.congestion_score]);
  filled += 1;
}

writeFileSync(JSON_PATH, JSON.stringify(forecast));
console.log(`filled=${filled} skipped=${skipped} N=${N} sites=${Object.keys(forecast.sites).length}`);
// sanity: print first site's first few cong values
const s0 = Object.keys(forecast.sites)[0];
console.log(s0, "cong[0..4]=", forecast.sites[s0].cong.slice(0, 5));
