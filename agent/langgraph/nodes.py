"""
LangGraph Node Definitions
定义工作流中的各个节点（Agent）
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np

from .state import AgentState
from ..congestion_score import (
    CongestionScoreCalculator,
    TrafficData,
    RoadInfo,
    ExternalFactors,
    calculate_congestion_score,
)
from ..data_loader import prediction_loader, external_loader


# ============ Intent Parser Node ============

def parse_intent_node(state: AgentState) -> Dict[str, Any]:
    """
    意图解析节点
    分析用户查询，确定意图和提取参数
    """
    query = state["query"].lower()

    # 简单的关键词匹配（可替换为LLM）
    if any(kw in query for kw in ["if", "what if", "假如", "如果", "would happen"]):
        intent = "whatif"
    elif any(kw in query for kw in ["plan", "trip", "travel", "when should", "best time", "规划"]):
        intent = "plan"
    elif any(kw in query for kw in ["why", "reason", "explain", "为什么", "原因"]):
        intent = "explain"
    elif any(kw in query for kw in ["compare", "vs", "versus", "比较"]):
        intent = "compare"
    else:
        intent = "forecast"

    return {
        "intent": intent,
        "messages": [{"role": "system", "content": f"Parsed intent: {intent}"}],
        "next_step": "route"
    }


# ============ Forecast Node ============

def forecast_node(state: AgentState) -> Dict[str, Any]:
    """
    预测节点
    优先从预测数据文件读取，如果没有则使用模拟数据
    使用 Congestion Score 计算综合拥堵评分
    """
    date_str = state["date"]
    site_id = state["site_id"]
    road = state["road"]
    hours = state["hours"]

    date = datetime.strptime(date_str, "%Y-%m-%d")

    # 尝试从预测文件加载数据
    loaded_predictions = _load_predictions_from_file(date_str, site_id, road, hours)

    if loaded_predictions:
        # 使用文件中的预测数据
        predictions = _process_loaded_predictions(loaded_predictions, date, road, site_id)
    else:
        # 使用模拟数据（fallback）
        predictions = _generate_mock_predictions(date, road, site_id, hours)

    # 峰值小时（基于 congestion_score）
    peak_hour = max(predictions, key=lambda x: x["congestion_score"])["hour"]

    # 日度汇总
    p50_values = [p["p50"] for p in predictions]
    scores = [p["congestion_score"] for p in predictions]

    # 计算日度平均 congestion score
    daily_congestion_score = np.mean(scores)
    if daily_congestion_score < 20:
        daily_level = "smooth"
    elif daily_congestion_score < 40:
        daily_level = "light"
    elif daily_congestion_score < 60:
        daily_level = "moderate"
    elif daily_congestion_score < 80:
        daily_level = "heavy"
    else:
        daily_level = "critical"

    result = {
        "predictions": predictions,
        "peak_hour": peak_hour,
        "daily_summary": {
            "total_volume": sum(p50_values),
            "avg_hourly_volume": int(np.mean(p50_values)),
            "max_hourly_volume": max(p50_values),
            "min_hourly_volume": min(p50_values),
            "avg_congestion_score": round(daily_congestion_score, 1),
            "daily_congestion_level": daily_level,
            "hours_with_heavy_congestion": sum(1 for s in scores if s >= 60),
        },
        "site_id": site_id,
        "road": road,
        "date": date_str,
        "data_source": "predictions_file" if loaded_predictions else "mock",
    }

    return {
        "forecast_result": result,
        "messages": [{"role": "assistant", "content": f"Forecast completed for {date_str}"}],
    }


def _load_predictions_from_file(
    date_str: str,
    site_id: str,
    road: str,
    hours: List[int]
) -> List[Dict[str, Any]]:
    """
    从预测文件加载数据

    Returns:
        预测记录列表，如果文件不存在或加载失败则返回空列表
    """
    try:
        # 首先尝试精确匹配 site_id
        records = prediction_loader.query(
            date=date_str,
            site_id=site_id,
            road=road,
            hours=hours
        )

        # 如果没有找到，尝试只用 road 和 hours 查询（取第一个站点的数据）
        if not records:
            all_records = prediction_loader.query(
                date=date_str,
                road=road,
                hours=hours
            )
            if all_records:
                # 获取第一个站点的数据
                first_site = all_records[0]["site_id"]
                records = [r for r in all_records if r["site_id"] == first_site]

        return records
    except Exception as e:
        print(f"Warning: Could not load predictions from file: {e}")
        return []


def _process_loaded_predictions(
    records: List[Dict[str, Any]],
    date: datetime,
    road: str,
    site_id: str
) -> List[Dict[str, Any]]:
    """
    处理从文件加载的预测数据，计算 Congestion Score
    """
    predictions = []

    # 外部因素（从记录或计算）
    is_weekend = date.weekday() >= 5
    is_friday_afternoon = date.weekday() == 4
    is_sunday_afternoon = date.weekday() == 6

    # 道路信息
    road_info = RoadInfo(
        road_id=road,
        segment_id=site_id,
        capacity=4000 if road == "A8" else 3500,
        is_bottleneck="Rosenheim" in site_id or "Kufstein" in site_id or "Inntal" in site_id,
    )

    for record in records:
        hour = record["hour"]
        p10 = record.get("kfz_h_p10", 0)
        p50 = record.get("kfz_h_p50", 0)
        p90 = record.get("kfz_h_p90", 0)
        sv_h = record.get("sv_h_p50", int(p50 * 0.1))
        v_kfz = record.get("v_kfz_p50", 120)

        is_holiday = record.get("is_holiday", False)
        is_school_holiday = record.get("is_school_holiday", False)
        is_peak_hour = (7 <= hour <= 9) or (16 <= hour <= 18)

        # 计算 Congestion Score
        external = ExternalFactors(
            is_weekend=is_weekend,
            is_friday_afternoon=is_friday_afternoon and hour >= 14,
            is_sunday_afternoon=is_sunday_afternoon and hour >= 14,
            is_peak_hour=is_peak_hour,
            is_public_holiday=is_holiday,
            is_school_holiday=is_school_holiday,
        )

        traffic = TrafficData(kfz_h=p50, sv_h=sv_h, v_kfz=v_kfz)

        calculator = CongestionScoreCalculator()
        congestion = calculator.calculate(traffic, road_info, external)

        predictions.append({
            "hour": hour,
            "p10": p10,
            "p50": p50,
            "p90": p90,
            "sv_h": sv_h,
            "v_kfz": round(v_kfz, 1),
            "congestion_score": congestion.total_score,
            "congestion_level": congestion.level.value,
            "congestion_color": congestion.color,
        })

    return sorted(predictions, key=lambda x: x["hour"])


def _generate_mock_predictions(
    date: datetime,
    road: str,
    site_id: str,
    hours: List[int]
) -> List[Dict[str, Any]]:
    """
    生成模拟预测数据（当预测文件不可用时使用）
    """
    predictions = []
    date_str = date.strftime("%Y-%m-%d")

    # 外部因素
    is_weekend = date.weekday() >= 5
    is_friday_afternoon = date.weekday() == 4
    is_sunday_afternoon = date.weekday() == 6

    # 假期检查
    holidays_2026 = {
        "2026-01-01", "2026-01-06", "2026-04-03", "2026-04-06",
        "2026-05-01", "2026-05-14", "2026-05-25", "2026-06-04",
        "2026-08-15", "2026-10-03", "2026-11-01", "2026-12-25", "2026-12-26",
    }
    is_public_holiday = date_str in holidays_2026
    is_school_holiday = _is_school_holiday(date)

    # 道路信息
    road_info = RoadInfo(
        road_id=road,
        segment_id=site_id,
        capacity=4000 if road == "A8" else 3500,
        is_bottleneck="Rosenheim" in site_id or "Kufstein" in site_id,
    )

    for hour in hours:
        # 基础流量
        base = 800 if road == "A8" else 600

        # 时段系数
        if 7 <= hour <= 9:
            multiplier = 1.8
        elif 16 <= hour <= 18:
            multiplier = 2.0
        elif 10 <= hour <= 15:
            multiplier = 1.4
        elif 5 <= hour <= 6:
            multiplier = 0.8
        else:
            multiplier = 0.5

        # 周末调整
        if is_weekend:
            if 9 <= hour <= 14:
                multiplier *= 1.3
            else:
                multiplier *= 0.8

        # 假期调整
        if is_public_holiday:
            multiplier *= 1.4
        elif is_school_holiday:
            multiplier *= 1.25

        # 季节调整
        month = date.month
        if month in [6, 7, 8]:
            multiplier *= 1.2
        elif month in [12, 1, 2]:
            multiplier *= 1.1

        # 计算流量
        p50 = int(base * multiplier)
        p10 = int(p50 * 0.75)
        p90 = int(p50 * 1.35)

        # 速度估算
        if p50 < 1000:
            v_kfz = 120
        elif p50 < 1500:
            v_kfz = 100
        elif p50 < 2000:
            v_kfz = 80
        else:
            v_kfz = max(40, 120 - (p50 - 800) * 0.05)

        sv_h = int(p50 * (0.12 if 6 <= hour <= 18 else 0.08))

        # 计算 Congestion Score
        is_peak_hour = (7 <= hour <= 9) or (16 <= hour <= 18)

        external = ExternalFactors(
            is_weekend=is_weekend,
            is_friday_afternoon=is_friday_afternoon and hour >= 14,
            is_sunday_afternoon=is_sunday_afternoon and hour >= 14,
            is_peak_hour=is_peak_hour,
            is_public_holiday=is_public_holiday,
            is_school_holiday=is_school_holiday,
        )

        traffic = TrafficData(kfz_h=p50, sv_h=sv_h, v_kfz=v_kfz)

        calculator = CongestionScoreCalculator()
        congestion = calculator.calculate(traffic, road_info, external)

        predictions.append({
            "hour": hour,
            "p10": p10,
            "p50": p50,
            "p90": p90,
            "sv_h": sv_h,
            "v_kfz": round(v_kfz, 1),
            "congestion_score": congestion.total_score,
            "congestion_level": congestion.level.value,
            "congestion_color": congestion.color,
        })

    return predictions


def _is_school_holiday(date: datetime) -> bool:
    """检查是否为学校假期"""
    school_holidays = [
        (datetime(2026, 2, 14), datetime(2026, 2, 22)),
        (datetime(2026, 3, 28), datetime(2026, 4, 12)),
        (datetime(2026, 5, 23), datetime(2026, 6, 7)),
        (datetime(2026, 7, 27), datetime(2026, 9, 7)),
        (datetime(2026, 10, 31), datetime(2026, 11, 8)),
        (datetime(2026, 12, 23), datetime(2027, 1, 5)),
    ]

    for start, end in school_holidays:
        if start <= date <= end:
            return True
    return False


# ============ Explanation Node ============

def explain_node(state: AgentState) -> Dict[str, Any]:
    """
    解释节点
    分析影响因素
    """
    date_str = state["date"]
    date = datetime.strptime(date_str, "%Y-%m-%d")

    factors = []

    # 检查假期
    holidays_2026 = {
        "2026-01-01": "New Year's Day",
        "2026-01-06": "Epiphany",
        "2026-12-25": "Christmas Day",
        "2026-12-26": "St. Stephen's Day",
    }

    if date_str in holidays_2026:
        factors.append({
            "type": "public_holiday",
            "name": holidays_2026[date_str],
            "impact": "high",
            "magnitude": 0.4,
            "description": f"Public holiday ({holidays_2026[date_str]}) - expect higher traffic"
        })

    # 检查周末
    if date.weekday() == 4:  # Friday
        factors.append({
            "type": "weekend",
            "name": "Friday",
            "impact": "moderate",
            "magnitude": 0.15,
            "description": "Friday afternoon - weekend departure traffic"
        })
    elif date.weekday() == 6:  # Sunday
        factors.append({
            "type": "weekend",
            "name": "Sunday",
            "impact": "moderate",
            "magnitude": 0.2,
            "description": "Sunday afternoon - weekend return traffic"
        })

    # 季节因素
    month = date.month
    if month in [6, 7, 8]:
        factors.append({
            "type": "season",
            "name": "Summer",
            "impact": "high",
            "magnitude": 0.3,
            "description": "Summer season - high tourist traffic towards Alps"
        })
    elif month in [12, 1, 2]:
        factors.append({
            "type": "season",
            "name": "Winter",
            "impact": "moderate",
            "magnitude": 0.2,
            "description": "Winter season - ski traffic towards Austria"
        })

    # 生成解释文本
    if factors:
        explanation = f"On {date.strftime('%A, %B %d, %Y')}:\n"
        for f in factors[:3]:
            explanation += f"• {f['description']}\n"
    else:
        explanation = f"On {date.strftime('%A, %B %d, %Y')}: Normal traffic conditions expected."

    result = {
        "factors": factors,
        "explanation": explanation,
        "date": date_str,
    }

    return {
        "explanation_result": result,
        "messages": [{"role": "assistant", "content": "Explanation generated"}],
    }


# ============ Retrieval Node ============

def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """
    检索节点
    获取外部信息（施工、活动等）
    """
    date_str = state["date"]
    road = state["road"]
    date = datetime.strptime(date_str, "%Y-%m-%d")

    # Mock施工数据
    constructions = []
    if datetime(2026, 6, 1) <= date <= datetime(2026, 9, 30):
        constructions.append({
            "id": "C001",
            "road": "A8",
            "description": "Bridge renovation - right lane closed",
            "impact": "moderate"
        })

    # Mock活动数据
    events = []
    if datetime(2026, 7, 18) <= date <= datetime(2026, 8, 31):
        events.append({
            "id": "E001",
            "name": "Salzburg Festival",
            "type": "cultural",
            "impact_level": "high",
        })

    if datetime(2026, 9, 19) <= date <= datetime(2026, 10, 4):
        events.append({
            "id": "E002",
            "name": "Oktoberfest",
            "type": "festival",
            "impact_level": "very_high",
        })

    # 生成警告
    warnings = []
    for c in constructions:
        if c["impact"] == "high":
            warnings.append({
                "type": "construction",
                "severity": "high",
                "message": f"⚠️ {c['road']}: {c['description']}"
            })

    for e in events:
        if e["impact_level"] in ["high", "very_high"]:
            warnings.append({
                "type": "event",
                "severity": "moderate",
                "message": f"🎭 {e['name']} in progress - high traffic expected"
            })

    result = {
        "constructions": constructions,
        "events": events,
        "warnings": warnings,
        "date": date_str,
        "road": road,
    }

    return {
        "retrieval_result": result,
        "messages": [{"role": "assistant", "content": f"Retrieved {len(events)} events, {len(constructions)} constructions"}],
    }


# ============ Simulation Node ============

def simulate_node(state: AgentState) -> Dict[str, Any]:
    """
    模拟节点
    What-if场景分析
    """
    scenario = state.get("scenario") or {}
    scenario_type = scenario.get("type", "weather_change")
    parameters = scenario.get("parameters", {})
    forecast = state.get("forecast_result") or {}

    base_predictions = forecast.get("predictions", [])
    if not base_predictions:
        # 生成默认预测
        base_predictions = [{"hour": h, "p50": 1200 + h * 30} for h in state["hours"]]

    simulated = []

    for pred in base_predictions:
        hour = pred.get("hour", 12)
        base_volume = pred.get("p50", 1500)
        base_speed = 120

        # 应用场景修改
        speed_modifier = 1.0

        if scenario_type == "weather_change":
            weather = parameters.get("weather", "clear")
            weather_factors = {
                "clear": 1.0, "cloudy": 0.98, "light_rain": 0.90,
                "heavy_rain": 0.75, "snow": 0.60, "ice": 0.50
            }
            speed_modifier = weather_factors.get(weather, 1.0)

        elif scenario_type == "accident":
            lanes_blocked = parameters.get("lanes_blocked", 1)
            speed_modifier = 1.0 - (lanes_blocked * 0.3)

        sim_speed = base_speed * speed_modifier
        delay_min = (100 / sim_speed - 100 / base_speed) * 60

        simulated.append({
            "hour": hour,
            "base_volume": base_volume,
            "simulated_speed_kmh": round(sim_speed, 1),
            "delay_minutes": round(max(0, delay_min), 1),
        })

    total_delay = sum(s["delay_minutes"] for s in simulated)

    # 生成替代方案
    alternatives = []
    if total_delay > 15:
        alternatives.append({
            "id": "early_departure",
            "name": "Early Departure",
            "description": "Leave 2-3 hours earlier",
            "estimated_time_saved_min": int(total_delay * 0.7),
        })

    # 建议
    if total_delay < 15:
        recommendation = "Traffic conditions are acceptable. Proceed with your trip."
    elif total_delay < 45:
        recommendation = "Moderate delays expected. Consider adjusting departure time."
    else:
        recommendation = "Significant delays expected. Consider alternative plans."

    result = {
        "scenario_type": scenario_type,
        "parameters": parameters,
        "hourly_results": simulated,
        "total_delay_minutes": round(total_delay, 1),
        "alternatives": alternatives,
        "recommendation": recommendation,
    }

    return {
        "simulation_result": result,
        "messages": [{"role": "assistant", "content": f"Simulation completed: {total_delay:.0f}min total delay"}],
    }


# ============ Response Generator Node ============

def generate_response_node(state: AgentState) -> Dict[str, Any]:
    """
    响应生成节点
    汇总各Agent结果，生成最终响应
    """
    intent = state["intent"]
    user_type = state["user_type"]

    response = {
        "intent": intent,
        "user_type": user_type,
        "date": state["date"],
        "road": state["road"],
    }

    # 根据意图组装响应
    if intent == "forecast":
        response["forecast"] = state.get("forecast_result")
        response["external_factors"] = state.get("retrieval_result")
        response["explanation"] = state.get("explanation_result")

    elif intent == "plan":
        forecast = state.get("forecast_result") or {}
        predictions = forecast.get("predictions", [])

        # 找最佳出发时间
        best_hours = [p["hour"] for p in predictions if p.get("congestion_level") in ["smooth", "light"]]
        recommended = best_hours[0] if best_hours else 7

        response["plan"] = {
            "recommended_departure": f"{recommended:02d}:00",
            "alternative_departures": [f"{h:02d}:00" for h in best_hours[:3]],
            "estimated_travel_time_min": 90,
            "warnings": (state.get("retrieval_result") or {}).get("warnings", []),
        }
        response["forecast"] = forecast

    elif intent == "whatif":
        response["simulation"] = state.get("simulation_result")
        response["base_forecast"] = state.get("forecast_result")

    elif intent == "explain":
        response["explanation"] = state.get("explanation_result")
        response["forecast"] = state.get("forecast_result")

    # 个性化
    response["personalization"] = _get_personalization(user_type)

    return {
        "final_response": response,
        "messages": [{"role": "assistant", "content": "Response generated"}],
    }


def _get_personalization(user_type: str) -> Dict[str, Any]:
    """获取个性化配置"""
    profiles = {
        "tourist": {"focus": "best travel experience", "priority": "scenic route, comfortable timing"},
        "resident": {"focus": "avoiding local congestion", "priority": "quick commute"},
        "logistics": {"focus": "delivery efficiency", "priority": "punctuality"},
        "tourism_business": {"focus": "customer arrival patterns", "priority": "peak visitor times"},
        "authority": {"focus": "traffic management", "priority": "congestion prevention"},
    }
    return profiles.get(user_type, profiles["tourist"])


# ============ Router Node ============

def route_node(state: AgentState) -> Dict[str, Any]:
    """
    路由节点
    根据意图决定下一步
    """
    intent = state["intent"]

    # 定义不同意图需要执行的节点
    routes = {
        "forecast": "parallel_agents",
        "plan": "parallel_agents",
        "explain": "parallel_agents",
        "whatif": "forecast_first",
        "compare": "forecast_first",
    }

    next_step = routes.get(intent, "parallel_agents")

    return {
        "next_step": next_step,
        "messages": [{"role": "system", "content": f"Routing to: {next_step}"}],
    }
