# AlpineFlow AI - Agent Layer
# Multi-Agent System + Graph RAG + LangGraph

__all__ = []

# LangGraph Agent System (recommended)
try:
    from .langgraph import TrafficAgentGraph, create_traffic_graph, AgentState
    __all__.extend(["TrafficAgentGraph", "create_traffic_graph", "AgentState"])
except ImportError as e:
    print(f"Warning: LangGraph imports failed: {e}")

# Data Loading
try:
    from .data_loader import prediction_loader, external_loader, get_forecast
    from .congestion_score import CongestionScoreCalculator, calculate_congestion_score
    __all__.extend([
        "prediction_loader", "external_loader", "get_forecast",
        "CongestionScoreCalculator", "calculate_congestion_score"
    ])
except ImportError as e:
    print(f"Warning: Data loader imports failed: {e}")

# Legacy Agent System (rule-based)
try:
    from .orchestrator import OrchestratorAgent
    from .agents import ForecastAgent, ExplanationAgent, RetrievalAgent, SimulationAgent
    __all__.extend([
        "OrchestratorAgent",
        "ForecastAgent",
        "ExplanationAgent",
        "RetrievalAgent",
        "SimulationAgent",
    ])
except ImportError:
    pass  # Legacy modules optional
