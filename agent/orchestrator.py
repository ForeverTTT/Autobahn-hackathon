"""
Orchestrator - Agent 调度器
根据用户画像和时间范围智能调度 Agent
"""
import asyncio
from typing import Dict, Any

from .models import AgentRequest, UserType
from .agents import (
    IntentParser,
    ParsedIntent,
    ForecastAgent,
    ContextAgent,
    SearchAgent,
    GenerationAgent,
)


class Orchestrator:
    """
    Agent 调度器

    核心流程:
    1. IntentParser 识别用户画像 + 时间范围 + 数据需求
    2. 根据时间范围长度，智能调度 Agent
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
            user_type: 用户类型（可选）

        Returns:
            针对用户画像的响应
        """
        # 1. 解析意图，识别用户画像、时间范围和数据需求
        parsed = await self.intent_parser.parse_async(query, user_type)

        # 打印调试信息
        print(f"[Orchestrator] Persona: {parsed.persona_type.value}")
        print(f"[Orchestrator] Core Question: {parsed.core_question}")
        print(f"[Orchestrator] Time Range: {parsed.time_range.type.value} ({parsed.time_range.description})")
        print(f"[Orchestrator]   - Start: {parsed.time_range.start_date}")
        print(f"[Orchestrator]   - End: {parsed.time_range.end_date}")
        print(f"[Orchestrator]   - Duration: {parsed.time_range.duration_days} days")
        print(f"[Orchestrator] Granularity: {parsed.data_requirements.granularity.value}")
        if parsed.trip_plan:
            print(f"[Orchestrator] Trip Type: {parsed.trip_plan.trip_type.value}")
            if parsed.trip_plan.stay_days:
                print(f"[Orchestrator] Stay Days: {parsed.trip_plan.stay_days}")

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

        # 3. 根据画像和时间范围决定需要哪些 Agent
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
            parsed_intent=parsed,  # 传递完整的解析结果
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
            },

            # 时间范围信息
            "time_range": {
                "type": parsed.time_range.type.value,
                "start_date": parsed.time_range.start_date,
                "end_date": parsed.time_range.end_date,
                "duration_days": parsed.time_range.duration_days,
                "description": parsed.time_range.description,
                "granularity": parsed.data_requirements.granularity.value,
            },

            # 行程计划（往返）
            "trip_plan": {
                "trip_type": parsed.trip_plan.trip_type.value if parsed.trip_plan else "one_way",
                "outbound_date": parsed.trip_plan.outbound_date if parsed.trip_plan else None,
                "outbound_time": parsed.trip_plan.outbound_time if parsed.trip_plan else None,
                "return_date": parsed.trip_plan.return_date if parsed.trip_plan else None,
                "return_time": parsed.trip_plan.return_time if parsed.trip_plan else None,
                "stay_days": parsed.trip_plan.stay_days if parsed.trip_plan else 0,
            } if parsed.trip_plan else None,

            # 解析结果
            "parsed": {
                "user_type": parsed.user_type.value,
                "destination": parsed.destination,
                "road": parsed.road,
                "intent": parsed.intent,
            },

            # 主要输出
            "advice": generation_result.data.get("advice"),
            "data": generation_result.data.get("data"),
            "factors": generation_result.data.get("factors"),

            # 原始数据
            "raw": {
                "forecast": forecast_result.data if forecast_result and forecast_result.success else None,
                "context": context_result.data if context_result and context_result.success else None,
                "search": search_result.data if search_result and search_result.success else None,
            }
        }

    def _create_agent_tasks(self, parsed: ParsedIntent, request: AgentRequest) -> Dict[str, Any]:
        """
        创建 Agent 任务 - 始终调度全部三个 Agent 并行执行
        """
        tasks = {
            "forecast": asyncio.create_task(self.forecast_agent.process(request)),
            "context": asyncio.create_task(self.context_agent.process(request)),
            "search": asyncio.create_task(self.search_agent.process(request)),
        }

        print(f"[Orchestrator] Running agents: forecast, context, search")

        return tasks

    def process_sync(self, query: str, user_type: UserType = None) -> Dict[str, Any]:
        """同步版本"""
        return asyncio.run(self.process(query, user_type))


# ============ 便捷函数 ============

def ask(query: str, user_type: str = None) -> str:
    """快速查询"""
    orchestrator = Orchestrator()
    user_type_enum = UserType(user_type) if user_type else None
    result = orchestrator.process_sync(query, user_type_enum)
    return result.get("advice", "无法生成建议")


def get_plan(
    date: str,
    destination: str = "salzburg",
    user_type: str = "traveler"
) -> Dict[str, Any]:
    """获取出行计划"""
    query = f"我想在 {date} 去 {destination}"
    orchestrator = Orchestrator()
    user_type_enum = UserType(user_type)
    return orchestrator.process_sync(query, user_type_enum)
