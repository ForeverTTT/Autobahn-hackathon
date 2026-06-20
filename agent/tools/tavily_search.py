"""
Tavily 搜索工具
将外部搜索计划、API 调用和结果归纳封装成可复用工具。
"""
import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

from .. import config
from ..models import AgentRequest, ExternalFactor


@dataclass
class TavilySearchTask:
    """一次 Tavily 搜索任务。"""
    factor_type: str
    name: str
    query: str
    max_results: int = config.TAVILY_MAX_RESULTS


def build_tavily_search_plan(request: AgentRequest) -> List[TavilySearchTask]:
    """为天气、施工、活动、事故分别生成 Tavily 查询。"""
    road = request.road or "A8"
    date = request.date
    destination = request.destination or ""
    route_hint = _route_hint(road, destination)

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


async def run_tavily_search_plan(
    tasks: List[TavilySearchTask],
) -> Dict[str, Any]:
    """并发运行 Tavily 搜索计划，并返回 factors/sources/errors。"""
    results = await asyncio.gather(
        *[_run_search_task(task) for task in tasks],
        return_exceptions=True,
    )

    factors: List[ExternalFactor] = []
    sources: List[Dict[str, Any]] = []
    errors: List[str] = []

    for task, result in zip(tasks, results):
        if isinstance(result, Exception):
            errors.append(f"{task.factor_type}: {result}")
            continue

        factor = result_to_external_factor(task, result)
        if factor:
            factors.append(factor)

        sources.extend(extract_tavily_sources(task, result))

    return {
        "factors": factors,
        "sources": sources,
        "errors": errors,
    }


async def _run_search_task(task: TavilySearchTask) -> Dict[str, Any]:
    """异步运行单个 Tavily 搜索任务。"""
    return await asyncio.to_thread(post_tavily_search, task)


def post_tavily_search(task: TavilySearchTask) -> Dict[str, Any]:
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


def result_to_external_factor(
    task: TavilySearchTask,
    result: Dict[str, Any],
) -> Optional[ExternalFactor]:
    """将 Tavily 结果归纳成 ExternalFactor。"""
    evidence = collect_tavily_evidence_text(result)
    if not evidence:
        return None

    impact = estimate_search_impact(task.factor_type, evidence)
    if impact == "none":
        return None

    description = build_tavily_description(result)
    if not description:
        return None

    return ExternalFactor(
        type=task.factor_type,
        name=task.name,
        description=description,
        impact=impact,
        source="search",
    )


def collect_tavily_evidence_text(result: Dict[str, Any]) -> str:
    """收集用于判断影响强度的搜索文本。"""
    parts: List[str] = []
    answer = result.get("answer")
    if answer:
        parts.append(str(answer))

    for item in result.get("results", [])[:config.SEARCH_EVIDENCE_RESULTS]:
        parts.append(str(item.get("title", "")))
        parts.append(str(item.get("content", "")))

    return " ".join(parts).lower()


def build_tavily_description(result: Dict[str, Any]) -> str:
    """生成给下游使用的简短描述。"""
    answer = result.get("answer")
    if answer:
        return truncate_text(str(answer), config.SEARCH_DESCRIPTION_LIMIT)

    for item in result.get("results", []):
        content = item.get("content")
        if content:
            return truncate_text(str(content), config.SEARCH_DESCRIPTION_LIMIT)

    return ""


def estimate_search_impact(factor_type: str, text: str) -> str:
    """用保守关键词规则判断交通影响强度。"""
    if contains_any(text, config.HIGH_IMPACT_TERMS.get(factor_type, [])):
        return "high"
    if contains_any(text, config.MODERATE_IMPACT_TERMS.get(factor_type, [])):
        return "moderate"

    return "none"


def extract_tavily_sources(
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


def _route_hint(road: str, destination: str) -> str:
    """根据道路和目的地生成搜索范围提示。"""
    road_upper = road.upper()
    route_template = config.ROUTE_HINTS.get(road_upper, config.ROUTE_HINTS["default"])
    return route_template.format(road=road, destination=destination).strip()


def contains_any(text: str, terms: List[str]) -> bool:
    return any(term in text for term in terms)


def truncate_text(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
