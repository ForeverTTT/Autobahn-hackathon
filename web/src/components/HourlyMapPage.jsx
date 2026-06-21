import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  formatHourRange,
  getDefaultDateKey,
  getHourlyStatus,
  HOURS,
  ROAD_DIRECTIONS,
  statusLabel as getStatusLabel,
  TRAFFIC_LEVELS,
} from "../lib/trafficData";
import { DateField, HourField } from "./TimeControls";
import FactorRadar from "./FactorRadar";

gsap.registerPlugin(ScrollTrigger);

const MAP_ZOOM = 11;

const ROUTE_SEGMENTS = [
  {
    road: "A8",
    title: "Munich — Irschenberg",
    path: [
      [48.102985, 11.613309],
      [48.099703, 11.613585],
      [48.082693, 11.618078],
      [48.080532, 11.619202],
      [48.07831, 11.620895],
      [48.055871, 11.64247],
      [48.053634, 11.644206],
      [48.019704, 11.661283],
      [47.993021, 11.679349],
      [47.988857, 11.681251],
      [47.964563, 11.68811],
      [47.959701, 11.689894],
      [47.95501, 11.69244],
      [47.929939, 11.70863],
      [47.900576, 11.720603],
      [47.897391, 11.722667],
      [47.894947, 11.725096],
      [47.89261, 11.728362],
      [47.890753, 11.732118],
      [47.865908, 11.794052],
      [47.864937, 11.798721],
      [47.864597, 11.802473],
      [47.864617, 11.806272],
      [47.865553, 11.816478],
      [47.865384, 11.821719],
      [47.864375, 11.829177],
      [47.862254, 11.838404],
      [47.861624, 11.844408],
      [47.860757, 11.847438],
      [47.856896, 11.856588],
      [47.854711, 11.859999],
      [47.850389, 11.864567],
      [47.848127, 11.866103],
      [47.843195, 11.868409],
      [47.838404, 11.873118],
      [47.828442, 11.891701],
      [47.827966, 11.893864],
      [47.827964, 11.896551],
      [47.830289, 11.905044],
      [47.830254, 11.91008],
      [47.829209, 11.91345],
      [47.822959, 11.925368],
      [47.822194, 11.928138],
      [47.821968, 11.930531],
      [47.822107, 11.932905],
      [47.822769, 11.935712],
      [47.826237, 11.942252],
      [47.827152, 11.946247],
    ],
  },
  {
    road: "A8",
    title: "Irschenberg — AD Inntal",
    path: [
      [47.827152, 11.946247],
      [47.827089, 11.949446],
      [47.825852, 11.958643],
      [47.822698, 11.966649],
      [47.821758, 11.970965],
      [47.821833, 11.990755],
      [47.820116, 12.016813],
      [47.817883, 12.028939],
      [47.816562, 12.048569],
      [47.814753, 12.063341],
      [47.809363, 12.100301],
      [47.807581, 12.119656],
    ],
  },
  {
    road: "A8",
    title: "AD Inntal — Chiemsee",
    path: [
      [47.807581, 12.119656],
      [47.8047, 12.155214],
      [47.802556, 12.170849],
      [47.802144, 12.185814],
      [47.800846, 12.190415],
      [47.798059, 12.194888],
      [47.796943, 12.197309],
      [47.795949, 12.202291],
      [47.795993, 12.205325],
      [47.796749, 12.21128],
      [47.796389, 12.219229],
      [47.798091, 12.232707],
      [47.797949, 12.245395],
      [47.798331, 12.252927],
      [47.799861, 12.262375],
      [47.803473, 12.274552],
      [47.804118, 12.278938],
      [47.804008, 12.294569],
      [47.803319, 12.302219],
      [47.802027, 12.308204],
      [47.801953, 12.311884],
      [47.806166, 12.332201],
      [47.809315, 12.34115],
      [47.812231, 12.353485],
      [47.814606, 12.359446],
      [47.815871, 12.367031],
      [47.817159, 12.371394],
      [47.821663, 12.379718],
      [47.8248, 12.382807],
      [47.830932, 12.387219],
      [47.832491, 12.389555],
      [47.833674, 12.392871],
      [47.834101, 12.396594],
      [47.83337, 12.408269],
      [47.833971, 12.418107],
      [47.833806, 12.436495],
      [47.834633, 12.442444],
      [47.836797, 12.449708],
      [47.837387, 12.452807],
      [47.83877, 12.479682],
      [47.838651, 12.48439],
      [47.838031, 12.488697],
      [47.831172, 12.516667],
      [47.829219, 12.528551],
      [47.82749, 12.546997],
      [47.827274, 12.552745],
      [47.826287, 12.560322],
      [47.826362, 12.565177],
      [47.828379, 12.583907],
      [47.827899, 12.597563],
      [47.828697, 12.609749],
      [47.827525, 12.619643],
      [47.829211, 12.632147],
      [47.828473, 12.642107],
    ],
  },
  {
    road: "A8",
    title: "Chiemsee — Salzburg",
    path: [
      [47.828473, 12.642107],
      [47.825269, 12.654488],
      [47.825461, 12.668413],
      [47.824325, 12.677188],
      [47.824806, 12.68064],
      [47.827479, 12.688842],
      [47.828819, 12.699364],
      [47.829207, 12.709518],
      [47.829172, 12.722881],
      [47.831148, 12.737223],
      [47.830552, 12.743441],
      [47.829614, 12.746405],
      [47.827183, 12.751569],
      [47.826346, 12.755922],
      [47.827135, 12.769196],
      [47.826548, 12.778071],
      [47.826633, 12.782258],
      [47.829189, 12.797526],
      [47.828807, 12.811229],
      [47.828146, 12.813936],
      [47.826302, 12.818818],
      [47.824731, 12.821799],
      [47.819966, 12.827724],
      [47.813044, 12.83389],
      [47.811129, 12.836055],
      [47.796067, 12.860933],
      [47.794038, 12.863556],
      [47.782041, 12.876],
      [47.769863, 12.894772],
      [47.768294, 12.898085],
      [47.766303, 12.905801],
      [47.765956, 12.908857],
      [47.768084, 12.933921],
      [47.768953, 12.966805],
      [47.770614, 12.976311],
      [47.77044, 12.979205],
      [47.769726, 12.98239],
    ],
  },
  {
    road: "A93",
    title: "AD Inntal — Brannenburg",
    path: [
      [47.807678, 12.119865],
      [47.809298, 12.101951],
      [47.810372, 12.094035],
      [47.810912, 12.093241],
      [47.81144, 12.093544],
      [47.81153, 12.094472],
      [47.811103, 12.095845],
      [47.810424, 12.096571],
      [47.809584, 12.096773],
      [47.808506, 12.096282],
      [47.803986, 12.09204],
      [47.800695, 12.090264],
      [47.797948, 12.089785],
      [47.79159, 12.090121],
      [47.787102, 12.090781],
      [47.781236, 12.09244],
      [47.775271, 12.09512],
      [47.769842, 12.098453],
      [47.763996, 12.103255],
      [47.749821, 12.117781],
      [47.739594, 12.126625],
    ],
  },
  {
    road: "A93",
    title: "Brannenburg — Oberaudorf",
    path: [
      [47.739594, 12.126625],
      [47.723518, 12.138933],
      [47.702306, 12.159092],
      [47.700056, 12.160501],
      [47.697281, 12.161675],
      [47.686149, 12.164221],
      [47.681204, 12.166446],
      [47.676145, 12.17051],
      [47.66801, 12.180687],
      [47.66524, 12.182367],
      [47.66095, 12.183338],
    ],
  },
  {
    road: "A93",
    title: "Oberaudorf — Kiefersfelden",
    path: [
      [47.66095, 12.183338],
      [47.65745, 12.184165],
      [47.653654, 12.185826],
      [47.642069, 12.191992],
      [47.628868, 12.200047],
      [47.623207, 12.201734],
      [47.618073, 12.202362],
      [47.615365, 12.202331],
      [47.612976, 12.201672],
      [47.610559, 12.200331],
      [47.60844, 12.198443],
      [47.606374, 12.19573],
      [47.603915, 12.190965],
      [47.601136, 12.183095],
      [47.598655, 12.178296],
      [47.598249, 12.176169],
    ],
  },
];

const SEVERITY = { smooth: 0, busy: 1, heavy: 2 };

// Real sensor stations per highway + direction, in travel order (start -> end),
// with on-route coordinates (from the main traffic table's bab_km/lat/lng).
// Each direction has exactly 3 sensors — there is none at the Munich end, so
// the chart legitimately begins at the first station (~km 20, near Holzkirchen).
const DIR_STATIONS = {
  "A8-1": [
    { site: "A8_Sbg_MQQ37_Sbg_H", label: "Holzkirchen", lat: 47.936, lng: 11.705 },
    { site: "A8_Sbg_MQQ213_Sbg_H", label: "Chiemsee", lat: 47.828, lng: 12.583 },
    { site: "A8_Sbg_MQQ245_Sbg_H", label: "Traunstein", lat: 47.831, lng: 12.733 },
  ],
  "A8-2": [
    { site: "A8_Mch_MQQ245_Mch_H", label: "Traunstein", lat: 47.831, lng: 12.734 },
    { site: "A8_Mch_MQQ209_Mch_H", label: "Chiemsee", lat: 47.826, lng: 12.565 },
    { site: "A8_Mch_MQB25_Mch_H", label: "Holzkirchen", lat: 47.936, lng: 11.705 },
  ],
  "A93-1": [
    { site: "A93_Kff_MQDZ_AD Inntal_(S)_Kff", label: "AD Inntal", lat: 47.794, lng: 12.09 },
    { site: "A93_Kff_MQ_Gletschergarten_Kff", label: "Gletschergarten", lat: 47.711, lng: 12.151 },
    { site: "A93_Kff_MQDZ_Kiefersfelden_(S)_Kff", label: "Kiefersfelden", lat: 47.606, lng: 12.195 },
  ],
  "A93-2": [
    { site: "A93_Ro_MQDZ_Kiefersfelden_(S)_Ro", label: "Kiefersfelden", lat: 47.606, lng: 12.195 },
    { site: "A93_Ro_MQ_Gletschergarten_Ro", label: "Gletschergarten", lat: 47.71, lng: 12.152 },
    { site: "A93_Ro_MQDZ_AD Inntal_(S)_Ro", label: "AD Inntal", lat: 47.794, lng: 12.09 },
  ],
};

const FORECAST_START = Date.UTC(2026, 0, 1);
const FORECAST_DAYS = 1461;

// Scroll-graph geometry (SVG user units) — a faithful take on the jEVVvOr pen.
const GV = { w: 120, h: 86, x0: 12, x1: 108, yTop: 14, yBase: 72 };
GV.cx = (GV.x0 + GV.x1) / 2;
GV.cy = (GV.yTop + GV.yBase) / 2;

function easeIOExpo(x) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  return x < 0.5
    ? Math.pow(2, 20 * x - 10) / 2
    : (2 - Math.pow(2, -20 * x + 10)) / 2;
}

function dayIndexOf(dateKey) {
  const [y, m, d] = dateKey.split("-").map(Number);
  const idx = Math.round((Date.UTC(y, m - 1, d) - FORECAST_START) / 86400000);
  return Math.max(0, Math.min(FORECAST_DAYS - 1, idx));
}

function statusColor(status) {
  return TRAFFIC_LEVELS[status]?.color ?? TRAFFIC_LEVELS.smooth.color;
}

// Road-segment colour from the REAL congestion_score (scored_traffic CSV).
// Keep these five bands identical to the Calendar daily-score thresholds.
function congestionStatus(score) {
  if (score >= 41) return "critical";
  if (score >= 37) return "heavy";
  if (score >= 31) return "moderate";
  if (score >= 25) return "light";
  return "smooth";
}

// Human-readable phrase per factor, for the MOCK radar narrative. Replaced by
// the live agent message later.
const FACTOR_NOTE = {
  Time: "the time-of-day rush pattern",
  Road: "the road segment & detector layout",
  Holiday: "holiday travel demand",
  Weather: "current weather and temperature",
  Event: "a nearby special event",
  Construction: "active roadworks",
};

const phrase = (label) => FACTOR_NOTE[label] ?? label;
const sentenceCase = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function buildFactorNotes(factors, directionLabel) {
  const ranked = factors
    .filter((f) => f.pct > 0)
    .sort((a, b) => b.pct - a.pct);
  if (!ranked.length) {
    return [
      `No standout situational reason on ${directionLabel} this hour — flow is tracking the historical baseline.`,
    ];
  }
  const notes = [
    `${sentenceCase(phrase(ranked[0].label))} is the main reason shaping flow on ${directionLabel} right now.`,
  ];
  if (ranked[1]) notes.push(`${sentenceCase(phrase(ranked[1].label))} adds a secondary push.`);
  if (ranked[2]) notes.push(`${sentenceCase(phrase(ranked[2].label))} is also in play.`);
  return notes;
}

// Turn the agent's bullet-point explanation string ("• …\n• …") into an array
// of clean bullet lines.
function parseExplanation(text) {
  if (!text || typeof text !== "string") return [];
  return text
    .split(/\r?\n/)
    .map((line) => line.replace(/^\s*[•\-*·–—]+\s*/, "").trim())
    .filter(Boolean);
}

function worseStatus(a, b) {
  return SEVERITY[a] >= SEVERITY[b] ? a : b;
}

function roadSegments(road) {
  return ROUTE_SEGMENTS.map((segment, index) => ({ ...segment, index })).filter(
    (segment) => segment.road === road,
  );
}

function samePoint([latA, lngA], [latB, lngB]) {
  return latA === latB && lngA === lngB;
}

function joinRoadPoints(road, dirNumber) {
  const points = [];
  roadSegments(road).forEach((segment) => {
    segment.path.forEach((point) => {
      if (!points.length || !samePoint(points.at(-1), point)) {
        points.push(point);
      }
    });
  });
  return dirNumber === 2 ? points.reverse() : points;
}

// Project a sensor coordinate onto the route and return its distance from the
// start of the currently selected travel direction.
function distanceAlongRoute(pts, cum, station) {
  let nearestDistance = 0;
  let nearestSquaredDistance = Infinity;

  for (let index = 1; index < pts.length; index += 1) {
    const [latA, lngA] = pts[index - 1];
    const [latB, lngB] = pts[index];
    const referenceLat =
      ((latA + latB + station.lat) / 3) * (Math.PI / 180);
    const longitudeScale = Math.cos(referenceLat);
    const ax = lngA * longitudeScale;
    const ay = latA;
    const bx = lngB * longitudeScale;
    const by = latB;
    const px = station.lng * longitudeScale;
    const py = station.lat;
    const dx = bx - ax;
    const dy = by - ay;
    const lengthSquared = dx * dx + dy * dy;
    const t =
      lengthSquared === 0
        ? 0
        : Math.max(
            0,
            Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared),
          );
    const projectedX = ax + t * dx;
    const projectedY = ay + t * dy;
    const squaredDistance =
      (px - projectedX) ** 2 + (py - projectedY) ** 2;

    if (squaredDistance < nearestSquaredDistance) {
      nearestSquaredDistance = squaredDistance;
      nearestDistance =
        cum[index - 1] + t * (cum[index] - cum[index - 1]);
    }
  }

  return nearestDistance;
}

function sliceBetween(pts, cum, startDistance, endDistance) {
  const sliced = [pointAt(pts, cum, startDistance)];
  for (let index = 1; index < pts.length - 1; index += 1) {
    if (cum[index] > startDistance && cum[index] < endDistance) {
      sliced.push(pts[index]);
    }
  }
  const endPoint = pointAt(pts, cum, endDistance);
  if (!samePoint(sliced.at(-1), endPoint)) sliced.push(endPoint);
  return sliced;
}

// Each direction has three sensor series. The visual road is split into three
// matching data zones, with boundaries halfway between neighbouring sensors.
function buildJourney(road, dirNumber) {
  const pts = joinRoadPoints(road, dirNumber);
  const { cum, len } = cumulative(pts);
  const stations = DIR_STATIONS[`${road}-${dirNumber}`] ?? [];
  const stationDistances = stations.map((station) =>
    distanceAlongRoute(pts, cum, station),
  );
  const boundaries = stationDistances
    .slice(0, -1)
    .map((distance, index) => (distance + stationDistances[index + 1]) / 2);
  const segmentEdges = [0, ...boundaries, len];
  const segments = stations.map((station, index) => ({
    title: `${station.label} sensor zone`,
    stationIndex: index,
    pts: sliceBetween(pts, cum, segmentEdges[index], segmentEdges[index + 1]),
  }));

  return { segments };
}

// Equirectangular step distance — good enough to interpolate evenly along the
// route (we only need relative proportions, not true geodesic metres).
function stepDist([la1, ln1], [la2, ln2]) {
  const dx = (ln2 - ln1) * Math.cos(((la1 + la2) / 2) * (Math.PI / 180));
  const dy = la2 - la1;
  return Math.hypot(dx, dy);
}

function cumulative(pts) {
  const cum = [0];
  let total = 0;
  for (let i = 1; i < pts.length; i += 1) {
    total += stepDist(pts[i - 1], pts[i]);
    cum.push(total);
  }
  return { cum, len: total };
}

function pointAt(pts, cum, dist) {
  const len = cum[cum.length - 1];
  if (dist <= 0) return pts[0];
  if (dist >= len) return pts[pts.length - 1];
  let i = 1;
  while (i < cum.length && cum[i] < dist) i += 1;
  const t = (dist - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
  const [la1, ln1] = pts[i - 1];
  const [la2, ln2] = pts[i];
  return [la1 + (la2 - la1) * t, ln1 + (ln2 - ln1) * t];
}

// Latlngs from the segment start up to `dist` (with an interpolated tip).
function sliceTo(pts, cum, dist) {
  if (dist <= 0) return [];
  const len = cum[cum.length - 1];
  if (dist >= len) return pts;
  const out = [];
  let i = 0;
  while (i < cum.length && cum[i] < dist) {
    out.push(pts[i]);
    i += 1;
  }
  out.push(pointAt(pts, cum, dist));
  return out;
}

function segmentStatus(date, road, direction, hour, segmentIndex) {
  if (direction === "both") {
    return worseStatus(
      getHourlyStatus(date, road, 1, hour, segmentIndex),
      getHourlyStatus(date, road, 2, hour, segmentIndex),
    );
  }
  return getHourlyStatus(date, road, direction, hour, segmentIndex);
}

function analyseCorridor(date, road, direction, hour, segments) {
  const rows = segments.map((segment) => {
    const status = segmentStatus(date, road, direction, hour, segment.index);
    let peakHour = hour;
    let peakSeverity = -1;
    HOURS.forEach((h) => {
      const sev = SEVERITY[segmentStatus(date, road, direction, h, segment.index)];
      if (sev > peakSeverity) {
        peakSeverity = sev;
        peakHour = h;
      }
    });
    return { title: segment.title, status, peakHour };
  });

  const corridorStatus = rows.reduce(
    (acc, row) => worseStatus(acc, row.status),
    "smooth",
  );
  const busiest = rows.reduce(
    (acc, row) => (SEVERITY[row.status] > SEVERITY[acc.status] ? row : acc),
    rows[0] ?? { title: "—", status: "smooth", peakHour: hour },
  );

  let calmHour = hour;
  let calmScore = Infinity;
  HOURS.forEach((h) => {
    const score = segments.reduce(
      (sum, segment) =>
        sum + SEVERITY[segmentStatus(date, road, direction, h, segment.index)],
      0,
    );
    if (score < calmScore) {
      calmScore = score;
      calmHour = h;
    }
  });

  return { rows, corridorStatus, busiest, calmHour };
}

function CalendarGlyph() {
  return (
    <svg viewBox="0 0 448 512" aria-hidden="true">
      <path d="M0 464c0 26.5 21.5 48 48 48h352c26.5 0 48-21.5 48-48V192H0v272zm320-196c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v40c0 6.6-5.4 12-12 12h-40c-6.6 0-12-5.4-12-12v-40zm0 128c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v40c0 6.6-5.4 12-12 12h-40c-6.6 0-12-5.4-12-12v-40zM192 268c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v40c0 6.6-5.4 12-12 12h-40c-6.6 0-12-5.4-12-12v-40zm0 128c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v40c0 6.6-5.4 12-12 12h-40c-6.6 0-12-5.4-12-12v-40zM64 268c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v40c0 6.6-5.4 12-12 12H76c-6.6 0-12-5.4-12-12v-40zm0 128c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v40c0 6.6-5.4 12-12 12H76c-6.6 0-12-5.4-12-12v-40zM400 64h-48V16c0-8.8-7.2-16-16-16h-32c-8.8 0-16 7.2-16 16v48H160V16c0-8.8-7.2-16-16-16h-32c-8.8 0-16 7.2-16 16v48H48C21.5 64 0 85.5 0 112v48h448v-48c0-26.5-21.5-48-48-48z" />
    </svg>
  );
}

function MarkerGlyph() {
  return (
    <svg viewBox="0 0 384 512" aria-hidden="true">
      <path d="M172.268 501.67C26.97 291.031 0 269.413 0 192 0 85.961 85.961 0 192 0s192 85.961 192 192c0 77.413-26.97 99.031-172.268 309.67-9.535 13.774-29.93 13.773-39.464 0zM192 272c44.183 0 80-35.817 80-80s-35.817-80-80-80-80 35.817-80 80 35.817 80 80 80z" />
    </svg>
  );
}

function ExpandGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m11.39 15.18-4.97 4.97 1.76 1.66c.81.81.24 2.19-.91 2.19H1.28C.57 24 0 23.42 0 22.71v-6a1.28 1.28 0 0 1 2.19-.91l1.66 1.77 4.97-4.97a.86.86 0 0 1 1.21 0l1.36 1.36c.33.33.33.88 0 1.21Zm1.22-6.36 4.97-4.97-1.76-1.66A1.28 1.28 0 0 1 16.73 0h6c.71 0 1.28.58 1.28 1.29v6a1.28 1.28 0 0 1-2.19.91l-1.66-1.77-4.97 4.97a.86.86 0 0 1-1.21 0l-1.36-1.36a.86.86 0 0 1 0-1.21Z" />
    </svg>
  );
}

function CloseGlyph() {
  return (
    <svg width="30" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.58.33a1.1 1.1 0 0 1 1.59 0l1.5 1.5c.44.44.44 1.15 0 1.59L19.59 7.5l1.83 1.83a1.13 1.13 0 0 1-.8 1.93h-6.75c-.62 0-1.12-.5-1.12-1.12V3.38a1.12 1.12 0 0 1 1.92-.8l1.83 1.83zM3.37 12.75h6.75c.62 0 1.12.5 1.12 1.12v6.75a1.12 1.12 0 0 1-1.92.8l-1.83-1.83-4.08 4.08c-.44.44-1.15.44-1.59 0l-1.5-1.5a1.1 1.1 0 0 1 0-1.59L4.4 16.5l-1.83-1.83a1.1 1.1 0 0 1-.24-1.23c.17-.42.58-.7 1.04-.7Z" />
    </svg>
  );
}

function initialMapState() {
  const query = window.location.hash.split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  const roadParam = params.get("road");
  const directionParam = Number(params.get("direction"));
  const hourParam = Number(params.get("hour"));
  const dateParam = params.get("date");
  const validDate = /^\d{4}-\d{2}-\d{2}$/.test(dateParam ?? "");
  const dateYear = validDate ? Number(dateParam.slice(0, 4)) : 0;

  // A highway + a direction always define a definite start -> end (and thus
  // where the probe dot begins). No "all"/"both" — a ride needs one direction.
  return {
    road: roadParam === "A93" ? "A93" : "A8",
    direction: directionParam === 2 ? 2 : 1,
    date:
      validDate && dateYear >= 2026 && dateYear <= 2029
        ? dateParam
        : getDefaultDateKey(),
    hour: hourParam >= 0 && hourParam <= 23 ? hourParam : 8,
  };
}

export default function HourlyMapPage() {
  const initialState = useRef(initialMapState());
  const [selectedRoad, setSelectedRoad] = useState(initialState.current.road);
  const [selectedDirection, setSelectedDirection] = useState(
    initialState.current.direction,
  );
  const [selectedDate, setSelectedDate] = useState(initialState.current.date);
  const [selectedHour, setSelectedHour] = useState(initialState.current.hour);
  const [forecast, setForecast] = useState(null);
  const [factorData, setFactorData] = useState(null);
  const [explain, setExplain] = useState({ status: "idle", notes: null }); // live agent narrative
  const [viewMode, setViewMode] = useState("local"); // "local" (scroll) | "global" (overview)

  const shellRef = useRef(null);
  const chartRef = useRef(null);
  const chartModelRef = useRef(null);
  const progressRef = useRef(0);
  const toolbarRef = useRef(null);
  const sectionRef = useRef(null);
  const mapPanelRef = useRef(null);
  const mapLiveRef = useRef(null);
  const mapElRef = useRef(null);
  const mapRef = useRef(null);
  const baseLayerRef = useRef(null);
  const segLayersRef = useRef([]); // [{ casing, line }]
  const probeMarkerRef = useRef(null);
  const timelineRef = useRef(null);
  const modeRef = useRef("local"); // current view mode for the render closure
  const lastDRef = useRef(0); // last scroll progress (to restore local view)
  const applyViewRef = useRef(null); // set inside the route effect

  // road is "A8" | "A93"; direction is 1 | 2 (the two named directions).
  const journeyRoad = selectedRoad;
  const dirNumber = selectedDirection;
  const routeKey = `${journeyRoad}-${dirNumber}`;

  // Geometry: per-segment latlngs + cumulative distance, rebuilt only when the
  // travelled corridor / direction changes.
  const geometry = useMemo(() => {
    const journey = buildJourney(journeyRoad, dirNumber);
    const segments = journey.segments.map((segment) => {
      const { cum, len } = cumulative(segment.pts);
      return {
        title: segment.title,
        stationIndex: segment.stationIndex,
        pts: segment.pts,
        cum,
        len,
      };
    });
    let acc = 0;
    const segStart = segments.map((s) => {
      const v = acc;
      acc += s.len;
      return v;
    });
    const total = acc || 1;
    const start = segments[0].pts[0];
    const last = segments[segments.length - 1].pts;
    return { segments, segStart, total, start, end: last[last.length - 1] };
  }, [journeyRoad, dirNumber]);

  const directionLabel = ROAD_DIRECTIONS[journeyRoad][dirNumber - 1];

  // Load the real CatBoost forecast (kfz_h_p50, vehicles/h) once.
  useEffect(() => {
    let alive = true;
    fetch(`${import.meta.env.BASE_URL}forecast.json`)
      .then((r) => r.json())
      .then((data) => alive && setForecast(data))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // Load the real per-hour factor attribution (radar, GLOBAL mode) once.
  useEffect(() => {
    let alive = true;
    fetch(`${import.meta.env.BASE_URL}factors.json`)
      .then((r) => r.json())
      .then((data) => alive && setFactorData(data))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // The chart x-axis is the REAL sensor stations (3 per direction), placed at
  // their true position along the route so each bar rises as the probe reaches
  // that station. kfz_h_p50 = all vehicles (bars + line); sv_h_pred = trucks
  // (points only). A separate per-map-segment value drives the road colouring.
  const chartData = useMemo(() => {
    const stations = DIR_STATIONS[`${journeyRoad}-${dirNumber}`] ?? [];
    const baseIdx = dayIndexOf(selectedDate) * 24;
    const kfzAt = (site, hour) =>
      forecast?.sites?.[site]?.kfz?.[baseIdx + hour] ?? 0;
    const svAt = (site, hour) =>
      forecast?.sites?.[site]?.sv?.[baseIdx + hour] ?? 0;
    const congAt = (site, hour) =>
      forecast?.sites?.[site]?.cong?.[baseIdx + hour] ?? 0;

    let dayMax = 0;
    if (forecast) {
      stations.forEach((st) => {
        const arr = forecast.sites[st.site]?.kfz;
        if (!arr) return;
        for (let h = 0; h < 24; h += 1) {
          dayMax = Math.max(dayMax, arr[baseIdx + h] ?? 0);
        }
      });
    }
    const max = Math.max(800, Math.ceil((dayMax * 1.12) / 200) * 200);
    const yFor = (v) => GV.yBase - (v / max) * (GV.yBase - GV.yTop);

    // categorical x-axis: the real stations, evenly spaced in travel order
    const n = stations.length;
    const points = stations.map((st, i) => {
      const value = forecast ? kfzAt(st.site, selectedHour) : 0;
      const truck = forecast ? svAt(st.site, selectedHour) : 0;
      return {
        label: st.label,
        value,
        truck,
        x: n === 1 ? GV.cx : GV.x0 + ((GV.x1 - GV.x0) * i) / (n - 1),
        y: yFor(value),
        ty: yFor(truck),
        popFrac: n === 1 ? 0 : i / (n - 1),
      };
    });
    const pathD = points
      .map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
      .join(" ");
    const truckPathD = points
      .map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(2)} ${p.ty.toFixed(2)}`)
      .join(" ");

    // The three visual data zones align one-to-one with the three sensor
    // series for this road and direction.
    const segCong = geometry.segments.map((segment) =>
      forecast
        ? congAt(stations[segment.stationIndex]?.site, selectedHour)
        : 0,
    );

    return { points, pathD, truckPathD, max, segCong };
  }, [forecast, selectedDate, selectedHour, journeyRoad, dirNumber, geometry]);

  // Global-mode factor radar — REAL attribution from factors.json. The
  // historical baseline (factor index 0) and construction are dropped, and the
  // remaining reasons are re-proportioned among themselves, then scaled so the
  // largest fills the chart (ratios kept).
  // No % is shown. Attribution covers 2026 only, so other years map to the same
  // month/day.
  const radarFactors = useMemo(() => {
    const allLabels = factorData?.factors ?? [
      "Baseline",
      "Time",
      "Road",
      "Holiday",
      "Weather",
      "Event",
      "Construction",
    ];
    const keep = allLabels
      .map((label, i) => ({ label, i }))
      .filter(({ label, i }) => i !== 0 && label.toLowerCase() !== "construction");
    if (!factorData) {
      return keep.map(({ label }) => ({ label, value: 0, pct: 0 }));
    }
    const [, mm, dd] = selectedDate.split("-").map(Number);
    const di = Math.round(
      (Date.UTC(2026, mm - 1, dd) - Date.UTC(2026, 0, 1)) / 86400000,
    );
    const idx =
      Math.max(0, Math.min(factorData.days - 1, di)) * factorData.hours +
      selectedHour;
    const corridor = factorData.corridors[`${journeyRoad}-${dirNumber}`];
    const row = corridor?.[idx] ?? allLabels.map(() => 0);

    const pcts = keep.map(({ i }) => row[i] ?? 0);
    const total = pcts.reduce((a, b) => a + b, 0) || 1;
    const shares = pcts.map((p) => p / total); // re-proportion among the kept
    const maxShare = Math.max(...shares, 1e-6);
    return keep.map(({ label }, k) => ({
      label,
      value: shares[k] / maxShare, // fill the radar, keep ratios
      pct: Math.round(shares[k] * 100),
    }));
  }, [factorData, selectedDate, selectedHour, journeyRoad, dirNumber]);

  // Local templated fallback for the read-out, used until the live agent
  // explanation arrives (or if the agent API is unreachable).
  const fallbackNotes = useMemo(
    () => buildFactorNotes(radarFactors, directionLabel),
    [radarFactors, directionLabel],
  );

  // Live natural-language explanation from the agent API
  // (GET /api/explain/{date}/{hour}). It's an LLM call so it can take a few
  // seconds — only fetch in GLOBAL mode, show a loading line, and fall back to
  // the templated notes on any error. The endpoint is per road (not direction).
  useEffect(() => {
    if (viewMode !== "global") return undefined;
    const controller = new AbortController();
    setExplain({ status: "loading", notes: null });
    fetch(
      `/api/explain/${selectedDate}/${selectedHour}?road=${journeyRoad}&lang=en`,
      { signal: controller.signal },
    )
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        const notes = parseExplanation(data?.explanation);
        setExplain(
          notes.length
            ? { status: "ready", notes }
            : { status: "error", notes: null },
        );
      })
      .catch((err) => {
        if (err.name !== "AbortError") setExplain({ status: "error", notes: null });
      });
    return () => controller.abort();
  }, [viewMode, selectedDate, selectedHour, journeyRoad]);

  // What the panel actually renders: live agent notes when ready, the templated
  // fallback otherwise (a loading flag drives a "generating…" line in the view).
  const radarNotes = explain.status === "ready" ? explain.notes : fallbackNotes;
  const notesLoading = explain.status === "loading";

  // Faithful jEVVvOr scroll-graph, driven imperatively from the shared scroll
  // progress: the line draws in, the dots pop, the focal point rides the line
  // and the camera zooms from the first point out to reveal the whole graph.
  const paintGraph = useCallback(() => {
    const model = chartModelRef.current;
    const svg = chartRef.current;
    if (!model || !svg) return;
    // global mode reveals the whole chart; local follows the scroll progress
    const d =
      modeRef.current === "global"
        ? 1
        : Math.max(0, Math.min(1, progressRef.current));
    const path = svg.querySelector(".g-path");
    const focal = svg.querySelector(".g-focal");
    const dots = svg.querySelectorAll(".g-dot");
    if (!path) return;

    const len = path.getTotalLength();
    path.style.strokeDasharray = `${len}`;
    path.style.strokeDashoffset = `${len * (1 - d)}`;

    // truck line draws in alongside the main line
    const truckPath = svg.querySelector(".g-truck-path");
    if (truckPath) {
      const tlen = truckPath.getTotalLength();
      truckPath.style.strokeDasharray = `${tlen}`;
      truckPath.style.strokeDashoffset = `${tlen * (1 - d)}`;
    }

    const pt = len
      ? path.getPointAtLength(len * d)
      : { x: model.points[0]?.x ?? GV.cx, y: model.points[0]?.y ?? GV.cy };
    if (focal) {
      focal.setAttribute("cx", pt.x.toFixed(2));
      focal.setAttribute("cy", pt.y.toFixed(2));
    }

    const bars = svg.querySelectorAll(".g-bar");
    const truckDots = svg.querySelectorAll(".g-truck-dot");
    dots.forEach((c, i) => {
      const p = model.points[i];
      if (!p) return;
      // bar + dot rise in sequence as the line draws past each point
      const start = Math.max(0, p.popFrac - 0.16);
      const denom = p.popFrac - start || 0.16;
      const fill = Math.max(0, Math.min(1, (d - start) / denom));
      c.setAttribute("r", (fill * 1.9).toFixed(2));
      const bar = bars[i];
      if (bar) {
        const h = (GV.yBase - p.y) * fill;
        bar.setAttribute("height", h.toFixed(2));
        bar.setAttribute("y", (GV.yBase - h).toFixed(2));
      }
      // truck point pops in the same way (no bar)
      const td = truckDots[i];
      if (td) td.setAttribute("r", (fill * 1.7).toFixed(2));
    });
  }, []);

  useEffect(() => {
    chartModelRef.current = chartData;
    paintGraph();
  }, [chartData, paintGraph]);

  // Keep the URL in sync (calendar deep-links still work).
  useEffect(() => {
    const params = new URLSearchParams({
      date: selectedDate,
      hour: String(selectedHour),
      road: selectedRoad,
      direction: String(selectedDirection),
    });
    window.history.replaceState(null, "", `#/map?${params.toString()}`);
  }, [selectedDate, selectedDirection, selectedHour, selectedRoad]);

  // Create the real, live Leaflet map once.
  useEffect(() => {
    const map = L.map(mapElRef.current, {
      center: geometry.start,
      zoom: MAP_ZOOM,
      zoomControl: false,
      attributionControl: true,
      dragging: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
      touchZoom: false,
      zoomSnap: 0,
    });
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {
        subdomains: "abcd",
        maxZoom: 20,
        detectRetina: true,
        keepBuffer: 6,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      },
    ).addTo(map);
    mapRef.current = map;
    const sizeTimer = setTimeout(() => map.invalidateSize(), 0);

    return () => {
      clearTimeout(sizeTimer);
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Build the route layers + scroll timeline for the current corridor.
  useEffect(() => {
    const map = mapRef.current;
    const section = sectionRef.current;
    const panel = mapPanelRef.current;
    if (!map || !section || !panel) return undefined;

    // Faint full-corridor context (both highways, always visible).
    const base = L.layerGroup().addTo(map);
    ["A8", "A93"].forEach((road) => {
      buildJourney(road, 1).segments.forEach((seg) => {
        L.polyline(seg.pts, {
          color: "#5b6b7a",
          weight: 2,
          opacity: 0.45,
          interactive: false,
        }).addTo(base);
      });
    });
    baseLayerRef.current = base;

    // One casing + one coloured line per segment (latlngs grow as we scroll).
    const segLayers = geometry.segments.map(() => {
      const casing = L.polyline([], {
        color: "#ffffff",
        weight: 9,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
        interactive: false,
      }).addTo(map);
      const line = L.polyline([], {
        color: TRAFFIC_LEVELS.smooth.color,
        weight: 5,
        opacity: 1,
        lineCap: "round",
        lineJoin: "round",
        interactive: false,
      }).addTo(map);
      return { casing, line };
    });
    segLayersRef.current = segLayers;

    // The probe is a real map marker anchored to a geographic point — so when
    // the map is dragged (in expanded mode) it stays on the road instead of
    // sticking to the screen centre. During the scroll ride the map keeps the
    // probe centred, so it still reads as a fixed point-of-view dot.
    const probeMarker = L.marker(geometry.start, {
      icon: L.divIcon({
        className: "probe-icon",
        html: '<span class="probe-dot"></span>',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      }),
      interactive: false,
      keyboard: false,
      zIndexOffset: 1000,
    }).addTo(map);
    probeMarkerRef.current = probeMarker;

    const render = (raw) => {
      // finish the reveal a touch before the very bottom so scrub easing can't
      // leave the route/line short of the end when you scroll all the way down.
      const d = Math.min(1, raw / 0.94);
      lastDRef.current = d;
      // global (overview) mode is static — scrolling must not move anything
      if (modeRef.current === "global") return;
      const probeDist = d * geometry.total;
      let k = 0;
      while (
        k < geometry.segments.length - 1 &&
        probeDist > geometry.segStart[k] + geometry.segments[k].len
      ) {
        k += 1;
      }
      const seg = geometry.segments[k];
      const probe = pointAt(seg.pts, seg.cum, probeDist - geometry.segStart[k]);

      // Whatever point we've scrolled to is dead-centre on the real map.
      map.setView(probe, MAP_ZOOM, { animate: false });
      probeMarker.setLatLng(probe);

      geometry.segments.forEach((s, j) => {
        const sStart = geometry.segStart[j];
        const sEnd = sStart + s.len;
        let drawn;
        if (probeDist >= sEnd) drawn = s.pts;
        else if (probeDist <= sStart) drawn = [];
        else drawn = sliceTo(s.pts, s.cum, probeDist - sStart);
        segLayers[j].casing.setLatLngs(drawn);
        segLayers[j].line.setLatLngs(drawn);
      });

      // the right-hand scroll-graph advances in lock-step with the probe
      progressRef.current = d;
      paintGraph();
    };

    const navH = document.querySelector(".topbar")?.offsetHeight ?? 78;
    const proxy = { d: 0 };
    // The stage is CSS-fixed (always fully on screen); a hidden spacer provides
    // the scroll distance. No pin -> nothing can scroll out / leave a blank.
    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: section,
        start: `top top+=${navH}`,
        end: "bottom bottom",
        scrub: 1,
        onRefresh: () => map.invalidateSize(),
      },
    });
    tl.to(proxy, {
      d: 1,
      ease: "none",
      duration: 1,
      onUpdate: () => render(proxy.d),
    });
    timelineRef.current = tl;

    // Local = the scroll ride (above). Global = a static overview: the whole
    // route + every bar shown, the map zoomed out to fit all segments.
    const applyView = (mode) => {
      modeRef.current = mode;
      if (mode === "global") {
        const allPts = geometry.segments.flatMap((s) => s.pts);
        if (allPts.length) {
          map.fitBounds(L.latLngBounds(allPts), {
            paddingTopLeft: [50, 50],
            paddingBottomRight: [50, 50],
          });
        }
        segLayers.forEach((layer, j) => {
          layer.casing.setLatLngs(geometry.segments[j].pts);
          layer.line.setLatLngs(geometry.segments[j].pts);
        });
        probeMarker.setOpacity(0);
        paintGraph(); // modeRef === "global" -> paints the full chart
      } else {
        probeMarker.setOpacity(1);
        render(lastDRef.current * 0.94); // restore the scroll view at MAP_ZOOM
      }
    };
    applyViewRef.current = applyView;

    // switching road/direction restarts the ride from the beginning
    lastDRef.current = 0;
    window.scrollTo(0, 0);

    map.invalidateSize();
    applyView(modeRef.current);

    return () => {
      tl.scrollTrigger?.kill();
      tl.kill();
      segLayers.forEach(({ casing, line }) => {
        casing.remove();
        line.remove();
      });
      probeMarker.remove();
      base.remove();
      segLayersRef.current = [];
      probeMarkerRef.current = null;
      timelineRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeKey]);

  // Live per-segment colour from the real congestion_score (date / hour change).
  useEffect(() => {
    segLayersRef.current.forEach((layer, i) => {
      const status = congestionStatus(chartData.segCong[i] ?? 0);
      layer.line.setStyle({ color: statusColor(status) });
    });
  }, [chartData]);

  // Toggle between the scroll ride (local) and the static overview (global).
  useEffect(() => {
    modeRef.current = viewMode;
    applyViewRef.current?.(viewMode);
  }, [viewMode]);

  // Measure the real nav + toolbar heights so the map sits flush below the
  // combined header (the nav is taller than a hardcoded guess) — keeps the
  // toolbar visually bound to the nav with no clipping.
  useEffect(() => {
    const measure = () => {
      const navH = document.querySelector(".topbar")?.offsetHeight ?? 78;
      const barH = toolbarRef.current?.offsetHeight ?? 60;
      const shell = shellRef.current;
      if (shell) {
        shell.style.setProperty("--nav-h", `${navH}px`);
        shell.style.setProperty("--bar-h", `${barH}px`);
      }
      ScrollTrigger.refresh();
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [selectedRoad]);

  useEffect(() => {
    const onResize = () => {
      mapRef.current && mapRef.current.invalidateSize();
      ScrollTrigger.refresh();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const selectRoad = (road) => {
    setSelectedRoad(road);
    setSelectedDirection(1);
  };

  return (
    <div className="map-page-shell" ref={shellRef}>
      <div className="map-toolbar map-toolbar--float" ref={toolbarRef}>
        <span className="panel-kicker">LIVE CORRIDOR</span>
        <div className="map-control">
          <span>Date</span>
          <DateField
            value={selectedDate}
            min="2026-01-01"
            max="2029-12-31"
            onChange={setSelectedDate}
          />
        </div>
        <div className="map-control">
          <span>Hour</span>
          <HourField value={selectedHour} onChange={setSelectedHour} />
        </div>
        <div className="map-toolbar-group">
          <span className="map-filter-label">Highway</span>
          <div className="map-pills">
            {["A8", "A93"].map((value) => (
              <button
                className={selectedRoad === value ? "active" : ""}
                type="button"
                key={value}
                onClick={() => selectRoad(value)}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        <div className="map-toolbar-group map-toolbar-dir">
          <span className="map-filter-label">Direction</span>
          <div className="map-dir-pills">
            {ROAD_DIRECTIONS[selectedRoad].map((label, index) => (
              <button
                className={selectedDirection === index + 1 ? "active" : ""}
                type="button"
                key={label}
                onClick={() => setSelectedDirection(index + 1)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <section className="map-scroll" ref={sectionRef}>
        <div className="map-stage" ref={mapPanelRef}>
          <div className="map-live" ref={mapLiveRef}>
            <div className="leaflet-map" ref={mapElRef} />
          </div>

          <div className="map-info">
          <div className="seg-chart-card">
            <div className="seg-chart-head">
              <h2>{directionLabel}</h2>
              <span className="seg-chart-kicker">
                {viewMode === "global"
                  ? `Factor influence · ${selectedDate} · ${formatHourRange(selectedHour)}`
                  : `Predicted volume · vehicles / h · ${selectedDate} · ${formatHourRange(selectedHour)}`}
              </span>
              {viewMode === "local" && (
                <div className="seg-legend">
                  <span>
                    <i className="lg lg-veh" /> All vehicles
                  </span>
                  <span>
                    <i className="lg lg-truck" /> Trucks
                  </span>
                </div>
              )}
              <div className="view-toggle" data-mode={viewMode}>
                <span className="view-toggle-thumb" />
                <button
                  type="button"
                  className={viewMode === "local" ? "active" : ""}
                  onClick={() => setViewMode("local")}
                >
                  Local
                </button>
                <button
                  type="button"
                  className={viewMode === "global" ? "active" : ""}
                  onClick={() => setViewMode("global")}
                >
                  Global
                </button>
              </div>
            </div>
            {viewMode === "global" ? (
              <div className="factor-readout">
                <FactorRadar factors={radarFactors} />
                {notesLoading ? (
                  <ul className="factor-notes">
                    <li className="factor-notes-loading">
                      Generating live explanation…
                    </li>
                  </ul>
                ) : (
                  <ul className="factor-notes">
                    {radarNotes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
            <svg
              className="seg-graph"
              ref={chartRef}
              viewBox={`0 0 ${GV.w} ${GV.h}`}
              preserveAspectRatio="xMidYMid meet"
              fill="none"
            >
              <g className="g-cam">
                {[0, 0.5, 1].map((t) => {
                  const y = GV.yBase - (GV.yBase - GV.yTop) * t;
                  return (
                    <g key={t}>
                      <line className="g-grid" x1={GV.x0} x2={GV.x1} y1={y} y2={y} />
                      <text className="g-ytick" x={GV.x0 - 2} y={y + 2} textAnchor="end">
                        {Math.round(chartData.max * t)}
                      </text>
                    </g>
                  );
                })}
                <line
                  className="g-axis"
                  x1={GV.x0}
                  x2={GV.x1}
                  y1={GV.yBase}
                  y2={GV.yBase}
                />
                {chartData.points.map((p, i) => {
                  const bw = 5;
                  return (
                    <g key={`${routeKey}-bar-${i}`}>
                      <line
                        className="g-stem"
                        x1={p.x}
                        x2={p.x}
                        y1={GV.yBase}
                        y2={GV.yTop}
                      />
                      <rect
                        className="g-bar"
                        x={p.x - bw / 2}
                        width={bw}
                        y={GV.yBase}
                        height={0}
                        rx={bw / 2}
                        fill={p.value >= chartData.max * 0.58 ? "#ab55ff" : "#2f54ff"}
                      />
                    </g>
                  );
                })}
                {/* trucks (sv_h_pred): a line with points only, no bars */}
                <path className="g-truck-path" d={chartData.truckPathD} />
                {chartData.points.map((p, i) => (
                  <circle
                    key={`${routeKey}-tk-${i}`}
                    className="g-truck-dot"
                    cx={p.x}
                    cy={p.ty}
                    r={0}
                  />
                ))}
                <path className="g-path" d={chartData.pathD} />
                {chartData.points.map((p, i) => (
                  <g key={`${routeKey}-pt-${i}`}>
                    <circle className="g-dot" cx={p.x} cy={p.y} r={0} />
                    <text
                      className="g-xtick"
                      x={p.x}
                      y={GV.yBase + 7}
                      textAnchor="middle"
                    >
                      {p.label}
                    </text>
                  </g>
                ))}
                <circle
                  className="g-focal"
                  r={2.1}
                  cx={chartData.points[0]?.x ?? GV.cx}
                  cy={chartData.points[0]?.y ?? GV.cy}
                />
              </g>
            </svg>
            )}
          </div>
        </div>
      </div>
      <div className="map-spacer" aria-hidden="true" />
      </section>
    </div>
  );
}
