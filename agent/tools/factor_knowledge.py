"""
Factor attribution knowledge helper.

Reads doc/FACTOR_CONTRIBUTIONS.md and exposes compact, user-facing knowledge
for GenerationAgent explanations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FACTOR_DOC_PATH = PROJECT_ROOT / "doc" / "FACTOR_CONTRIBUTIONS.md"


@dataclass(frozen=True)
class FactorContributionInfo:
    """User-facing interpretation for one daily attribution group."""
    display_name: str
    short_name: str
    human_name: str
    baseline: bool
    usual_range: str
    explanation: str
    user_message: str
    caution: str = ""


FACTOR_CONTRIBUTION_GUIDE: Dict[str, FactorContributionInfo] = {
    "Historical Traffic Baseline": FactorContributionInfo(
        display_name="Historical Traffic Baseline",
        short_name="HP",
        human_name="历史交通模式",
        baseline=True,
        usual_range="通常 55-70%",
        explanation="基于 2023-2025 年传感器数据，表示这个站点在相似小时、星期、月份和季节下的常规交通模式。",
        user_message="交通主要符合历史常态，说明这一天更像往年同期/同星期的普通模式。",
    ),
    "Road Segment and Detector Attributes": FactorContributionInfo(
        display_name="Road Segment and Detector Attributes",
        short_name="SL",
        human_name="路段和检测器属性",
        baseline=True,
        usual_range="通常 10-25%",
        explanation="表示站点位置、道路、方向、里程和地理属性带来的基础差异。",
        user_message="该路段本身的位置和方向决定了较高或较低的基础车流。",
    ),
    "Date and Time Pattern": FactorContributionInfo(
        display_name="Date and Time Pattern",
        short_name="CA",
        human_name="日期和时间规律",
        baseline=False,
        usual_range="通常 4-15%",
        explanation="纯日历和时间信号，包括小时、星期、月份、季节和周末模式。",
        user_message="日期位置本身在推动车流，比如夏季周末、周五或特定月份节奏。",
    ),
    "Holiday Effect": FactorContributionInfo(
        display_name="Holiday Effect",
        short_name="HO",
        human_name="假期效应",
        baseline=False,
        usual_range="高峰日可达 20-35%",
        explanation="覆盖巴伐利亚、萨尔茨堡、蒂罗尔学校/公共假期，以及出发/返程交通窗口。",
        user_message="假期出行正在把车流抬高，尤其要关注学校假期、出发波和返程波。",
    ),
    "Weather and Temperature": FactorContributionInfo(
        display_name="Weather and Temperature",
        short_name="WE",
        human_name="天气和温度",
        baseline=False,
        usual_range="通常 3-8%，冬季可更高",
        explanation="包含气温、路温、降水、降雪、低能见度和结冰风险；未来日期多是气候态平均。",
        user_message="天气/温度是有意义的修正因子，但未来日期通常表示季节性气候特征，不等于实时天气预报。",
        caution="不要把高 WE 直接理解为确定会有恶劣天气；它更多表示该月份/小时的典型天气影响。",
    ),
    "Special Events": FactorContributionInfo(
        display_name="Special Events",
        short_name="EV",
        human_name="特殊活动",
        baseline=False,
        usual_range="多数日期 <2%，活动日可达 5-15%",
        explanation="覆盖慕尼黑、萨尔茨堡、罗森海姆、库夫施泰因等走廊城市的节庆、演出和大型活动。",
        user_message="沿线活动会带来额外交通，建议结合活动表或实时搜索确认。",
    ),
    "Construction Impact": FactorContributionInfo(
        display_name="Construction Impact",
        short_name="CO",
        human_name="施工影响",
        baseline=False,
        usual_range="通常缺失，已知施工日可达 5-15%",
        explanation="包含施工活动、2+0 交通组织、封闭车道和 A8/A93 施工数量。",
        user_message="已知施工可能影响容量，尤其是 2+0 或多车道关闭时要单独提高风险判断。",
        caution="训练期施工样本有限，施工影响不应只依赖模型贡献值，Agent 层需要结合施工规则保守处理。",
    ),
}


ALIAS_TO_DISPLAY_NAME = {
    "HP": "Historical Traffic Baseline",
    "TT": "Historical Traffic Baseline",
    "SL": "Road Segment and Detector Attributes",
    "CA": "Date and Time Pattern",
    "HO": "Holiday Effect",
    "WE": "Weather and Temperature",
    "EV": "Special Events",
    "CO": "Construction Impact",
}


_doc_cache: Optional[Dict[str, Any]] = None


def load_factor_contribution_knowledge() -> Dict[str, Any]:
    """Load the markdown guide and expose structured factor knowledge."""
    global _doc_cache
    if _doc_cache is not None:
        return _doc_cache

    markdown = ""
    try:
        markdown = FACTOR_DOC_PATH.read_text(encoding="utf-8")
    except OSError:
        markdown = ""

    _doc_cache = {
        "doc_path": str(FACTOR_DOC_PATH),
        "doc_loaded": bool(markdown),
        "doc_chars": len(markdown),
        "version": "v4",
        "groups": FACTOR_CONTRIBUTION_GUIDE,
    }
    return _doc_cache


def normalize_factor_name(name: Any) -> str:
    """Normalize full display names and legacy abbreviations."""
    raw_name = str(name or "").strip()
    return ALIAS_TO_DISPLAY_NAME.get(raw_name, raw_name)


def get_factor_info(name: Any) -> Optional[FactorContributionInfo]:
    """Return factor guide entry for a display name or legacy abbreviation."""
    return FACTOR_CONTRIBUTION_GUIDE.get(normalize_factor_name(name))


def explain_factor_contribution(name: Any, value: float) -> Dict[str, Any]:
    """Convert a factor share into a user-facing explanation payload."""
    normalized_name = normalize_factor_name(name)
    info = get_factor_info(normalized_name)
    if not info:
        return {
            "name": normalized_name,
            "value": value,
            "label": normalized_name,
            "baseline": False,
            "message": f"{normalized_name} 贡献约 {value:.1f}%。",
            "caution": "",
        }

    return {
        "name": info.display_name,
        "value": value,
        "label": info.human_name,
        "short_name": info.short_name,
        "baseline": info.baseline,
        "usual_range": info.usual_range,
        "message": f"{info.human_name} 贡献约 {value:.1f}%。{info.user_message}",
        "explanation": info.explanation,
        "caution": info.caution,
    }


def summarize_factor_reasons(
    reasons: List[Dict[str, Any]],
    top_n: int = 3,
    include_baseline: bool = False,
) -> List[Dict[str, Any]]:
    """Summarize daily forecast reason rows using the markdown guide."""
    parsed = []
    for reason in reasons or []:
        name = reason.get("name")
        try:
            value = float(reason.get("value", 0))
        except (TypeError, ValueError):
            value = 0.0
        explanation = explain_factor_contribution(name, value)
        if include_baseline or not explanation.get("baseline"):
            parsed.append(explanation)

    parsed.sort(key=lambda item: item.get("value", 0), reverse=True)
    return parsed[:top_n]


def aggregate_daily_reasons(records: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """Average factor shares across multiple station-day forecast records."""
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}

    for record in records or []:
        for reason in record.get("reasons", []) or []:
            name = normalize_factor_name(reason.get("name"))
            try:
                value = float(reason.get("value", 0))
            except (TypeError, ValueError):
                continue
            totals[name] = totals.get(name, 0.0) + value
            counts[name] = counts.get(name, 0) + 1

    aggregated = [
        {"name": name, "value": round(total / counts[name], 1)}
        for name, total in totals.items()
        if counts.get(name)
    ]
    return sorted(aggregated, key=lambda item: item["value"], reverse=True)
