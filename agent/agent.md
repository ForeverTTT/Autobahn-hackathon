# Agent 详细逻辑说明

本文档详细说明每个 Agent 的处理逻辑、输入输出和实现细节。

---

## 目录

1. [IntentParser - 意图解析器](#1-intentparser---意图解析器)
2. [ForecastAgent - 预测Agent](#2-forecastagent---预测agent)
3. [ContextAgent - 上下文Agent](#3-contextagent---上下文agent)
4. [SearchAgent - 搜索Agent](#4-searchagent---搜索agent)
5. [GenerationAgent - 响应生成Agent](#5-generationagent---响应生成agent)
6. [Orchestrator - 调度器](#6-orchestrator---调度器)

---

## 1. IntentParser - 意图解析器

**位置**: `agents/intent_parser.py`

### 职责

使用 **LLM** 理解用户自然语言输入，识别：
1. **用户画像 (Persona)** - 决定用户需要什么帮助
2. **数据需求** - 决定需要查询什么数据
3. 日期、目的地、道路、意图

### 核心输出: ParsedIntent

```python
@dataclass
class ParsedIntent:
    # 基础信息
    user_type: UserType
    persona_type: PersonaType    # 用户画像
    date: str
    destination: Optional[str]
    road: str
    intent: str

    # 用户核心问题
    core_question: str           # "Can I arrive on time?" 等

    # 数据需求
    data_requirements: DataRequirements
```

```python
@dataclass
class DataRequirements:
    time_range: str      # today, week, flexible
    granularity: str     # hourly, daily, segment, simple, detailed
    hours: List[int]     # 关注的小时 [6,7,8,9,...]
    features: List[str]  # 需要的功能
```

### 处理逻辑

```
用户输入: "我每天开车上班，今天下班几点走最好？"
                │
                ▼
┌─────────────────────────────────────────┐
│            LLM 语义理解                  │
│                                         │
│  识别 persona: "每天上班" → commuter    │
│  识别 date: "今天" → 2026-06-20         │
│  识别 intent: "几点走" → plan           │
└─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│        获取 Persona 数据需求             │
│                                         │
│  COMMUTER:                              │
│  - time_range: "today"                  │
│  - granularity: "hourly"                │
│  - hours: [6,7,8,9,16,17,18,19]        │
│  - features: [best_departure_time,      │
│               peak_hour_warning,        │
│               time_saved]               │
└─────────────────────────────────────────┘
                │
                ▼
        ParsedIntent {
            persona_type: COMMUTER,
            core_question: "Can I arrive on time?",
            data_requirements: {
                time_range: "today",
                granularity: "hourly",
                hours: [6,7,8,9,16,17,18,19]
            }
        }
```

### Persona → 数据需求映射

| Persona | time_range | granularity | hours | 核心功能 |
|---------|------------|-------------|-------|----------|
| **Commuter** | today | hourly | 6-9, 16-19 | 最佳出发时间 |
| **Traveler** | week | daily | 6-22 | 日期推荐 |
| **Logistics** | today | segment | 4-14 | 路段延误 |
| **Tourist** | flexible | simple | 7-20 | 简单建议 |
| **Operator** | week | detailed | 0-24 | 因素分析 |

### Persona 识别关键词

| Persona | 关键词示例 |
|---------|------------|
| commuter | "上班"、"通勤"、"每天"、"下班" |
| traveler | "带家人"、"周末出游"、"度假"、"旅行" |
| logistics | "送货"、"运输"、"货车"、"物流" |
| tourist | "第一次来"、"不熟悉"、"游客" |
| operator | "管理"、"监控"、"交警"、"为什么堵" |

### 代码示例

```python
from agent.agents import IntentParser
import asyncio

parser = IntentParser(use_llm=True)

async def main():
    # 通勤者
    result = await parser.parse_async("今天下班几点走最好")
    print(result.persona_type)           # PersonaType.COMMUTER
    print(result.core_question)          # "Can I arrive on time?"
    print(result.data_requirements.hours) # [6,7,8,9,16,17,18,19]

    # 物流司机
    result = await parser.parse_async("我送货的，明天去奥地利哪段路会堵")
    print(result.persona_type)           # PersonaType.LOGISTICS
    print(result.core_question)          # "Where will delays happen?"
    print(result.data_requirements.granularity)  # "segment"

asyncio.run(main())
```

### Orchestrator 如何使用数据需求

```python
# Orchestrator 根据 data_requirements 决定调用哪些 Agent

if persona == COMMUTER:
    # 只需要今日小时预测
    tasks = [forecast_agent]

elif persona == LOGISTICS:
    # 需要预测 + 施工信息
    tasks = [forecast_agent, search_agent]

elif persona == OPERATOR:
    # 需要所有数据
    tasks = [forecast_agent, context_agent, search_agent]
```

---

### LLM vs 关键词匹配

| 用户输入 | 关键词匹配 | LLM 理解 |
|----------|-----------|----------|
| "我跑长途的" | ❌ 无法识别 | ✅ → LOGISTICS |
| "想自驾游" | ❌ 无法识别 | ✅ → TRAVELER |
| "帮我规划下出行" | ❌ 无法识别 | ✅ → intent: plan |
| "Austria" | ✅ → salzburg | ✅ → salzburg |
| "下个周末" | ❌ 无法识别 | ✅ → 正确日期 |

### 支持的 LLM 提供商

| 提供商 | 模型 | 环境变量 |
|--------|------|----------|
| OpenAI | gpt-4o-mini (默认) | `OPENAI_API_KEY` |
| Anthropic | claude-3-5-sonnet | `ANTHROPIC_API_KEY` |

配置方式:
```bash
# 使用 OpenAI
export OPENAI_API_KEY="sk-..."
export LLM_PROVIDER="openai"

# 或使用 Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"
```

### Fallback 机制

如果 LLM 调用失败，自动回退到关键词匹配：

```python
async def parse_async(self, query, default_user_type):
    if self.use_llm:
        try:
            return await self._parse_with_llm(query, ...)
        except Exception as e:
            print(f"LLM failed: {e}, falling back...")

    # 回退到关键词匹配
    return self.parse(query, default_user_type)
```

---

## 2. ForecastAgent - 预测Agent

**位置**: `agents/forecast_agent.py`

### 职责

- 从 `forecast_2026_2029.csv` 读取预测数据
- 计算每小时拥堵分数
- 返回日度预测汇总

### 处理逻辑

```
AgentRequest {date, road, hours}
                │
                ▼
┌─────────────────────────────────────────┐
│      PredictionLoader.query()           │
│                                         │
│  从 CSV 按日期分块读取                   │
│  过滤: road, site_id, hours             │
└─────────────────────────────────────────┘
                │
                ▼
        有数据? ─────否────▶ 生成模拟数据
                │
               是
                │
                ▼
┌─────────────────────────────────────────┐
│      计算拥堵分数 (每小时)               │
│                                         │
│  输入:                                  │
│  - kfz_h: 总车流量                      │
│  - sv_h: 重车流量                       │
│  - v_kfz: 平均车速                      │
│                                         │
│  计算:                                  │
│  - 流量因子 (25%)                       │
│  - 速度因子 (30%)                       │
│  - 容量因子 (25%)                       │
│  - 外部因子 (20%)                       │
│                                         │
│  输出:                                  │
│  - congestion_score: 0-100              │
│  - congestion_level: smooth/light/...   │
└─────────────────────────────────────────┘
                │
                ▼
        DailyForecast {
            predictions: [HourlyPrediction, ...],
            peak_hour: 16,
            avg_congestion_score: 35.5,
            total_volume: 28000
        }
```

### 拥堵分数计算

```python
# 权重
WEIGHTS = {
    "traffic": 0.25,    # 流量/容量比
    "speed": 0.30,      # 速度下降比
    "capacity": 0.25,   # 容量利用 + 重车比例
    "external": 0.20,   # 周末/假期/高峰
}

# 等级映射
score < 20  → SMOOTH   (畅通，绿色)
score < 40  → LIGHT    (轻微，黄色)
score < 60  → MODERATE (中等，橙色)
score < 80  → HEAVY    (严重，红色)
score >= 80 → CRITICAL (拥堵，深红)
```

### 输出示例

```python
HourlyPrediction(
    hour=8,
    kfz_h_p10=1342,
    kfz_h_p50=1789,
    kfz_h_p90=2415,
    sv_h=180,
    v_kfz=88.2,
    congestion_score=35.5,
    congestion_level=CongestionLevel.LIGHT
)
```

---

## 3. ContextAgent - 上下文Agent

**位置**: `agents/context_agent.py`

### 职责

查询 `data_autobahn` 中的**离线外部因素**：
- 天气、气温
- 假期、学校假期
- 季节性因素
- 周末效应
- 历史交通参考

### 处理逻辑

```
AgentRequest {date, road}
                │
                ▼
┌─────────────────────────────────────────┐
│        并行查询多个数据源                 │
│                                         │
│  ┌──────────┐  ┌──────────┐            │
│  │ 天气数据  │  │ 假期数据  │            │
│  │ weather  │  │ holiday  │            │
│  │ 日级.csv │  │ 日级.csv │            │
│  └──────────┘  └──────────┘            │
│                                         │
│  ┌──────────┐  ┌──────────┐            │
│  │ 季节规则  │  │ 周末规则  │            │
│  │ (代码)   │  │ (代码)   │            │
│  └──────────┘  └──────────┘            │
└─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│        生成 ExternalFactor 列表          │
│                                         │
│  ExternalFactor(                        │
│      type="holiday",                    │
│      name="圣诞节",                      │
│      description="公共假期，流量增加",    │
│      impact="high",                     │
│      source="context"  ← 标记为离线数据  │
│  )                                      │
└─────────────────────────────────────────┘
```

### 因素类型

| 类型 | 来源 | 说明 |
|------|------|------|
| `weather` | weather日级.csv | 历史天气/气候基准 |
| `holiday` | holiday日级.csv + 硬编码 | 公共假期 |
| `school_holiday` | holiday日级.csv | 学校假期 |
| `season` | 代码规则 | 夏季旅游季/冬季滑雪季 |
| `weekend` | 代码规则 | 周五出行/周日返程 |
| `historical` | 历史数据查询 | 去年同期参考 |

### 季节因素规则

```python
# 夏季 (6-8月)
if month in [6, 7, 8]:
    factors.append(ExternalFactor(
        type="season",
        name="夏季旅游季",
        description="前往阿尔卑斯方向交通增加",
        impact="high"
    ))

# 冬季 (12-2月)
if month in [12, 1, 2]:
    factors.append(ExternalFactor(
        type="season",
        name="冬季滑雪季",
        description="前往奥地利方向交通增加",
        impact="moderate"
    ))
```

### 周末因素规则

```python
# 周五
if weekday == 4:
    factors.append(ExternalFactor(
        type="weekend",
        name="周五出行高峰",
        description="下午出城方向拥堵加剧",
        impact="moderate"
    ))

# 周日
if weekday == 6:
    factors.append(ExternalFactor(
        type="weekend",
        name="周日返程高峰",
        description="下午返城方向拥堵加剧",
        impact="moderate"
    ))
```

---

## 4. SearchAgent - 搜索Agent

**位置**: `agents/search_agent.py`

### 职责

**实时搜索**更新数据（当前为模拟，实际应接入 API）：
- 天气预报（最近 15 天）
- 政府施工公告
- 活动信息
- 事故/临时封路

### 处理逻辑

```
AgentRequest {date, road}
                │
                ▼
┌─────────────────────────────────────────┐
│         并行调用多个 API                 │
│                                         │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ 天气 API     │  │ Autobahn API │    │
│  │ (15天预报)   │  │ (施工公告)   │    │
│  └──────────────┘  └──────────────┘    │
│                                         │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ 活动日历 API │  │ 交通信息 API │    │
│  │ (音乐节等)   │  │ (事故信息)   │    │
│  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│        生成 ExternalFactor 列表          │
│                                         │
│  ExternalFactor(                        │
│      type="construction",               │
│      name="A8 桥梁翻新",                 │
│      description="Rosenheim附近...",    │
│      impact="moderate",                 │
│      source="search"  ← 标记为实时数据   │
│  )                                      │
└─────────────────────────────────────────┘
```

### 天气预报逻辑

```python
async def _search_weather(self, date: str):
    # 计算距离目标日期的天数
    days_ahead = (date_obj - today).days

    # 只能预报未来 15 天
    if days_ahead > 15:
        return [ExternalFactor(
            type="weather",
            name="天气预报不可用",
            description=f"超出15天预报范围",
            impact="low"
        )]

    # TODO: 调用真实天气 API
    # 当前使用模拟数据
```

### 施工信息逻辑

```python
async def _search_construction(self, date: str, road: str):
    # TODO: 调用 https://autobahn.api.bund.dev/

    # 当前硬编码示例施工
    if road == "A8" and in_date_range(date, "2026-06-01", "2026-09-30"):
        return [ExternalFactor(
            type="construction",
            name="A8 桥梁翻新工程",
            description="Rosenheim 附近，右车道封闭",
            impact="moderate"
        )]
```

### 活动信息逻辑

```python
async def _search_events(self, date: str):
    # 萨尔茨堡音乐节 (7月中 - 8月底)
    if in_date_range(date, "2026-07-18", "2026-08-31"):
        return [ExternalFactor(
            type="event",
            name="萨尔茨堡音乐节",
            description="A8 往萨尔茨堡方向下午拥堵加剧",
            impact="high"
        )]

    # 慕尼黑啤酒节 (9月中 - 10月初)
    if in_date_range(date, "2026-09-19", "2026-10-04"):
        return [ExternalFactor(
            type="event",
            name="慕尼黑啤酒节",
            description="慕尼黑周边交通压力极大",
            impact="very_high"
        )]
```

### 实际 API 接入建议

| 数据类型 | 推荐 API |
|----------|----------|
| 天气预报 | OpenWeatherMap / DWD (德国气象局) |
| 施工公告 | https://autobahn.api.bund.dev/ |
| 活动信息 | 本地活动日历 API |
| 事故信息 | 实时交通信息 API |

---

## 5. GenerationAgent - 响应生成Agent

**位置**: `agents/generation_agent.py`

### 核心理念

> **不同用户需要的不是"预测堵车"，而是"基于预测做更好的决定"。**

### 用户画像 → 核心问题

| Persona | Core Question | 需要的决策支持 |
|---------|---------------|----------------|
| 🚗 **Commuter** | "Can I arrive on time?" | 最佳出发时间 + 节省时间 |
| 👨‍👩‍👧 **Family Traveler** | "Which day should we travel?" | 日历视图 + 日期推荐 |
| 🚚 **Logistics** | "Where will delays happen?" | 路段预测 + 延误估算 |
| 🧳 **Tourist** | "Tell me what I should do." | 简单直接的建议 |
| 🏢 **Operator** | "Why will congestion happen?" | 因素贡献 + 管理建议 |

### 处理逻辑

```
输入:
├── AgentRequest (用户请求 + 用户类型)
├── DailyForecast (预测结果)
├── List[ExternalFactor] (上下文因素)
└── List[ExternalFactor] (搜索因素)
                │
                ▼
┌─────────────────────────────────────────┐
│         识别用户画像 (Persona)           │
│                                         │
│  user_type → PersonaProfile             │
│  - core_question                        │
│  - data_needs                           │
│  - output_style                         │
└─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│      根据 Persona 选择生成策略           │
│                                         │
│  Commuter   → _generate_commuter_response│
│  Traveler   → _generate_traveler_response│
│  Logistics  → _generate_logistics_response│
│  Tourist    → _generate_tourist_response │
│  Operator   → _generate_operator_response│
└─────────────────────────────────────────┘
                │
                ▼
          针对性输出
```

---

### 1. Commuter: "Can I arrive on time?"

**输入**: 今日小时级预测
**输出**: 最佳出发时间 + 避开时段 + 节省时间

```markdown
### 🚗 今日通勤建议

**最佳出发时间**: 16:30
**避开时段**: 17:00, 18:00

预计节省 **~25 分钟**

⚠️ 17:00-18:00 为今日最拥堵时段
```

---

### 2. Family Traveler: "Which day should we travel?"

**输入**: 未来一周日级预测 + 假期信息
**输出**: 日历视图 + 最佳出行日 + 原因解释

```markdown
### 📅 出行日历: 慕尼黑 → 萨尔茨堡

| 日期 | 星期 | 拥堵预测 | 原因 |
|------|------|----------|------|
| 2026-07-24 | 周五 | 🔴 严重 | 假期首日, 周五出行高峰 |
| 2026-07-25 | 周六 | 🟠 中等 | 周末出行 |
| 2026-07-26 | 周日 | 🟢 畅通 | - |

✅ **最佳出行日**: 周日 (2026-07-26)

⚠️ 巴伐利亚学校假期开始，周五拥堵严重
```

---

### 3. Logistics: "Where will delays happen?"

**输入**: 路段级预测 + 施工信息
**输出**: 路段地图 + 延误估算 + 瓶颈检测

```markdown
### 🚚 路段预测: A8 München → Salzburg

| 路段 | 状态 | 预计延误 | 原因 |
|------|------|----------|------|
| München Nord | 🟢 | +0 min | - |
| Rosenheim | 🟠 | +12 min | 重车流量大 |
| Salzburg 入口 | 🔴 | +25 min | 瓶颈路段, 施工 |

**总延误估算**: +37 分钟
**建议出发时间**: 05:30 前

⚠️ 瓶颈路段: Salzburg 入口
```

---

### 4. Tourist: "Tell me what I should do."

**输入**: 简化预测
**输出**: 像朋友一样的简单建议

```markdown
### 🧳 驾驶建议

**周六去萨尔茨堡？**

由于假期交通，拥堵风险较高。

✅ **建议**: 7:30 前出发，可以避开大部分车流

🚗 预计行程: 1小时30分钟
```

---

### 5. Operator: "Why will congestion happen?"

**输入**: 详细预测 + 所有因素
**输出**: 可解释AI + 因素贡献 + 管理建议

```markdown
### 🏢 拥堵分析报告

**预测日期**: 2026-07-25
**预测路段**: A8 München-Salzburg
**风险等级**: 🔴 高风险

#### 影响因素贡献

```
假期效应        ████████████████░░░░  +35%
周末效应        ██████████░░░░░░░░░░  +25%
历史模式        ████████████░░░░░░░░  +30%
天气因素        ████░░░░░░░░░░░░░░░░  +10%
```

#### 建议措施

1. 考虑启动可变限速
2. 增派巡逻力量至瓶颈路段
3. 提前发布公众出行建议
```

---

### 代码结构

```python
class GenerationAgent:

    async def process(self, request, forecast, context_factors, search_factors):
        # 1. 识别用户画像
        persona = self._get_persona(request.user_type)

        # 2. 根据画像选择生成策略
        if persona.type == PersonaType.COMMUTER:
            return self._generate_commuter_response(...)
        elif persona.type == PersonaType.FAMILY_TRAVELER:
            return self._generate_traveler_response(...)
        elif persona.type == PersonaType.LOGISTICS:
            return self._generate_logistics_response(...)
        elif persona.type == PersonaType.TOURIST:
            return self._generate_tourist_response(...)
        elif persona.type == PersonaType.OPERATOR:
            return self._generate_operator_response(...)
```

---

## 6. Orchestrator - 调度器

**位置**: `orchestrator.py`

### 职责

- 解析用户意图
- **并行**执行三个数据 Agent
- 汇总结果给 GenerationAgent
- 返回最终响应

### 处理逻辑

```
用户查询: "周六去萨尔茨堡，什么时候出发好？"
                │
                ▼
┌─────────────────────────────────────────┐
│      IntentParser.parse_async()         │
│              (LLM)                      │
│                                         │
│  → ParsedIntent {                       │
│      user_type: TRAVELER,               │
│      date: "2026-06-27",                │
│      destination: "salzburg"            │
│  }                                      │
└─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│         创建 AgentRequest               │
└─────────────────────────────────────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐
│Forecast│ │Context │ │ Search │
│ Agent  │ │ Agent  │ │ Agent  │
└────────┘ └────────┘ └────────┘
    │           │           │
    │   asyncio.gather()    │
    │    (并行执行)          │
    │           │           │
    └───────────┼───────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│        GenerationAgent.process()        │
│                                         │
│  输入:                                  │
│  - request                              │
│  - forecast (预测结果)                  │
│  - context_factors (上下文因素)         │
│  - search_factors (搜索因素)            │
└─────────────────────────────────────────┘
                │
                ▼
        最终响应 {
            success: true,
            parsed: {...},
            plan: TravelPlan,
            advice: "## 🚗 ...",
            options: [TravelOption, ...],
            factors: [ExternalFactor, ...]
        }
```

### 并行执行代码

```python
async def process(self, query: str, user_type: UserType = None):
    # 1. 解析意图 (使用 LLM)
    parsed = await self.intent_parser.parse_async(query, user_type)
    request = AgentRequest(...)

    # 2. 并行执行三个 Agent
    forecast_task = asyncio.create_task(self.forecast_agent.process(request))
    context_task = asyncio.create_task(self.context_agent.process(request))
    search_task = asyncio.create_task(self.search_agent.process(request))

    # 等待所有任务完成
    forecast_result, context_result, search_result = await asyncio.gather(
        forecast_task, context_task, search_task
    )

    # 3. 汇总给 GenerationAgent
    generation_result = await self.generation_agent.process(
        request=request,
        forecast=forecast_result.data.get("forecast"),
        context_factors=context_result.data.get("factors", []),
        search_factors=search_result.data.get("factors", []),
    )

    # 4. 返回结果
    return {...}
```

### 使用示例

```python
from agent import Orchestrator, UserType

# 异步使用
async def main():
    orchestrator = Orchestrator()
    result = await orchestrator.process(
        "周六去萨尔茨堡，什么时候出发好？",
        UserType.TRAVELER
    )
    print(result["advice"])

# 同步使用
from agent import ask
advice = ask("周六去萨尔茨堡")
print(advice)
```

---

## 数据流总结

```
用户输入
    │
    ▼
IntentParser (LLM) ────────────────────────────────────┐
    │                                                  │
    ▼                                                  │
AgentRequest                                           │
    │                                                  │
    ├──────────────┬──────────────┐                   │
    │              │              │                   │
    ▼              ▼              ▼                   │
ForecastAgent  ContextAgent  SearchAgent              │
    │              │              │                   │
    │   (并行)     │   (并行)     │   (并行)          │
    │              │              │                   │
    ▼              ▼              ▼                   │
DailyForecast  factors[]     factors[]               │
    │              │              │                   │
    └──────────────┼──────────────┘                   │
                   │                                   │
                   ▼                                   │
            GenerationAgent ◀──────────────────────────┘
                   │                                ParsedIntent
                   │                                (user_type)
                   ▼
            TravelPlan + Advice (Markdown)
                   │
                   ▼
              用户响应
```
