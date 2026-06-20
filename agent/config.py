"""
Agent Layer Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: str = "openai"  # openai, anthropic, local
    model: str = "gpt-4o"
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class ModelConfig:
    """预测模型配置"""
    models_dir: str = "../models"
    targets: list = field(default_factory=lambda: ["kfz_h", "sv_h", "v_kfz"])
    quantiles: list = field(default_factory=lambda: [0.1, 0.5, 0.9])


@dataclass
class GraphRAGConfig:
    """Graph RAG配置"""
    backend: str = "local_table_graph"
    require_date_for_forecast: bool = True


@dataclass
class AgentConfig:
    """Agent系统总配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    graph_rag: GraphRAGConfig = field(default_factory=GraphRAGConfig)

    # 数据路径
    data_dir: str = "../data_autobahn"
    holidays_file: str = "../external/holidays/holidays.csv"

    # Agent行为配置
    max_agent_iterations: int = 5
    verbose: bool = True


# 默认配置实例
default_config = AgentConfig()
