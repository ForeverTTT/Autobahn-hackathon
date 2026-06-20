"""
API 处理工具
把 FastAPI 路由中的业务处理逻辑抽出来，供 api_app.py 调用。
"""
import asyncio
from typing import Any, Dict, List, Optional

from ..models import AgentRequest, UserType
from ..orchestrator import Orchestrator


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
