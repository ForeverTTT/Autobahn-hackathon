# 小时级交通预测建模方案

> 基于 `data_autobahn/` 内全部数据，预测 **2026–2029 年每天每小时**、**12 个探测站点**的三个指标：
>
> | 目标 | 字段 | 含义 |
> |---|---|---|
> | 总流量 | `kfz_h` | 小时总车流量（辆/h） |
> | 大车流量 | `sv_h` | 小时重型车流量（辆/h） |
> | 平均车速 | `v_kfz` | 小时加权平均车速（km/h） |
>
> **主力模型：CatBoost 分位数回归**  
> **探索亮点：Temporal Fusion Transformer (TFT)**  
> **设计原则：主流量数据为主，其余全部为 conditional data**

与 [`SOLUTION.md`](SOLUTION.md) 对齐：本任务是 **2026–2029 纯条件预测**——远期没有实测序列、没有真实天气，模型只能依赖提前可知的日历/假期/气候态特征。

---

## 目录

1. [数据清单与角色分工](#1-数据清单与角色分工)
2. [建模单元与预测网格](#2-建模单元与预测网格)
3. [核心约束](#3-核心约束)
4. [数据处理流程](#4-数据处理流程)
5. [特征工程（数据怎么喂进去）](#5-特征工程数据怎么喂进去)
6. [CatBoost 模型设计（主力）](#6-catboost-模型设计主力)
7. [TFT 模型设计（探索层）](#7-tft-模型设计探索层)
8. [训练 / 验证 / 推理](#8-训练--验证--推理)
9. [评估指标与输出格式](#9-评估指标与输出格式)
10. [落地优先级与目录结构](#10-落地优先级与目录结构)

---

## 1. 数据清单与角色分工

所有输入均来自 `data_autobahn/`：

| 文件 | 角色 | 粒度 | 时间范围 | 2026–2029 可用性 |
|---|---|---|---|---|
| `合并表格，小时交通流量.csv` | **主数据** | 站点 × 小时 | 2023–2025 | 仅用于训练画像，不直接作为未来输入 |
| `合并表格，时间，气温，路温.csv` | conditional | 分钟 | 2023–2025 | 未来用 (doy, hour) 气候态 |
| `合并表格，holiday日级.csv` | conditional | 日 | 2023–2029 | ✅ 完全可知 |
| `合并表格，weather日级.csv` | conditional | 日 | 2023–2029 | ✅ 气候态列可用 |
| `合并表格，construction日级.csv` | conditional | 日 | 2023–2029 | 已知施工可用，未知置 0 |
| `合并表格，special_events日级.csv` | conditional | 日 | 2023–2029 | 已知活动可用，未知置 0 |

### 主表 schema

```
road, direction, site_name, bab_km, longitude, latitude,
devices, datum, t_start, wochentag, tagestyp,
kfz_h, sv_h, v_kfz
```

- 分隔符 `;`，部分数值含逗号小数（如 `11,704721`），需统一转 float。
- `tagestyp`：日类型（`w`=工作日 / `s`=周日及公共假日 / `u`=学校假期等），是强特征。
- `sv_h` 与 5 分钟表 `q_lkw` 定义不同，**以小时表 `sv_h` 为训练目标**。

---

## 2. 建模单元与预测网格

### 2.1 建模单元

```
site_id = road + "_" + direction + "_" + site_name
```

- **12 个站点**：A8 / A93 × 2 方向 × 3 公里桩位置。
- 每个 `site_id` 一条独立小时序列。
- 三目标分别建模，不共享输出头。

### 2.2 预测网格

```
12 站点 × 1461 天 (2026–2029) × 24 小时 ≈ 420,768 行
```

每行对应一个 `(site_id, date, hour)` 的预测。

---

## 3. 核心约束

预测 2026–2029 时，**不能使用需要未来实测值的特征**：

| 可用 ✅ | 不可用 ❌ |
|---|---|
| 日历（星期/月/小时/季节） | `lag_1`, `lag_7`, `rolling_mean_7` |
| 假期 / 交通窗口（已知） | 未来真实 `kfz_h` / `v_kfz` |
| 历史画像（按日历键聚合，见 §5.2） | 未来真实天气 / 路温 |
| 气候态天气 / 路温 | 递归多步预测链（主力路径禁止） |
| 已知施工 / 活动 | 未知事件（置 0 + 置信度扣分） |

> **历史画像特征**是本方案把「主流量数据为主」落地的关键：从 2023–2025 按 `(site, hour, weekday, tagestyp, …)` 聚合出典型流量/车速，2026–2029 直接 lookup，不依赖未来实测。

---

## 4. 数据处理流程

### 4.1 主表清洗

```python
# 伪代码
df["ts"]   = parse(datum + t_start)          # DD.MM.YYYY + HH:MM:SS
df["date"] = df["ts"].dt.date
df["hour"] = df["ts"].dt.hour
df["site_id"] = df["road"] + "_" + df["direction"] + "_" + df["site_name"]

# 异常处理
df.loc[df["kfz_h"] < 0, "kfz_h"] = NaN
# v_kfz 仅在 kfz_h > 0 时有效
```

- 短缺口（≤2 小时）：同 `(site, weekday, hour)` 中位数填补，标记 `is_imputed=1`。
- 长缺口：不插值，训练降权或剔除。

### 4.2 路温 / 气温 → 小时聚合

`合并表格，时间，气温，路温.csv` 按小时聚合：

```
lt_mean, fbt_mean, fbt_min   # fbt_min 用于结冰风险
```

- 训练期：用实测小时值。
- 2026–2029：按 `(doy, hour)` 或 `(month, hour)` 计算多年气候态均值/分位。

### 4.3 conditional 日级表合并

四张日级表按 `date` left join 到主网格。合并键统一为 `date`（`YYYY-MM-DD`）。

### 4.4 中间产物

```
processed/
  clean_hourly.parquet      # 清洗后主表
  hourly_with_cond.parquet  # 合并 conditional 后
  features.parquet          # 完整特征矩阵
  forecast.parquet          # 2026–2029 预测结果
```

---

## 5. 特征工程（数据怎么喂进去）

特征分 **主信号（历史画像）** 与 **conditional 偏移** 两层。

### 5.1 日历特征（确定性骨架）

```
hour (0–23)              + hour_sin, hour_cos
weekday (1–7)            + dow_sin, dow_cos
month, day_of_year       + month_sin/cos, doy_sin/cos
week_of_year, is_weekend
is_friday, is_saturday, is_sunday
season                   # 冬/春/夏/秋
tagestyp                 # w/s/u，来自主表
```

### 5.2 历史画像特征（★ 主流量数据的核心入模方式）

从训练集 (2023–2025) 按**纯日历键**聚合，做成 lookup 表。键不含未来信息，2026–2029 可直接查：

```
# 总流量
prof_kfz_site_hour_dow       = median(kfz_h)  by (site_id, hour, weekday)
prof_kfz_site_hour_tagestyp  = median(kfz_h)  by (site_id, hour, tagestyp)
prof_kfz_site_hour_month     = median(kfz_h)  by (site_id, hour, month)
prof_kfz_site_dow_p90        = p90(kfz_h)     by (site_id, hour, weekday)

# 大车流量占比（供 sv_h 建模）
lkw_ratio = sv_h / kfz_h   # kfz_h > 0 时
prof_lkwratio_site_hour_dow = median(lkw_ratio) by (site_id, hour, weekday)

# 车速
prof_v_site_hour_dow         = median(v_kfz)    by (site_id, hour, weekday)
prof_v_site_hour_p85         = p85(v_kfz)      by (site_id, hour)   # 自由流基准
```

**计算时必须 out-of-fold**（见 §8.2），防止验证期信息泄漏。

> 这组特征通常贡献 70–85% 的解释力。CatBoost 在其之上学习 conditional 数据的偏移修正。

### 5.3 站点静态特征

```
site_id    # CatBoost categorical
road, direction, site_name, bab_km, longitude, latitude
```

### 5.4 conditional 特征（条件偏移项）

#### 节假日（`holiday日级.csv`）

```
is_school_holiday_DE_BY / AT_SB / AT_TI
is_public_holiday_DE_BY / AT_SB / AT_TI
school_holiday_count, public_holiday_count    # 跨州叠加 = 峰值强驱动
is_holiday_start, is_holiday_end
in_traffic_window, window_direction, window_risk_level
a8_direction, a93_direction
```

**建议额外派生**（脚本中补算）：

```
days_to_holiday_start, days_since_holiday_start
days_to_holiday_end,   days_since_holiday_end
is_first_saturday_of_summer    # 暑假首个周六 = 出发峰
is_return_sunday               # 假期末返程周日
```

#### 天气（`weather日级.csv`）

```
# 历史用 observed 列，未来用 climatology 列
precip_mm, snowfall_mm, low_vis_hours
t_min_c, t_max_c, has_ice_risk
precip_mm_mean, precip_prob_wet, ice_risk_prob   # 气候态
weather_source   # observed / climatology → 置信度信号
```

#### 路温 / 气温（小时级，未来用气候态）

```
lt_hour, fbt_hour, fbt_min_hour
```

#### 施工（`construction日级.csv`）

```
has_a8_construction, has_a93_construction
a8_construction_count, a93_construction_count
has_2_plus_0, two_plus_0_count
max_closed_lanes, sum_closed_lanes
has_target_bbox_construction
```

#### 特殊事件（`special_events日级.csv`）

```
has_special_event, active_event_count
max_impact_level, impact_score
affects_a8_ost, affects_a93_sued
has_munich_event, has_salzburg_event, has_rosenheim_event, has_kufstein_event
has_confirmed_event, has_estimated_event
```

### 5.5 数据质量 / 不确定性标记（进置信度模块）

```
is_imputed, weather_source, is_known_event
forecast_year   # 2026→高置信 … 2029→低置信
```

---

## 6. CatBoost 模型设计（主力）

### 6.1 为什么选 CatBoost

| 优势 | 对本任务的匹配 |
|---|---|
| 原生类别特征处理 | `site_id`, `road`, `direction`, `tagestyp`, `season` 无需 one-hot |
| 分位数回归 | `loss_function='Quantile:alpha=0.1/0.5/0.9'` 直接出 P10/P50/P90 |
| 训练稳健 | 默认较少调参即可收敛 |
| SHAP 可解释 | 对应 SOLUTION 可解释性要求 |
| 表格特征 SOTA 级 | 纯日历 + 假期特征下通常优于 TFT |

### 6.2 总体策略

- **一个全局模型**（12 站合训，`site_id` 作 categorical），比每站单训更稳健、能跨站共享假期模式。
- 三个目标各训独立模型组（共 3 × 3 = 9 个分位模型，或按需扩展）。

### 6.3 目标 1：总流量 `kfz_h`

```python
from catboost import CatBoostRegressor

cat_features = [
    "site_id", "road", "direction", "site_name",
    "tagestyp", "season", "weather_source",
    "window_direction", "window_risk_level",
]

model_p50 = CatBoostRegressor(
    loss_function="Quantile:alpha=0.5",
    iterations=3000,
    learning_rate=0.03,
    depth=8,
    l2_leaf_reg=5,
    cat_features=cat_features,
    eval_metric="Quantile:alpha=0.5",
    early_stopping_rounds=100,
    random_seed=42,
    verbose=200,
)
# 同理训练 alpha=0.1 (P10), alpha=0.9 (P90)
```

**输入特征** = §5.1 日历 + §5.2 历史画像 + §5.3 静态 + §5.4 conditional（**无 lag**）。

**输出**：

```
kfz_h_p10, kfz_h_p50, kkfz_h_p90
区间宽度 (p90 - p10) → 不确定性指标
```

### 6.4 目标 2：大车流量 `sv_h`

推荐 **占比法**（比直接回归绝对量更平稳）：

```
Step 1: CatBoost 预测 lkw_ratio = sv_h / kfz_h
Step 2: sv_h_pred = lkw_ratio_pred × kfz_h_p50_pred
```

- 画像特征换成 `prof_lkwratio_*`。
- 同时保留「直接预测 `sv_h`」作为对照，验证集取 MAPE 更低者。

### 6.5 目标 3：平均车速 `v_kfz`

车速与流量呈非线性拥堵关系，自由流时段占多数，直接回归易被均值主导。

**推荐两段式**：

```
Step 1: 自由流基准 = prof_v_site_hour_p85  (历史 p85 速度)
Step 2: CatBoost 预测 speed_drop = 基准 - v_kfz
        特征额外加入: kfz_h_p50_pred, sum_closed_lanes, fbt_min_hour,
                      precip_mm, snowfall_mm, has_ice_risk
Step 3: v_kfz_pred = 基准 - speed_drop_pred，截断到 [20, 160] km/h
```

也保留「直接回归 `v_kfz`」作为 baseline 对照。

### 6.6 CatBoost 超参起点

| 参数 | 建议值 | 说明 |
|---|---|---|
| `iterations` | 2000–5000 | 配合 early stopping |
| `learning_rate` | 0.02–0.05 | 小学习率 + 多迭代 |
| `depth` | 6–10 | 假期交互较深，8 起步 |
| `l2_leaf_reg` | 3–10 | 防过拟合 |
| `min_data_in_leaf` | 50–200 | 小时级样本量大，可设 100 |
| `subsample` | 0.8 | 默认即可 |
| `random_seed` | 42 | 可复现 |

### 6.7 模型持久化

```
models/
  kfz_p10.cbm, kfz_p50.cbm, kfz_p90.cbm
  lkwratio_p50.cbm          # 或 sv_p50.cbm
  speed_drop_p50.cbm        # 或 v_p50.cbm
```

---

## 7. TFT 模型设计（探索层）

> ⚠️ **不进主交付关键路径**。纯日历特征下大概率不如 CatBoost；远期 observed inputs 不可得。作为 PPT 对照实验。

### 7.1 三类输入

```
A. Static covariates
   site_id, road, direction, bab_km, longitude, latitude

B. Time-varying KNOWN (未来可知)
   hour, weekday, month, is_weekend,
   holiday flags, holiday offset, weather climatology

C. Time-varying OBSERVED (仅历史)
   kfz_h, sv_h, v_kfz, lt, fbt
```

### 7.2 框架与配置

- 库：`pytorch-forecasting` → `TemporalFusionTransformer`
- 编码器长度：14–28 天
- 预测长度：7 天（多步）
- 2026–2029：仅作历史回测对比，不作 4 年主力预测

### 7.3 与 CatBoost 的分工

| | CatBoost | TFT |
|---|---|---|
| 角色 | 主力预测 | 探索亮点 |
| 输入 | 表格特征 + 历史画像 | 序列 + known future |
| 远期预测 | ✅ 直接推理 | ❌ observed 不可得 |
| 可解释 | SHAP | Variable Selection + Attention |
| 交付 | 必须 | 可选 |

---

## 8. 训练 / 验证 / 推理

### 8.1 时序切分（禁止随机划分）

```
训练集: 2023-01-01 ~ 2024-12-31
验证集: 2025-01-01 ~ 2025-12-31     ← 模拟"预测未来整年"
```

进阶：expanding window rolling CV（多折）。

额外构造 **峰值小时子集**（历史 top 5% `kfz_h`）单独评估 Recall。

### 8.2 历史画像 out-of-fold

```
Fold 1: 画像用 2023 数据 → 验证 2024 部分
Fold 2: 画像用 2023–2024 → 验证 2025
最终:   画像用 2023–2025 全量 → 推理 2026–2029
```

### 8.3 2026–2029 推理流程

```
1. 构建未来网格 (12 站 × 1461 天 × 24h)
2. 填入日历特征 (§5.1)
3. lookup 历史画像 (§5.2, 用 2023–2025 全量聚合)
4. 合并 conditional:
     holiday  → 已知
     weather  → climatology 列
     路温      → (doy, hour) 气候态
     施工/事件 → 已知或置 0
5. CatBoost 推理:
     kfz_h P10/P50/P90
     lkw_ratio → sv_h
     speed_drop → v_kfz
6. 落库 forecast.parquet / forecast.csv
```

---

## 9. 评估指标与输出格式

### 9.1 指标

```
流量回归:   MAE, RMSE, MAPE        (整体 + 分站 + 分小时)
峰值识别:   Precision@TopK, Recall(top 10% 小时)   ← 最关键
大车流量:   MAPE (sv_h 单独)
车速:       MAE, 拥堵小时命中率
区间校准:   PICP (P10–P90 覆盖率 ≈ 80%), MPIW, 可靠性图
```

### 9.2 输出 schema

```
site_id, road, direction, site_name, bab_km,
date, hour, weekday, tagestyp,

kfz_h_p10, kfz_h_p50, kfz_h_p90,
sv_h_pred,
v_kfz_pred,

confidence,          # High / Medium / Low
interval_width,      # p90 - p10
explanation          # SHAP top-k 因子（可选）
```

### 9.3 置信度规则（简要）

| 信号 | 高置信 | 低置信 |
|---|---|---|
| 区间宽度 | 窄 | 宽 |
| 预测年份 | 2026 | 2029 |
| 天气来源 | observed | climatology |
| 特殊事件 | 已知 | 未知 |
| 相似日数量 | 多 | 少 |

---

## 10. 落地优先级与目录结构

### 10.1 执行顺序

```
🟢 核心（必须完成）
 1. 主表清洗 → clean_hourly.parquet
 2. 日历特征 + 历史画像特征 (§5.1/5.2)        ← 最高优先级
 3. conditional 四表合并
 4. CatBoost 分位回归 → kfz_h P10/P50/P90
 5. sv_h (占比法) + v_kfz (两段式)
 6. 2025 hold-out 评估 + SHAP 解释

🟡 加分
 7. 假期偏移派生特征 (§5.4)
 8. 区间校准 + 可靠性图
 9. 峰值小时 Recall 评估
10. Similar-Day 可解释证据（独立展示，不入 ensemble）

🔵 炫技
11. TFT 对照实验
12. Conformal 校准
```

### 10.2 建议目录

```
data_autobahn/               # 原始合并表（只读）
processed/                   # 中间产物
models/                      # .cbm 模型文件
src/
  data/
    load_traffic.py          # 主表加载 + schema 标准化
    aggregate_temp.py        # 分钟路温 → 小时
    merge_conditional.py     # 四表日级合并
  features/
    calendar.py              # §5.1 日历特征
    profiles.py              # §5.2 历史画像 (out-of-fold)
    holidays.py              # 假期偏移派生
    build.py                 # 拼装 features.parquet
  models/
    catboost_quantile.py     # §6 CatBoost 训练 + 推理
    sv_ratio.py              # 大车流量占比模型
    speed.py                 # 车速两段式模型
    tft.py                   # §7 TFT 探索（可选）
  output/
    predict_future.py        # 2026–2029 推理
    evaluate.py              # 评估指标
    store.py                 # forecast.parquet 落库
doc/
  SOLUTION.md                # 系统总方案
  model.md                   # 本文档
```

### 10.3 依赖

```
catboost>=1.2
pandas, numpy, pyarrow
shap                         # 可解释性
pytorch-forecasting          # TFT 可选
```

---

## 附录：数据流总览

```
data_autobahn/
  合并表格，小时交通流量.csv ──────→ 清洗 ──→ 历史画像 (§5.2)
  合并表格，时间，气温，路温.csv ──→ 小时聚合 ──→ 气候态
  合并表格，holiday日级.csv ──────→ conditional ┐
  合并表格，weather日级.csv ──────→ conditional ├─→ features.parquet
  合并表格，construction日级.csv ─→ conditional ┤
  合并表格，special_events日级.csv → conditional ┘
                                              ↓
                                    CatBoost 分位数回归
                                    (kfz_h / sv_h / v_kfz)
                                              ↓
                                    forecast.parquet
                                    (2026–2029, 12站, 每小时)
```

**一句话总结**：把 2023–2025 主流量数据凝练成「历史画像特征」，CatBoost 在其之上用 conditional 数据（假期/气候态/施工/事件）做偏移修正，直接推理 2026–2029 全网格——无需 lag、无需递归、可 SHAP 解释。
