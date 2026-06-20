# Intent Parser 意图识别详解

本文档详细说明 IntentParser 的设计理念、识别逻辑和数据需求映射。

---

## 目录

1. [设计理念](#1-设计理念)
2. [用户画像定义](#2-用户画像定义)
3. [时间范围识别](#3-时间范围识别)
4. [识别流程](#4-识别流程)
5. [五种用户画像详解](#5-五种用户画像详解)
6. [数据需求映射](#6-数据需求映射)
7. [LLM Prompt 设计](#7-llm-prompt-设计)
8. [Fallback 机制](#8-fallback-机制)
9. [代码示例](#9-代码示例)

---

## 1. 设计理念

### 核心观点

> **不同用户需要的不是"预测堵车"，而是"基于预测做更好的决定"。**

传统方式：所有用户看到相同的预测数据
```
用户输入 → 预测数据 → 展示给用户
```

我们的方式：根据用户画像提供针对性决策支持
```
用户输入 → 识别画像 → 理解核心问题 → 确定数据需求 → 针对性输出
```

### 为什么需要意图识别？

| 用户 | 同样问"周六路况" | 实际需要的答案 |
|------|------------------|----------------|
| 通勤者 | 几点出发最好 | "16:30出发，节省25分钟" |
| 家庭游客 | 周六适合出行吗 | "周六中等拥堵，周日更好" |
| 物流司机 | 哪段路会堵 | "Salzburg入口延误+25分钟" |
| 游客 | 怎么走 | "7:30前出发就好" |
| 管理者 | 为什么会堵 | "假期效应+35%，建议限速" |

---

## 2. 用户画像定义

### 五种用户画像 (Persona)

```python
class PersonaType(str, Enum):
    COMMUTER = "commuter"           # 🚗 日常通勤者
    FAMILY_TRAVELER = "traveler"    # 👨‍👩‍👧 家庭旅行者
    LOGISTICS = "logistics"         # 🚚 物流司机
    TOURIST = "tourist"             # 🧳 游客
    OPERATOR = "operator"           # 🏢 交通管理者
```

### 画像对比表

| 画像 | 典型场景 | 核心问题 | 关注点 |
|------|----------|----------|--------|
| 🚗 Commuter | 每天开车上下班 | Can I arrive on time? | 今天几点走最好 |
| 👨‍👩‍👧 Traveler | 周末带家人出游 | Which day should we travel? | 哪天出行最好 |
| 🚚 Logistics | 货车送货 | Where will delays happen? | 哪段路会延误 |
| 🧳 Tourist | 第一次来德国 | Tell me what I should do. | 简单告诉我怎么做 |
| 🏢 Operator | 交通管理/交警 | Why will congestion happen? | 为什么会堵 |

---

## 3. 时间范围识别

### 为什么需要智能时间识别？

用户经常使用模糊的时间表达，如 "暑假"、"下周末"、"圣诞节期间"。系统需要：
1. 识别时间范围类型
2. 计算具体的开始和结束日期
3. 根据时间跨度自动调整数据粒度

### TimeRangeType 时间范围类型

```python
class TimeRangeType(str, Enum):
    """时间范围类型"""
    TODAY = "today"              # 今天
    TOMORROW = "tomorrow"        # 明天
    THIS_WEEK = "this_week"      # 本周
    NEXT_WEEK = "next_week"      # 下周
    THIS_WEEKEND = "this_weekend"  # 这周末
    NEXT_WEEKEND = "next_weekend"  # 下周末
    THIS_MONTH = "this_month"    # 本月
    NEXT_MONTH = "next_month"    # 下月
    SUMMER = "summer"            # 暑假 (7月1日 - 8月31日)
    WINTER = "winter"            # 寒假/冬季 (12月1日 - 2月28日)
    CHRISTMAS = "christmas"      # 圣诞节期间 (12月20日 - 1月6日)
    EASTER = "easter"            # 复活节期间
    CUSTOM = "custom"            # 自定义范围 (如"7月中旬")
    FLEXIBLE = "flexible"        # 灵活/未指定
```

### TimeRange 数据结构

```python
@dataclass
class TimeRange:
    """时间范围"""
    type: TimeRangeType          # 范围类型
    start_date: str              # YYYY-MM-DD 开始日期
    end_date: str                # YYYY-MM-DD 结束日期
    duration_days: int           # 天数
    description: str             # 用户原话，如 "暑假"、"下周末"
```

### 时间范围映射表

| 用户表达 | TimeRangeType | 日期计算 | 天数 |
|----------|---------------|----------|------|
| 今天 | TODAY | 当天 | 1 |
| 明天 | TOMORROW | 明天 | 1 |
| 这周末 | THIS_WEEKEND | 本周六 - 本周日 | 2 |
| 下周末 | NEXT_WEEKEND | 下周六 - 下周日 | 2 |
| 本周 | THIS_WEEK | 本周一 - 本周日 | 7 |
| 下周 | NEXT_WEEK | 下周一 - 下周日 | 7 |
| 暑假/夏天 | SUMMER | 7月1日 - 8月31日 | 62 |
| 寒假/冬天/滑雪季 | WINTER | 12月1日 - 2月28日 | 90 |
| 圣诞节 | CHRISTMAS | 12月20日 - 1月6日 | 18 |
| 复活节 | EASTER | 4月1日 - 4月15日 | 15 |
| 7月中旬 | CUSTOM | 7月10日 - 7月20日 | 11 |

### DataGranularity 数据粒度

根据时间范围长度**自动调整**数据粒度：

```python
class DataGranularity(str, Enum):
    """数据粒度"""
    HOURLY = "hourly"      # 小时级 - 适用于 1 天
    DAILY = "daily"        # 日级 - 适用于 1 周内
    WEEKLY = "weekly"      # 周级 - 适用于 1 个月以上
    MONTHLY = "monthly"    # 月级 - 适用于跨季度
```

### 粒度自动调整规则

```python
def _determine_granularity(duration_days: int) -> DataGranularity:
    if duration_days <= 1:
        return DataGranularity.HOURLY    # 1天 → 小时级
    elif duration_days <= 7:
        return DataGranularity.DAILY     # 1周 → 日级
    elif duration_days <= 60:
        return DataGranularity.WEEKLY    # 2个月 → 周级
    else:
        return DataGranularity.MONTHLY   # 跨季度 → 月级
```

### 示例：暑假时间识别

用户输入: `"暑假去奥地利，什么时候出发不堵？"`

```python
ParsedIntent {
    persona_type: FAMILY_TRAVELER,
    core_question: "Which day should we travel?",
    time_range: TimeRange {
        type: SUMMER,
        start_date: "2026-07-01",
        end_date: "2026-08-31",
        duration_days: 62,
        description: "暑假"
    },
    data_requirements: DataRequirements {
        granularity: WEEKLY,     # 62天 → 周级
        hours: [6-22],
        features: [
            "daily_congestion_level",
            "holiday_impact",
            "best_travel_day",
            "holiday_calendar",     # 长时间范围额外功能
            "event_calendar",
            "best_windows"
        ]
    }
}
```

### 输出根据时间范围调整

| 时间范围 | 粒度 | 输出类型 |
|----------|------|----------|
| 1 天 | HOURLY | 小时级建议 (最佳出发时间) |
| 2-14 天 | DAILY | 日历视图 (每日拥堵预测) |
| 14+ 天 | WEEKLY | 周窗口推荐 (最佳/避开时段) |

---

## 4. 识别流程

### 完整流程图

```
用户输入: "暑假去奥地利，什么时候出发不堵？"
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                  Step 1: LLM 语义理解                │
│                                                     │
│   LLM 返回:                                         │
│   {                                                 │
│     "persona": "traveler",                          │
│     "time_range": {                                 │
│       "type": "summer",                             │
│       "start_date": "2026-07-01",                   │
│       "end_date": "2026-08-31",                     │
│       "description": "暑假"                         │
│     },                                              │
│     "destination": "salzburg",                      │
│     "road": "A8",                                   │
│     "intent": "plan"                                │
│   }                                                 │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              Step 2: 解析时间范围                    │
│                                                     │
│   TimeRange {                                       │
│     type: SUMMER,                                   │
│     start_date: "2026-07-01",                       │
│     end_date: "2026-08-31",                         │
│     duration_days: 62,                              │
│     description: "暑假"                             │
│   }                                                 │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│          Step 3: 根据时间跨度确定数据粒度             │
│                                                     │
│   duration_days = 62                                │
│   → granularity = WEEKLY  (因为 > 14 天)            │
│                                                     │
│   DataRequirements {                                │
│     time_range: TimeRange {...},                    │
│     granularity: WEEKLY,                            │
│     hours: [6-22],                                  │
│     features: [                                     │
│       "daily_congestion_level",                     │
│       "holiday_calendar",     ← 长时间范围额外功能   │
│       "best_windows"          ← 最佳窗口推荐        │
│     ]                                               │
│   }                                                 │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              Step 4: 返回 ParsedIntent               │
│                                                     │
│   ParsedIntent {                                    │
│     persona_type: FAMILY_TRAVELER,                  │
│     core_question: "Which day should we travel?",   │
│     time_range: TimeRange {                         │
│       type: SUMMER,                                 │
│       duration_days: 62                             │
│     },                                              │
│     data_requirements: DataRequirements {           │
│       granularity: WEEKLY                           │
│     }                                               │
│   }                                                 │
└─────────────────────────────────────────────────────┘
```

### 输出数据结构

```python
@dataclass
class TimeRange:
    """时间范围"""
    type: TimeRangeType          # 范围类型 (SUMMER, WINTER, etc.)
    start_date: str              # YYYY-MM-DD 开始日期
    end_date: str                # YYYY-MM-DD 结束日期
    duration_days: int           # 天数
    description: str             # 用户原话描述


@dataclass
class DataRequirements:
    """数据需求"""
    time_range: TimeRange        # 时间范围 (包含类型、日期、天数)
    granularity: DataGranularity # HOURLY, DAILY, WEEKLY, MONTHLY
    hours: List[int]             # 关注的小时
    features: List[str]          # 需要的功能


@dataclass
class ParsedIntent:
    """意图解析结果"""

    # 基础信息
    user_type: UserType           # 兼容旧系统
    persona_type: PersonaType     # 用户画像
    destination: Optional[str]    # 目的地
    road: str                     # 高速公路
    intent: str                   # 具体意图

    # 用户画像信息
    core_question: str            # 用户核心问题

    # 时间范围（智能识别）
    time_range: TimeRange         # 包含完整时间范围信息

    # 数据需求
    data_requirements: DataRequirements
```

---

## 5. 五种用户画像详解

### 5.1 🚗 Commuter（日常通勤者）

#### 用户特征
```
- 每天固定时间上下班
- 经常走同一条路线
- 对路况有一定了解
- 时间敏感，不想迟到
```

#### 典型场景
```
"我每天8点上班，今天几点出发好？"
"下班想早点走，17点会堵吗？"
"明早通勤路上堵不堵？"
```

#### 识别关键词
```python
COMMUTER_KEYWORDS = [
    # 中文
    "上班", "下班", "通勤", "每天", "工作日", "早上去公司", "下班回家",
    # 英文
    "commute", "daily", "work", "office", "every day", "morning rush"
]
```

#### 核心问题
```
"Can I arrive on time?"
"我能准时到达吗？"
```

#### 数据需求
```python
data_needs = {
    "time_range": "today",              # 只关心今天
    "granularity": "hourly",            # 小时级精度
    "hours": [6, 7, 8, 9, 16, 17, 18, 19],  # 早晚高峰
    "features": [
        "hourly_congestion",            # 每小时拥堵预测
        "best_departure_time",          # 最佳出发时间
        "peak_hour_warning",            # 高峰时段警告
        "time_saved",                   # 可节省时间
    ],
}
```

#### 识别逻辑
```python
def is_commuter(query: str) -> bool:
    """判断是否为通勤者"""

    # 关键词匹配
    keywords = ["上班", "下班", "通勤", "每天"]
    if any(kw in query for kw in keywords):
        return True

    # 语义理解 (LLM)
    # "明早8点要到公司" → 通勤场景
    # "每天都走这条路" → 日常通勤

    return False
```

#### 输出示例
```markdown
### 🚗 今日通勤建议

**最佳出发时间**: 16:30
**避开时段**: 17:00-18:30

预计节省 **~25 分钟**

⚠️ 17:15-18:00 为今日最拥堵时段

**影响因素**:
- 周五下班高峰
```

---

### 5.2 👨‍👩‍👧 Family Traveler（家庭旅行者）

#### 用户特征
```
- 周末/假期出游
- 带家人/孩子一起
- 希望旅途轻松愉快
- 可以灵活选择日期
```

#### 典型场景
```
"周末想带家人去萨尔茨堡，哪天走好？"
"暑假去奥地利，什么时候出发不堵？"
"下周自驾游，推荐哪天？"
```

#### 识别关键词
```python
TRAVELER_KEYWORDS = [
    # 中文
    "带家人", "带孩子", "周末出游", "度假", "旅行", "自驾游",
    "出去玩", "假期", "旅游",
    # 英文
    "family", "vacation", "trip", "holiday", "weekend trip", "road trip"
]
```

#### 核心问题
```
"Which day should we travel?"
"哪一天出行最好？"
```

#### 数据需求
```python
data_needs = {
    "time_range": "week",               # 未来一周
    "granularity": "daily",             # 日级预测
    "hours": list(range(6, 22)),        # 全天
    "features": [
        "daily_congestion_level",       # 每日拥堵等级
        "holiday_impact",               # 假期影响分析
        "best_travel_day",              # 最佳出行日推荐
        "congestion_reason",            # 拥堵原因解释
    ],
}
```

#### 识别逻辑
```python
def is_family_traveler(query: str) -> bool:
    """判断是否为家庭旅行者"""

    # 家庭相关
    if any(kw in query for kw in ["带家人", "带孩子", "一家人", "family"]):
        return True

    # 旅行相关
    if any(kw in query for kw in ["度假", "旅行", "自驾游", "vacation"]):
        return True

    # 日期选择相关
    if "哪天" in query or "什么时候" in query:
        if any(kw in query for kw in ["出游", "出发", "走"]):
            return True

    return False
```

#### 输出示例 - 中等时间范围 (一周)

```markdown
### 📅 出行日历: 慕尼黑 → 萨尔茨堡
**时间范围**: 下周

| 日期 | 星期 | 拥堵预测 | 原因 |
|------|------|----------|------|
| 07-24 | 周五 | 🔴 严重 | 假期首日 + 周五出行高峰 |
| 07-25 | 周六 | 🟠 中等 | 周末出行 |
| 07-26 | 周日 | 🟢 畅通 | - |
| 07-27 | 周一 | 🟢 畅通 | 工作日 |
| 07-28 | 周二 | 🟢 畅通 | 工作日 |

✅ **最佳出行日**: 周日 (07-26)

💡 **建议**: 周日上午出发，或周六 14:00 后出发

⚠️ 巴伐利亚学校假期开始，周五拥堵严重
```

#### 输出示例 - 长时间范围 (暑假)

用户输入: `"暑假去奥地利，什么时候出发不堵？"`

```markdown
### 📅 暑假出行推荐
**路线**: A8 München → Salzburg
**时间范围**: 2026-07-01 至 2026-08-31

#### 最佳出行窗口

| 时段 | 拥堵风险 | 原因 |
|------|----------|------|
| 7月上旬 | 🟠 medium | 夏季旅游高峰 |
| 7月中旬 | 🔴 high | 周末出行高峰, 夏季旅游高峰 |
| 7月下旬 | 🔴 high | 巴伐利亚学校假期开始 |
| 8月上旬 | 🔴 high | 夏季旅游高峰 |
| 8月中旬 | 🟠 medium | 夏季旅游高峰 |
| 8月下旬 | 🟢 low | - |

✅ **推荐时段**: 8月下旬
⚠️ **建议避开**: 7月中旬, 7月下旬

#### 重要提醒
- 📅 **巴伐利亚学校假期**: 7月25日-9月5日，流量大增
- 🎭 **萨尔茨堡音乐节**: 7月20日-8月31日，目的地拥堵
```

---

### 5.3 🚚 Logistics（物流司机）

#### 用户特征
```
- 货车/卡车司机
- 需要准时送达
- 关心路段级延误
- 时间就是金钱
```

#### 典型场景
```
"我送货的，明天去奥地利哪段路会堵？"
"货车走A8，几点出发能避开拥堵？"
"跑长途运输，Rosenheim那段堵吗？"
```

#### 识别关键词
```python
LOGISTICS_KEYWORDS = [
    # 中文
    "送货", "运输", "货车", "物流", "配送", "快递", "卡车",
    "拉货", "跑长途", "货运", "司机",
    # 英文
    "truck", "delivery", "logistics", "freight", "cargo", "shipping"
]
```

#### 核心问题
```
"Where will delays happen?"
"哪里会有延误？"
```

#### 数据需求
```python
data_needs = {
    "time_range": "today",              # 今天
    "granularity": "segment",           # 路段级预测
    "hours": list(range(4, 14)),        # 早班配送时段
    "features": [
        "segment_prediction",           # 路段预测
        "bottleneck_detection",         # 瓶颈检测
        "delay_estimation",             # 延误估算
        "risk_warning",                 # 风险提醒
    ],
}
```

#### 识别逻辑
```python
def is_logistics(query: str) -> bool:
    """判断是否为物流司机"""

    # 直接关键词
    if any(kw in query for kw in ["送货", "货车", "物流", "卡车", "truck"]):
        return True

    # 职业描述
    if any(kw in query for kw in ["跑长途", "拉货", "运输"]):
        return True

    # 路段关注
    if "哪段" in query and any(kw in query for kw in ["堵", "延误"]):
        return True

    return False
```

#### 输出示例
```markdown
### 🚚 路段预测: A8 München → Salzburg

| 路段 | 状态 | 预计延误 | 原因 |
|------|------|----------|------|
| München Nord | 🟢 畅通 | +0 min | - |
| München Süd | 🟢 畅通 | +0 min | - |
| Rosenheim | 🟠 轻微 | +12 min | 重车流量大 |
| Salzburg 入口 | 🔴 严重 | +25 min | 瓶颈路段 + 施工 |

**总延误估算**: +37 分钟
**建议出发时间**: 05:30 前

⚠️ 瓶颈路段: Salzburg 入口
- 施工：右车道封闭
- 建议：预留额外 30 分钟
```

---

### 5.4 🧳 Tourist（游客）

#### 用户特征
```
- 不熟悉德国交通
- 第一次来或偶尔来
- 不想看复杂数据
- 需要简单直接的建议
```

#### 典型场景
```
"第一次来德国，怎么开车去萨尔茨堡？"
"我是游客，周六路况怎样？"
"不了解这边交通，能给点建议吗？"
```

#### 识别关键词
```python
TOURIST_KEYWORDS = [
    # 中文
    "第一次来", "不熟悉", "游客", "旅游", "不了解", "初次",
    # 英文
    "tourist", "visit", "new to", "first time", "visitor", "unfamiliar"
]
```

#### 核心问题
```
"Tell me what I should do."
"告诉我该怎么做"
```

#### 数据需求
```python
data_needs = {
    "time_range": "flexible",           # 灵活
    "granularity": "simple",            # 简化，不需要复杂数据
    "hours": list(range(7, 20)),        # 白天
    "features": [
        "simple_recommendation",        # 简单建议
        "natural_language",             # 自然语言输出
        "actionable_advice",            # 可执行的建议
    ],
}
```

#### 识别逻辑
```python
def is_tourist(query: str) -> bool:
    """判断是否为游客"""

    # 明确表示不熟悉
    if any(kw in query for kw in ["第一次", "不熟悉", "不了解", "游客"]):
        return True

    # 英文游客表达
    if any(kw in query for kw in ["tourist", "first time", "new to"]):
        return True

    # 默认：如果没有匹配到其他画像，当作游客处理
    # 因为游客需要最简单的建议

    return False
```

#### 输出示例
```markdown
### 🧳 驾驶建议

**周六去萨尔茨堡？**

由于假期交通，拥堵风险较高。

✅ **建议**: 7:30 前出发，可以避开大部分车流

🚗 预计行程: 1小时30分钟（正常 1小时20分钟）

💡 **小贴士**:
- 德国高速不限速，但建议保持 130 km/h
- 可在 Chiemsee 服务区休息
```

---

### 5.5 🏢 Operator（交通管理者）

#### 用户特征
```
- 交通管理机构/交警
- 需要理解拥堵原因
- 提前制定管理措施
- 需要数据支撑决策
```

#### 典型场景
```
"周六A8为什么会堵？"
"分析一下假期的交通影响"
"需要采取什么管控措施？"
```

#### 识别关键词
```python
OPERATOR_KEYWORDS = [
    # 中文
    "管理", "监控", "交警", "为什么堵", "原因", "分析",
    "管控", "措施", "预警",
    # 英文
    "operator", "manage", "why", "control", "authority",
    "analyze", "reason", "measure"
]
```

#### 核心问题
```
"Why will congestion happen?"
"为什么会拥堵？"
```

#### 数据需求
```python
data_needs = {
    "time_range": "week",               # 未来一周
    "granularity": "detailed",          # 详细分析
    "hours": list(range(0, 24)),        # 全天 24 小时
    "features": [
        "explainable_prediction",       # 可解释的预测
        "factor_contribution",          # 因素贡献分析
        "trend_analysis",               # 趋势分析
        "risk_assessment",              # 风险评估
    ],
}
```

#### 识别逻辑
```python
def is_operator(query: str) -> bool:
    """判断是否为交通管理者"""

    # 询问原因
    if "为什么" in query and any(kw in query for kw in ["堵", "拥堵", "congestion"]):
        return True

    # 管理相关
    if any(kw in query for kw in ["管理", "管控", "交警", "措施"]):
        return True

    # 分析相关
    if "分析" in query and any(kw in query for kw in ["交通", "拥堵", "原因"]):
        return True

    return False
```

#### 输出示例
```markdown
### 🏢 拥堵分析报告

**预测日期**: 2026-07-25 (周六)
**预测路段**: A8 München-Salzburg
**风险等级**: 🔴 高风险

---

#### 影响因素贡献分析

```
假期效应        ████████████████░░░░  +35%
周末效应        ██████████░░░░░░░░░░  +25%
历史模式        ████████████░░░░░░░░  +30%
天气因素        ████░░░░░░░░░░░░░░░░  +10%
```

**总影响**: 预计流量比平日增加 **+100%**

---

#### 时段分析

| 时段 | 预测等级 | 预计流量 |
|------|----------|----------|
| 06:00-09:00 | 🟠 中等 | 2,500 车/小时 |
| 09:00-12:00 | 🔴 严重 | 3,800 车/小时 |
| 12:00-15:00 | 🔴 严重 | 4,200 车/小时 |
| 15:00-18:00 | 🟠 中等 | 3,000 车/小时 |

---

#### 建议措施

1. **可变限速**: 考虑在 09:00 启动 100 km/h 限速
2. **巡逻力量**: 增派至 Rosenheim 和 Salzburg 入口
3. **公众建议**: 提前发布出行预警，建议错峰出行
4. **应急准备**: 在瓶颈路段准备应急车道开放预案
```

---

## 6. 数据需求映射

### 完整映射表

| Persona | time_range | granularity | hours | 调用的 Agent |
|---------|------------|-------------|-------|--------------|
| Commuter | today | hourly | 6-9, 16-19 | Forecast |
| Traveler | week | daily | 6-22 | Forecast + Context |
| Logistics | today | segment | 4-14 | Forecast + Search |
| Tourist | flexible | simple | 7-20 | Forecast |
| Operator | week | detailed | 0-24 | Forecast + Context + Search |

### 代码实现

```python
# personas.py

PERSONAS = {
    PersonaType.COMMUTER: PersonaProfile(
        type=PersonaType.COMMUTER,
        emoji="🚗",
        name="Daily Commuter",
        core_question="Can I arrive on time?",
        data_needs={
            "time_range": "today",
            "granularity": "hourly",
            "hours": [6, 7, 8, 9, 16, 17, 18, 19],
            "features": ["best_departure_time", "peak_hour_warning", "time_saved"],
        },
    ),

    PersonaType.FAMILY_TRAVELER: PersonaProfile(
        type=PersonaType.FAMILY_TRAVELER,
        emoji="👨‍👩‍👧",
        name="Family Traveler",
        core_question="Which day should we travel?",
        data_needs={
            "time_range": "week",
            "granularity": "daily",
            "hours": list(range(6, 22)),
            "features": ["daily_congestion_level", "holiday_impact", "best_travel_day"],
        },
    ),

    # ... 其他画像
}
```

### Orchestrator 如何使用

```python
# orchestrator.py

def _create_agent_tasks(self, parsed, request):
    """根据画像决定调用哪些 Agent"""

    tasks = {}
    persona = parsed.persona_type

    # Forecast Agent - 几乎都需要
    tasks["forecast"] = self.forecast_agent.process(request)

    # Context Agent - 需要离线因素
    if persona in [PersonaType.FAMILY_TRAVELER, PersonaType.OPERATOR]:
        tasks["context"] = self.context_agent.process(request)

    # Search Agent - 需要实时信息
    if persona in [PersonaType.LOGISTICS, PersonaType.OPERATOR]:
        tasks["search"] = self.search_agent.process(request)

    return tasks
```

---

## 7. LLM Prompt 设计

### System Prompt

```python
SYSTEM_PROMPT = """你是 AlpineFlow 交通助手的意图解析器。

你的任务是理解用户的自然语言输入，识别：

1. **persona** (用户画像) - 最重要！决定了用户需要什么样的帮助：

   - commuter: 日常通勤者
     特征: 每天开车上下班，关心"能否准时到达"
     关键词: "上班"、"下班"、"通勤"、"每天"

   - traveler: 家庭旅行者
     特征: 周末/假期出游，关心"哪天出行最好"
     关键词: "带家人"、"周末出游"、"度假"、"旅行"

   - logistics: 物流司机
     特征: 货运/快递，关心"哪里会延误"
     关键词: "送货"、"运输"、"货车"、"物流"

   - tourist: 游客
     特征: 不熟悉德国交通，需要"简单直接的建议"
     关键词: "第一次来"、"不熟悉"、"游客"

   - operator: 交通管理者
     特征: 交警/管理机构，关心"为什么会拥堵"
     关键词: "管理"、"监控"、"交警"、"为什么堵"

2. **date**: 目标日期 (YYYY-MM-DD 格式)
   - "今天" → 今天日期
   - "明天" → 明天日期
   - "周六" → 最近的周六
   - 没提到 → null

3. **destination**: 目的地
   - salzburg: 萨尔茨堡、奥地利
   - innsbruck: 因斯布鲁克、滑雪、阿尔卑斯
   - 没提到 → null

4. **road**: 高速公路
   - A8: 慕尼黑-萨尔茨堡 (默认)
   - A93: 慕尼黑-因斯布鲁克

5. **intent**: 具体意图
   - plan: 规划出行、询问最佳时间
   - forecast: 查看预测、路况
   - construction: 施工信息
   - events: 活动信息
   - general: 一般问题

返回 JSON 格式，不要包含其他文本。"""
```

### User Prompt 模板

```python
def build_user_prompt(query: str, today: datetime) -> str:
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday = weekday_names[today.weekday()]

    return f"""今天是 {today.strftime("%Y-%m-%d")} ({weekday})

用户输入: "{query}"

请分析并返回 JSON:
{{
    "persona": "commuter|traveler|logistics|tourist|operator",
    "date": "YYYY-MM-DD 或 null",
    "destination": "salzburg|innsbruck|null",
    "road": "A8|A93",
    "intent": "plan|forecast|construction|events|general"
}}"""
```

### LLM 调用示例

```python
async def _parse_with_llm(self, query: str, llm_client) -> ParsedIntent:
    today = datetime.now()

    prompt = build_user_prompt(query, today)
    result = await llm_client.generate_json(prompt, SYSTEM_PROMPT)

    # 解析结果
    persona_type = self._str_to_persona(result.get("persona", "tourist"))
    persona = get_persona(persona_type)

    return ParsedIntent(
        persona_type=persona_type,
        core_question=persona.core_question,
        date=result.get("date") or today.strftime("%Y-%m-%d"),
        destination=result.get("destination"),
        road=result.get("road", "A8"),
        intent=result.get("intent", "general"),
        data_requirements=self._build_data_requirements(persona),
    )
```

---

## 8. Fallback 机制

### 为什么需要 Fallback？

- LLM API 可能超时或失败
- API Key 可能未配置
- 需要保证系统可用性

### Fallback 实现

```python
class IntentParser:

    async def parse_async(self, query: str, default_user_type=None) -> ParsedIntent:
        """异步解析，优先使用 LLM"""

        if self.use_llm:
            llm_client = self._get_llm_client()
            if llm_client:
                try:
                    return await self._parse_with_llm(query, llm_client)
                except Exception as e:
                    print(f"LLM failed: {e}, falling back to keyword matching")

        # Fallback: 使用关键词匹配
        return self.parse(query, default_user_type)

    def parse(self, query: str, default_user_type=None) -> ParsedIntent:
        """同步解析，使用关键词匹配"""

        query_lower = query.lower()

        # 识别 persona
        persona_type = self._parse_persona(query_lower)

        # 解析日期
        date = self._parse_date(query)

        # 解析目的地
        destination = self._parse_destination(query_lower)

        # ... 其他解析

        return ParsedIntent(...)
```

### 关键词匹配规则

```python
PERSONA_KEYWORDS = {
    PersonaType.COMMUTER: [
        "上班", "下班", "通勤", "每天", "工作日",
        "commute", "daily", "work"
    ],
    PersonaType.FAMILY_TRAVELER: [
        "带家人", "带孩子", "周末出游", "度假", "旅行",
        "family", "vacation", "trip"
    ],
    PersonaType.LOGISTICS: [
        "送货", "运输", "货车", "物流", "配送", "快递",
        "truck", "delivery", "logistics"
    ],
    PersonaType.TOURIST: [
        "第一次", "不熟悉", "游客", "旅游",
        "tourist", "visit", "new to"
    ],
    PersonaType.OPERATOR: [
        "管理", "监控", "交警", "为什么堵", "原因", "分析",
        "operator", "manage", "why"
    ],
}

def _parse_persona(self, query: str) -> PersonaType:
    """使用关键词匹配识别 Persona"""
    for persona, keywords in PERSONA_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            return persona
    return PersonaType.TOURIST  # 默认当游客
```

---

## 9. 代码示例

### 基础使用

```python
from agent.agents import IntentParser
import asyncio

parser = IntentParser(use_llm=True)

async def main():
    # 通勤者 - 今天
    result = await parser.parse_async("今天下班几点走最好")
    print(f"Persona: {result.persona_type}")           # COMMUTER
    print(f"Core Question: {result.core_question}")    # Can I arrive on time?
    print(f"Time Range: {result.time_range.type}")     # TODAY
    print(f"Duration: {result.time_range.duration_days} days")  # 1
    print(f"Granularity: {result.data_requirements.granularity}")  # HOURLY

    # 家庭旅行者 - 暑假（长时间范围）
    result = await parser.parse_async("暑假去奥地利，什么时候出发不堵")
    print(f"Persona: {result.persona_type}")           # FAMILY_TRAVELER
    print(f"Time Range: {result.time_range.type}")     # SUMMER
    print(f"Start: {result.time_range.start_date}")    # 2026-07-01
    print(f"End: {result.time_range.end_date}")        # 2026-08-31
    print(f"Duration: {result.time_range.duration_days} days")  # 62
    print(f"Granularity: {result.data_requirements.granularity}")  # WEEKLY

    # 物流司机
    result = await parser.parse_async("送货去奥地利，哪段路会堵")
    print(f"Persona: {result.persona_type}")           # LOGISTICS
    print(f"Granularity: {result.data_requirements.granularity}")  # segment

asyncio.run(main())
```

### 与 Orchestrator 集成

```python
from agent import Orchestrator

async def main():
    orchestrator = Orchestrator()

    # 短时间范围 - 通勤者
    result = await orchestrator.process("我每天开车上班，今天几点走好")
    print(f"识别画像: {result['persona']['type']}")
    print(f"时间范围: {result['time_range']['type']}")  # today
    print(f"粒度: {result['time_range']['granularity']}")  # hourly
    print(f"建议:\n{result['advice']}")

    # 长时间范围 - 暑假规划
    result = await orchestrator.process("暑假去奥地利，什么时候出发不堵")
    print(f"识别画像: {result['persona']['type']}")  # traveler
    print(f"时间范围: {result['time_range']['type']}")  # summer
    print(f"时间跨度: {result['time_range']['duration_days']} 天")  # 62
    print(f"粒度: {result['time_range']['granularity']}")  # weekly
    print(f"建议:\n{result['advice']}")  # 周级窗口推荐

asyncio.run(main())
```

### 输出示例 - 短时间范围

```
识别画像: commuter
时间范围: today
粒度: hourly
建议:
### 🚗 今日通勤建议

**最佳出发时间**: 16:30
**避开时段**: 17:00-18:30

预计节省 **~25 分钟**
```

### 输出示例 - 长时间范围

```
识别画像: traveler
时间范围: summer
时间跨度: 62 天
粒度: weekly
建议:
### 📅 暑假出行推荐

| 时段 | 拥堵风险 | 原因 |
|------|----------|------|
| 7月上旬 | 🟠 medium | 夏季旅游高峰 |
| 7月中旬 | 🔴 high | 周末高峰 |
| 8月下旬 | 🟢 low | - |

✅ **推荐时段**: 8月下旬
⚠️ **建议避开**: 7月中旬, 7月下旬
```

---

## 总结

### 核心流程

```
用户输入: "暑假去奥地利"
    │
    ▼
┌─────────────────┐
│  LLM 语义理解    │  ← 识别用户画像 + 时间范围
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  解析时间范围    │  ← "暑假" → 7月1日-8月31日 (62天)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  确定数据粒度    │  ← 62天 → WEEKLY
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  构建 ParsedIntent │  ← 完整的意图解析结果
└─────────────────┘
    │
    ▼
Orchestrator 根据画像+时间范围调度 Agent
    │
    ▼
GenerationAgent 根据时间长度选择输出格式
    │
    ├── 1天 → 小时级建议
    ├── 2-14天 → 日历视图
    └── 14+天 → 周窗口推荐
```

### 设计原则

1. **用户画像驱动**: 先识别用户是谁，再决定给什么
2. **时间范围智能识别**: 支持模糊时间表达（暑假、圣诞节等）
3. **粒度自动调整**: 根据时间跨度自动选择 HOURLY/DAILY/WEEKLY/MONTHLY
4. **数据需求明确**: 不同画像需要不同粒度的数据
5. **智能调度**: 只调用必要的 Agent，提高效率
6. **输出格式自适应**: 短/中/长时间范围使用不同输出格式
7. **Fallback 保障**: LLM 失败时回退到关键词匹配
