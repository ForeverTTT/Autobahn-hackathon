// Factor-influence radar for the Map page's GLOBAL mode.
// MOCK DATA for now (real factor-attribution data is not wired yet) — values
// are seeded from the current selection so they feel alive across date/hour.

export const RADAR_FACTORS = [
  "Weather",
  "Accident",
  "Event",
  "Construction",
  "Holiday",
];

function hash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i += 1) {
    h = (h * 31 + str.charCodeAt(i)) % 100003;
  }
  return h;
}

export function buildFactors(seedKey) {
  return RADAR_FACTORS.map((label) => {
    const v = (hash(`${seedKey}|${label}`) % 1000) / 1000;
    return { label, value: 0.22 + v * 0.73 }; // mock influence 0.22–0.95
  });
}

const W = 280;
const H = 236;
const CX = 140;
const CY = 116;
const R = 76;

export default function FactorRadar({ factors }) {
  const n = factors.length;
  const angle = (i) => ((-90 + (360 / n) * i) * Math.PI) / 180;
  const pt = (i, lvl) => [
    CX + R * lvl * Math.cos(angle(i)),
    CY + R * lvl * Math.sin(angle(i)),
  ];
  const fmt = ([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`;

  const gridPolys = [0.25, 0.5, 0.75, 1].map((lvl) =>
    factors.map((_, i) => fmt(pt(i, lvl))).join(" "),
  );
  const axisLines = factors.map((_, i) => pt(i, 1));
  const valuePts = factors.map((f, i) =>
    pt(i, Math.max(0.05, Math.min(1, f.value))),
  );
  const valuePoly = valuePts.map(fmt).join(" ");
  const labelPts = factors.map((_, i) => pt(i, 1.2));

  return (
    <svg className="radar radar--in" viewBox={`0 0 ${W} ${H}`}>
      <g className="radar-grid">
        {gridPolys.map((p, i) => (
          <polygon key={`g${i}`} points={p} />
        ))}
        {axisLines.map(([x, y], i) => (
          <line key={`a${i}`} x1={CX} y1={CY} x2={x} y2={y} />
        ))}
      </g>
      <polygon className="radar-area" points={valuePoly} />
      {valuePts.map(([x, y], i) => (
        <circle key={`d${i}`} className="radar-dot" cx={x} cy={y} r={2.6} />
      ))}
      {labelPts.map(([x, y], i) => (
        <text
          key={`l${i}`}
          className="radar-label"
          x={x}
          y={y}
          textAnchor={x < CX - 2 ? "end" : x > CX + 2 ? "start" : "middle"}
          dominantBaseline="middle"
        >
          {factors[i].label}
        </text>
      ))}
    </svg>
  );
}
