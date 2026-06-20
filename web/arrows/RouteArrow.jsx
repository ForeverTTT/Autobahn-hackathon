const ARROWS = {
  1: {
    line: "M 32 86 L 32 24",
    outlineHead: "32,5 13,31 51,31",
    mainHead: "32,10 19,28 45,28",
  },
  2: {
    line: "M 32 14 L 32 76",
    outlineHead: "32,95 13,69 51,69",
    mainHead: "32,90 19,72 45,72",
  },
};

export default function RouteArrow({ road, direction, status, label }) {
  const arrow = ARROWS[direction];

  return (
    <svg
      className={`route-direction-shape ${road.toLowerCase()} ${status}`}
      viewBox="0 0 64 100"
      role="img"
      aria-label={label}
      preserveAspectRatio="xMidYMid meet"
    >
      <path
        d={arrow.line}
        fill="none"
        stroke="#ffffff"
        strokeWidth="18"
        strokeLinecap="round"
      />
      <polygon
        points={arrow.outlineHead}
        fill="#ffffff"
        stroke="#ffffff"
        strokeLinejoin="round"
      />
      <path
        d={arrow.line}
        fill="none"
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
      />
      <polygon
        points={arrow.mainHead}
        fill="currentColor"
        stroke="currentColor"
        strokeLinejoin="round"
      />
    </svg>
  );
}
