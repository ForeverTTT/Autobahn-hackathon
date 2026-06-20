"""
LangGraph Tools
定义Agent可调用的工具
"""
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from ..graph_rag import GraphRAG
from .data_loader import external_loader, prediction_loader


_GRAPH_RAG = GraphRAG()


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

    road = site_id.split("_")[0] if site_id and site_id.startswith("A") else "A8"
    records = prediction_loader.query(date=date, site_id=site_id, road=road, hours=hours)
    if not records:
        records = prediction_loader.query(date=date, road=road, hours=hours)

    if records:
        first_site = records[0].get("site_id")
        records = [record for record in records if record.get("site_id") == first_site]

    predictions = [
        {
            "hour": int(record.get("hour", 0)),
            "volume": float(record.get("kfz_h_p50", 0)),
            "p10": float(record.get("kfz_h_p10", 0)),
            "p50": float(record.get("kfz_h_p50", 0)),
            "p90": float(record.get("kfz_h_p90", 0)),
            "speed_kmh": float(record.get("v_kfz_p50", record.get("v_kfz_pred", 0))),
            "sv_h": float(record.get("sv_h_p50", record.get("sv_h_pred", 0))),
        }
        for record in records
    ]

    return {
        "date": date,
        "site_id": records[0].get("site_id") if records else site_id,
        "road": road,
        "predictions": predictions,
        "peak_hour": max(predictions, key=lambda x: x["volume"])["hour"] if predictions else None,
        "data_source": "data_autobahn_csv",
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
    return {
        "date": date,
        "road": road,
        "events": external_loader.get_events(date, road),
        "data_source": "data_autobahn_csv",
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
    return {
        "date": date,
        "road": road,
        "constructions": external_loader.get_construction(date, road),
        "data_source": "data_autobahn_csv",
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


@tool
def query_traffic_graph(cypher: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    查询本地交通 Graph RAG。

    支持受控 Cypher 子集，例如：
    MATCH (f:Forecast) WHERE f.date = $date AND f.road = $road RETURN f LIMIT 24
    """
    if params is None:
        params = {}
    rows = _GRAPH_RAG.query_cypher(cypher, params)
    return {"rows": rows, "count": len(rows)}


# 工具列表
TRAFFIC_TOOLS = [
    get_traffic_forecast,
    get_events,
    get_construction_info,
    simulate_scenario,
    get_best_departure_time,
    query_traffic_graph,
]
