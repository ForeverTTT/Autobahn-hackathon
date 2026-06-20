# AlpineFlow AI Agent 层架构说明

`agent/` 是 AlpineFlow AI 的智能体层，负责把已经生成好的交通预测数据、站点信息、天气/施工等外部因素，组织成可以被前端、API、LLM 调用的个性化出行助手服务。

这一层的定位不是重新训练模型，而是把「预测结果」转化为「可解释、可查询、可规划」的交通决策服务，并针对不同用户类型生成个性化建议。

---

## 1. 总体架构

当前 Agent 层由四个专职 Agent 加一个底层 GraphRAG 能力组成：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         用户自然语言询问                                  │
│            "我周六想从慕尼黑去萨尔茨堡，什么时候出发最好？"                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      IntentParser (意图解析)                             │
│                                                                         │
│   根据用户类型分类，识别用户需求：                                         │
│   👨‍👩‍👧 Traveler  → 最佳出发时间、舒适体验                                  │
│   🏠 Resident   → 避开本地交通影响                                       │
│   🚚 Logistics  → 优化运输时间、降低延误                                  │
│   🏨 Tourism    → 预测游客高峰、调整运营                                  │
│   🚦 Authority  → 交通管理措施、公众建议                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  ForecastAgent  │       │  ContextAgent   │       │   SearchAgent   │
│   (预测Agent)    │       │  (上下文Agent)  │       │   (搜索Agent)   │
│                 │       │                 │       │                 │
│ 读取预测数据：   │       │ 查询外部因素：   │       │ 实时搜索：       │
│ - kfz_h P10/50/90│      │ - 天气、气温     │       │ - 天气预报(15天) │
│ - v_kfz 车速    │       │ - 假期、学校假期 │       │ - 政府施工公告   │
│ - sv_h 重车流量 │       │ - 历史交通参考   │       │ - 活动信息       │
│ - 拥堵分数计算  │       │ - 季节性因素     │       │ - 事故/封路信息  │
└─────────────────┘       └─────────────────┘       └─────────────────┘
        │                           │                           │
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                          ⬇️ 三个Agent并行执行，结果汇总
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      GenerationAgent (响应生成)                          │
│                                                                         │
│   生成自然语言回复：                                                      │
│   ✅ 多个可对比的出行方案（不同出发时间）                                  │
│   ✅ 个性化建议（根据用户类型）                                           │
│   ✅ 出行压力指数                                                        │
│   ✅ 注意事项和预警                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            用户回复                                      │
│                                                                         │
│   "建议您周六 08:00 出发，预计 09:35 到达萨尔茨堡。                        │
│    出行压力指数: 3/10 (较轻松)                                           │
│                                                                         │
│    ⚠️ 注意事项:                                                         │
│    - A8 Rosenheim 附近有桥梁施工，预计延误 10-15 分钟                     │
│    - 萨尔茨堡音乐节期间，下午返程可能拥堵                                  │
│                                                                         │
│    📋 方案对比:                                                          │
│    | 出发  | 到达  | 时长  | 压力 |                                      │
│    | 06:00 | 07:26 | 86分钟 | 1/10 |                                     │
│    | 08:00 | 09:35 | 95分钟 | 3/10 | ← 推荐                              │
│    | 10:00 | 11:45 | 105分钟| 5/10 |"                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 预测数据文件说明

### 文件位置

```
data_autobahn/forecast_2026_2029.csv
```

### 文件内容

该文件包含 CatBoost 模型生成的 **2026-2029 年** 交通流量预测数据：

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 日期 YYYY-MM-DD |
| `hour` | int | 小时 0-23 |
| `site_id` | string | 站点ID，如 `A8_Mch_MQB25_Mch_H` |
| `road` | string | 高速公路 A8 / A93 |
| `direction` | string | 方向 Mch(慕尼黑) / Sbg(萨尔茨堡) / Ro / Kff |
| `kfz_h_p10` | float | 流量预测 P10 (低估计) |
| `kfz_h_p50` | float | 流量预测 P50 (中位数预测) |
| `kfz_h_p90` | float | 流量预测 P90 (高估计) |
| `sv_h_pred` | float | 重型车流量预测 |
| `v_kfz_pred` | float | 平均车速预测 (km/h) |
| `tagestyp` | string | 日类型: w(工作日) / s(周末) / u(假日) |
| `is_holiday` | bool | 是否公共假期 |
| `is_school_holiday` | bool | 是否学校假期 |

### 示例数据

```csv
date,hour,site_id,road,direction,kfz_h_p10,kfz_h_p50,kfz_h_p90,sv_h_pred,v_kfz_pred,tagestyp,is_holiday,is_school_holiday
2026-07-15,8,A8_Mch_MQB25_Mch_H,A8,Mch,1342,1789,2415,180,88.2,w,false,true
2026-07-15,9,A8_Mch_MQB25_Mch_H,A8,Mch,1456,1926,2587,195,82.5,w,false,true
```

### 数据量

- **时间范围**: 2026-01-01 至 2029-12-31 (4年)
- **站点数**: 6 个主要测量站点，3 个a8

### 数据加载方式

采用**渐进式加载**，不一次性读取全部数据：

```python
# 只加载查询日期的数据
loader.query("2026-07-15", road="A8", hours=[8, 9, 10])

# LRU 缓存最近 7 天数据
```

---

## 3. Agent 详细说明

### 3.1 IntentParser (意图解析)

**位置**: `chat_assistant.py` / `orchestrator.py`

**职责**: 根据用户类型分类，识别用户需求

| 用户类型 | 关键词 | 优先关注 |
|----------|--------|----------|
| 👨‍👩‍👧 Traveler | 旅游、度假、出游 | 最佳出发时间、舒适体验 |
| 🏠 Resident | 居民、通勤、上班 | 避开高峰、快速通行 |
| 🚚 Logistics | 物流、货运、送货 | 准时送达、避免延误 |
| 🏨 Tourism | 酒店、餐厅、游客接待 | 客流高峰预测 |
| 🚦 Authority | 交通管理、警察 | 拥堵预警、资源调度 |

**解析内容**:
- 用户类型
- 目的地 (萨尔茨堡 / 因斯布鲁克)
- 出行日期 (今天 / 明天 / 周六 / 7月25日)
- 查询意图 (出行计划 / 交通预测 / 施工查询)

---

### 3.2 ForecastAgent (预测Agent)

**位置**: `agents/forecast_agent.py`

**职责**: 读取预测数据，计算拥堵分数

**数据来源**: `data_autobahn/forecast_2026_2029.csv`

**输出内容**:
- 每小时流量预测 (P10 / P50 / P90)
- 平均车速
- 重型车比例
- **拥堵分数** (0-100，综合流量、车速、容量、外部因素)
- **拥堵等级** (smooth / light / moderate / heavy / critical)
- 峰值小时
- 日度汇总

**拥堵分数计算**:

```
拥堵分数 = 流量因子(25%) + 速度因子(30%) + 容量因子(25%) + 外部因子(20%)
```

---

### 3.3 ContextAgent (上下文Agent)

**位置**: `agents/explanation_agent.py` (原 ExplanationAgent)

**职责**: 查询 `data_autobahn` 中解释拥堵的外部原因

**重要**: 与 ForecastAgent 查询**同一时间段**的数据

**数据来源**:
- `data_autobahn/合并表格，weather日级.csv` - 天气、气温
- `data_autobahn/合并表格，holiday日级.csv` - 公共假期
- `data_autobahn/合并表格，special_events日级.csv` - 特殊活动
- `data_autobahn/合并表格，小时交通流量.csv` - 历史交通参考

**输出内容**:
| 因素类型 | 示例 | 影响 |
|----------|------|------|
| 天气 | 大雨、降雪 | 限速、能见度降低 |
| 气温 | 高温 > 35°C | 事故风险增加 |
| 假期 | 圣诞节、复活节 | 流量激增 |
| 学校假期 | 暑假 | 家庭出游增多 |
| 周末效应 | 周五下午、周日傍晚 | 出城/返城高峰 |
| 季节 | 夏季旅游季、冬季滑雪季 | 通往阿尔卑斯交通增加 |
| 历史参考 | 去年同期 | 参考历史拥堵模式 |

---

### 3.4 SearchAgent (搜索Agent)

**位置**: `agents/retrieval_agent.py` (原 RetrievalAgent)

**职责**: 实时搜索更新数据

**重要**: 获取无法预先存储的实时信息

**数据来源**:
| 数据类型 | 来源 | 时效性 |
|----------|------|--------|
| 天气预报 | 天气 API | 未来 15 天 |
| 施工公告 | Autobahn API | 实时 |
| 活动信息 | 活动日历 API | 实时 |
| 事故信息 | 交通信息 API | 实时 |

**Autobahn API 示例**:
```
https://autobahn.api.bund.dev/
```

**输出内容**:
- 施工信息 (位置、影响、绕行建议)
- 活动信息 (萨尔茨堡音乐节、慕尼黑啤酒节)
- 天气预报 (降雨、降雪预警)
- 临时封路/事故

---

### 3.5 GenerationAgent (响应生成)

**位置**: `agents/generation_agent.py`

**职责**: 汇总所有信息，生成自然语言回复

**输入**: ForecastAgent + ContextAgent + SearchAgent 的结构化结果

**输出格式**:

```markdown
## 🚗 慕尼黑 → 萨尔茨堡
**日期**: 2026-07-25 (周六)
**用户类型**: 👨‍👩‍👧 Traveler

### ✨ 推荐出行方案
- **出发时间**: 08:00
- **预计到达**: 09:35
- **预计行程**: 95 分钟 (延误约 15 分钟)
- **出行压力指数**: 🟢🟢🟢🟢🟢🟢🟢🔴🔴🔴 (3/10)

### ⚠️ 注意事项
- 🚧 A8 桥梁翻新工程: 右车道封闭，预计延误 10-15 分钟
- 🎭 萨尔茨堡音乐节: 下午返程可能拥堵

### 📋 方案对比
| 出发 | 到达 | 时长 | 压力指数 | 推荐 |
|------|------|------|----------|------|
| 06:00 | 07:26 | 86分钟 | 1/10 | ✅ 最佳 |
| 08:00 | 09:35 | 95分钟 | 3/10 | 👍 推荐 |
| 10:00 | 11:45 | 105分钟 | 5/10 | ⚠️ 一般 |

### 💡 个性化建议
- 建议携带足够的水和零食
- 可在 Chiemsee 服务区休息，欣赏湖景
- 今日路况良好，旅途愉快！
```

---

## 4. 工作流说明

### 核心流程

```
用户询问: "周六去萨尔茨堡，什么时候出发好？"
                        │
                        ▼
              ┌─────────────────┐
              │  IntentParser   │  解析用户类型 + 提取参数
              │                 │  (Traveler, 2026-07-25, 萨尔茨堡)
              └─────────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
┌─────────┐       ┌─────────┐       ┌─────────┐
│Forecast │       │ Context │       │ Search  │
│ Agent   │       │  Agent  │       │  Agent  │
│         │       │         │       │         │
│预测数据  │       │外部因素  │       │实时搜索  │
│07-25    │       │07-25    │       │施工/天气 │
└─────────┘       └─────────┘       └─────────┘
    │                   │                   │
    │         ⬇️ 并行执行，同时返回           │
    └───────────────────┼───────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │GenerationAgent  │  汇总结果 → 自然语言
              │                 │  + 方案对比 + 个性化建议
              └─────────────────┘
                        │
                        ▼
              用户收到回复
```

### 关键点

1. **三个 Agent 并行执行**
   - ForecastAgent、ContextAgent、SearchAgent 同时运行
   - 查询同一时间段的数据 (如 2026-07-25)
   - 结果同时返回给 GenerationAgent

2. **数据来源分工**
   - ForecastAgent: 读取 `forecast_2026_2029.csv` (离线预测)
   - ContextAgent: 读取 `data_autobahn` 日级条件数据 (离线)
   - SearchAgent: 调用实时 API (天气预报、施工公告)

3. **GenerationAgent 汇总生成**
   - 整合三个 Agent 的结果
   - 生成至少 3 个可对比的出行方案
   - 根据用户类型生成个性化建议

---

## 5. 多轮对话 (ChatSession)

### 支持的追问类型

| 类型 | 关键词 | 示例 | 处理方式 |
|------|--------|------|----------|
| 追问原因 | 为什么、原因 | "为什么推荐这个时间" | 读取保存的数据，生成解释 |
| 修改计划 | 改成、换成 | "改成周日呢" | 重新查询，对比建议 |
| 假设问题 | 如果、假如 | "如果下午2点出发呢" | 分析特定时间的数据 |
| 询问细节 | 天气、返程 | "那天天气怎么样" | 从保存的因素中提取 |
| 确认 | 好的、可以 | "好的" | 结束对话 |

### 会话上下文

```python
@dataclass
class SessionContext:
    # 解析结果
    parsed_intent: ParsedIntent      # 用户意图、目的地、日期等

    # 原始数据 (用于解释原因)
    forecast_data: Dict              # 各时段预测数据
    context_factors: List            # 影响因素 (节假日、天气等)
    search_factors: List             # 实时因素 (施工、事故等)

    # 生成的建议
    advice: str                      # 当前计划
```

### 多轮对话流程

```
用户: "周六去萨尔茨堡"
        │
        ▼
┌─────────────────┐
│  检测: 新查询    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  调用全部 Agent (Forecast/Context/Search) │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  保存到 Session  │  ← 保存预测数据、因素、建议
└────────┬────────┘
         │
         ▼
AI: "建议早上7点出发..."

═══════════════════════════════════════════

用户: "为什么"
        │
        ▼
┌─────────────────┐
│ 检测: 追问原因   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 读取 Session 数据│  ← 不重新调用 Agent
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LLM 生成解释     │  ← 用具体数据解释
└────────┬────────┘
         │
         ▼
AI: "因为7点流量只有1600辆/h，10点会增加到2800辆/h..."
```

---

## 6. 目录结构

```
agent/
├── __init__.py             # 模块入口，导出所有公共接口
├── orchestrator.py         # Agent 调度器 (chat, ask, get_plan)
├── session.py              # 多轮对话会话管理 (ChatSession)
├── models.py               # 数据模型定义
├── personas.py             # 用户画像定义
├── config.py               # 配置
│
├── agents/
│   ├── __init__.py
│   ├── intent_parser.py    # 意图解析Agent
│   ├── forecast_agent.py   # 预测Agent
│   ├── context_agent.py    # 上下文Agent
│   ├── search_agent.py     # 搜索Agent
│   ├── generation_agent.py # 响应生成Agent
│   └── prompt.py           # Prompt 模板
│
├── tools/
│   ├── __init__.py
│   ├── llm_client.py       # LLM 客户端
│   ├── prediction_loader.py # 预测数据加载
│   ├── context_loader.py   # 上下文数据加载
│   └── congestion.py       # 拥堵分数计算
│
├── test.ipynb              # 基础测试 Notebook
└── test_session.ipynb      # 多轮对话测试 Notebook
```

---

## 6. 使用方式

### 方式 1: 简单对话 (无状态)

```python
from agent import chat

# 单次问答
print(chat("周六去萨尔茨堡，什么时候出发好？"))
```

### 方式 2: 多轮对话 (推荐)

```python
from agent import ChatSession

session = ChatSession()

# 第一轮: 获取计划
print(session.chat("周六去萨尔茨堡"))

# 第二轮: 追问原因
print(session.chat("为什么"))  # AI 会用具体数据解释

# 第三轮: 修改计划
print(session.chat("改成周日呢"))  # AI 会对比周六周日

# 第四轮: 假设问题
print(session.chat("如果我只能下午2点出发呢"))

# 第五轮: 询问细节
print(session.chat("那天天气怎么样"))
```

### 方式 3: 全局会话 (最简便)

```python
from agent import chat_session, clear_session

# 直接对话，自动保存上下文
print(chat_session("周六去萨尔茨堡"))
print(chat_session("为什么"))  # 自动关联上一轮

# 开始新话题
clear_session()
print(chat_session("后天去因斯布鲁克"))
```

### 方式 4: 带调试信息

```python
from agent import ask

# verbose=True 显示 Agent 调度过程
print(ask("明天去萨尔茨堡", verbose=True))
```

### API 使用

```bash
# 启动服务
uvicorn agent.tools.api_app:create_app --factory --reload --port 8000

# 请求出行计划
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-07-25",
    "road": "A8",
    "user_type": "traveler"
  }'
```

### 直接调用 TravelAssistant

```python
from agent.travel_assistant import TravelAssistant, UserType

assistant = TravelAssistant()

# 生成完整计划
plan = assistant.generate_plan(
    route_id="munich_salzburg_a8",
    date="2026-07-25",
    user_type=UserType.TRAVELER
)

print(plan.personalized_advice)  # Markdown 格式
print(plan.options)              # 方案列表
print(plan.external_factors)     # 外部因素
```

---

## 7. 个性化建议示例

### 👨‍👩‍👧 Traveler (游客)

```
推荐 08:00 出发，旅途轻松愉快。
- 建议携带水和零食
- Chiemsee 服务区可休息观景
- 避开 16:00 后返程高峰
```

### 🚚 Logistics (物流)

```
推荐 06:00 前出发，避开早高峰。
- 注意大车限速路段
- Rosenheim 施工预计延误 15 分钟
- 预留额外时间确保准时送达
```

### 🚦 Authority (交通管理)

```
预计 16:00-18:00 为拥堵高峰。
- 🚨 建议增派警力/救援资源
- 考虑启动可变限速提示
- 关注 A8 km 85-90 施工路段
```

---

## 8. 扩展建议

### 接入真实 API

1. **天气 API**: OpenWeatherMap / DWD
2. **施工 API**: https://autobahn.api.bund.dev/
3. **活动 API**: 本地活动日历

### 增加新用户类型

在 `travel_assistant.py` 中的 `USER_PROFILES` 添加：

```python
UserType.COMMUTER: UserProfile(
    user_type=UserType.COMMUTER,
    priorities=["避开高峰", "最短时间"],
    recommendation_style="帮助日常通勤更高效"
)
```

### 增加新路线

在 `travel_assistant.py` 中的 `ROUTES` 添加：

```python
"munich_garmisch": Route(
    name="慕尼黑 → 加米施",
    origin="München",
    destination="Garmisch-Partenkirchen",
    segments=[...],
    total_distance_km=90,
    free_flow_time_min=60
)
```
