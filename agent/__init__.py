"""
AlpineFlow AI Agent 层

个性化出行助手，支持:
- 交通预测
- 外部因素分析
- 实时信息搜索
- 个性化建议生成

使用方式:
    from agent import chat

    # 对话式交互（推荐）
    print(chat("周六去萨尔茨堡，什么时候出发好？"))

    # 带调试信息
    from agent import ask
    print(ask("明天去萨尔茨堡", verbose=True))
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
    chat,
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
from .tools import (
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

# Prompts
from .agents.prompt import (
    AGENT_PROMPTS,
    GENERATION_PERSONA_PROMPTS,
    build_generation_prompt,
    get_agent_prompt,
    get_generation_persona_prompt,
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
    "chat",
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
    # Prompts
    "AGENT_PROMPTS",
    "GENERATION_PERSONA_PROMPTS",
    "build_generation_prompt",
    "get_agent_prompt",
    "get_generation_persona_prompt",
]

__version__ = "1.0.0"
