"""
ChatSession - 多轮对话会话管理

支持:
- 对话历史记录
- 上下文保存（计划、预测数据、影响因素）
- 追问原因、修改计划、假设性问题
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from .models import AgentRequest, AgentResponse, UserType
from .agents import (
    IntentParser,
    ParsedIntent,
    ForecastAgent,
    ContextAgent,
    SearchAgent,
    GenerationAgent,
)


class FollowUpType(Enum):
    """追问类型"""
    NEW_QUERY = "new_query"           # 新查询
    ASK_REASON = "ask_reason"         # 追问原因 (为什么)
    MODIFY_PLAN = "modify_plan"       # 修改计划 (改成...)
    HYPOTHETICAL = "hypothetical"     # 假设问题 (如果...呢)
    ASK_DETAIL = "ask_detail"         # 询问细节 (天气、返程等)
    COMPARE = "compare"               # 对比 (有什么不同)
    CONFIRM = "confirm"               # 确认 (好的、就这样)


@dataclass
class Message:
    """对话消息"""
    role: str  # "user" or "assistant"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionContext:
    """会话上下文 - 保存用于追问的数据"""
    # 解析结果
    parsed_intent: Optional[ParsedIntent] = None

    # 原始数据（用于解释原因）
    forecast_data: Optional[Dict] = None
    context_data: Optional[Dict] = None
    context_factors: List[Any] = field(default_factory=list)
    search_factors: List[Any] = field(default_factory=list)

    # 生成的建议
    advice: Optional[str] = None

    # 完整结果
    full_result: Optional[Dict] = None


class ChatSession:
    """
    多轮对话会话

    Example:
        session = ChatSession()

        # 第一轮
        print(session.chat("周六去萨尔茨堡"))

        # 追问原因
        print(session.chat("为什么"))

        # 修改计划
        print(session.chat("改成周日呢"))
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.history: List[Message] = []
        self.context: Optional[SessionContext] = None

        # Agents
        self.intent_parser = IntentParser()
        self.forecast_agent = ForecastAgent()
        self.context_agent = ContextAgent()
        self.search_agent = SearchAgent()
        self.generation_agent = GenerationAgent()

    def _log(self, message: str):
        if self.verbose:
            print(message)

    def _detect_follow_up_type(self, query: str) -> FollowUpType:
        """检测追问类型"""
        query_lower = query.lower().strip()

        # 追问原因
        reason_keywords = ["为什么", "why", "原因", "怎么", "咋"]
        if any(kw in query_lower for kw in reason_keywords):
            return FollowUpType.ASK_REASON

        # 修改计划
        modify_keywords = ["改成", "换成", "改为", "换到", "改到", "不去", "改天"]
        if any(kw in query_lower for kw in modify_keywords):
            return FollowUpType.MODIFY_PLAN

        # 假设问题
        hypothetical_keywords = ["如果", "假如", "要是", "假设", "万一", "只能"]
        if any(kw in query_lower for kw in hypothetical_keywords):
            return FollowUpType.HYPOTHETICAL

        # 询问细节
        detail_keywords = ["天气", "返程", "回来", "回程", "路线", "多远", "多久", "几点"]
        if any(kw in query_lower for kw in detail_keywords):
            return FollowUpType.ASK_DETAIL

        # 对比
        compare_keywords = ["对比", "比较", "区别", "不同", "vs", "还是"]
        if any(kw in query_lower for kw in compare_keywords):
            return FollowUpType.COMPARE

        # 确认
        confirm_keywords = ["好的", "可以", "就这样", "行", "ok", "确定", "好"]
        if query_lower in confirm_keywords or len(query_lower) <= 3:
            return FollowUpType.CONFIRM

        # 默认为新查询
        return FollowUpType.NEW_QUERY

    async def _process_new_query(self, query: str, user_type: UserType = None) -> str:
        """处理新查询 - 调用全部 Agent"""
        self._log(f"[Session] Processing new query: {query}")

        # 1. 解析意图
        parsed = await self.intent_parser.parse_async(query, user_type)
        self._log(f"[Session] Parsed: {parsed.persona_type.value}, {parsed.destination}")

        # 2. 创建请求
        request = AgentRequest(
            query=query,
            date=parsed.time_range.start_date,
            road=parsed.road,
            hours=parsed.data_requirements.hours,
            user_type=parsed.user_type,
            destination=parsed.destination,
            start_date=parsed.time_range.start_date,
            end_date=parsed.time_range.end_date,
            granularity=parsed.data_requirements.granularity.value,
            include_factors=True,
        )

        # 3. 并行调用 Agent
        forecast_task = asyncio.create_task(self.forecast_agent.process(request))
        context_task = asyncio.create_task(self.context_agent.process(request))
        search_task = asyncio.create_task(self.search_agent.process(request))

        forecast_result, context_result, search_result = await asyncio.gather(
            forecast_task, context_task, search_task
        )

        # 4. 提取预测数据
        forecast_data = None
        if forecast_result and forecast_result.success:
            if forecast_result.data.get("mode") == "daily":
                forecast_data = forecast_result.data.get("daily_forecasts")
            else:
                forecast_data = forecast_result.data.get("forecast")

        # 5. 生成建议
        generation_result = await self.generation_agent.process(
            request=request,
            parsed_intent=parsed,
            forecast=forecast_data,
            context_data=context_result.data.get("context", {}) if context_result and context_result.success else {},
            context_factors=context_result.data.get("factors", []) if context_result and context_result.success else [],
            search_factors=search_result.data.get("factors", []) if search_result and search_result.success else [],
        )

        advice = generation_result.data.get("advice", "无法生成建议")

        # 6. 保存上下文
        self.context = SessionContext(
            parsed_intent=parsed,
            forecast_data=forecast_result.data if forecast_result and forecast_result.success else None,
            context_data=context_result.data.get("context", {}) if context_result and context_result.success else {},
            context_factors=context_result.data.get("factors", []) if context_result and context_result.success else [],
            search_factors=search_result.data.get("factors", []) if search_result and search_result.success else [],
            advice=advice,
            full_result={
                "forecast": forecast_result.data if forecast_result else None,
                "context": context_result.data if context_result else None,
                "search": search_result.data if search_result else None,
            }
        )

        return advice

    async def _process_ask_reason(self, query: str) -> str:
        """处理追问原因"""
        self._log(f"[Session] Processing ask_reason: {query}")

        if not self.context or not self.context.forecast_data:
            return "抱歉，请先告诉我您的出行计划，我才能解释原因。"

        # 使用 LLM 基于保存的数据生成解释
        from .tools import generate

        # 构建数据摘要
        forecast_summary = self._summarize_forecast()
        factors_summary = self._summarize_factors()

        prompt = f"""用户之前询问了出行建议，我给出了以下回答：

{self.context.advice}

现在用户追问："{query}"

以下是我做出建议的数据依据：

## 预测数据
{forecast_summary}

## 影响因素
{factors_summary}

请用简洁的中文解释为什么给出这样的建议，要引用具体数据（如流量、速度、时间等）。"""

        explanation = await generate(
            prompt,
            system="你是一个交通顾问，需要解释你的建议依据。使用具体数据支持你的解释。回答要简洁明了。",
        )

        return explanation

    async def _process_modify_plan(self, query: str) -> str:
        """处理修改计划请求"""
        self._log(f"[Session] Processing modify_plan: {query}")

        if not self.context or not self.context.parsed_intent:
            return "抱歉，请先告诉我您的出行计划，然后再修改。"

        # 保存旧的建议用于对比
        old_advice = self.context.advice
        old_parsed = self.context.parsed_intent

        # 使用 LLM 理解修改意图
        from .tools import generate_json

        modify_prompt = f"""用户原本的计划是：
- 目的地: {old_parsed.destination}
- 日期: {old_parsed.time_range.start_date} 至 {old_parsed.time_range.end_date}
- 道路: {old_parsed.road}

用户现在说: "{query}"

请分析用户想要修改什么。返回 JSON:
{{
    "modify_type": "date" | "destination" | "time" | "other",
    "new_value": "提取的新值",
    "new_query": "重新组织的完整查询"
}}"""

        modify_info = await generate_json(
            modify_prompt,
            system="分析用户的修改意图",
        )

        if not modify_info:
            modify_info = {"new_query": query}

        # 用新查询重新获取建议
        new_query = modify_info.get("new_query", query)
        new_advice = await self._process_new_query(new_query)

        # 生成对比说明
        comparison = f"""### 计划对比

**原计划**: {old_parsed.time_range.description}
**新计划**: {self.context.parsed_intent.time_range.description}

---

{new_advice}"""

        return comparison

    async def _process_hypothetical(self, query: str) -> str:
        """处理假设性问题"""
        self._log(f"[Session] Processing hypothetical: {query}")

        if not self.context or not self.context.forecast_data:
            return "抱歉，请先告诉我您的出行计划，然后再问假设问题。"

        from .tools import generate

        forecast_summary = self._summarize_forecast()

        prompt = f"""用户的原始出行计划：
- 目的地: {self.context.parsed_intent.destination}
- 日期: {self.context.parsed_intent.time_range.start_date}
- 我之前的建议: {self.context.advice[:200]}...

用户现在问: "{query}"

可用的预测数据：
{forecast_summary}

请基于数据回答用户的假设性问题。如果用户问的是特定时间出发，请从数据中找出那个时间的预测并给出建议。"""

        answer = await generate(
            prompt,
            system="你是交通顾问，回答用户的假设性问题。要具体、实用，引用数据支持你的回答。",
        )

        return answer

    async def _process_ask_detail(self, query: str) -> str:
        """处理询问细节"""
        self._log(f"[Session] Processing ask_detail: {query}")

        if not self.context:
            return "抱歉，请先告诉我您的出行计划。"

        from .tools import generate

        # 判断询问类型
        query_lower = query.lower()

        # 天气相关
        if "天气" in query_lower:
            factors_summary = self._summarize_factors()
            prompt = f"""用户询问天气信息。

出行计划: {self.context.parsed_intent.destination}, {self.context.parsed_intent.time_range.description}

可用的因素信息:
{factors_summary}

请提取并回答天气相关信息。如果没有天气数据，告诉用户。"""

        # 返程相关
        elif any(kw in query_lower for kw in ["返程", "回来", "回程"]):
            prompt = f"""用户询问返程信息。

原始出行计划: 去 {self.context.parsed_intent.destination}, {self.context.parsed_intent.time_range.description}

请给出返程建议。考虑：
1. 通常返程高峰在下午15-18点
2. 建议避开高峰时段
3. 如果是周末，周日下午返程会更堵"""

        else:
            forecast_summary = self._summarize_forecast()
            factors_summary = self._summarize_factors()
            prompt = f"""用户询问: "{query}"

出行计划: {self.context.parsed_intent.destination}, {self.context.parsed_intent.time_range.description}

预测数据:
{forecast_summary}

影响因素:
{factors_summary}

请回答用户的问题。"""

        answer = await generate(
            prompt,
            system="你是交通顾问，回答用户的具体问题。简洁实用。",
        )

        return answer

    def _summarize_forecast(self) -> str:
        """生成预测数据摘要"""
        if not self.context or not self.context.forecast_data:
            return "无预测数据"

        data = self.context.forecast_data
        lines = []

        # 处理小时级数据
        if "forecast" in data:
            forecast = data["forecast"]
            if isinstance(forecast, dict) and "predictions" in forecast:
                lines.append(f"日期: {forecast.get('date', 'N/A')}, 道路: {forecast.get('road', 'N/A')}")
                for pred in forecast.get("predictions", [])[:8]:  # 只取前8个时段
                    hour = pred.get("hour", "?")
                    flow = pred.get("kfz_h_p50", 0)
                    speed = pred.get("v_kfz", 0)
                    level = pred.get("congestion_level", "unknown")
                    lines.append(f"  {hour}:00 - 流量: {flow:.0f}辆/h, 速度: {speed:.1f}km/h, 状态: {level}")

        # 处理日级数据
        if "daily_forecasts" in data:
            for day in data.get("daily_forecasts", [])[:5]:
                date = day.get("date", "N/A")
                level = day.get("congestion_level", "unknown")
                lines.append(f"  {date}: {level}")

        return "\n".join(lines) if lines else "无预测数据"

    def _summarize_factors(self) -> str:
        """生成影响因素摘要"""
        if not self.context:
            return "无因素数据"

        lines = []

        # Context factors
        for factor in self.context.context_factors[:5]:
            if hasattr(factor, 'name') and hasattr(factor, 'description'):
                lines.append(f"- [{factor.type}] {factor.name}: {factor.description[:50]}")
            elif isinstance(factor, dict):
                lines.append(f"- {factor.get('name', 'Unknown')}: {factor.get('description', '')[:50]}")

        # Search factors
        for factor in self.context.search_factors[:5]:
            if hasattr(factor, 'name') and hasattr(factor, 'description'):
                lines.append(f"- [{factor.type}] {factor.name}: {factor.description[:50]}")
            elif isinstance(factor, dict):
                lines.append(f"- {factor.get('name', 'Unknown')}: {factor.get('description', '')[:50]}")

        return "\n".join(lines) if lines else "无因素数据"

    async def chat_async(self, query: str) -> str:
        """异步对话"""
        # 添加用户消息到历史
        self.history.append(Message(role="user", content=query))

        # 检测追问类型
        follow_up_type = FollowUpType.NEW_QUERY
        if self.context is not None:
            follow_up_type = self._detect_follow_up_type(query)

        self._log(f"[Session] Follow-up type: {follow_up_type.value}")

        # 根据类型处理
        if follow_up_type == FollowUpType.NEW_QUERY:
            response = await self._process_new_query(query)
        elif follow_up_type == FollowUpType.ASK_REASON:
            response = await self._process_ask_reason(query)
        elif follow_up_type == FollowUpType.MODIFY_PLAN:
            response = await self._process_modify_plan(query)
        elif follow_up_type == FollowUpType.HYPOTHETICAL:
            response = await self._process_hypothetical(query)
        elif follow_up_type == FollowUpType.ASK_DETAIL:
            response = await self._process_ask_detail(query)
        elif follow_up_type == FollowUpType.CONFIRM:
            response = "好的，祝您旅途愉快！如有其他问题随时问我。"
        else:
            # COMPARE 或其他情况，作为新查询处理
            response = await self._process_new_query(query)

        # 添加助手消息到历史
        self.history.append(Message(role="assistant", content=response))

        return response

    def chat(self, query: str) -> str:
        """同步对话 - 支持 Jupyter notebook"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.chat_async(query))

        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(self.chat_async(query))

    def clear(self):
        """清除对话历史和上下文"""
        self.history = []
        self.context = None
        self._log("[Session] Cleared")

    @property
    def plan(self) -> Optional[str]:
        """获取当前计划"""
        return self.context.advice if self.context else None

    @property
    def data(self) -> Optional[Dict]:
        """获取原始数据"""
        return self.context.full_result if self.context else None


# ============ 全局会话（便捷使用）============

_global_session: Optional[ChatSession] = None


def get_session(verbose: bool = False) -> ChatSession:
    """获取全局会话"""
    global _global_session
    if _global_session is None:
        _global_session = ChatSession(verbose=verbose)
    return _global_session


def chat_session(query: str) -> str:
    """使用全局会话对话"""
    return get_session().chat(query)


def clear_session():
    """清除全局会话"""
    global _global_session
    if _global_session:
        _global_session.clear()
    _global_session = None
