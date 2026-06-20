# AlpineFlow AI - Agent Layer
# Personalized Travel Assistant

__all__ = []

# ============ 核心模块 (推荐使用) ============

# Travel Assistant - 个性化出行助手
try:
    from .travel_assistant import (
        TravelAssistant,
        UserType,
        TravelPlan,
        TravelOption,
        quick_plan,
        create_assistant,
        TOOLS_SCHEMA,
    )
    __all__.extend([
        "TravelAssistant",
        "UserType",
        "TravelPlan",
        "TravelOption",
        "quick_plan",
        "create_assistant",
        "TOOLS_SCHEMA",
    ])
except ImportError as e:
    print(f"Warning: Travel assistant imports failed: {e}")

# Data Loading - 数据加载
try:
    from .data_loader import prediction_loader, external_loader, get_forecast
    from .congestion_score import CongestionScoreCalculator, calculate_congestion_score
    from .graph_rag import GraphRAG
    __all__.extend([
        "prediction_loader", "external_loader", "get_forecast",
        "CongestionScoreCalculator", "calculate_congestion_score", "GraphRAG"
    ])
except ImportError as e:
    print(f"Warning: Data loader imports failed: {e}")

# ============ 可选模块 ============

# LangGraph Agent System (可选，用于复杂工作流)
try:
    from .langgraph import TrafficAgentGraph, create_traffic_graph, AgentState
    __all__.extend(["TrafficAgentGraph", "create_traffic_graph", "AgentState"])
except ImportError:
    pass  # LangGraph optional

# Legacy Agent System (rule-based)
try:
    from .orchestrator import OrchestratorAgent
    from .agents import ForecastAgent, ExplanationAgent, RetrievalAgent, SimulationAgent, GraphRAGAgent
    __all__.extend([
        "OrchestratorAgent",
        "ForecastAgent",
        "ExplanationAgent",
        "RetrievalAgent",
        "SimulationAgent",
        "GraphRAGAgent",
    ])
except ImportError:
    pass  # Legacy modules optional
