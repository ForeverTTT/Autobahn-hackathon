"""
API 处理工具
把 FastAPI 路由中的业务处理逻辑抽出来，供 api_app.py 调用。
"""
import asyncio
from typing import Any, Dict, List, Optional

from ..models import AgentRequest, UserType
from ..orchestrator import Orchestrator
from .llm_client import generate


async def handle_chat(
    orchestrator: Orchestrator,
    query: str,
    user_type: Optional[str] = "traveler",
) -> Dict[str, Any]:
    """处理自然语言对话请求。"""
    user_type_enum = UserType(user_type) if user_type else None
    return await orchestrator.process(query, user_type_enum)


async def handle_plan(
    orchestrator: Orchestrator,
    date: str,
    destination: Optional[str] = "salzburg",
    user_type: Optional[str] = "traveler",
) -> Dict[str, Any]:
    """处理出行计划请求。"""
    query = f"我想在 {date} 去 {destination or 'salzburg'}"
    user_type_enum = UserType(user_type) if user_type else UserType.TRAVELER
    return await orchestrator.process(query, user_type_enum)


async def handle_forecast(
    date: str,
    road: Optional[str] = "A8",
    site_id: Optional[str] = None,
    hours: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """处理交通预测请求。"""
    from ..agents import ForecastAgent

    agent = ForecastAgent()
    request = AgentRequest(
        query="forecast",
        date=date,
        road=road or "A8",
        site_id=site_id,
        hours=hours or list(range(6, 22)),
    )
    result = await agent.process(request)

    if result.success:
        return result.data
    raise RuntimeError(result.message)


async def handle_factors(date: str, road: str = "A8") -> Dict[str, Any]:
    """处理外部因素请求。"""
    from ..agents import ContextAgent, SearchAgent

    request = AgentRequest(query="factors", date=date, road=road)
    context_agent = ContextAgent()
    search_agent = SearchAgent()

    context_result, search_result = await asyncio.gather(
        context_agent.process(request),
        search_agent.process(request),
    )

    factors = []
    if context_result.success:
        factors.extend(context_result.data.get("factors", []))
    if search_result.success:
        factors.extend(search_result.data.get("factors", []))

    return {
        "date": date,
        "road": road,
        "factors": factors,
    }


async def handle_options(
    orchestrator: Orchestrator,
    date: str,
    destination: str = "salzburg",
    user_type: str = "traveler",
) -> Dict[str, Any]:
    """处理出行方案对比请求。"""
    query = f"我想在 {date} 去 {destination}"
    result = await orchestrator.process(query, UserType(user_type))

    options = result.get("options", [])
    return {
        "date": date,
        "destination": destination,
        "user_type": user_type,
        "options": [
            {
                "departure": option.departure_time,
                "arrival": option.arrival_time,
                "duration_min": option.travel_time_min,
                "delay_min": option.delay_min,
                "stress_index": option.stress_index,
                "recommendation": option.recommendation,
            }
            for option in options
        ],
    }


async def handle_hourly_explanation(
    date: str,
    hour: int,
    road: str = "A8",
    lang: str = "zh",
) -> Dict[str, Any]:
    """
    生成某小时交通状况的自然语言解释。

    Args:
        date: 日期 (YYYY-MM-DD)
        hour: 小时 (0-23)
        road: 道路 (A8, A93)
        lang: 语言 (zh, en, de)

    Returns:
        {
            "date": "2026-07-25",
            "hour": 8,
            "road": "A8",
            "congestion_level": "moderate",
            "congestion_score": 45,
            "explanation": "8点交通中等拥堵，主要因为...",
            "factors": [...]
        }
    """
    from ..agents import ForecastAgent, ContextAgent, SearchAgent

    # 1. 获取该小时的预测数据
    forecast_agent = ForecastAgent()
    request = AgentRequest(
        query="hourly explain",
        date=date,
        road=road,
        hours=[hour],
        granularity="hourly",
    )
    forecast_result = await forecast_agent.process(request)

    # 提取预测数据
    prediction = None
    if forecast_result.success:
        forecast_data = forecast_result.data.get("forecast")
        if forecast_data:
            # 处理字典格式
            if isinstance(forecast_data, dict):
                predictions = forecast_data.get("predictions", [])
            # 处理对象格式 (DailyForecast)
            elif hasattr(forecast_data, "predictions"):
                predictions = forecast_data.predictions
            else:
                predictions = []

            if predictions:
                # 找到对应小时的预测
                for pred in predictions:
                    pred_hour = pred.get("hour") if isinstance(pred, dict) else getattr(pred, "hour", None)
                    if pred_hour == hour:
                        prediction = pred if isinstance(pred, dict) else pred.__dict__
                        break
                if not prediction and predictions:
                    first = predictions[0]
                    prediction = first if isinstance(first, dict) else first.__dict__

    # 2. 获取影响因素
    context_request = AgentRequest(
        query="context",
        date=date,
        road=road,
        hours=[hour],
    )
    context_agent = ContextAgent()
    search_agent = SearchAgent()

    context_result, search_result = await asyncio.gather(
        context_agent.process(context_request),
        search_agent.process(context_request),
    )

    # 整理因素
    factors = []
    factor_descriptions = []

    if context_result.success:
        for f in context_result.data.get("factors", []):
            factor_info = {
                "type": getattr(f, "type", "unknown"),
                "name": getattr(f, "name", ""),
                "description": getattr(f, "description", ""),
                "impact": getattr(f, "impact", "neutral"),
            }
            factors.append(factor_info)
            factor_descriptions.append(f"{factor_info['name']}: {factor_info['description']}")

    if search_result.success:
        for f in search_result.data.get("factors", []):
            factor_info = {
                "type": getattr(f, "type", "unknown"),
                "name": getattr(f, "name", ""),
                "description": getattr(f, "description", ""),
                "impact": getattr(f, "impact", "neutral"),
            }
            factors.append(factor_info)
            factor_descriptions.append(f"{factor_info['name']}: {factor_info['description']}")

    # 3. 生成自然语言解释
    congestion_level = prediction.get("congestion_level", "unknown") if prediction else "unknown"
    congestion_score = prediction.get("congestion_score", 0) if prediction else 0
    flow = prediction.get("kfz_h_p50", 0) if prediction else 0
    speed = prediction.get("v_kfz", 0) if prediction else 0

    # 拥堵等级翻译
    level_names = {
        "zh": {
            "smooth": "畅通",
            "light": "轻度拥堵",
            "moderate": "中度拥堵",
            "heavy": "严重拥堵",
            "critical": "极度拥堵",
        },
        "en": {
            "smooth": "Smooth",
            "light": "Light congestion",
            "moderate": "Moderate congestion",
            "heavy": "Heavy congestion",
            "critical": "Critical congestion",
        },
        "de": {
            "smooth": "Flüssig",
            "light": "Leichter Stau",
            "moderate": "Mittlerer Stau",
            "heavy": "Starker Stau",
            "critical": "Sehr starker Stau",
        },
    }

    level_name = level_names.get(lang, level_names["zh"]).get(congestion_level, congestion_level)

    # 构建 prompt
    if lang == "zh":
        prompt = f"""请用要点形式解释以下交通状况原因：

日期: {date}
时间: {hour}:00
道路: {road}
拥堵等级: {level_name}
拥堵指数: {congestion_score}/100
流量: {flow:.0f} 辆/小时
平均车速: {speed:.1f} km/h

影响因素:
{chr(10).join(factor_descriptions) if factor_descriptions else "无特殊因素"}

要求:
- 用 2-4 个要点解释原因
- 每个要点以 "•" 开头
- 每个要点一行，简洁明了
- 提及具体数据（如流量、车速）
- 提及主要影响因素

示例格式:
• 施工影响：A8多处施工封闭车道
• 流量较高：4500辆/小时，接近高峰
• 假期因素：暑假期间出行增多"""
        system = "你是交通状况解释助手，用要点形式解释交通原因。每个要点简洁有力。"

    elif lang == "en":
        prompt = f"""Explain the following traffic condition in bullet points:

Date: {date}
Time: {hour}:00
Road: {road}
Congestion Level: {level_name}
Congestion Score: {congestion_score}/100
Traffic Flow: {flow:.0f} vehicles/hour
Average Speed: {speed:.1f} km/h

Factors:
{chr(10).join(factor_descriptions) if factor_descriptions else "No special factors"}

Requirements:
- Use 2-4 bullet points to explain
- Start each point with "•"
- One point per line, concise
- Include specific data (flow, speed)
- Mention key factors

Example format:
• Construction: Multiple lane closures on A8
• High volume: 4500 veh/h, near peak
• Holiday effect: Summer vacation increases travel"""
        system = "You are a traffic explanation assistant. Use bullet points to explain traffic conditions."

    else:  # de
        prompt = f"""Erklären Sie die folgende Verkehrssituation in Stichpunkten:

Datum: {date}
Zeit: {hour}:00
Straße: {road}
Staustufe: {level_name}
Stauindex: {congestion_score}/100
Verkehrsfluss: {flow:.0f} Fahrzeuge/Stunde
Durchschnittsgeschwindigkeit: {speed:.1f} km/h

Einflussfaktoren:
{chr(10).join(factor_descriptions) if factor_descriptions else "Keine besonderen Faktoren"}

Anforderungen:
- Verwenden Sie 2-4 Stichpunkte
- Beginnen Sie jeden Punkt mit "•"
- Ein Punkt pro Zeile, prägnant
- Nennen Sie konkrete Daten (Fluss, Geschwindigkeit)
- Erwähnen Sie wichtige Faktoren

Beispielformat:
• Baustelle: Mehrere Fahrspuren auf A8 gesperrt
• Hohes Volumen: 4500 Fzg/h, nahe Spitze
• Ferieneffekt: Sommerferien erhöhen Reiseverkehr"""
        system = "Sie sind ein Verkehrserklärungs-Assistent. Verwenden Sie Stichpunkte zur Erklärung."

    explanation = await generate(prompt, system=system)

    return {
        "date": date,
        "hour": hour,
        "road": road,
        "congestion_level": congestion_level,
        "congestion_level_name": level_name,
        "congestion_score": congestion_score,
        "flow": round(flow),
        "speed": round(speed, 1),
        "explanation": explanation.strip(),
        "factors": factors,
    }


async def handle_batch_explanations(
    date: str,
    hours: List[int],
    road: str = "A8",
    lang: str = "zh",
) -> Dict[str, Any]:
    """
    批量生成多个小时的交通解释。

    Args:
        date: 日期
        hours: 小时列表
        road: 道路
        lang: 语言

    Returns:
        {
            "date": "2026-07-25",
            "road": "A8",
            "explanations": [
                {"hour": 8, "explanation": "...", ...},
                {"hour": 9, "explanation": "...", ...},
            ]
        }
    """
    # 并行获取所有小时的解释
    tasks = [
        handle_hourly_explanation(date, hour, road, lang)
        for hour in hours
    ]
    results = await asyncio.gather(*tasks)

    return {
        "date": date,
        "road": road,
        "explanations": results,
    }
