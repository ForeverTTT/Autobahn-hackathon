"""
Run the full AlpineFlow agent chain from the command line.

Usage:
	python agent/main.py "2026-07-25 去 Salzburg，什么时候出发最好？"
"""
import argparse
import asyncio
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from agent.models import UserType
from agent.orchestrator import Orchestrator


DEFAULT_QUERY = "我想在 2026-07-25 去 Salzburg，什么时候出发最好？"


def to_jsonable(value: Any) -> Any:
	"""Convert dataclasses/enums into JSON-printable values."""
	if is_dataclass(value):
		return to_jsonable(asdict(value))
	if isinstance(value, dict):
		return {key: to_jsonable(item) for key, item in value.items()}
	if isinstance(value, list):
		return [to_jsonable(item) for item in value]
	if hasattr(value, "value"):
		return value.value
	return value


def print_section(title: str, value: Any) -> None:
	"""Pretty-print one result section."""
	print(f"\n{'=' * 12} {title} {'=' * 12}")
	if isinstance(value, str):
		print(value)
	else:
		print(json.dumps(to_jsonable(value), ensure_ascii=False, indent=2))


def summarize_raw(raw: dict) -> dict:
	"""Summarize raw agent outputs without dumping every record."""
	if not raw:
		return {}

	forecast = raw.get("forecast") or {}
	context = raw.get("context") or {}
	search = raw.get("search") or {}
	context_payload = context.get("context", {}) if isinstance(context, dict) else {}
	historical_payload = context_payload.get("historical_same_period", {}) if isinstance(context_payload, dict) else {}

	return {
		"forecast_mode": forecast.get("mode") if isinstance(forecast, dict) else None,
		"forecast_source": forecast.get("data_source") if isinstance(forecast, dict) else None,
		"daily_forecast_count": len(forecast.get("daily_forecasts", [])) if isinstance(forecast, dict) else 0,
		"context_counts": {
			key: len(value) if isinstance(value, list) else None
			for key, value in context_payload.items()
			if key != "historical_same_period"
		},
		"historical_same_period_counts": {
			key: len(value) if isinstance(value, list) else None
			for key, value in historical_payload.items()
		},
		"context_factor_count": len(context.get("factors", [])) if isinstance(context, dict) else 0,
		"search_factor_count": len(search.get("factors", [])) if isinstance(search, dict) else 0,
		"search_source_count": len(search.get("sources", [])) if isinstance(search, dict) else 0,
		"search_errors": search.get("errors", []) if isinstance(search, dict) else [],
	}


async def run_chain(query: str, user_type: str) -> dict:
	"""Run Intent -> Forecast/Context/Search -> Generation."""
	orchestrator = Orchestrator()
	user_type_enum = UserType(user_type) if user_type else None
	return await orchestrator.process(query, user_type_enum)


async def main() -> None:
	parser = argparse.ArgumentParser(description="Run the full AlpineFlow agent chain.")
	parser.add_argument("query", nargs="?", default=DEFAULT_QUERY, help="Natural-language user query")
	parser.add_argument(
		"--user-type",
		default="traveler",
		choices=[item.value for item in UserType],
		help="User type/persona hint",
	)
	parser.add_argument(
		"--show-raw",
		action="store_true",
		help="Print complete raw outputs from Forecast/Context/Search agents",
	)
	args = parser.parse_args()

	result = await run_chain(args.query, args.user_type)

	print_section("QUERY", args.query)
	print_section("SUCCESS", result.get("success"))
	print_section("PERSONA", result.get("persona"))
	print_section("TIME RANGE", result.get("time_range"))
	print_section("ADVICE", result.get("advice"))
	print_section("FACTORS", result.get("factors"))
	if args.show_raw:
		print_section("RAW", result.get("raw"))
	else:
		print_section("RAW SUMMARY", summarize_raw(result.get("raw")))


if __name__ == "__main__":
	asyncio.run(main())
