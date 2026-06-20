"""
用户画像定义
不同用户需要的不是"预测堵车"，而是"基于预测做更好的决定"
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class PersonaType(str, Enum):
    """用户类型"""
    COMMUTER = "commuter"           # 日常通勤者
    FAMILY_TRAVELER = "traveler"    # 家庭旅行用户
    LOGISTICS = "logistics"         # 物流司机
    TOURIST = "tourist"             # 游客
    OPERATOR = "operator"           # 交通管理者


@dataclass
class PersonaProfile:
    """用户画像"""
    type: PersonaType
    emoji: str
    name: str
    name_zh: str

    # 核心问题
    core_question: str
    core_question_zh: str

    # 用户关注点
    concerns: List[str]

    # 需要的数据类型
    data_needs: Dict[str, Any]

    # 输出风格
    output_style: str

    # 示例回答模板
    example_response: str


# ============ 用户画像定义 ============

PERSONAS: Dict[PersonaType, PersonaProfile] = {

    # 1. Daily Commuter - 日常通勤者
    PersonaType.COMMUTER: PersonaProfile(
        type=PersonaType.COMMUTER,
        emoji="🚗",
        name="Daily Commuter",
        name_zh="日常通勤者",

        core_question="Can I arrive on time?",
        core_question_zh="我能准时到达吗？",

        concerns=[
            "今天几点开始堵？",
            "什么时候出发最好？",
            "哪个时间段风险最高？",
        ],

        data_needs={
            "time_range": "today",           # 只需要今天
            "granularity": "hourly",         # 小时级预测
            "hours": list(range(6, 10)) + list(range(16, 20)),  # 早晚高峰
            "features": [
                "hourly_congestion",         # 小时拥堵预测
                "best_departure_time",       # 最佳出发时间
                "peak_hour_warning",         # 高峰时段警告
                "time_saved",                # 可节省时间
            ],
        },

        output_style="具体时间建议，量化节省时间",

        example_response="""
### 🚗 今日通勤建议

**最佳出发时间**: 16:30
**避开时段**: 17:00-18:30 (高峰)

预计节省 **~25 分钟**

⚠️ 17:15-18:00 为今日最拥堵时段
""",
    ),

    # 2. Family Traveler - 家庭旅行用户
    PersonaType.FAMILY_TRAVELER: PersonaProfile(
        type=PersonaType.FAMILY_TRAVELER,
        emoji="👨‍👩‍👧",
        name="Family Traveler",
        name_zh="家庭旅行用户",

        core_question="Which day should we travel?",
        core_question_zh="哪一天出行最好？",

        concerns=[
            "周五晚上还是周六早上走？",
            "假期第一天会不会爆堵？",
            "带孩子不想堵车几个小时",
        ],

        data_needs={
            "time_range": "week",            # 未来一周
            "granularity": "daily",          # 日级预测
            "hours": list(range(6, 22)),     # 全天
            "features": [
                "daily_congestion_level",    # 每日拥堵等级
                "holiday_impact",            # 假期影响
                "best_travel_day",           # 最佳出行日
                "congestion_reason",         # 拥堵原因解释
            ],
        },

        output_style="日历视图 + AI解释原因",

        example_response="""
### 📅 本周出行日历

| 日期 | 拥堵预测 | 原因 |
|------|----------|------|
| 周五 | 🔴 严重 | 假期首日 + 周末出行 |
| 周六 | 🟠 中等 | 上午较堵，下午好转 |
| 周日 | 🟢 畅通 | 最佳出行日 |

💡 **建议**: 周日上午出发，或周六 14:00 后出发

⚠️ 巴伐利亚学校假期明天开始，预计周五拥堵严重
""",
    ),

    # 3. Logistics Driver - 物流司机
    PersonaType.LOGISTICS: PersonaProfile(
        type=PersonaType.LOGISTICS,
        emoji="🚚",
        name="Logistics Driver",
        name_zh="物流司机",

        core_question="Where will delays happen?",
        core_question_zh="哪里会有延误？",

        concerns=[
            "哪一段高速容易堵",
            "会延误多久",
            "有没有瓶颈路段",
        ],

        data_needs={
            "time_range": "today",           # 今天
            "granularity": "segment",        # 路段级
            "hours": list(range(4, 14)),     # 早班配送时段
            "features": [
                "segment_prediction",        # 路段预测
                "bottleneck_detection",      # 瓶颈检测
                "delay_estimation",          # 延误估算
                "risk_warning",              # 风险提醒
            ],
        },

        output_style="路段地图 + 延误估算 + 原因",

        example_response="""
### 🚚 路段预测: A8 München → Salzburg

| 路段 | 状态 | 预计延误 | 原因 |
|------|------|----------|------|
| München Nord | 🟢 | +0 min | - |
| Rosenheim | 🟠 | +12 min | 重车流量大 |
| Salzburg 入口 | 🔴 | +25 min | 瓶颈路段 + 施工 |

**总延误估算**: +37 分钟
**建议出发时间**: 05:30 前
""",
    ),

    # 4. Tourist - 游客
    PersonaType.TOURIST: PersonaProfile(
        type=PersonaType.TOURIST,
        emoji="🧳",
        name="Tourist",
        name_zh="游客",

        core_question="Tell me what I should do.",
        core_question_zh="告诉我该怎么做",

        concerns=[
            "不懂德国交通",
            "不想看复杂数据",
            "只要简单明确的建议",
        ],

        data_needs={
            "time_range": "flexible",        # 灵活
            "granularity": "simple",         # 简化
            "hours": list(range(7, 20)),     # 白天
            "features": [
                "simple_recommendation",     # 简单建议
                "natural_language",          # 自然语言
                "actionable_advice",         # 可执行建议
            ],
        },

        output_style="简单直接，像朋友建议",

        example_response="""
### 🧳 驾驶建议

**周六上午去萨尔茨堡？**

由于假期交通，周六上午拥堵风险较高。

✅ **建议**: 7:30 前出发，可以避开大部分车流

🚗 预计行程: 1.5 小时（正常 1 小时 20 分钟）
""",
    ),

    # 5. Traffic Operator - 交通管理者
    PersonaType.OPERATOR: PersonaProfile(
        type=PersonaType.OPERATOR,
        emoji="🏢",
        name="Traffic Operator",
        name_zh="交通管理者",

        core_question="Why will congestion happen?",
        core_question_zh="为什么会拥堵？",

        concerns=[
            "不是简单预测堵",
            "而是理解原因",
            "提前制定管理措施",
        ],

        data_needs={
            "time_range": "week",            # 未来一周
            "granularity": "detailed",       # 详细
            "hours": list(range(0, 24)),     # 全天
            "features": [
                "explainable_prediction",    # 可解释预测
                "factor_contribution",       # 因素贡献
                "trend_analysis",            # 趋势分析
                "risk_assessment",           # 风险评估
            ],
        },

        output_style="可解释AI + 因素分析 + 管理建议",

        example_response="""
### 🏢 拥堵分析报告

**预测日期**: 2026-07-25 (周六)
**预测路段**: A8 München-Salzburg
**预测等级**: 🔴 严重拥堵

#### 影响因素贡献

```
假期效应        ████████████████░░░░  +35%
周末效应        ██████████░░░░░░░░░░  +25%
历史模式        ████████████░░░░░░░░  +30%
天气因素        ████░░░░░░░░░░░░░░░░  +10%
```

#### 建议措施

1. 考虑启动可变限速
2. 增派巡逻力量至 Rosenheim 路段
3. 提前发布公众出行建议
""",
    ),
}


# ============ 辅助函数 ============

def get_persona(persona_type: PersonaType) -> PersonaProfile:
    """获取用户画像"""
    return PERSONAS.get(persona_type, PERSONAS[PersonaType.TOURIST])


def get_data_needs(persona_type: PersonaType) -> Dict[str, Any]:
    """获取用户数据需求"""
    persona = get_persona(persona_type)
    return persona.data_needs


def get_required_features(persona_type: PersonaType) -> List[str]:
    """获取用户需要的功能"""
    persona = get_persona(persona_type)
    return persona.data_needs.get("features", [])


# 旧 UserType 到新 PersonaType 的映射
USER_TYPE_TO_PERSONA = {
    "traveler": PersonaType.FAMILY_TRAVELER,
    "resident": PersonaType.COMMUTER,
    "logistics": PersonaType.LOGISTICS,
    "tourism": PersonaType.TOURIST,
    "authority": PersonaType.OPERATOR,
}
