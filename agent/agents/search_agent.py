"""
SearchAgent - Tavily-only Search-o1 Agent
分别搜索天气、施工、活动、事故信息，并归纳为 ExternalFactor。
"""
from datetime import datetime

from .. import config
from .base import BaseAgent
from ..models import AgentRequest, AgentResponse
from ..tools import build_tavily_search_plan, run_tavily_search_plan


class SearchAgent(BaseAgent):
    """
    Tavily-only Search-o1 Agent

    流程:
    1. 将交通风险拆成 weather / construction / event / incident 四类
    2. 分别调用 Tavily 搜索
    3. 从搜索摘要和来源中判断影响强度
    4. 输出 ExternalFactor，供 GenerationAgent 使用

    配置:
    - 设置环境变量 TAVILY_API_KEY
    """

    @property
    def name(self) -> str:
        return "SearchAgent"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理搜索请求。"""
        try:
            tasks = build_tavily_search_plan(request)

            if not config.TAVILY_API_KEY:
                return self._success({
                    "factors": [],
                    "date": request.date,
                    "road": request.road,
                    "search_plan": [task.__dict__ for task in tasks],
                    "sources": [],
                    "errors": ["TAVILY_API_KEY not set in agent/config.py or environment"],
                    "search_time": datetime.now().isoformat(),
                })

            search_result = await run_tavily_search_plan(tasks)

            return self._success({
                "factors": search_result["factors"],
                "date": request.date,
                "road": request.road,
                "search_plan": [task.__dict__ for task in tasks],
                "sources": search_result["sources"],
                "errors": search_result["errors"],
                "search_time": datetime.now().isoformat(),
            })

        except Exception as e:
            return self._error(f"Search error: {str(e)}")
