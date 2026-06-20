"""
Graph RAG Agent
把本地图查询层包装成可被 Orchestrator / LangGraph 调用的专职 Agent。
"""
from typing import Any, Dict, List

from ..base import BaseAgent, AgentResponse, AgentType
from ..config import AgentConfig, default_config
from ..graph_rag import CypherQueryError, GraphRAG


class GraphRAGAgent(BaseAgent):
    """Agent wrapper around the local table-backed GraphRAG."""

    def __init__(self, config: AgentConfig = None):
        super().__init__(AgentType.GRAPH_RAG, config or default_config)
        self.graph = GraphRAG()

    async def initialize(self) -> bool:
        await self.graph.initialize()
        self._initialized = True
        return True

    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """
        Request examples:
        - {"cypher": "MATCH (f:Forecast) WHERE f.date = $date RETURN f", "params": {...}}
        - {"action": "factors", "date": "2026-08-01", "segment_id": "A8_Mch_MQB25_Mch_H"}
        - {"action": "explain", "date": "2026-08-01", "segment_id": "...", "hour": 9}
        """
        try:
            if not self._initialized:
                await self.initialize()

            action = request.get("action", "cypher" if request.get("cypher") else "context")

            if action == "cypher":
                data = self.graph.query_cypher(request["cypher"], request.get("params", {}))
            elif action == "factors":
                data = self.graph.query_factors(
                    request.get("segment_id") or request.get("site_id", ""),
                    request["date"],
                )
            elif action == "explain":
                data = self.graph.explain_congestion(
                    request.get("segment_id") or request.get("site_id", ""),
                    request["date"],
                    int(request.get("hour", 8)),
                )
            elif action == "stats":
                data = self.graph.get_statistics()
            else:
                data = self.graph.get_user_relevant_info(
                    request.get("user_type", "tourist"),
                    request["date"],
                    request.get("road", "A8"),
                )

            return AgentResponse(
                success=True,
                data=data,
                message="Graph RAG query completed",
                agent_type=self.agent_type,
                confidence=0.9,
            )
        except (KeyError, CypherQueryError, ValueError) as exc:
            return AgentResponse(
                success=False,
                data=None,
                message=f"Graph RAG query error: {exc}",
                agent_type=self.agent_type,
                confidence=0.0,
            )

    def get_capabilities(self) -> List[str]:
        return [
            "local_graph_rag",
            "cypher_subset_query",
            "forecast_graph_context",
            "factor_retrieval",
            "congestion_explanation",
        ]