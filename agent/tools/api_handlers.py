"""
API 处理工具
把 FastAPI 路由中的业务处理逻辑抽出来，供 api_app.py 调用。
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..models import AgentRequest, UserType
from ..orchestrator import Orchestrator
from ..session import ChatSession


@dataclass
class _SessionEntry:
    session: ChatSession = field(default_factory=ChatSession)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ChatSessionRegistry:
    """Keep independent multi-turn agent sessions for API clients."""

    def __init__(self):
        self._sessions: Dict[str, _SessionEntry] = {}
        self._lock = asyncio.Lock()

    async def chat(
        self,
        query: str,
        user_type: Optional[str] = "traveler",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_session_id = session_id or str(uuid4())
        user_type_enum = UserType(user_type) if user_type else None

        async with self._lock:
            entry = self._sessions.get(resolved_session_id)
            if entry is None:
                entry = _SessionEntry()
                self._sessions[resolved_session_id] = entry

        async with entry.lock:
            message = await entry.session.chat_async(query, user_type_enum)
            context = entry.session.context

            return {
                "success": True,
                "session_id": resolved_session_id,
                "message": message,
                "advice": message,
                "history_length": len(entry.session.history),
                "plan": {
                    "destination": (
                        context.parsed_intent.destination
                        if context and context.parsed_intent
                        else None
                    ),
                    "start_date": (
                        context.parsed_intent.time_range.start_date
                        if context and context.parsed_intent
                        else None
                    ),
                    "end_date": (
                        context.parsed_intent.time_range.end_date
                        if context and context.parsed_intent
                        else None
                    ),
                },
            }

    async def clear(self, session_id: str) -> bool:
        async with self._lock:
            entry = self._sessions.pop(session_id, None)
        if entry is not None:
            async with entry.lock:
                entry.session.clear()
        return entry is not None


async def handle_chat(
    sessions: ChatSessionRegistry,
    query: str,
    user_type: Optional[str] = "traveler",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """处理支持追问和修改计划的多轮自然语言对话。"""
    return await sessions.chat(query, user_type, session_id)


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
