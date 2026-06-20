export default function RouteArrow({ road, status, label }) {
  return (
    <svg
      className={`route-direction-shape ${road.toLowerCase()} ${status}`}
      viewBox="0 0 64 100"
      role="img"
      aria-label={label}
      preserveAspectRatio="xMidYMid meet"
    >
      <line
        x1="32"
        y1="12"
        x2="32"
        y2="88"
        stroke="#ffffff"
        strokeWidth="18"
        strokeLinecap="round"
      />
      <line
        x1="32"
        y1="12"
        x2="32"
        y2="88"
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
      />
    </svg>
  );
}
