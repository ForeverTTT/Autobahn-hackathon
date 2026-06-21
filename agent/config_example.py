"""
Agent 配置

所有 Agent 参数集中放在这里。
真实 API key 建议通过环境变量注入；如果只是本地演示，
也可以把默认值临时填在这里，但不要提交真实密钥。
"""
import os


# ============ GPT / OpenAI LLM ============

LLM_PROVIDER = "openai"
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

OPENAI_API_KEY_DEFAULT = ""
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", OPENAI_API_KEY_DEFAULT)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")


# ============ Tavily ============

TAVILY_API_KEY_DEFAULT = ""
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", TAVILY_API_KEY_DEFAULT)
TAVILY_ENDPOINT = "https://api.tavily.com/search"
TAVILY_SEARCH_DEPTH = "advanced"
TAVILY_INCLUDE_ANSWER = True
TAVILY_INCLUDE_RAW_CONTENT = False
TAVILY_MAX_RESULTS = 5
TAVILY_TIMEOUT_SECONDS = 20


# ============ Search Output ============

SEARCH_EVIDENCE_RESULTS = 5
SEARCH_SOURCE_RESULTS = 3
SEARCH_DESCRIPTION_LIMIT = 320


# ============ Route Hints ============

ROUTE_HINTS = {
    "A8": "A8 Munich Rosenheim Salzburg {destination}",
    "A93": "A93 Rosenheim Kufstein Innsbruck {destination}",
    "default": "{road} Bavaria Germany {destination}",
}


# ============ Tavily Query Templates ============

SEARCH_TASKS = {
    "weather": {
        "name": "Weather forecast search",
        "query_template": (
            "{date} weather forecast {route_hint} driving conditions "
            "rain snow storm ice severe weather DWD"
        ),
    },
    "construction": {
        "name": "{road} construction and closure search",
        "query_template": (
            "{date} {road} Autobahn construction roadworks closure "
            "lane closed Baustelle Sperrung {route_hint}"
        ),
    },
    "event": {
        "name": "Corridor event search",
        "query_template": (
            "{date} major events festivals concerts public holidays "
            "traffic Munich Salzburg Bavaria {destination}"
        ),
    },
    "incident": {
        "name": "{road} incident and congestion search",
        "query_template": (
            "{date} live traffic incidents accident closure congestion "
            "Stau Unfall {road} {route_hint}"
        ),
    },
}


# ============ Impact Keywords ============

HIGH_IMPACT_TERMS = {
    "weather": [
        "severe weather", "weather warning", "storm", "heavy rain",
        "snow", "ice", "black ice", "thunderstorm", "unwetter",
        "starkregen", "schnee", "glätte",
    ],
    "construction": [
        "full closure", "closure", "closed", "blocked", "sperrung",
        "vollsperrung", "lane closure", "right lane closed",
        "left lane closed",
    ],
    "event": [
        "oktoberfest", "salzburg festival", "major event", "large crowds",
        "public holiday", "school holiday", "festival traffic",
    ],
    "incident": [
        "accident", "crash", "closure", "closed", "blocked", "unfall",
        "stau", "traffic jam", "major delay",
    ],
}

MODERATE_IMPACT_TERMS = {
    "weather": [
        "rain", "showers", "fog", "wind", "wet road", "regen", "nebel",
    ],
    "construction": [
        "construction", "roadworks", "maintenance", "lane", "delay",
        "baustelle", "arbeiten", "traffic restrictions",
    ],
    "event": [
        "event", "festival", "concert", "match", "trade fair", "messe",
        "veranstaltung", "holiday", "traffic",
    ],
    "incident": [
        "congestion", "delay", "slow traffic", "traffic", "incident",
        "stockender verkehr", "traffic restrictions",
    ],
}
