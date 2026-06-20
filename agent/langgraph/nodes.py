"""
LangGraph Node Definitions
定义工作流中的各个节点（Agent）
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np

from .state import AgentState


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
    调用模型获取交通预测
    """
    date_str = state["date"]
    site_id = state["site_id"]
    hours = state["hours"]

    date = datetime.strptime(date_str, "%Y-%m-%d")
    predictions = []

    for hour in hours:
        # 基于时间模式的Mock预测
        base = 800

        # 早晚高峰
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
        if date.weekday() >= 5:
            if 9 <= hour <= 14:
                multiplier *= 1.3
            else:
                multiplier *= 0.8

        p50 = int(base * multiplier)
        p10 = int(p50 * 0.75)
        p90 = int(p50 * 1.35)

        # 拥堵等级
        if p50 < 800:
            level = "smooth"
        elif p50 < 1200:
            level = "light"
        elif p50 < 1600:
            level = "moderate"
        elif p50 < 2000:
            level = "heavy"
        else:
            level = "critical"

        predictions.append({
            "hour": hour,
            "p10": p10,
            "p50": p50,
            "p90": p90,
            "congestion_level": level,
        })

    # 峰值小时
    peak_hour = max(predictions, key=lambda x: x["p50"])["hour"]

    # 日度汇总
    p50_values = [p["p50"] for p in predictions]

    result = {
        "predictions": predictions,
        "peak_hour": peak_hour,
        "daily_summary": {
            "total_volume": sum(p50_values),
            "avg_hourly_volume": int(np.mean(p50_values)),
            "max_hourly_volume": max(p50_values),
            "min_hourly_volume": min(p50_values),
        },
        "site_id": site_id,
        "date": date_str,
    }

    return {
        "forecast_result": result,
        "messages": [{"role": "assistant", "content": f"Forecast completed for {date_str}"}],
    }


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
