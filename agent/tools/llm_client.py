"""
LLM 客户端工具
只支持 OpenAI GPT 的异步文本/JSON 生成。
"""
import json
from typing import Any, Dict, Optional

from .. import config


class LLMClient:
    """
    GPT LLM 客户端。

    配置:
        在 agent/config.py 或环境变量中配置 OPENAI_API_KEY。
        模型由 OPENAI_MODEL 控制，默认使用 GPT 系列模型。
    """

    def __init__(
        self,
        provider: str = None,
        model: str = None,
    ):
        if provider and provider != "openai":
            raise ValueError("Only OpenAI GPT is supported")
        self.provider = "openai"
        self.model = model or config.OPENAI_MODEL
        self._init_openai()

    def _init_openai(self):
        """初始化 OpenAI 客户端。"""
        try:
            from openai import AsyncOpenAI
            api_key = config.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set in agent/config.py or environment")

            client_kwargs = {"api_key": api_key}
            if config.OPENAI_BASE_URL:
                client_kwargs["base_url"] = config.OPENAI_BASE_URL
            self.client = AsyncOpenAI(**client_kwargs)
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    async def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """生成文本。"""
        temperature = config.LLM_TEMPERATURE if temperature is None else temperature
        max_tokens = config.LLM_MAX_TOKENS if max_tokens is None else max_tokens

        return await self._generate_openai(prompt, system, temperature, max_tokens)

    async def _generate_openai(
        self,
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """OpenAI 生成。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def generate_json(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
    ) -> Dict[str, Any]:
        """生成 JSON，并自动解析返回值。"""
        json_prompt = f"{prompt}\n\nReturn ONLY valid JSON, no other text."
        response = await self.generate(json_prompt, system, temperature)

        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])

        return json.loads(response)


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例。"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


async def generate(prompt: str, system: str = None) -> str:
    """快捷生成函数。"""
    client = get_llm_client()
    return await client.generate(prompt, system)


async def generate_json(prompt: str, system: str = None) -> Dict[str, Any]:
    """快捷 JSON 生成函数。"""
    client = get_llm_client()
    return await client.generate_json(prompt, system)
