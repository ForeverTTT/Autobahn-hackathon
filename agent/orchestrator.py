"""
Orchestrator - Agent 调度器
根据用户画像智能调度 Agent，获取针对性数据
"""
import asyncio
from typing import Dict, Any

from .models import AgentRequest, UserType
from .personas import PersonaType
from .agents import (
    IntentParser,
    ForecastAgent,
    ContextAgent,
    SearchAgent,
    GenerationAgent,
)


class Orchestrator:
    """
    Agent 调度器

    核心流程:
    1. IntentParser 识别用户画像 + 数据需求
    2. 根据数据需求，智能调度 Agent
    3. 汇总结果给 GenerationAgent
    4. 返回针对用户画像的响应
    """

    def __init__(self):
        self.intent_parser = IntentParser()
        self.forecast_agent = ForecastAgent()
        self.context_agent = ContextAgent()
        self.search_agent = SearchAgent()
        self.generation_agent = GenerationAgent()

    async def process(self, query: str, user_type: UserType = None) -> Dict[str, Any]:
        """
        处理用户查询

        Args:
            query: 用户输入
            user_type: 用户类型（可选，会被 LLM 识别覆盖）

        Returns:
            针对用户画像的响应
        """
        # 1. 解析意图，识别用户画像和数据需求
        parsed = await self.intent_parser.parse_async(query, user_type)

        # 打印调试信息
        print(f"[Orchestrator] Persona: {parsed.persona_type.value}")
        print(f"[Orchestrator] Core Question: {parsed.core_question}")
        print(f"[Orchestrator] Data Needs: {parsed.data_requirements.granularity}, hours={parsed.data_requirements.hours[:3]}...")

        # 2. 创建请求（包含数据需求）
        request = AgentRequest(
            query=query,
            date=parsed.date,
            road=parsed.road,
            hours=parsed.data_requirements.hours,  # 从数据需求获取
            user_type=parsed.user_type,
            destination=parsed.destination,
        )

        # 3. 根据画像决定需要哪些 Agent
        tasks = self._create_agent_tasks(parsed, request)

        # 4. 并行执行 Agent
        results = await asyncio.gather(*tasks.values())
        result_dict = dict(zip(tasks.keys(), results))

        # 5. 提取结果
        forecast_result = result_dict.get("forecast")
        context_result = result_dict.get("context")
        search_result = result_dict.get("search")

        # 6. 汇总给 GenerationAgent
        generation_result = await self.generation_agent.process(
            request=request,
            forecast=forecast_result.data.get("forecast") if forecast_result and forecast_result.success else None,
            context_factors=context_result.data.get("factors", []) if context_result and context_result.success else [],
            search_factors=search_result.data.get("factors", []) if search_result and search_result.success else [],
        )

        # 7. 返回结果
        return {
            "success": generation_result.success,
            "query": query,

            # 用户画像信息
            "persona": {
                "type": parsed.persona_type.value,
                "core_question": parsed.core_question,
                "data_granularity": parsed.data_requirements.granularity,
                "time_range": parsed.data_requirements.time_range,
            },

            # 解析结果
            "parsed": {
                "user_type": parsed.user_type.value,
                "date": parsed.date,
                "destination": parsed.destination,
                "road": parsed.road,
                "intent": parsed.intent,
            },

            # 主要输出
            "advice": generation_result.data.get("advice"),
            "data": generation_result.data.get("data"),
            "factors": generation_result.data.get("factors"),

            # 原始数据（调试用）
            "raw": {
                "forecast": forecast_result.data if forecast_result and forecast_result.success else None,
                "context": context_result.data if context_result and context_result.success else None,
                "search": search_result.data if search_result and search_result.success else None,
            }
        }

    def _create_agent_tasks(self, parsed, request) -> Dict[str, Any]:
        """
        根据用户画像决定需要调用哪些 Agent

        不同画像需要不同的数据:
        - Commuter: 今日小时预测 (forecast)
        - Traveler: 未来一周日历 (forecast + context)
        - Logistics: 路段预测 (forecast + search for 施工)
        - Tourist: 简化数据 (forecast)
        - Operator: 全部数据 (forecast + context + search)
        """
        tasks = {}
        persona = parsed.persona_type
        granularity = parsed.data_requirements.granularity

        # Forecast Agent - 几乎都需要
        if granularity in ["hourly", "daily", "segment", "simple", "detailed"]:
            tasks["forecast"] = asyncio.create_task(
                self.forecast_agent.process(request)
            )

        # Context Agent - 需要离线因素（假期、季节等）
        if persona in [
            PersonaType.FAMILY_TRAVELER,  # 需要假期信息
            PersonaType.OPERATOR,         # 需要全部因素
        ] or granularity == "detailed":
            tasks["context"] = asyncio.create_task(
                self.context_agent.process(request)
            )

        # Search Agent - 需要实时信息（施工、天气等）
        if persona in [
            PersonaType.LOGISTICS,        # 需要施工信息
            PersonaType.FAMILY_TRAVELER,  # 需要天气预报
            PersonaType.OPERATOR,         # 需要全部信息
        ] or granularity == "detailed":
            tasks["search"] = asyncio.create_task(
                self.search_agent.process(request)
            )

        # 至少要有 forecast
        if not tasks:
            tasks["forecast"] = asyncio.create_task(
                self.forecast_agent.process(request)
            )

        print(f"[Orchestrator] Running agents: {list(tasks.keys())}")

        return tasks

    def process_sync(self, query: str, user_type: UserType = None) -> Dict[str, Any]:
        """同步版本"""
        return asyncio.run(self.process(query, user_type))


# ============ 便捷函数 ============

def ask(query: str, user_type: str = None) -> str:
    """
    快速查询

    Args:
        query: 用户问题
        user_type: 用户类型 (可选)

    Returns:
        个性化建议（Markdown格式）
    """
    orchestrator = Orchestrator()
    user_type_enum = UserType(user_type) if user_type else None
    result = orchestrator.process_sync(query, user_type_enum)
    return result.get("advice", "无法生成建议")


def get_plan(
    date: str,
    destination: str = "salzburg",
    user_type: str = "traveler"
) -> Dict[str, Any]:
    """
    获取出行计划

    Args:
        date: 日期 YYYY-MM-DD
        destination: 目的地
        user_type: 用户类型

    Returns:
        完整计划
    """
    query = f"我想在 {date} 去 {destination}"
    orchestrator = Orchestrator()
    user_type_enum = UserType(user_type)
    return orchestrator.process_sync(query, user_type_enum)
