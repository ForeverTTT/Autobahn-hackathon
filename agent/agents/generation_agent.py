"""
Generation Agent (生成Agent)
负责基于结构化决策结果生成最终响应。
"""
from typing import Any, Dict, List

from ..base import BaseAgent, AgentResponse, AgentType
from ..config import AgentConfig, default_config


class GenerationAgent(BaseAgent):
    """
    生成Agent
    - 消费 Orchestrator 形成的 structured_decision_result 节点
    - 生成面向用户的摘要、关键发现和建议
    - 保留结构化决策结果，方便 API 或前端继续细粒度展示
    """

    def __init__(self, config: AgentConfig = None):
        super().__init__(AgentType.GENERATION, config or default_config)

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        try:
            result = request.get("structured_decision_result")
            if not isinstance(result, dict) or result.get("node") != "structured_decision_result":
                raise ValueError("GenerationAgent requires a structured_decision_result node")

            user_type = result.get("user_type", "tourist")
            intent = result.get("intent", result.get("type", "general"))

            data = {
                "type": result.get("type", intent),
                "source_node": result.get("node", "structured_decision_result"),
                "summary": self._build_summary(result),
                "key_findings": self._build_key_findings(result),
                "recommendations": self._build_recommendations(result, user_type),
                "confidence": result.get("confidence", 0.85),
                "details": result,
            }

            return AgentResponse(
                success=True,
                data=data,
                message="Final response generated successfully",
                agent_type=self.agent_type,
                confidence=data["confidence"],
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                data=None,
                message=f"Generation error: {str(e)}",
                agent_type=self.agent_type,
                confidence=0.0,
            )

    def get_capabilities(self) -> List[str]:
        return [
            "structured_decision_response_generation",
            "decision_result_synthesis",
            "recommendation_generation",
            "structured_output_preservation",
        ]

    def _build_summary(self, result: Dict[str, Any]) -> str:
        result_type = result.get("type", "general")
        forecast = result.get("forecast") or result.get("base_forecast") or {}
        daily_summary = forecast.get("daily_summary", {}) if isinstance(forecast, dict) else {}
        explanation = result.get("explanation") or {}
        external = result.get("external_factors") or {}
        plan = result.get("plan") or {}

        if result_type == "trip_plan" and plan:
            return (
                f"Recommended departure is {plan.get('recommended_departure', 'unknown')}; "
                f"estimated arrival is {plan.get('estimated_arrival', 'unknown')} with "
                f"about {plan.get('estimated_travel_time_min', 'unknown')} minutes of travel time."
            )

        if result_type == "what_if":
            simulation = result.get("simulation") or {}
            sim_summary = simulation.get("simulation_result", {}).get("summary", {})
            return (
                f"Scenario simulation estimates {sim_summary.get('total_delay_minutes', 0)} total delay minutes; "
                f"worst hour is {sim_summary.get('worst_hour', 'unknown')}:00."
            )

        if explanation.get("explanation"):
            return explanation["explanation"]

        if daily_summary:
            return (
                f"Peak traffic is expected around {daily_summary.get('peak_hour', 'unknown')}:00, "
                f"with main congestion level {daily_summary.get('main_congestion_level', 'moderate')}."
            )

        impact = external.get("overall_impact", {}) if isinstance(external, dict) else {}
        if impact:
            return f"External traffic impact is assessed as {impact.get('level', 'unknown')}."

        return "Traffic response generated from the structured decision result."

    def _build_key_findings(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        forecast = result.get("forecast") or result.get("base_forecast") or {}
        external = result.get("external_factors") or {}
        explanation = result.get("explanation") or {}
        graph_context = result.get("graph_context") or explanation.get("graph_context") or {}

        daily_summary = forecast.get("daily_summary", {}) if isinstance(forecast, dict) else {}
        if daily_summary:
            findings.append({
                "type": "forecast",
                "message": f"Peak hour: {daily_summary.get('peak_hour', 'unknown')}:00",
            })

        warnings = external.get("warnings", []) if isinstance(external, dict) else []
        for warning in warnings[:3]:
            findings.append({
                "type": warning.get("type", "warning"),
                "message": warning.get("message", "Traffic warning"),
            })

        for factor in explanation.get("factors", [])[:3]:
            findings.append({
                "type": factor.get("type", "factor"),
                "message": factor.get("description", factor.get("name", "Relevant factor")),
            })

        if graph_context.get("summary"):
            findings.append({
                "type": "graph_rag",
                "message": graph_context["summary"],
            })

        return findings

    def _build_recommendations(self, result: Dict[str, Any], user_type: str) -> List[str]:
        recommendations: List[str] = []
        plan = result.get("plan") or {}
        external = result.get("external_factors") or {}
        simulation = result.get("simulation") or {}

        if plan.get("recommended_departure"):
            recommendations.append(f"Depart around {plan['recommended_departure']} if your schedule is flexible.")

        for warning in external.get("warnings", [])[:2] if isinstance(external, dict) else []:
            recommendation = warning.get("recommendation")
            if recommendation:
                recommendations.append(recommendation)

        for recommendation in simulation.get("recommendations", [])[:2] if isinstance(simulation, dict) else []:
            if isinstance(recommendation, str):
                recommendations.append(recommendation)
            elif isinstance(recommendation, dict) and recommendation.get("message"):
                recommendations.append(recommendation["message"])

        user_defaults = {
            "tourist": "Prefer off-peak travel windows and keep extra time for leisure stops.",
            "resident": "Use familiar local alternatives when motorway peaks are high.",
            "logistics": "Prioritize predictable arrival windows and truck-friendly routes.",
            "tourism_business": "Prepare staffing around predicted arrival peaks.",
            "authority": "Watch high-impact factors for traffic management actions.",
        }
        recommendations.append(user_defaults.get(user_type, user_defaults["tourist"]))

        return list(dict.fromkeys(recommendations))