"""
SearchAgent - Tavily-only Search-o1 Agent
分别搜索天气、施工、活动、事故信息，并归纳为 ExternalFactor。
"""
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

from .. import config
from .base import BaseAgent
from ..models import AgentRequest, AgentResponse, ExternalFactor


@dataclass
class TavilySearchTask:
    """一次 Tavily 搜索任务。"""
    factor_type: str
    name: str
    query: str
    max_results: int = config.TAVILY_MAX_RESULTS


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
            tasks = self._build_search_plan(request)

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

            results = await asyncio.gather(
                *[self._run_search_task(task) for task in tasks],
                return_exceptions=True,
            )

            factors: List[ExternalFactor] = []
            sources: List[Dict[str, Any]] = []
            errors: List[str] = []

            for task, result in zip(tasks, results):
                if isinstance(result, Exception):
                    errors.append(f"{task.factor_type}: {result}")
                    continue

                factor = self._result_to_factor(task, result)
                if factor:
                    factors.append(factor)

                sources.extend(self._extract_sources(task, result))

            return self._success({
                "factors": factors,
                "date": request.date,
                "road": request.road,
                "search_plan": [task.__dict__ for task in tasks],
                "sources": sources,
                "errors": errors,
                "search_time": datetime.now().isoformat(),
            })

        except Exception as e:
            return self._error(f"Search error: {str(e)}")

    def _build_search_plan(self, request: AgentRequest) -> List[TavilySearchTask]:
        """为天气、施工、活动、事故分别生成 Tavily 查询。"""
        road = request.road or "A8"
        date = request.date
        destination = request.destination or ""
        route_hint = self._route_hint(road, destination)

        template_values = {
            "date": date,
            "road": road,
            "destination": destination,
            "route_hint": route_hint,
        }

        return [
            TavilySearchTask(
                factor_type=factor_type,
                name=task_config["name"].format(**template_values),
                query=task_config["query_template"].format(**template_values),
            )
            for factor_type, task_config in config.SEARCH_TASKS.items()
        ]

    async def _run_search_task(self, task: TavilySearchTask) -> Dict[str, Any]:
        """异步运行单个 Tavily 搜索任务。"""
        return await asyncio.to_thread(self._post_tavily, task)

    def _post_tavily(self, task: TavilySearchTask) -> Dict[str, Any]:
        """调用 Tavily Search API。"""
        payload = {
            "api_key": config.TAVILY_API_KEY,
            "query": task.query,
            "search_depth": config.TAVILY_SEARCH_DEPTH,
            "include_answer": config.TAVILY_INCLUDE_ANSWER,
            "include_raw_content": config.TAVILY_INCLUDE_RAW_CONTENT,
            "max_results": task.max_results,
        }

        req = urlrequest.Request(
            config.TAVILY_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlrequest.urlopen(req, timeout=config.TAVILY_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Tavily HTTP {e.code}: {detail}") from e
        except urlerror.URLError as e:
            raise RuntimeError(f"Tavily request failed: {e.reason}") from e

    def _result_to_factor(
        self,
        task: TavilySearchTask,
        result: Dict[str, Any],
    ) -> Optional[ExternalFactor]:
        """将 Tavily 结果归纳成 ExternalFactor。"""
        evidence = self._collect_evidence_text(result)
        if not evidence:
            return None

        impact = self._estimate_impact(task.factor_type, evidence)
        if impact == "none":
            return None

        description = self._build_description(result)
        if not description:
            return None

        return ExternalFactor(
            type=task.factor_type,
            name=task.name,
            description=description,
            impact=impact,
            source="search",
        )

    def _collect_evidence_text(self, result: Dict[str, Any]) -> str:
        """收集用于判断影响强度的搜索文本。"""
        parts: List[str] = []
        answer = result.get("answer")
        if answer:
            parts.append(str(answer))

        for item in result.get("results", [])[:config.SEARCH_EVIDENCE_RESULTS]:
            parts.append(str(item.get("title", "")))
            parts.append(str(item.get("content", "")))

        return " ".join(parts).lower()

    def _build_description(self, result: Dict[str, Any]) -> str:
        """生成给下游使用的简短描述。"""
        answer = result.get("answer")
        if answer:
            return self._truncate(str(answer), config.SEARCH_DESCRIPTION_LIMIT)

        for item in result.get("results", []):
            content = item.get("content")
            if content:
                return self._truncate(str(content), config.SEARCH_DESCRIPTION_LIMIT)

        return ""

    def _estimate_impact(self, factor_type: str, text: str) -> str:
        """用保守关键词规则判断交通影响强度。"""
        if self._contains_any(text, config.HIGH_IMPACT_TERMS.get(factor_type, [])):
            return "high"
        if self._contains_any(text, config.MODERATE_IMPACT_TERMS.get(factor_type, [])):
            return "moderate"

        return "none"

    def _extract_sources(
        self,
        task: TavilySearchTask,
        result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """保留 Tavily 来源，便于调试和演示。"""
        sources = []
        for item in result.get("results", [])[:config.SEARCH_SOURCE_RESULTS]:
            sources.append({
                "type": task.factor_type,
                "title": item.get("title"),
                "url": item.get("url"),
                "score": item.get("score"),
            })
        return sources

    def _route_hint(self, road: str, destination: str) -> str:
        """根据道路和目的地生成搜索范围提示。"""
        road_upper = road.upper()
        route_template = config.ROUTE_HINTS.get(road_upper, config.ROUTE_HINTS["default"])
        return route_template.format(road=road, destination=destination).strip()

    def _contains_any(self, text: str, terms: List[str]) -> bool:
        return any(term in text for term in terms)

    def _truncate(self, text: str, limit: int) -> str:
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."