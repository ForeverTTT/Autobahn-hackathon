// Factor-influence radar for the Map page's GLOBAL mode.
// Driven by REAL factor attribution (public/factors.json, from the model's
// per-hour `reason` breakdown). The historical baseline is excluded (it's a
// structural prior, not a situational cause); the remaining reasons are
// re-proportioned among themselves and scaled to fill the chart, so the
// polygon shows their relative weight. No raw % is drawn.
//
// Props: factors = [{ label, value (0..1) }]

const W = 300;
const H = 236;
const CX = 150;
const CY = 112;
const R = 82;

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
    pt(i, Math.max(0.04, Math.min(1, f.value))),
  );
  const valuePoly = valuePts.map(fmt).join(" ");
  const labelPts = factors.map((_, i) => pt(i, 1.16));

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
