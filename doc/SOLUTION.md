# 混合专家-AI 交通预测系统

### TFT-Enhanced Holiday-Aware Explainable Traffic Forecasting for A8 East & A93 South

> TUM Hackathon Challenge · Host: Die Autobahn GmbH des Bundes
> 目标：把当前依赖人工专家判断的"交通日历 (Fahrkalender)"，转变为可扩展、数据驱动、可解释的自动化预测系统，覆盖 **A8 East / A93 South 双方向，2026–2029 全部日期**，输出每日车流量、绿→深红颜色等级、置信度与人类可读解释。

---

## 目录

1. [项目定位与核心思想](#1-项目定位与核心思想)
2. [整体系统架构](#2-整体系统架构)
3. [数据层：数据来源与组织](#3-数据层数据来源与组织)
4. [数据处理流程（重点）](#4-数据处理流程重点)
5. [特征工程层（重点）](#5-特征工程层重点)
6. [模型层设计（重点）](#6-模型层设计重点)
7. [融合与校准层](#7-融合与校准层)
8. [输出生成层](#8-输出生成层)
9. [不确定性量化与可信度（重点 · Confidence as a First-Class Output）](#9-不确定性量化与可信度重点--confidence-as-a-first-class-output)
10. [可解释性体系（重点）](#10-可解释性体系重点)
11. [智能体系统（重点 · Agentic Layer：Explainer / Planner / RAG）](#11-智能体系统重点--agentic-layerexplainer--planner--rag)
12. [用户界面层](#12-用户界面层)
13. [评估指标](#13-评估指标)
14. [Hackathon 落地优先级与排期](#14-hackathon-落地优先级与排期)
15. [技术栈与项目结构](#15-技术栈与项目结构)
16. [Pitch 话术与用户价值映射](#16-pitch-话术与用户价值映射)
17. [风险与取舍说明](#17-风险与取舍说明)

---

## 1. 项目定位与核心思想

这不是一个普通的时间序列预测任务，而是一个 **长达 4 年、纯靠"提前可知的日历/假期特征"的条件回归 + 情景预测** 任务。

> **关键约束**：预测 2029 年某天时，我们手里没有那天的实测车流量序列，也没有真实天气。模型输入只能依赖**确定性可提前知道的特征**（星期、月份、各国学校假期、公共假期、桥接日、假期首尾日、已知限流/Dosierung 日）。天气只能以**气候态/情景**方式参与，不能作为硬输入。

这个定性判断决定了整套系统的设计：**以稳健的表格模型为主力，以专家规则 + 相似历史日强化可解释性，以日历 UI 交付用户价值，TFT 作为时序探索性亮点。**

核心数据流：

```
历史交通数据
  + 日历 / 假期 / 天气(气候态) / 特殊事件
        ↓
多模型预测 (Similar-Day + GBDT + TFT)
        ↓
专家规则校正
        ↓
融合与校准
        ↓
颜色等级映射 (绿 → 深红)
        ↓
用户可读解释 + 置信度
        ↓
交互式交通日历 UI
```

设计三原则：

1. **可解释性 > 黑盒精度**：公共部门必须能向公众解释"为什么这天是深红"。
2. **诚实处理不可知性**：未来天气不可知 → 用气候态 + 情景，并把这一点透明展示，反而提升可信度。
3. **分层可交付**：核心层 / 加分层 / 炫技层，每层做完都能独立 demo，绝不"样样半成品"。

---

## 2. 整体系统架构

```
┌────────────────────────────────────────────────────┐
│                   Data Sources                       │
│  历史车流量 · 天气(气候态) · 学校假期 · 公共假日 · 事件 │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│              Data Processing Layer                    │
│  清洗 · 异常检测 · 缺失填补 · 日/小时双粒度聚合         │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│             Feature Engineering Layer                 │
│  日期 · 跨国假期 · 假期偏移(出发/返程波) · 天气 · 滞后   │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│            Multi-Model Forecasting Layer             │
│  A. Similar-Day Retrieval   (可解释历史证据)          │
│  B. CatBoost / LightGBM     (主力 · 分位数回归)       │
│  C. Temporal Fusion Transformer (时序探索亮点)        │
│  D. Expert Rule Layer       (领域知识 · 校正)         │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│           Ensemble & Calibration Layer               │
│         融合多模型 · 校准车流量 · 生成区间             │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│              Output Generation Layer                  │
│  车流量 · 颜色等级 · 高峰时段 · 置信度 · 解释          │
│        (落库为确定性 forecast store, 供工具查询)       │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│            Agentic Layer (4 agents, Tools + RAG)     │
│  ① Orchestrator/Trust-Guard  ② Retrieval(Tools+RAG)  │
│  ③ Explainer                 ④ Planner               │
│        (数字只来自工具, ① 号 agent 防幻觉)            │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│         User Surfaces: Calendar UI + Chat            │
│  月历(着色/峰值/视角切换) + 对话式解释 & 行程规划      │
└────────────────────────────────────────────────────┘
```

每个模块的职责一览：

| 模块 | 主要作用 | 输入 | 输出 | 优点 |
|---|---|---|---|---|
| Data Processing | 清洗/对齐/聚合 | 原始传感器数据 | daily/hourly 表 | 数据质量保障 |
| Feature Engineering | 构造预测特征 | 日期+假期+天气 | 特征矩阵 | 决定模型上限 |
| Similar-Day Retrieval | 找历史相似日 | 日期/假期/方向 | 相似日均值+参考日 | 极强可解释性 |
| CatBoost / LightGBM | 主力表格预测 | 全特征 | 每日车流量 P10/P50/P90 | 稳健+SHAP |
| TFT | 时序趋势预测 | 历史序列+已知未来 | 多步车流量 | 捕捉连续出发/返程潮 |
| Expert Rule Layer | 注入领域知识 | 假期/事件规则 | 风险修正+解释 | 贴近专家判断 |
| Ensemble | 融合预测 | 多模型结果 | 最终车流量 | 更稳健 |
| Threshold Mapping | 颜色等级 | 车流量+阈值 | 绿→深红 | 透明易解释 |
| Explanation Layer | 生成解释 | SHAP+规则+相似日 | 用户/专家解释 | 提升信任 |
| Agentic Layer | 对话解释+行程规划 | 用户提问+工具+RAG | 自然语言答复/方案 | 落地用户价值·防幻觉 |

---

## 3. 数据层：数据来源与组织

### 3.1 主数据：历史交通数据（Autobahn 提供）

预期字段（按实际数据调整）：

```
road          道路 (A8 East / A93 South)
direction     方向 (outbound 去阿尔卑斯 / inbound 返程)
date          日期
time / hour   时间(若为小时级)
traffic_volume / vehicle_count   车流量 / 车辆计数
sensor_id     传感器/计数站编号(可选)
```

统一成两个标准粒度表：

```
# 日级 (核心建模粒度)
daily_volume:
  date, road, direction, daily_volume

# 小时级 (用于日内曲线; 若有小时数据则保留)
hourly_volume:
  date, hour, road, direction, hourly_volume
```

> **建议**：小时级数据务必保留。它是"日内高峰时段(早峰/晚峰)"输出的唯一可靠来源，也是颜色映射之外的第二大用户价值点。

### 3.2 外部辅助数据（鼓励使用）

| 类型 | 内容 | 推荐来源 |
|---|---|---|
| 学校假期 | 德国各州 + 奥地利/瑞士/荷兰/捷克/意大利 | `ferien-api.de`、OpenHolidays API |
| 公共假期 | 德国 + 邻国 | Nager.Date API、`feiertage-api.de` |
| 天气(气候态) | 气温/降水/降雪/能见度/风 | DWD 开放数据、Open-Meteo 历史归档 |
| 特殊事件 | 边境管制/Dosierung、大型活动、施工 | 手工整理 + Autobahn 提供 |

> **阿尔卑斯走廊关键洞察**：A8/A93 的峰值高度由"**德国南部 + 邻国假期叠加**"驱动（典型如巴伐利亚暑假 + 奥地利/荷兰假期重叠）。把跨国学校假期做细，是本方案最大的领域 insight。

---

## 4. 数据处理流程（重点）

数据质量直接决定模型上限。完整流程分 7 步：

### 4.1 数据加载与 schema 标准化

- 统一列名、日期格式 (`YYYY-MM-DD`)、时区。
- 标准化 `road` / `direction` 取值（建立枚举映射，避免 "A8 east"/"A8 East"/"A8-E" 混用）。
- 建立 `corridor_id = road + "_" + direction` 作为最细建模单元（共 4 个序列：A8E-out / A8E-in / A93S-out / A93S-in）。

### 4.2 缺失值处理

传感器数据常见缺失/掉线。分两类：

- **短缺口（≤2 天/几个小时）**：按"同 corridor、同 weekday、邻近日期"做时间插值或同类日均值填补。
- **长缺口（整段缺失）**：不强行插值，标记 `is_imputed=True`，并在该日的置信度上施加惩罚；建模时可对这些行降权或剔除。

### 4.3 异常值检测与修正

- **物理不可能值**：负数、超过物理容量上限 → 置为缺失再填补。
- **统计离群**：对每个 `corridor_id × weekday × month` 分组，用 IQR 或 robust z-score 检测离群点。
- **关键区分**：异常分两种——
  - **数据错误**（传感器故障）→ 修正/剔除；
  - **真实极端事件**（事故封路、超级假期日）→ **保留**，并尽量打上事件标签（这正是模型要学的高价值样本）。
- 处理策略：宁可保守保留真实峰值，避免把"真正的深红日"当噪声抹平。

### 4.4 粒度聚合与一致性校验

- 由 hourly 聚合出 daily，并校验 `sum(hourly) ≈ daily`（若两者都提供）。
- 为每个 `corridor_id × date_type` 计算**典型 24 小时占比曲线**（normalized hourly profile），供日内曲线模块使用。

### 4.5 外部数据对齐与合并

- 学校/公共假期：按 `date` + 相关地区展开为布尔列（详见特征工程）。
- 天气：历史按 `date` 合并真实值；**未来 2026–2029 用按 (corridor, day-of-year) 计算的气候态均值**填充，并保留"好天气/坏天气"两套情景值。
- 事件：按 `date` 标记，未知未来事件留空（并体现在置信度）。

### 4.6 训练/验证集划分（时间序列必须时序划分）

- **禁止随机划分**（会信息泄漏）。采用**按时间切分**：例如用最后一整年作为验证集（hold-out），模拟"预测未来"。
- 进阶：**滚动时间窗交叉验证**（rolling/expanding window），更贴近真实部署评估。
- 特别构造一个"**峰值日验证子集**"，单独看模型在历史深红日上的表现。

### 4.7 数据契约与可复现

- 所有处理步骤封装为可复现 pipeline（脚本/notebook），固定随机种子。
- 输出中间产物：`clean_daily.parquet`、`clean_hourly.parquet`、`features.parquet`，避免重复计算。

---

## 5. 特征工程层（重点）

**模型强不强，很大程度取决于特征设计。** 本任务的灵魂是 holiday-aware traffic forecasting，因此特征围绕"日历 + 跨国假期 + 出发/返程波"展开。

### 5.1 基础日期特征

```
year, month, day, day_of_year
week_of_year
day_of_week            # 0-6
is_weekend
is_friday, is_saturday, is_sunday
season                 # 冬/春/夏/秋
is_school_summer_period
```

周期性建议用 **sin/cos 编码**（`month`, `day_of_week`, `day_of_year`），让模型平滑捕捉季节性：

```
month_sin = sin(2π·month/12),  month_cos = cos(2π·month/12)
dow_sin   = sin(2π·dow/7),     dow_cos   = cos(2π·dow/7)
doy_sin   = sin(2π·doy/365),   doy_cos   = cos(2π·doy/365)
```

作用：捕捉周末出行、夏季/冬季/圣诞季节性、工作日 vs 休闲交通的区分。

### 5.2 道路与方向特征

```
road            # A8 East / A93 South
direction       # outbound / inbound
corridor_id     # 4 个单元
```

作用：A8 与 A93 规模不同；**出城/返程高峰不对称**——假期开始 outbound 更堵，假期结束 inbound 更堵。方向特征是建模这种不对称的关键。

### 5.3 假期特征（核心）

跨国、跨州展开为布尔/类别列：

```
# 德国相关州 (A8/A93 上游客源)
is_school_holiday_Bavaria
is_school_holiday_Baden_Wuerttemberg
# 邻国
is_school_holiday_Austria
is_school_holiday_Switzerland
is_school_holiday_Netherlands
is_school_holiday_Czechia
is_school_holiday_Italy

# 公共假期
is_public_holiday_DE
is_public_holiday_AT
is_public_holiday_CH

# 组合
is_long_weekend
is_bridge_day                 # 桥接日(假期与周末间的工作日)
holiday_overlap_count         # 当天有多少地区同时放假 (强驱动)
holiday_type                  # 暑假/圣诞/复活节/滑雪季/秋假...
```

> `holiday_overlap_count`（多地区假期叠加计数）是预测峰值的最强单一特征之一，务必构造。

### 5.4 假期偏移特征（最重要 · 决定峰值命中率）

比简单的 `is_holiday` 重要得多。真正的深红峰值往往出现在**假期的边缘日**，而非假期中间。

```
days_to_holiday_start         # 距假期开始还有几天
days_since_holiday_start
days_to_holiday_end
days_since_holiday_end

is_holiday_start_day
is_first_saturday_of_holiday  # 暑假第一个周六 = 经典出发峰
is_return_sunday              # 假期结束前的返程周日
is_departure_wave_day         # 出发潮日
is_return_wave_day            # 返程潮日
is_day_before_school_starts   # 开学前一天 = 返程峰
```

典型高峰日示例：
- 巴伐利亚暑假**第一个周六** → outbound 深红
- 圣诞假期结束前的**返程周日** → inbound 深红
- 长周末后的**返程日** → inbound 峰
- 滑雪季周末（冬季周五晚/周六早 outbound）

### 5.5 天气特征（气候态 / 情景）

```
temperature, rain_mm, snowfall, visibility, wind
weather_condition
is_good_travel_weather        # 好天气 → 休闲出行增加
is_heavy_snow                 # 雪天 → 拥堵风险↑、置信度↓
```

> 历史用真实天气；**未来用气候态均值**，并提供"好天气/坏天气"两条情景。把"我们诚实处理了天气不可知性"讲出来 = 可信度加分。

### 5.6 历史滞后与统计特征（主要供 GBDT / TFT observed inputs）

```
volume_lag_1, volume_lag_7, volume_lag_14, volume_lag_28
rolling_mean_7, rolling_mean_14, rolling_mean_28
rolling_std_7
same_weekday_last_year_volume
similar_holiday_last_year_volume
```

> **重要警告**：lag/rolling 特征在预测**远期未来（2027–2029）**时不可得。两种策略：
> 1. **主力 GBDT 用"无 lag 版本"**（纯日历+假期+气候态），保证 4 年全程可预测——这是推荐主路径；
> 2. lag 特征仅用于"短期回测/验证"或 TFT 的 observed inputs（配合递归预测，需注意误差累积）。
> 文档与 demo 中要把这个区分讲清楚，体现严谨性。

### 5.7 相似日检索特征（来自 Model A，作为可解释证据）

```
similar_day_mean_volume
similar_day_median_volume
similar_day_p90_volume
similar_day_count
similar_day_confidence
```

> 定位选择（避免信息重复）：**推荐把相似日作为"可解释历史证据"独立展示，不强行喂入 GBDT 再进 ensemble**，以免信息泄漏/重复计算。若时间充裕想做特征版本，则二选一。

---

## 6. 模型层设计（重点）

系统不是单一模型，而是 4 个模块协同。下面逐个说明。

### 6.1 Model A — Similar-Day Retrieval（相似历史日检索）

**本质**：一个 historical memory module，不是传统 ML 模型，而是"把专家经验数据化"。

**做法**：为目标日构造特征向量（weekday/season/holiday_type/holiday_offset/overlap/方向），在历史库中用距离度量（加权欧氏 / Gower 距离，对类别+数值混合）检索 Top-K 最相似日，统计其实际车流量分布。

**输入**：
```
target_date, road, direction, weekday, season,
holiday_type, holiday_offset, holiday_overlap_count, weather_type
```

**输出**：
```
similar_day_mean_volume, similar_day_median_volume,
similar_day_p90_volume, similar_day_count,
similar_day_confidence, top_similar_days(可追溯的真实日期列表)
```

**价值**：极强可解释性。一句话就能让评委/用户信服——
> "本预测参考了历史上 12 个相似的假期周六，这些日子平均车流量 86,500，P90 为 94,000。"

### 6.2 Model B — CatBoost / LightGBM 回归（主力模型）

**定位**：系统的稳健主力。表格特征（weekday/month/road/direction/holiday/weather/overlap）上梯度提升树近乎 SOTA，训练快、对类别和特征交互天然友好、可用 SHAP 解释。

**模型选择**：类别特征多 → **CatBoost**（原生类别处理）；追求速度/生态 → LightGBM。本方案默认 **CatBoost**。

**关键设计：分位数回归输出置信区间**。训练 3 个分位模型（或多分位）：
```
P10 模型 → 乐观下界
P50 模型 → 主预测 (中位数)
P90 模型 → 悲观上界
区间宽度 (P90 - P10) → 直接作为不确定性/置信度指标
```

**输入**：日期特征 + 道路方向 + 假期特征 + 假期偏移 + 天气(气候态) + 特殊事件 + (短期回测时)lag 特征。

**输出**：
```
gbdt_pred_p10, gbdt_pred_p50, gbdt_pred_p90
```

**负责**：表格非线性关系、假期/周末/天气组合效应、方向不对称、稳健日车流量预测、SHAP 解释。

### 6.3 Model C — Temporal Fusion Transformer（时序探索亮点）

**定位**：捕捉历史车流量序列中的时间依赖、季节趋势、连续出发潮/返程潮、跨年度重复模式。它与 GBDT 互补——GBDT 把每天当独立样本，TFT 学连续时间结构。

**三类输入**：
```
A. Static covariates (不随时间变化)
   road, direction, corridor_id, sensor_id
B. Time-varying KNOWN inputs (未来已知, 非常契合 2026–2029)
   date, weekday, month, is_weekend,
   school/public holiday flags, holiday offset,
   departure_wave / return_wave / long_weekend flags
C. Time-varying OBSERVED inputs (仅历史已知)
   historical_daily_volume, lag_1, lag_7,
   rolling_mean_7, rolling_mean_28
```

**输出**：`tft_pred`（支持多步预测；对 2026–2029 用滚动预测或完整未来日历特征多步预测）。

**适配理由**：交通现象有明显连续结构——周/年季节性、出发潮、返程潮、滑雪季、暑假走廊、圣诞出行潮。TFT 能学"是否正在形成出发潮 / 返程高峰是否临近 / 今年假期窗口是否类似往年"。

**可解释性**：Variable Selection（变量重要性）+ Temporal Attention（关注的历史时间点）。

> ⚠️ **务实警告（强烈建议遵守）**：在 hackathon 时间内，TFT 是**高风险低回报**——纯日历特征下大概率赢不过 CatBoost，且 observed inputs 在远期未来不可得（递归预测误差累积）。**因此把 TFT 放在"炫技层 / future work / 单独跑通的对照实验"，绝不放进主交付关键路径。** 由专人单独负责，跑通即作为"我们也探索了时序 SOTA"的亮点。

### 6.4 Model D — Expert Rule Layer（专家规则层）

**定位**：连接"人工专家经验"与"AI 预测"的桥梁，把交通领域知识显式编码——这正是 PDF "把专家判断转为可扩展系统"的直接回应。

**典型规则（5–8 条关键即可）**：
```
if is_first_saturday_of_bavaria_summer_holiday:
    outbound 风险 +1, volume 上调
if is_day_before_school_starts:
    inbound (返程) 风险 +1
if is_long_weekend_return_day:
    inbound 风险 +1
if holiday_overlap (AT & Bavaria):
    volume 上调
if is_border_control_dosierung_day:
    拥堵风险 +1
if is_heavy_snow_scenario:
    置信度 -10%
```

**输出**：
```
rule_adjustment_volume        # 例: +5,000 因巴伐利亚暑假开始
rule_adjustment_risk_level    # 例: +1 级 因假期首个周六
rule_triggered_explanations   # 文本解释列表
rule_confidence_modifier      # 例: -10% 因天气不确定
```

**价值**：让系统像真实交通管理系统，覆盖边境管制、假期开始、长周末返程、滑雪季周末、特殊事件等历史样本稀少、纯模型难学的情形。

---

## 7. 融合与校准层

把多模型结果合成最终预测。

### 7.1 输入
```
similar_day_pred, gbdt_pred (p50), tft_pred, rule_adjustment
```

### 7.2 推荐：简单加权 + 规则修正（hackathon 务实版）

```
final_volume = w1·gbdt_p50 + w2·tft_pred + w3·similar_day
               + rule_adjustment_volume
区间: final_p10 = gbdt_p10 + 调整,  final_p90 = gbdt_p90 + 调整
```

默认权重（以 GBDT 为主）：
```
gbdt 0.6, tft 0.2, similar_day 0.2   (TFT 未上线时: gbdt 0.75, similar_day 0.25)
```

> **取舍说明**：原方案的"按日类型动态切换权重"理论上更优，但 hackathon 内**无法充分验证权重是否真的更好**，手调权重反而显得不严谨。**默认用简单固定加权**；若有时间，可用验证集网格搜一组全局最优权重（比动态规则更可信）。

### 7.3 校准

- 对最终预测做**保序回归 / 简单线性校准**，对齐预测分布与历史实际分布。
- 分位数校准检查：验证集上 P10–P90 区间的实际覆盖率是否接近 80%。

---

## 8. 输出生成层

### 8.1 颜色等级映射（不单独训分类器）

按**每条路、每个方向**单独计算历史分位数阈值：

```
thresholds[corridor_id]:
  green:     < 40th percentile
  yellow:    40–60th
  orange:    60–75th
  red:       75–90th
  dark_red:  > 90th percentile
```

> 不单独训颜色分类模型——直接由车流量阈值映射，透明、可解释、可审计。除非主办方提供了大量含专家主观调整的历史颜色标签。

### 8.2 日内高峰时段模块

- **有小时数据**：训练/统计小时级模型，自动识别 `morning_peak / midday_peak / afternoon_peak / evening_peak`。
- **仅日级数据**：用**典型 pattern template**——先把日子分类（normal_weekday / holiday_departure_saturday / holiday_return_sunday / ski_weekend / summer_friday / christmas_departure），每类配一条典型 24h 分布曲线。
  ```
  holiday_departure_saturday → peak 06:00–11:00 outbound
  holiday_return_sunday      → peak 14:00–20:00 inbound
  ```
> hackathon 优先用 template（性价比高），有余力再训小时级模型。

### 8.3 置信度模块

综合多个信号给出 high/medium/low（实现概览，完整的不确定性量化与校准方法见 **第 9 章**）：

```
模型一致性:    多模型预测接近 → 高;  分歧大 → 低
相似日数量:    similar_day_count 高 → 高
历史方差:      该类日历史波动小 → 高
区间宽度:      P90-P10 窄 → 高
事件不确定性:  未知特殊事件 → 降低
天气不确定性:  极端天气情景 → 降低
```

### 8.4 每日最终输出格式

```
Date: 2026-08-01
Road: A8 East
Direction: outbound / toward Alps
Predicted volume: 92,300 vehicles/day  (P10 85,000 – P90 98,000)
Traffic category: Dark red
Peak window: 06:00–11:00
Confidence: High
Explanation (user):
  预计为深红色——这是巴伐利亚暑假开始后的第一个周六，
  且与奥地利假期重叠，历史相似日显示该方向交通量显著偏高。
  主要高峰预计在 06:00–11:00。
Technical explanation:
  - CatBoost (P50): 89,200
  - TFT: 91,000
  - Similar-day reference: 86,500 (12 days)
  - Expert rule adjustment: +3,000 (Bavaria summer start)
  - Final calibrated: 92,300
```

---

## 9. 不确定性量化与可信度（重点 · Confidence as a First-Class Output）

> 这是直接回应评分标准 **"Plausibility — Would I trust this forecast?"** 的核心章节。
> 我们把"置信度"当作**一等输出（first-class output）**，与车流量、颜色等级并列，而不是事后附加的装饰。每个预测都同时给出"**数值 + 区间 + 可信度等级 + 该区间为何可信的证据**"。

### 9.1 为什么置信度对本任务尤其重要

- 预测跨度长达 2026–2029，越往后不确定性越大；用户必须知道"哪些预测可信、哪些只是粗略参考"。
- 公共部门对外沟通需要**可辩护的把握度**——不能只给一个数字，要能说"我们有多大把握，以及为什么"。
- 不同用户对不确定性的反应不同：物流调度需要"高置信日"才敢排程；旅客只需大致趋势。置信度让同一份预测服务不同决策门槛。

### 9.2 三层互补的不确定性来源

我们的不确定性不是单一拍脑袋的数字，而是**三层互补、各自有出处**：

**第 1 层 — 模型内生预测区间（Quantile Regression）**
- CatBoost 训练 P10 / P50 / P90 分位模型，直接产出预测区间，如 `92,300 (P10 85,000 – P90 98,000)`。
- 区间宽度 `P90 − P10` 即量化不确定性：窄=确定，宽=不确定。
- 关键：这是**模型从数据中学到的**条件不确定性（假期边缘日天然比普通工作日区间更宽），不是事后加的常数。

**第 2 层 — 校准 / Conformal 保证（让区间"可信"而非只是"好看"）**
- 仅有区间不够，必须验证区间**名副其实**：在验证集上检查 **P10–P90 区间的实际覆盖率是否 ≈ 80%**。
- 若覆盖率偏离（如只有 60% → 模型过度自信），用以下方法校正：
  - **Split Conformal Prediction**：用校准集的残差分位数，给出有**有限样本覆盖保证**的区间（理论上保证覆盖率，简单且严谨，是本方案的杀手锏）。
  - 或保序回归（Isotonic）/ 温度缩放对分位数做后校准。
- 产出 **可靠性图（reliability diagram）**：横轴名义置信度、纵轴实际覆盖率，对角线 = 完美校准。这张图就是"Would I trust this forecast"的直接证明。

**第 3 层 — 综合可信度评级（给用户的 High / Medium / Low）**
- 把多种信号融合成一个直观等级，信号包括：

| 信号 | 高置信 | 低置信 |
|---|---|---|
| 区间宽度 (P90−P10) | 窄 | 宽 |
| 多模型一致性 | GBDT/TFT/相似日预测接近 | 分歧大 |
| 相似日数量 similar_day_count | 多（历史样本充足） | 少（罕见情形） |
| 同类日历史方差 | 小 | 大 |
| 预测时间跨度 | 近期 | 远期(2029) |
| 特殊事件 | 无未知事件 | 存在未知事件/Dosierung |
| 天气情景敏感性 | 好坏天气差异小 | 差异大(如滑雪季雪情) |

- 融合方式（hackathon 务实版）：把各信号归一化后加权打分 → 阈值切成 High/Medium/Low；规则层可对特定情形（未知事件、极端天气）直接下调一级。

### 9.3 置信度如何呈现给用户

- **数值层**：`预测 92,300 辆/日（P10 85,000 – P90 98,000）`。
- **等级层**：日历单元角标显示 ●高 / ◐中 / ○低；低置信日用斜纹/虚线边框区分，避免用户误把"粗略估计"当"确定预测"。
- **解释层**：一句话讲清为何这个置信度——
  > "置信度：中。该日为 2029 年远期预测，且历史相似日仅 4 个；若遇极端降雪，实际拥堵可能高于预测。"
- **情景层**：对天气敏感日提供"好天气 / 坏天气"两条情景曲线，让用户看到不确定性的来源与范围。

### 9.4 置信度与颜色等级的关系（重要设计）

- 颜色等级（绿→深红）基于 **P50 主预测** 映射，保持日历清晰。
- 但当预测落在**等级边界附近且区间很宽**时（例如 P50 落在 red/dark-red 阈值附近，P90 已进入 dark-red），在该单元标注"**可能升级为深红**"的不确定性提示，而不是武断给单一颜色。
- 这样既保留交通日历的简洁表达，又诚实传达边界风险——兼顾"清晰"与"可信"。

### 9.5 落地优先级说明

- **核心层必做**：第 1 层分位数区间 + 第 3 层 High/Medium/Low 评级（CatBoost 分位回归天然支持，几乎零额外成本）。
- **加分层**：第 2 层 Conformal/校准 + 可靠性图（强烈推荐做，是 Plausibility 评分的决定性证据，实现量也不大）。
- **炫技层**：多模型一致性纳入置信度、情景曲线交互。

---

## 10. 可解释性体系（重点）

可解释性是本系统的**核心卖点**和最大评分点。我们提供**四个来源、两个层次**的解释。

### 10.1 四个解释来源

1. **SHAP（来自 CatBoost/LightGBM）** — 量化每个特征对该日预测的贡献值。
   ```
   Bavaria summer holiday start: +12,400
   Saturday effect:              +8,100
   A8 East outbound:             +6,900
   Austria holiday overlap:      +4,300
   similar-day baseline:         +3,800
   ```
2. **Similar-Day 证据** — "参考了 12 个历史相似日，均值 86,500"，可追溯真实日期。
3. **Expert Rule 触发说明** — "因巴伐利亚暑假首个周六，风险 +1 级"。
4. **TFT 时序可解释** — Variable Selection（重视哪些变量）+ Temporal Attention（关注哪些历史时间点）。

> 分工原则：**SHAP + 规则 + 相似日 负责面向用户/评委的解释；TFT 负责时序层面的解释。** 不把全部解释任务压给 TFT（它的解释不如 SHAP 直观）。

### 10.2 两个解释层次

**用户层（普通旅客/居民）** — 自然语言，一句话讲清"为什么红、什么时候堵"：
> "预计深红：巴伐利亚暑假开始后第一个周六 + 奥地利假期重叠，历史相似日交通显著偏高；高峰 06:00–11:00。"

**专家层（交通管理者/评委）** — 量化因子分解：
> Top factors: ①Bavaria summer start +12,400 ②Saturday +8,100 ③A8E outbound +6,900 ④Austria overlap +4,300 ⑤similar-day +3,800

### 10.3 解释生成流程

```
SHAP top-k factors  ┐
rule triggers       ├→ 模板化/规则化自然语言生成 → 用户解释 + 专家解释
similar-day evidence┘
```
> hackathon 阶段用**模板拼接**生成自然语言即可（稳定、可控）；有余力可接 LLM 润色，但要保证数字来自真实 SHAP/规则，避免幻觉。

---

## 11. 智能体系统（重点 · Agentic Layer：Explainer / Planner / RAG）

在确定性预测系统之上，叠加一层**多智能体对话系统**，把"预测数字 + 解释原语"转化为**自然语言解释**与**个性化行程规划**，真正服务 PDF 的五类用户。

> **铁律（Single Source of Truth）**：预测系统（第 6–10 章）是**唯一事实来源**。智能体**永远不自己编造车流量/日期/置信度**——所有数值必须通过工具调用从预测库取得，再由 Orchestrator/Trust-Guard 校验。LLM 只负责"理解意图、组织语言、做规划推理"，不负责"记忆事实"。这是公共部门场景可信落地的前提。

> **精简到 4 个 agent**：为控制复杂度同时**保留全部功能**，我们把原本的 6 个角色按职责合并为 **4 个**——取证类（预测工具 + RAG 知识）合并为 **Retrieval Agent**；编排与防幻觉校验合并为 **Orchestrator / Trust-Guard**；**Explainer** 与 **Planner** 保持独立。所有工具、RAG、防幻觉、规划、解释功能一个不少。

### 11.1 为什么要 Agentic Layer

- 日历 UI 适合"浏览"，但用户真实诉求是**对话式问答 + 决策**："我想 8 月初带孩子从慕尼黑去加尔达湖，哪天走最不堵？"
- 把第 9/10 章的置信度与解释原语，用自然语言**因人而异**地表达（旅客 vs 物流 vs 交通管理者语气/重点不同）。
- 规划是**多日、多方向、带约束的优化**，超出静态日历的表达力，天然适合 Planner Agent。

### 11.2 智能体角色设计（4 个 · 功能全保留）

| Agent | 合并自 | 职责（含全部原功能） | 输入 | 输出 |
|---|---|---|---|---|
| **① Orchestrator / Trust-Guard（编排 + 防幻觉校验）** | Orchestrator + Verifier | 解析意图、拆解任务、调度其他 agent、汇总回答；并在输出前**核对每个数字/日期都有工具来源**、标注不确定性、拦截幻觉、超界拒答 | 用户自然语言 + persona / 草稿 + 工具记录 | 校验通过的最终回复 / 打回重写 |
| **② Retrieval Agent（取证：预测工具 + RAG + 联网搜索）** | Forecast Tool-Agent + RAG Knowledge | 三类取证：①调结构化工具查预测库（确定性数字/区间/等级/峰段/置信度/SHAP/相似日）；②调 `rag_search` 检索本地领域知识做接地，**接入你现成的 RAG 模板**；③调 `web_search`（Tavily 等）联网补充实时/最新信息（官方通告、施工、临近事件、天气展望） | corridor/date/范围 / 自然语言查询 | 定量预测结果 + 带出处的定性知识 + 带链接的实时信息 |
| **③ Explainer Agent（解释）** | （不变） | 把预测+证据+知识组织成 persona 自适应的解释（用户层/专家层） | 预测结果 + RAG + SHAP/规则 | persona 化解释文本 |
| **④ Planner Agent（行程规划）** | （不变） | 多日多方向带约束优化出行方案 | 起讫/日期窗/约束 | 推荐出发日+时段+备选+理由 |

### 11.3 工具层（Function Calling / Tools）

智能体通过一组**确定性工具**访问预测系统，而非直接读模型：

```
get_forecast(corridor, date)
    → {volume_p50, p10, p90, category, peak_window, confidence}
get_forecast_range(corridor, date_start, date_end)
    → 每日预测列表（用于规划/趋势）
get_shap_factors(corridor, date)
    → top-k 贡献因子（解释用）
get_similar_days(corridor, date)
    → 历史相似日 + 实际流量（证据用）
get_calendar(region, date_range)
    → 学校/公共假期、桥接日、已知 Dosierung 日
recommend_departure_window(origin_region, corridor, date_range, constraints)
    → 候选出发日/时段排序（Planner 内部调用）
rag_search(query)
    → 领域知识片段 + 出处（接你的 RAG 模板, 本地知识库）
web_search(query)
    → 实时联网检索 (Tavily / SerpAPI / Bing 等)
      官方通告·施工·临近大型活动·天气展望, 返回摘要 + 来源 URL
```

> **本地 RAG vs 联网搜索的分工**：`rag_search` 取**稳定的领域知识**（假期语义、专家规则、方法论）；`web_search` 取**时效性强、知识库未覆盖**的内容（如"本周 A8 是否有施工/封路""临近某音乐节"）。两者都**必须带出处**，由 Orchestrator/Trust-Guard 核对，并在回复中附引用/链接。联网结果**只作为定性补充**，不覆盖预测库的车流量数字。

### 11.4 RAG 知识库（你的模板插这里）

RAG 负责**定性领域知识的接地**，与"定量预测"互补。建议知识库内容：

- **假期语义与出行规律**：各州/邻国假期含义、为何首个周六/返程周日是峰值。
- **专家规则文档与理由**：Dosierung（边境限流）机制、滑雪季模式、长周末返程规律。
- **Autobahn 官方指引/FAQ**：出行建议、限行/施工通告、官方术语。
- **本系统方法论摘要**：让 Explainer 能回答"这个预测是怎么来的、为什么可信"。
- **历史事件备忘**：重大封路/事故/活动记录。

此外，Retrieval Agent 通过 `web_search`（Tavily 等）补充**知识库覆盖不到的实时信息**：Autobahn 官方实时通告、当前/临近施工与封路、临近大型活动（演唱会/球赛/展会）、未来天气展望。这让对话在"长期日历预测"之外，还能反映**最新动态**，更贴近真实出行决策。

> 集成方式：把你现成的 RAG 模板包成 `rag_search(query)` 工具，由 **Retrieval Agent** 调用；检索结果**必须带出处**，供 Orchestrator/Trust-Guard 核对、供解释附引用。RAG 只提供"定性知识/措辞依据"，**绝不**用来生成具体车流量数字（数字只走预测工具）。

### 11.5 数据流（一次问答的生命周期）

```
用户提问 + persona
      ↓
① Orchestrator/Trust-Guard 解析意图 → 判断"解释类"还是"规划类"，调度取证
      ↓
② Retrieval Agent 取证 (一个 agent 内完成全部取数):
  ├─ get_forecast / get_forecast_range        (确定性数字)
  ├─ get_shap_factors / get_similar_days      (解释证据)
  ├─ rag_search                               (本地定性知识 + 出处)
  └─ web_search (Tavily 等)                    (实时信息 + 来源 URL, 按需)
      ↓
③ Explainer / ④ Planner 组织答案 (按 persona 调整重点与语气)
      ↓
① Orchestrator/Trust-Guard 校验:
  每个数字/日期是否都能在工具返回中找到来源?
  不确定性是否如实呈现? 远期/低置信是否提示?
  → 通过则输出; 不通过则打回重写
      ↓
返回: 自然语言解释 / 行程方案 (附置信度 + 引用 + 可点开的日历链接)
```

### 11.6 Planner Agent 设计（行程规划）

把"预测"变成"决策"，这是对用户最直接的价值。

- **输入**：起点地区、目的地/走廊与方向、可行日期窗、约束（必须周末走/避免夜间/带儿童/货车限行等）、风险偏好（保守=只选高置信低流量日）。
- **过程**：调 `get_forecast_range` 拿窗口内每日预测 → 按"流量↓ + 置信度↑ + 满足约束"打分排序 → 结合 `get_calendar` 规避已知 Dosierung/峰值 → 给出**主推方案 + 2 个备选**。
- **输出示例**：
  > "推荐 **7/28（周二）06:00 前出发**：A8E outbound 预测 58,000 辆（绿/黄交界，置信度高），明显优于 8/1 周六（92,300，深红）。备选 7/29 或 7/27。返程建议避开 8/30 周日返程潮（inbound 深红）。"

### 11.7 Explainer Agent 设计（persona 自适应解释）

同一份预测，按用户角色调整**重点、语气、信息粒度**：

- **旅客/游客**：口语化，强调"哪天/几点走最省心"。
- **居民**：强调"哪些时段最堵、如何避开"。
- **物流/客运**：强调可靠性与置信度，给可排程的确定性结论。
- **旅游业**：强调未来高峰到达日，便于接待/排班。
- **交通管理者**：给量化因子分解 + 方法论，可对外沟通、可审计。

### 11.8 防幻觉与可信度保障（由 Orchestrator / Trust-Guard 承担）

公共部门场景的关键防线（合并进 ① 号 agent，在汇总输出前执行）：

- **数字接地**：回复中每个车流量/日期/等级/置信度，必须能映射到某次工具返回；否则打回。
- **不确定性透明**：远期或低置信预测，必须显式提示（"这是 2029 年远期估计，仅供粗略参考"）。
- **引用可溯**：定性结论附 RAG 出处；定量结论附预测来源（corridor+date）；**联网信息附来源 URL**。
- **来源可信度分级**：官方来源（Autobahn/DWD）> 主流媒体 > 其他；低可信来源需注明"未经核实"。
- **拒答边界**：超出数据覆盖（非 A8E/A93S、超 2029）时明确说明；实时路况以 `web_search` 联网结果为准并标注时效，不臆测。

### 11.9 技术实现与 Hackathon 取舍

- **框架**：LangGraph / 原生 function-calling 均可。"4 个 agent"在 hackathon 可先用**单 LLM + 多角色 prompt + 工具集**模拟（role = system prompt），跑通后再拆成独立节点。
- **预测库即工具后端**：把第 8 章输出存为 `forecast.parquet / SQLite`，工具函数做查询——保证 agent 拿到的永远是确定性结果。
- **落地优先级**：
  - 🟢 核心：Retrieval Agent（预测工具）+ Explainer + Orchestrator 单轮问答（数字全部接地）
  - 🟡 加分：Planner Agent + Retrieval 的 RAG 部分（接你的模板）+ persona 自适应
  - 🔵 炫技：Trust-Guard 自动重写 + 多轮对话记忆 + 多 agent 并行编排

### 11.10 与评分标准的对应

| 评分标准 | Agentic Layer 的贡献 |
|---|---|
| Plausibility（会信任吗） | Orchestrator/Trust-Guard 接地校验 + 引用可溯 + 不确定性透明 |
| Relevance（规划相关性） | Planner 直接产出可执行出行决策 |
| Transparency & Explainability | Explainer persona 自适应解释 + Retrieval 的 RAG 出处 |
| Practical applicability | 对话式交互贴近真实公众服务/热线场景 |
| Innovation & smart use of data | 预测 + RAG + 多智能体融合，数字与知识各司其职 |

---

## 12. 用户界面层

**交互式交通日历（Streamlit / Web）**，这是 demo 最出彩的部分。

核心组件：
- **月历视图**：每天按绿→深红着色（双方向可切换/并排）。
- **单日详情**：点击某天 → 车流量 + 置信区间 + 24h 高峰曲线 + 用户解释 + 专家因子分解 + 相似参考日。
- **峰值预警**：自动高亮标注"关键拥堵日（深红）"。
- **用户视角切换**（对应 PDF 五类用户）：
  - 旅客：高亮"低峰出发窗口"
  - 居民：高亮"避开的高峰时段"
  - 物流：按可靠日筛选 + 置信度排序
  - 旅游业：列出未来高峰到达日
  - 交通管理：一致、可解释的全局视图
- **对话入口（接第 11 章 Agentic Layer）**：日历页内嵌聊天框，用户可直接问"哪天走最不堵 / 为什么这天是深红"，由 Explainer/Planner 实时作答；答复中的日期可回链到日历高亮。

---

## 13. 评估指标

### 13.1 车流量回归
```
MAE, RMSE, MAPE   (整体 + 分 corridor)
```

### 13.2 峰值日识别（最关键 —— 用户最关心"最堵的日子有没有抓到"）
```
Precision@Top-K peak days
Recall for top 10% traffic days
Recall for dark-red days
```

### 13.3 颜色等级
```
category accuracy, weighted F1, confusion matrix
```

### 13.4 不确定性 / 置信度可靠性（对应第 9 章 · 直接支撑 Plausibility 评分）
```
区间覆盖率 (PICP):   P10–P90 实际覆盖率是否 ≈ 80%
区间宽度 (MPIW):     在保证覆盖率前提下区间是否尽量窄
可靠性图 (reliability diagram): 名义置信度 vs 实际覆盖率, 越贴对角线越好
分组校准:            高/中/低置信日的实际 MAE 是否随置信度单调下降
                     (即"高置信日确实更准")
Conformal 覆盖保证:  Split-Conformal 区间在测试集上的经验覆盖率
```

### 13.5 解释质量（定性）
```
解释是否匹配已知假期/事件原因?
Top SHAP 因子是否合理?
相似参考日是否 make sense?
```

---

## 14. Hackathon 落地优先级与排期

**严格分三层，按顺序做，每层做完都能独立 demo，绝不样样半成品。**

### 🟢 核心层（必须 100% 完成 = 能拿奖的最小系统）
1. 数据清洗 → daily_volume（按 corridor）
2. **特征工程做满**（日期 + 跨国假期 + 假期偏移/出发返程波）← 最高优先级
3. **CatBoost 分位数回归**（P10/P50/P90）→ 预测值 + 置信区间
4. 历史分位数 → 绿→深红颜色映射
5. **SHAP → 每日"为什么红"文字解释**
6. **专家规则层**（5–8 条关键规则做修正 + 解释文本）
7. **Streamlit 月历 UI**：着色 + 点击看曲线/解释/置信度

### 🟡 加分层（核心稳了再做）
8. 日内曲线（优先 typical pattern template）
9. **Similar-Day Retrieval**（作为可解释历史证据展示）
10. 峰值日自动标注 + Top-K recall 评估
11. **预测落库 + Retrieval Agent(预测工具) + Explainer + Orchestrator**（单轮对话问答，数字全接地）
12. **Planner Agent + Retrieval 的 RAG 部分**（行程规划 + 接你的 RAG 模板）

### 🔵 炫技层（有余力 / 专人负责）
13. **TFT**：跑通一版，PPT 里与 CatBoost 对比讲"探索时序 SOTA"
14. Trust-Guard 自动重写 + 多轮对话 + 多 agent 并行编排
15. 动态权重 / Conformal 校准 / LLM 解释润色

### 建议执行顺序（先打通端到端最小闭环再迭代精度）
```
Step 1  清洗历史数据 → daily + hourly
Step 2  构建日历/假期/偏移/气候态特征
Step 3  Similar-Day baseline (可解释兜底)
Step 4  CatBoost 分位数回归
Step 5  (可选) TFT 对照
Step 6  模型对比评估
Step 7  设定 ensemble 权重 (默认/网格搜)
Step 8  计算 corridor 颜色阈值
Step 9  接入 SHAP + 规则解释
Step 10 Streamlit 交通日历 UI
Step 11 预测落库 + Retrieval Agent + Explainer + Orchestrator (对话问答)
Step 12 Planner Agent + RAG (行程规划) + Trust-Guard 防幻觉
```

---

## 15. 技术栈与项目结构

### 15.1 技术栈
```
数据处理:   pandas, numpy, pyarrow(parquet)
模型:       catboost / lightgbm, (可选) pytorch-forecasting(TFT)
解释:       shap
假期数据:   holidays(py), OpenHolidays/Nager.Date API
天气:       open-meteo / DWD
智能体:     LangGraph / function-calling, LLM(OpenAI 等)
RAG:        现成 RAG 模板 + 向量库(faiss/chroma)
联网搜索:   Tavily (或 SerpAPI / Bing Search)
预测后端:   forecast.parquet / SQLite (供 agent 工具查询)
UI:         streamlit (+ plotly / altair 画日历与曲线; chat 界面)
```

### 15.2 建议目录结构
```
hackathon/
├── data/
│   ├── raw/                  # 原始交通数据
│   ├── external/             # 假期/天气/事件
│   └── processed/            # clean_daily.parquet 等
├── src/
│   ├── data/
│   │   ├── load.py           # 加载+schema标准化
│   │   ├── clean.py          # 缺失/异常处理
│   │   └── aggregate.py      # 日/小时聚合
│   ├── features/
│   │   ├── calendar.py       # 日期特征
│   │   ├── holidays.py       # 跨国假期+偏移特征
│   │   ├── weather.py        # 气候态/情景
│   │   └── build.py          # 拼装特征矩阵
│   ├── models/
│   │   ├── similar_day.py    # Model A
│   │   ├── gbdt.py           # Model B (分位数)
│   │   ├── tft.py            # Model C (可选)
│   │   ├── rules.py          # Model D
│   │   └── ensemble.py       # 融合+校准
│   ├── output/
│   │   ├── color_map.py      # 颜色阈值
│   │   ├── daily_profile.py  # 日内曲线
│   │   ├── confidence.py     # 置信度
│   │   ├── explain.py        # SHAP+规则→解释文本
│   │   └── store.py          # 预测落库 forecast.parquet/SQLite
│   ├── agents/               # 智能体系统 (第 11 章, 4 个 agent)
│   │   ├── tools.py          # get_forecast / get_calendar / rag_search / web_search(Tavily) ...
│   │   ├── orchestrator.py   # ① 编排/路由 + 防幻觉接地校验
│   │   ├── retrieval.py      # ② 预测工具 + RAG (接入现成 RAG 模板)
│   │   ├── explainer.py      # ③ persona 自适应解释
│   │   └── planner.py        # ④ 行程规划
│   └── evaluate.py
├── rag/                      # RAG 知识库 (你的模板 + 领域文档/索引)
├── app/
│   ├── calendar_app.py       # Streamlit 日历 UI
│   └── chat_app.py           # 对话式 Agent UI
├── notebooks/                # EDA
├── requirements.txt
├── README.md
└── SOLUTION.md               # 本文档
```

---

## 16. Pitch 话术与用户价值映射

### 16.1 一句话定位（presentation）

> **EN**: We propose a TFT-enhanced hybrid expert-AI forecasting system. CatBoost provides robust, quantile-based tabular prediction; similar-day retrieval gives interpretable historical evidence; an expert rule layer converts traffic-domain knowledge into scalable logic; and TFT explores temporal travel waves. The output is a daily traffic forecast mapped into transparent green-to-dark-red categories with confidence scores and human-readable explanations — for A8 East & A93 South, every day of 2026–2029.

> **中文**：我们提出基于 TFT 增强的混合专家-AI 交通预测系统。CatBoost 提供稳健的分位数表格预测；相似历史日检索提供可解释的历史依据；专家规则层把交通领域知识转化为可扩展逻辑；TFT 探索假期交通的连续时间波动。系统输出每日车流量，映射为透明的绿→深红等级，并附置信度与人类可读解释——覆盖 A8 East / A93 South，2026–2029 每一天。

### 16.2 用户价值映射（对应 PDF 五类用户故事）

| 用户 | 系统提供 |
|---|---|
| 旅客/游客 | 低峰出发窗口、避堵日历 |
| 当地居民 | 高峰日/时段预警，调整日常 |
| 物流/客运 | 可靠日筛选 + 置信度，提前排程 |
| 旅游业 | 未来高峰到达日，协调接待/排班 |
| 交通管理 | 一致、可解释、可沟通的预测 |

### 16.3 技术亮点话术
```
1. CatBoost 分位数回归 → 稳健预测 + 原生置信区间
2. 跨国假期 + 出发/返程波特征 → 精准命中阿尔卑斯走廊峰值
3. Similar-Day Retrieval → 可追溯的历史证据
4. Expert Rule Layer → 把人工专家经验规模化
5. SHAP + 颜色阈值映射 → 每个预测都可解释、可审计
6. 诚实的天气情景处理 → 公共部门级可信度
7. 三层置信度 + Conformal 校准 + 可靠性图 → 可证明的"Would I trust this forecast"
8. 4 智能体 (Orchestrator/Trust-Guard · Retrieval · Explainer · Planner) → 对话式解释与行程规划, 数字全程接地防幻觉
```

---

## 17. 风险与取舍说明

| 风险 | 说明 | 对策 |
|---|---|---|
| TFT 高风险低回报 | 纯日历特征难胜 GBDT；远期 observed inputs 不可得，递归误差累积 | 降级为炫技层/对照，专人负责，不进关键路径 |
| 方案过大做不完 | 4 模型+ensemble+UI 是团队两周量 | 严格三层优先级，先打通核心最小闭环 |
| 动态权重过度工程 | hackathon 内无法验证、显得不严谨 | 默认固定加权；有时间则网格搜全局权重 |
| 相似日信息重复 | 既当 GBDT 特征又进 ensemble → 泄漏/重复 | 定位为"可解释证据"独立展示，不强行进 ensemble |
| 未来天气不可知 | 当硬输入会失真 | 气候态 + 好/坏天气情景，透明展示 |
| lag 特征远期不可用 | 2027–2029 无真实历史值 | 主力 GBDT 用无 lag 版；lag 仅用于回测/TFT |
| 智能体幻觉/编数字 | LLM 可能臆造车流量/日期 → 公共部门致命 | 数字只走工具；Orchestrator/Trust-Guard 接地校验；超界拒答 |
| Agentic Layer 拖慢核心 | 多 agent+RAG 工程量大 | 精简为 4 agent；核心仅 Retrieval(工具)+Explainer+Orchestrator 单轮；Planner/RAG 列加分层 |

**一句话总结**：架构设计满分，真正的得分点不在 TFT，而在**扎实的假期特征 + 分位数置信区间 + SHAP/规则/相似日的可解释叙事 + 漂亮的日历 UI**。把野心匹配到时间上，成功率从"勉强 demo"变成"稳拿前列"。
