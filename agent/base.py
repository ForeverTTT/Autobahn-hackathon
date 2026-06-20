"""
Base Agent Class
所有Agent的基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum


class AgentType(Enum):
    """Agent类型枚举"""
    ORCHESTRATOR = "orchestrator"
    FORECAST = "forecast"
    EXPLANATION = "explanation"
    RETRIEVAL = "retrieval"
    SIMULATION = "simulation"


@dataclass
class AgentMessage:
    """Agent之间的消息格式"""
    sender: AgentType
    receiver: AgentType
    content: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentResponse:
    """Agent响应格式"""
    success: bool
    data: Any
    message: str
    agent_type: AgentType
    confidence: float = 1.0


class BaseAgent(ABC):
    """
    Agent基类
    所有专职Agent都继承此类
    """

    def __init__(self, agent_type: AgentType, config: Any = None):
        self.agent_type = agent_type
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化Agent资源"""
        pass

    @abstractmethod
    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """处理请求并返回响应"""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """返回Agent的能力列表"""
        pass

    async def health_check(self) -> bool:
        """健康检查"""
        return self._initialized

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} type={self.agent_type.value}>"
