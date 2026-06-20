# 小时级交通预测 — 已实现方案

> **对应 notebook**：`model/model_notebook.ipynb`  
> **状态**：已训练，已生成 2026–2029 预测  
> 本文档描述**实际实现的代码**，不是设计草案。过时的设计文档见 `doc/SOLUTION.md`。

基于 `data_autobahn/` 内全部数据，预测 **2026–2029 年每天每小时**、**12 个站点**的三个目标：

| 目标 | 字段 | 方法 | 模型文件 |
|------|------|------|---------|
| 总流量 | `kfz_h` | MultiQuantile 单模型 (P10/P50/P90) | `models/kfz_h/multi.cbm` |
| 大车流量 | `sv_h` | 占比法：`lkw_ratio × kfz_h_p50` | `models/sv_h/lkw_ratio.cbm` |
| 平均车速 | `v_kfz` | 两段式：`prof_v_p85 − speed_drop` | `models/v_kfz/speed_drop.cbm` |

核心约束：预测 2029 年的某个小时时，**没有实测流量序列、没有真实天气**。模型输入全部来自确定性可提前知道的特征（日历、假期、气候态天气），历史流量通过画像特征（profile lookup）进入模型，不使用 lag、不使用递归。

---

## 1. 数据流

```
data_autobahn/
  合并表格，小时交通流量.csv  ──→ 画像构建 (§3) ──→ prof_kfz_shd/sht/shm/p90/shs
  合并表格，时间，气温，路温.csv ──→ 小时聚合 + 气候态
  合并表格，holiday日级.csv     ──→ ┐
  合并表格，weather日级.csv     ──→ ├─ merge_conditional()
  合并表格，construction日级.csv ──→ ┤
  合并表格，special_events日级.csv ─→ ┘
                                        ↓
                              CatBoost 训练 / 推理
                                        ↓
                              forecast_2026_2029.csv (420,768 rows)
```

所有表分隔符 `;`，第 2 行是中文说明（`skiprows=[1]` 跳过），部分列用逗号小数。主表 `kfz_h < 0` 置 NaN，`v_kfz` 仅在 `kfz_h > 0` 时有效。

---

## 2. 特征工程

### 2.1 特征组

| 组 | 特征数 | 示例 | 类型 |
|----|--------|------|------|
| CALENDAR | 17 | `hour`, `weekday`, `month`, `doy`, `is_weekend/friday/saturday/sunday`, `hour_sin/cos`, `dow_sin/cos`, `month_sin/cos`, `doy_sin/cos` | 数值 |
| STATIC_NUM | 3 | `bab_km`, `longitude`, `latitude` | 数值 |
| STATIC_CAT | 6 | `site_id`, `road`, `direction`, `site_name`, `tagestyp`, `season` | 类别 |
| PROF_KFZ | 5 | `prof_kfz_shd` (site×h×weekday), `prof_kfz_sht` (site×h×tagestyp), `prof_kfz_shm` (site×h×month), `prof_kfz_p90`, `prof_kfz_shs` (site×h×season) | 数值 |
| PROF_LKW | 2 | `prof_lkw_shd`, `prof_lkw_sht` | 数值 |
| PROF_V | 3 | `prof_v_shd`, `prof_v_p85` (自由流基准), `prof_v_sht` | 数值 |
| HOLIDAY | 17 | `is_school/public_holiday_DE_BY/AT_SB/AT_TI`, `school/public_holiday_count`, `is_holiday_start/end`, `days_to_holiday_start`, `days_since_holiday_end`, `total_holiday_overlap`, `is_departure/return_wave_day`, `in_traffic_window` | 数值 |
| HOLIDAY_CAT | 4 | `window_direction`, `window_risk_level`, `a8_direction`, `a93_direction` | 类别 |
| WEATHER | 6 | `w_precip`, `w_snow`, `w_lowvis`, `w_tmin`, `w_tmax`, `w_ice` | 数值 |
| WEATHER_CAT | 1 | `weather_source` | 类别 |
| TEMP | 3 | `lt_mean` (气温), `fbt_mean` (路温), `fbt_min` | 数值 |
| CONSTRUCTION | 9 | `has_a8/a93_construction`, `has_2_plus_0`, `two_plus_0_count`, `max_closed_lanes`, `sum_closed_lanes`, `has_target_bbox_construction` | 数值 |
| EVENTS | 12 | `has_special_event`, `active_event_count`, `max_impact_level`, `impact_score`, `affects_a8_ost/a93_sued`, `has_{munich,salzburg,rosenheim,kufstein}_event`, `has_confirmed/estimated_event` | 数值 |
| G3 (speed only) | 1 | `kfz_p50_pred` — 流量预测值喂入速度模型 | 数值 |

**各目标的特征集**：
```python
FEATURES_KFZ = CALENDAR + STATIC_NUM + STATIC_CAT + PROF_KFZ + COND    # 82 特征
FEATURES_LKW = CALENDAR + STATIC_NUM + STATIC_CAT + PROF_KFZ + PROF_LKW + COND  # 84
FEATURES_SPD = CALENDAR + STATIC_NUM + STATIC_CAT + PROF_KFZ + PROF_V + COND + ["kfz_p50_pred"]  # 86
```

其中 `COND = HOLIDAY + HOLIDAY_CAT + WEATHER + WEATHER_CAT + TEMP + CONSTRUCTION + EVENTS`。

### 2.2 历史画像（核心信号，~64% 重要性）

画像从**训练集**（2023–2024）聚合，不触碰验证集，防止泄漏：

```python
profiles = build_profiles(train_df)        # 只用 2023-2024
train_df = apply_profiles(train_df, profiles)
val_df   = apply_profiles(val_df, profiles)  # val=2025，profiles 仍然来自训练集
```

每个画像是 groupby-median（或 quantile）的 lookup 表。缺失键用全局中位数兜底。画像键名遵循 `prof_{target}_{dimensions}` 约定：
- `shd` = site × hour × weekday
- `sht` = site × hour × tagestyp
- `shm` = site × hour × month
- `shs` = site × hour × season

### 2.3 未来网格的 tagestyp 修复（关键）

`build_future_grid()` 中，未来日期没有真实的 `tagestyp`。v1 简单地 `weekday==7 → s, else w`，导致暑假被当成工作日。v2 使用 `derive_tagestyp()` 从 holiday flags 重建 tagestyp（s>u>w 优先级），对 2023–2025 真实值准确率 99.91%。

### 2.4 未来天气 / 施工

- 天气：未来使用 `(month, hour)` 气候态均值
- 温度：未来回填气候态
- 施工 / 事件：未来未知 → 置 0。**注意**：训练期施工数据本身就是 0（API 无历史数据），所以施工特征重要性 = 0% 是正确的

---

## 3. CatBoost 模型

### 3.1 kfz_h：MultiQuantile 单模型

```python
CatBoostRegressor(
    loss_function="MultiQuantile:alpha=0.1,0.5,0.9",
    iterations=2000, learning_rate=0.02, depth=8,
    l2_leaf_reg=3.0, min_data_in_leaf=50,
    subsample=0.85, rsm=0.8,
    early_stopping_rounds=200, task_type="CPU",
)
```

单模型同时输出 P10/P50/P90。共享树结构自带防分位交叉。推理后施加单调性约束（`P90 ≥ P50 ≥ P10`），再应用 conformal 校准量（`±conf_quantile`）。

### 3.2 sv_h：占比法

```
lkw_ratio = sv_h / kfz_h   →   CatBoostRegressor(loss_function="RMSE")
sv_h_pred = lkw_ratio_pred × kfz_h_p50
```

占比比直接回归绝对量更平稳，且天然约束 `sv_h ≤ kfz_h`。

### 3.3 v_kfz：两段式 + G3

```
speed_drop = prof_v_p85 − v_kfz        （训练目标，截尾 [-20, 60]）
v_kfz_pred = prof_v_p85 − speed_drop_pred
```

**G3 增强**：`kfz_p50_pred` 作为速度模型的输入特征，让模型看到流量预测值，捕捉流量→速度的拥堵关系。需要两阶段训练（先训 kfz → 预测 kfz_p50 → 训 speed）。

```python
CatBoostRegressor(
    loss_function="RMSE",
    iterations=1200, learning_rate=0.02, depth=5,
    l2_leaf_reg=15.0, min_data_in_leaf=200,
    early_stopping_rounds=100, random_strength=1.0, rsm=0.85,
)
```

比流量模型更保守（更浅的树、更强的正则化），因为速度-流量关系简单但噪声大。

---

## 4. 训练 / 验证 / 推理

### 4.1 时序切分

```
训练集: 2023-01-01 ~ 2024-12-31  (210,528 rows)
验证集: 2025-01-01 ~ 2025-12-31  (105,120 rows)
推理:   2026-01-01 ~ 2029-12-31  (420,768 rows)
```

禁止随机划分。画像只用训练集构建。

### 4.2 Split Conformal 校准

验证集（2025）按时间切两半：前半算 `conf_quantile`，后半报 PICP。结果：

- 原始 PICP：**71.4%**
- 校准后 PICP：**81.5%**（诚实 held-out，目标 80%）
- `conf_quantile = +26.3 veh/h`，保存到 `processed/conformal.json`，推理时应用到 P10/P90

### 4.3 2026–2029 推理

`predict_grid()` 函数：
1. 构建 12 站 × 1461 天 × 24h 网格
2. 填入日历特征 → merge conditional（未来天气=气候态，施工/事件=0）
3. `derive_tagestyp()` 重建 tagestyp
4. `apply_profiles()` lookup 画像
5. kfz 预测 → sv_h 预测（ratio × kfz_p50）→ speed 预测（需要 kfz_p50_pred）
6. 应用 conformal 校准
7. 计算 `interval_width`、`relative_interval_width`（置信度）；因子归因单独输出到 `data_autobahn/factor_attribution_daily.csv`

---

## 5. 评估结果（2025 hold-out）

| 指标 | v1 (model.ipynb) | v2 (model_notebook.ipynb) |
|------|-------------------|---------------------------|
| kfz_h MAE | 137.1 veh/h | **135.4** |
| kfz_h RMSE | 238.7 | **235.4** |
| kfz_h MAPE | 16.4% | **16.1%** |
| kfz_h WMAPE | — | **10.7%** |
| sv_h MAE | 24.5 veh/h | **23.7** |
| sv_h MAPE | 20.9% | **19.9%** |
| v_kfz MAE | 5.9 km/h | **5.7** (G3) |
| v_kfz MAPE | 7.5% | **7.3%** |
| PICP (原始) | 69.5% | **71.4%** |
| PICP (校准后) | — | **81.5%** |
| MPIW (校准后) | 365 veh/h | **393** |
| Peak Recall (top10%) | 88.1% | **88.1%** |

---

## 6. 输出格式

### 6.1 预测主表

文件：`data_autobahn/forecast_2026_2029.csv`（420,768 rows × 13 columns）

| 列 | 类型 | 说明 |
|----|------|------|
| `site_id` | str | 站点标识 |
| `road` | str | A8 / A93 |
| `direction` | str | Mch / Sbg / Ro / Kff |
| `site_name` | str | 站点名称 |
| `date` | datetime | 日期 (2026-01-01 ~ 2029-12-31) |
| `hour` | int | 小时 (0–23) |
| `kfz_h_p10` | float | 总流量 P10 (veh/h) |
| `kfz_h_p50` | float | 总流量 P50 (veh/h) |
| `kfz_h_p90` | float | 总流量 P90 (veh/h) |
| `sv_h_pred` | float | 大车流量预测 (veh/h) |
| `v_kfz_pred` | float | 平均车速预测 (km/h) |
| `interval_width` | float | 区间宽度 p90−p10 (veh/h) |
| `relative_interval_width` | float | 归一化不确定性 width/(p50+1) |

> **v3 变更**：`factor_contributions` 列已从主表移除（原 107 MB 超 GitHub 限制）。
> 因子归因改为紧凑的**逐日表** `data_autobahn/factor_attribution_daily.csv`（17,532 行, ~1.2 MB）。

### 6.2 因子归因表

文件：`data_autobahn/factor_attribution_daily.csv`（17,532 rows × 5 columns）

| 列 | 类型 | 说明 |
|----|------|------|
| `site_id` | str | 站点标识 |
| `road` | str | A8 / A93 |
| `direction` | str | Mch / Sbg / Ro / Kff |
| `date` | datetime | 日期 (2026-01-01 ~ 2029-12-31) |
| `factors` | str | 缩略因子贡献，格式 `"TT:76;CA:12;HO:10;WE:2"` |

6 个因子缩略码（按重要性排序）：

| 缩略码 | 因子名 | 含义 |
|--------|--------|------|
| **TT** | Typical Traffic | 历史画像 + 站点位置 — 该站点此时此刻的正常流量水平 |
| **CA** | Calendar | 时刻/星期/月份/季节的周期模式 |
| **HO** | Holiday | 三州学校假期 + 公共假日 + 出发/返程波 |
| **WE** | Weather | 气温/路温/降水/雪/冰/能见度（未来用气候态） |
| **EV** | Events | 特殊活动（Oktoberfest、Salzburg Festival 等） |
| **CO** | Construction | 道路施工 / 2+0 车道配置 |

每行因子按贡献百分比降序排列，只显示 ≥1% 的因子。百分比是小时级消融贡献按 `kfz_h_p50` **流量加权**汇总到天的。详见 `doc/FACTOR_CONTRIBUTIONS.md`。

计算方式：特征组消融（group ablation），轮流清零每个因子组 → 重预测 → |完整 − 消融| = 该组贡献 → 归一化到百分比。覆盖 82 个特征，分配到 6 个因子组（v3 将 Site Location 合并入 Typical Traffic）。

---

## 7. 已知限制

- **最终模型未全量重训**：2025 用于验证，未并入最终交付模型。少用一年数据，对 2024 才上线的 Gletschergarten 站影响较大。
- **施工特征训练信号为零**：训练期无 2+0 样本。即使修复了数据 pipeline bug，API 也没有历史数据。详见 `doc/CONSTRUCTION_DATA_ISSUE.md`。
- **远期为纯条件预测**：天气用气候态、施工/事件未知置 0。预测区间只刻画模型误差，不含未来政策/事故不确定性。

---

## 8. 文件清单

| 文件/目录 | 角色 |
|-----------|------|
| `model/model_notebook.ipynb` | 训练+评估+推理（当前主力） |
| `model/tft.ipynb` | TFT 探索实验（队友） |
| `models/kfz_h/multi.cbm` | 总流量 MultiQuantile 模型 |
| `models/sv_h/lkw_ratio.cbm` | 大车占比模型 |
| `models/v_kfz/speed_drop.cbm` | 速度降速模型 |
| `models/snapshots/` | CatBoost 训练快照 |
| `models/tft/` | TFT checkpoint + 日志 |
| `processed/` | 中间产物（.gitignore，可清空重跑） |
| `data_autobahn/forecast_2026_2029.csv` | 交付预测文件 |
| `doc/MODEL.md` | 项目层面的模型总览 |
| `doc/CONSTRUCTION_DATA_ISSUE.md` | 施工数据问题调查 |
| `clean_outputs.sh` | 一键清除训练输出（重跑前使用） |
