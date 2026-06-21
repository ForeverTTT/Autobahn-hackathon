"""
API 处理工具
把 FastAPI 路由中的业务处理逻辑抽出来，供 api_app.py 调用。
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from ..models import AgentRequest, UserType
from ..orchestrator import Orchestrator
from ..session import ChatSession


# ============ 缓存配置 ============
_explanation_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 300  # 缓存 5 分钟

# 预生成的解释 CSV 缓存
_pregenerated_explanations: Dict[str, Dict[str, Any]] = {}
_pregenerated_loaded: bool = False


def _load_pregenerated_explanations() -> None:
    """加载预生成的解释 CSV 文件"""
    global _pregenerated_explanations, _pregenerated_loaded

    if _pregenerated_loaded:
        return

    import csv
    from pathlib import Path

    data_dir = Path(__file__).parent.parent.parent / "data_autobahn"

    for lang in ["en", "zh", "de"]:
        csv_path = data_dir / f"explanations_{lang}.csv"
        if not csv_path.exists():
            continue

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # key: date:hour:road:lang
                    key = f"{row['date']}:{row['hour']}:{row['road']}:{row['lang']}"
                    _pregenerated_explanations[key] = {
                        "date": row["date"],
                        "hour": int(row["hour"]),
                        "road": row["road"],
                        "congestion_level": row["congestion_level"],
                        "congestion_level_name": row["congestion_level_name"],
                        "congestion_score": float(row["congestion_score"]),
                        "flow": int(row["flow"]),
                        "speed": float(row["speed"]),
                        "explanation": row["explanation"],
                        "factors": [],  # CSV 中不存储因素详情
                    }
            print(f"[api_handlers] 加载预生成解释: {csv_path.name} ({len([k for k in _pregenerated_explanations if k.endswith(f':{lang}')])} 条)")
        except Exception as e:
            print(f"[api_handlers] 加载 {csv_path} 失败: {e}")

    _pregenerated_loaded = True


def _get_pregenerated(date: str, hour: int, road: str, lang: str) -> Optional[Dict[str, Any]]:
    """从预生成的 CSV 中获取解释"""
    _load_pregenerated_explanations()
    key = f"{date}:{hour}:{road}:{lang}"
    return _pregenerated_explanations.get(key)


def _get_cached(cache_key: str) -> Optional[Dict[str, Any]]:
    """获取缓存，如果过期则返回 None"""
    if cache_key in _explanation_cache:
        cached_time, cached_data = _explanation_cache[cache_key]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            return cached_data
        else:
            del _explanation_cache[cache_key]
    return None


def _set_cache(cache_key: str, data: Dict[str, Any]) -> None:
    """设置缓存"""
    _explanation_cache[cache_key] = (time.time(), data)


# ============ 模板生成解释（快速模式） ============
def _generate_template_explanation(
    lang: str,
    level_name: str,
    congestion_score: float,
    flow: float,
    speed: float,
    factors: List[Dict[str, Any]],
) -> str:
    """用模板生成解释，不调用 LLM"""
    lines = []

    if lang == "en":
        # 基于拥堵等级的描述
        lines.append(f"• Traffic status: {level_name}, congestion score {congestion_score}/100")

        # 流量和速度
        if flow > 0:
            lines.append(f"• Traffic flow: {flow:.0f} vehicles/hour, average speed {speed:.1f} km/h")

        # 影响因素（最多3个）
        for f in factors[:3]:
            name = f.get("name", "")
            desc = f.get("description", "")
            if name and desc:
                lines.append(f"• {name}: {desc[:100]}")

    elif lang == "de":
        lines.append(f"• Verkehrsstatus: {level_name}, Stauindex {congestion_score}/100")

        if flow > 0:
            lines.append(f"• Verkehrsfluss: {flow:.0f} Fahrzeuge/Stunde, Durchschnittsgeschwindigkeit {speed:.1f} km/h")

        for f in factors[:3]:
            name = f.get("name", "")
            desc = f.get("description", "")
            if name and desc:
                lines.append(f"• {name}: {desc[:100]}")

    else:  # zh
        lines.append(f"• 交通状态：{level_name}，拥堵指数 {congestion_score}/100")

        if flow > 0:
            lines.append(f"• 流量 {flow:.0f} 辆/小时，平均车速 {speed:.1f} km/h")

        for f in factors[:3]:
            name = f.get("name", "")
            desc = f.get("description", "")
            if name and desc:
                lines.append(f"• {name}：{desc[:100]}")

    return "\n".join(lines) if lines else "• No data available"


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
    query = f"I want to travel to {destination or 'salzburg'} on {date}."
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
    query = f"I want to travel to {destination} on {date}."
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
    # 1. 优先从预生成的 CSV 读取（最快）
    pregenerated = _get_pregenerated(date, hour, road, lang)
    if pregenerated:
        return pregenerated

    # 2. 检查内存缓存
    cache_key = f"explain:{date}:{hour}:{road}:{lang}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # 3. 实时生成（fallback）
    from ..agents import ForecastAgent, ContextAgent, SearchAgent

    # 1. 并行获取预测数据和影响因素
    forecast_agent = ForecastAgent()
    context_agent = ContextAgent()
    search_agent = SearchAgent()

    forecast_request = AgentRequest(
        query="hourly explain",
        date=date,
        road=road,
        hours=[hour],
        granularity="hourly",
    )
    context_request = AgentRequest(
        query="context",
        date=date,
        road=road,
        hours=[hour],
    )

    # 全部并行执行
    forecast_result, context_result, search_result = await asyncio.gather(
        forecast_agent.process(forecast_request),
        context_agent.process(context_request),
        search_agent.process(context_request),
    )

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

    # 整理因素
    factors = []

    if context_result.success:
        for f in context_result.data.get("factors", []):
            factor_info = {
                "type": getattr(f, "type", "unknown"),
                "name": getattr(f, "name", ""),
                "description": getattr(f, "description", ""),
                "impact": getattr(f, "impact", "neutral"),
            }
            factors.append(factor_info)

    if search_result.success:
        for f in search_result.data.get("factors", []):
            factor_info = {
                "type": getattr(f, "type", "unknown"),
                "name": getattr(f, "name", ""),
                "description": getattr(f, "description", ""),
                "impact": getattr(f, "impact", "neutral"),
            }
            factors.append(factor_info)

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

    # 使用模板生成解释（不调用 LLM，极速响应）
    explanation = _generate_template_explanation(
        lang=lang,
        level_name=level_name,
        congestion_score=congestion_score,
        flow=flow,
        speed=speed,
        factors=factors,
    )

    result = {
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

    # 存入缓存
    _set_cache(cache_key, result)
    return result


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
