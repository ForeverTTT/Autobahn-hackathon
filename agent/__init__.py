"""
AlpineFlow AI Agent 层

个性化出行助手，支持:
- 交通预测
- 外部因素分析
- 实时信息搜索
- 个性化建议生成

使用方式:
    from agent import ask, get_plan, Orchestrator

    # 快速查询
    advice = ask("周六去萨尔茨堡，什么时候出发好？")
    print(advice)

    # 获取完整计划
    plan = get_plan("2026-07-25", destination="salzburg", user_type="traveler")
"""

# 核心模型
from .models import (
    UserType,
    CongestionLevel,
    HourlyPrediction,
    DailyForecast,
    ExternalFactor,
    TravelOption,
    TravelPlan,
    AgentRequest,
    AgentResponse,
    ROUTES,
    USER_PROFILES,
)

# 调度器
from .orchestrator import (
    Orchestrator,
    ask,
    get_plan,
)

# Agents
from .agents import (
    IntentParser,
    ForecastAgent,
    ContextAgent,
    SearchAgent,
    GenerationAgent,
)

# 工具
from .tools import (
    prediction_loader,
    context_loader,
    calculate_congestion,
)

# LLM
from .llm import (
    LLMClient,
    get_llm_client,
    generate,
    generate_json,
)

# Personas
from .personas import (
    PersonaType,
    PersonaProfile,
    PERSONAS,
    get_persona,
    get_data_needs,
    get_required_features,
)

__all__ = [
    # 模型
    "UserType",
    "CongestionLevel",
    "HourlyPrediction",
    "DailyForecast",
    "ExternalFactor",
    "TravelOption",
    "TravelPlan",
    "AgentRequest",
    "AgentResponse",
    "ROUTES",
    "USER_PROFILES",
    # 调度器
    "Orchestrator",
    "ask",
    "get_plan",
    # Agents
    "IntentParser",
    "ForecastAgent",
    "ContextAgent",
    "SearchAgent",
    "GenerationAgent",
    # 工具
    "prediction_loader",
    "context_loader",
    "calculate_congestion",
    # LLM
    "LLMClient",
    "get_llm_client",
    "generate",
    "generate_json",
    # Personas
    "PersonaType",
    "PersonaProfile",
    "PERSONAS",
    "get_persona",
    "get_data_needs",
    "get_required_features",
]

__version__ = "1.0.0"
