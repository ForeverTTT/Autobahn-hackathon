"""
LangGraph Tools
定义Agent可调用的工具
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from langchain_core.tools import tool


@tool
def get_traffic_forecast(
    date: str,
    site_id: str = "A8_Rosenheim",
    hours: List[int] = None
) -> Dict[str, Any]:
    """
    获取交通流量预测

    Args:
        date: 日期，格式 YYYY-MM-DD
        site_id: 站点ID，如 A8_Rosenheim
        hours: 小时列表，默认6-21点

    Returns:
        包含小时级预测的字典
    """
    if hours is None:
        hours = list(range(6, 22))

    dt = datetime.strptime(date, "%Y-%m-%d")
    predictions = []

    for hour in hours:
        base = 800
        if 7 <= hour <= 9:
            multiplier = 1.8
        elif 16 <= hour <= 18:
            multiplier = 2.0
        elif 10 <= hour <= 15:
            multiplier = 1.4
        else:
            multiplier = 0.6

        if dt.weekday() >= 5:
            multiplier *= 1.2 if 9 <= hour <= 14 else 0.8

        volume = int(base * multiplier)
        level = "smooth" if volume < 800 else "light" if volume < 1200 else "moderate" if volume < 1600 else "heavy"

        predictions.append({
            "hour": hour,
            "volume": volume,
            "congestion_level": level
        })

    return {
        "date": date,
        "site_id": site_id,
        "predictions": predictions,
        "peak_hour": max(predictions, key=lambda x: x["volume"])["hour"]
    }


@tool
def get_events(date: str, road: str = "A8") -> Dict[str, Any]:
    """
    获取影响交通的事件信息

    Args:
        date: 日期，格式 YYYY-MM-DD
        road: 高速公路，A8 或 A93

    Returns:
        事件列表
    """
    dt = datetime.strptime(date, "%Y-%m-%d")
    events = []

    # Salzburg Festival
    if datetime(2026, 7, 18) <= dt <= datetime(2026, 8, 31):
        events.append({
            "name": "Salzburg Festival",
            "type": "cultural",
            "impact": "high"
        })

    # Oktoberfest
    if datetime(2026, 9, 19) <= dt <= datetime(2026, 10, 4):
        events.append({
            "name": "Oktoberfest",
            "type": "festival",
            "impact": "very_high"
        })

    # Summer holidays
    if datetime(2026, 7, 27) <= dt <= datetime(2026, 9, 7):
        events.append({
            "name": "Bavaria Summer School Holiday",
            "type": "school_holiday",
            "impact": "high"
        })

    return {
        "date": date,
        "road": road,
        "events": events
    }


@tool
def get_construction_info(date: str, road: str = "A8") -> Dict[str, Any]:
    """
    获取施工信息

    Args:
        date: 日期
        road: 高速公路

    Returns:
        施工信息列表
    """
    dt = datetime.strptime(date, "%Y-%m-%d")
    constructions = []

    if datetime(2026, 6, 1) <= dt <= datetime(2026, 9, 30) and road == "A8":
        constructions.append({
            "location": "A8 km 45-48",
            "description": "Bridge renovation - right lane closed",
            "impact": "moderate"
        })

    return {
        "date": date,
        "road": road,
        "constructions": constructions
    }


@tool
def simulate_scenario(
    date: str,
    scenario_type: str,
    parameters: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    模拟What-if场景

    Args:
        date: 日期
        scenario_type: 场景类型 (weather_change, accident, traffic_increase)
        parameters: 场景参数，如 {"weather": "heavy_rain"}

    Returns:
        模拟结果
    """
    if parameters is None:
        parameters = {}

    base_speed = 120
    delay_factor = 1.0

    if scenario_type == "weather_change":
        weather = parameters.get("weather", "clear")
        factors = {"clear": 1.0, "rain": 0.85, "heavy_rain": 0.7, "snow": 0.5}
        delay_factor = 1 / factors.get(weather, 1.0)

    elif scenario_type == "accident":
        lanes = parameters.get("lanes_blocked", 1)
        delay_factor = 1 + lanes * 0.4

    elif scenario_type == "traffic_increase":
        increase = parameters.get("percent", 20)
        delay_factor = 1 + increase / 100

    estimated_delay = int((delay_factor - 1) * 45)  # 基准45分钟

    return {
        "scenario_type": scenario_type,
        "parameters": parameters,
        "estimated_delay_minutes": max(0, estimated_delay),
        "recommendation": "Consider alternative timing" if estimated_delay > 20 else "Proceed as planned"
    }


@tool
def get_best_departure_time(
    date: str,
    origin: str = "Munich",
    destination: str = "Salzburg",
    user_type: str = "tourist"
) -> Dict[str, Any]:
    """
    获取最佳出发时间建议

    Args:
        date: 出行日期
        origin: 出发地
        destination: 目的地
        user_type: 用户类型

    Returns:
        出发时间建议
    """
    dt = datetime.strptime(date, "%Y-%m-%d")

    # 基于星期几的建议
    if dt.weekday() == 4:  # Friday
        best = "06:00"
        avoid = ["14:00", "15:00", "16:00", "17:00", "18:00"]
    elif dt.weekday() == 5:  # Saturday
        best = "06:00"
        avoid = ["09:00", "10:00", "11:00"]
    elif dt.weekday() == 6:  # Sunday
        best = "08:00"
        avoid = ["15:00", "16:00", "17:00", "18:00", "19:00"]
    else:
        best = "09:00"
        avoid = ["07:00", "08:00", "17:00", "18:00"]

    return {
        "date": date,
        "origin": origin,
        "destination": destination,
        "recommended_departure": best,
        "avoid_times": avoid,
        "estimated_travel_time_min": 90,
        "user_type": user_type
    }


# 工具列表
TRAFFIC_TOOLS = [
    get_traffic_forecast,
    get_events,
    get_construction_info,
    simulate_scenario,
    get_best_departure_time,
]
