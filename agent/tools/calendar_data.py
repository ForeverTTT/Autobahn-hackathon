"""Calendar-facing access to the scored daily traffic forecast."""

from __future__ import annotations

import calendar
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DAILY_SCORE_FILE = (
    PROJECT_ROOT / "data_autobahn" / "scored_traffic_2026_2029_daily.csv"
)

DIRECTION_CODES = {
    "A8": ("Sbg", "Mch"),
    "A93": ("Kff", "Ro"),
}

DIRECTION_LABELS = {
    "A8": ("Munich → Salzburg", "Salzburg → Munich"),
    "A93": ("Rosenheim → Kufstein", "Kufstein → Rosenheim"),
}


def score_to_level(score: float) -> str:
    if score < 24:
        return "smooth"
    if score < 29:
        return "light"
    if score < 34:
        return "moderate"
    if score < 39:
        return "heavy"
    return "critical"


class CalendarTrafficLoader:
    """Loads daily scores once and returns monthly direction averages."""

    def __init__(self, file_path: Path = DEFAULT_DAILY_SCORE_FILE):
        self.file_path = Path(file_path)
        self._score_index: Dict[tuple[str, str, str], List[float]] | None = None

    def _load(self) -> Dict[tuple[str, str, str], List[float]]:
        if self._score_index is not None:
            return self._score_index
        if not self.file_path.exists():
            raise FileNotFoundError(f"Daily traffic score file not found: {self.file_path}")

        score_index: Dict[tuple[str, str, str], List[float]] = defaultdict(list)
        with self.file_path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                try:
                    score = float(row["congestion_score"])
                except (KeyError, TypeError, ValueError):
                    continue
                key = (row.get("date", ""), row.get("road", ""), row.get("direction", ""))
                score_index[key].append(score)

        self._score_index = dict(score_index)
        return self._score_index

    def query_month(self, year: int, month: int, road: str) -> Dict[str, Any]:
        road = road.upper()
        if road not in DIRECTION_CODES:
            raise ValueError("road must be A8 or A93")
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")

        index = self._load()
        direction_codes = DIRECTION_CODES[road]
        direction_labels = DIRECTION_LABELS[road]
        days_in_month = calendar.monthrange(year, month)[1]
        days = []

        for day in range(1, days_in_month + 1):
            date = f"{year:04d}-{month:02d}-{day:02d}"
            direction_results = []

            for position, (code, label) in enumerate(
                zip(direction_codes, direction_labels),
                start=1,
            ):
                scores = index.get((date, road, code), [])
                if not scores:
                    direction_results.append(
                        {
                            "direction": position,
                            "code": code,
                            "label": label,
                            "score": None,
                            "level": "unavailable",
                        }
                    )
                    continue

                score = round(sum(scores) / len(scores), 1)
                direction_results.append(
                    {
                        "direction": position,
                        "code": code,
                        "label": label,
                        "score": score,
                        "level": score_to_level(score),
                    }
                )

            days.append({"date": date, "directions": direction_results})

        return {
            "year": year,
            "month": month,
            "road": road,
            "source": self.file_path.name,
            "aggregation": "mean score across sites for each road direction",
            "days": days,
        }


calendar_traffic_loader = CalendarTrafficLoader()
