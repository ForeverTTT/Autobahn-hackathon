"""
Agent 配置

所有 SearchAgent 参数集中放在这里。
真实 API key 建议通过环境变量 TAVILY_API_KEY 注入；如果只是本地演示，
也可以把 key 临时填到 TAVILY_API_KEY_DEFAULT，但不要提交真实密钥。
"""
import os


# ============ Tavily ============

TAVILY_API_KEY_DEFAULT = "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"
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
        "name": "天气预报搜索",
        "query_template": (
            "{date} weather forecast {route_hint} driving conditions "
            "rain snow storm ice severe weather DWD"
        ),
    },
    "construction": {
        "name": "{road} 施工/封路搜索",
        "query_template": (
            "{date} {road} Autobahn construction roadworks closure "
            "lane closed Baustelle Sperrung {route_hint}"
        ),
    },
    "event": {
        "name": "沿线活动搜索",
        "query_template": (
            "{date} major events festivals concerts public holidays "
            "traffic Munich Salzburg Bavaria {destination}"
        ),
    },
    "incident": {
        "name": "{road} 事故/拥堵搜索",
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