# 小时级交通预测 — 已实现方案 (v4 Final Retrain)

> **对应 notebook**：`model/model_notebook.ipynb`  
> **状态**：v4 Final Retrain 模式 — 全量 2023–2025 训练，周期性抽样验证  
> **推理引擎**：`model/agent_inference.py` — 解耦式按需推理（2027–2029）  
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
                              CatBoost 训练 (2023–2025 full)
                                        ↓
                          ┌─ 2026: notebook Cell 50 预生成 ─────────┐
                          │  forecast_2026_hourly.csv (含 reason 列) │
                          └──────────────────────────────────────────┘
                          ┌─ 2027–2029: agent_inference.py 按需推理 ─┐
                          │  python agent_inference.py --start ...    │
                          └──────────────────────────────────────────┘
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

画像从**训练集**（2023–2025 full，~90% 天）聚合，不触碰验证集，防止泄漏：

```python
profiles = build_profiles(train_df)        # 只用 train_df（~90% 天数，覆盖全季）
train_df = apply_profiles(train_df, profiles)
val_df   = apply_profiles(val_df, profiles)  # val=周期性抽出的 ~10% 天，profiles 仍然来自训练集
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

### 4.1 时序切分（★ v4: 周期性间隔抽样）

**v4 Final Retrain 策略**：全量 2023-01-01 ~ 2025-12-31 数据参与训练，通过周期性抽样产生验证集。

```python
TRAIN_END = pd.Timestamp("2025-12-31 23:59:59")
VAL_EVERY_N = 10    # 每 10 天抽 1 天 → ~10% hold-out
unique_dates = np.sort(base_filtered["date"].unique())
val_dates = unique_dates[::10]
```

- **训练集**：~32,850 天（~315,600 rows）— 覆盖全部 36 个月、所有季节
- **验证集**：~365 天（~35,000 rows）— 均匀分布，每个季节/假期类型/天气模式都参与 Early Stopping
- **推理**：2026-01-01 ~ 2029-12-31 (420,768 rows)

**为什么不用时间切分（如留出 Q4）**：
- 10-12 月缺少夏季出游高峰和春季换季特征 → Early Stopping 会在秋冬季过拟合
- 假日分布不均（有圣诞节但无复活节/暑假）
- 周期性抽样确保每个季节都有 ~10% 的天在验证集，模型在各季节均衡收敛

禁止随机划分（相邻天高度相关会泄漏）。画像只用训练集构建。

### 4.2 Conformal 校准（硬编码泛化量）

因为 2025 年数据已全部并入训练，新的验证集（周期性抽样出的 ~10% 天）算出的 `conf_quantile` 仍是 In-sample 的，会偏窄。

**v4 策略**：**硬编码**前期在 2025 完全 hold-out 实验中测出的泛化扩宽量：

```python
_cq = 23.3   # Hardcoded from 2025 fully held-out calibration
```

- 此值来自 v2/v3 实验：2025 年作为完全独立的 hold-out 年，Split Conformal 测得
- 原始 PICP：**71.4%** → 校准后 PICP：**81.5%**（诚实 held-out，命中 ≥80% 目标）
- 未来重训若特征/模型大改，需重新在独立 hold-out 上测算此值

### 4.3 推理（解耦架构）

**2026 年**：notebook Cell 50 在训练完成后自动生成 `forecast_2026_hourly.csv`（含小时级 `reason` 列），Agent 和前端直接加载。

**2027–2029 年**：由 `agent_inference.py` 按需推理。该脚本离 notebook 独立运行：
1. 加载 3 个 `.cbm` 模型 + 预构建的特征网格 Parquet
2. 对指定日期范围生成小时级预测 + 消融归因
3. 输出格式对齐 2026 年大合表

```bash
# CLI 模式
python agent_inference.py --start 2027-01-01 --end 2029-12-31 --out forecast_2729_hourly.csv

# 作为模块内嵌
from agent_inference import TrafficPredictor
p = TrafficPredictor()
df = p.predict_and_explain("2028-07-04", "2028-07-04")
```

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

### 6.1 2026 年小时级大合表（★ v4 新格式）

文件：`data_autobahn/forecast_2026_hourly.csv`（~105,000 rows × 14 columns）

| 列 | 类型 | 说明 |
|----|------|------|
| `site_id` | str | 站点标识 |
| `road` | str | A8 / A93 |
| `direction` | str | Mch / Sbg / Ro / Kff |
| `site_name` | str | 站点名称 |
| `date` | str | 日期 (2026-01-01 ~ 2026-12-31) |
| `hour` | int | 小时 (0–23) |
| `kfz_h_p10` | int | 总流量 P10 (veh/h) |
| `kfz_h_p50` | int | 总流量 P50 (veh/h) |
| `kfz_h_p90` | int | 总流量 P90 (veh/h) |
| `sv_h_pred` | int | 大车流量预测 (veh/h) |
| `v_kfz_pred` | float | 平均车速预测 (km/h) |
| `interval_width` | int | 区间宽度 p90−p10 (veh/h) |
| `relative_interval_width` | float | 归一化不确定性 width/(p50+1) |
| **`reason`** | str | 🆕 **小时级**因子归因，格式 `"Historical Traffic Baseline: 67.2%；Holiday Effect: 10.7%..."` |

> **v4 变更**：`reason` 列从逐日汇总改为**小时级**输出。Agent 收到每一行数据时自带完整的因子归因解释。
> `reason` 格式对齐原逐日表 — 全名 + 1 位小数百分比 + `%；` 分隔，Agent 已有解析代码无需改动。

### 6.2 逐日汇总表（向后兼容）

文件：`data_autobahn/forecast_2026_daily.csv`（4,380 rows × 13 columns）

| 列 | 类型 | 说明 |
|----|------|------|
| `site_id` | str | 站点标识 |
| `road` | str | A8 / A93 |
| `direction` | str | Mch / Sbg / Ro / Kff |
| `date` | str | 日期 (2026-01-01 ~ 2026-12-31) |
| … | … | 24h 汇总值（流量的 kfz_h_* / sv_h_pred 为 sum，车速/置信度为 mean） |
| `原因` | str | 日级因子归因（流量加权小时消融汇总） |

### 6.3 因子归因（7 组）

| 组名 | 显示名 | 所含特征 |
|------|--------|---------|
| Station & Location | Road Segment and Detector Attributes | site_id, road, direction, site_name, bab_km, longitude, latitude |
| Historical Patterns | Historical Traffic Baseline | prof_kfz_shd, prof_kfz_sht, prof_kfz_shm, prof_kfz_p90, prof_kfz_shs |
| Calendar & Season | Date and Time Pattern | CALENDAR (17 features) + season |
| Holiday Effect | Holiday Effect | HOLIDAY (17) + HOLIDAY_CAT (4) + tagestyp |
| Weather & Road | Weather and Temperature | WEATHER (6) + WEATHER_CAT (1) + TEMP (3) |
| Special Events | Special Events | EVENTS (12) |
| Construction | Construction Impact | CONSTRUCTION (9) |

计算方式：特征组消融（group ablation），轮流清零每个因子组 → 重预测 → |完整 − 消融| = 该组贡献 → 归一化到百分比。温度特征清零时填 `10.0°C`（春秋气候态），避免触发冰雪逻辑。覆盖 82 个特征，分配到 7 个因子组。

---

## 7. 已知限制

- **施工特征训练信号为零**：训练期无 2+0 样本。即使修复了数据 pipeline bug，API 也没有历史数据。详见 `doc/CONSTRUCTION_DATA_ISSUE.md`。
- **远期为纯条件预测**：天气用气候态、施工/事件未知置 0。预测区间只刻画模型误差，不含未来政策/事故不确定性。
- **Conformal 校准量硬编码**：`conf_quantile = 23.3` 来自 2025 hold-out 实验。若未来重训时特征/模型架构大幅改动，需重新在独立 hold-out 上测算。

---

## 8. 文件清单

| 文件/目录 | 角色 |
|-----------|------|
| `model/model_notebook.ipynb` | ★ v4 Final Retrain 训练 + 2026 预生成（主力） |
| `model/agent_inference.py` | ★ 解耦式推理引擎（2027–2029 按需 + CLI） |
| `model/tft.ipynb` | TFT 探索实验（已废弃） |
| `models/kfz_h/multi.cbm` | 总流量 MultiQuantile 模型 |
| `models/sv_h/lkw_ratio.cbm` | 大车占比模型 |
| `models/v_kfz/speed_drop.cbm` | 速度降速模型 |
| `models/snapshots/` | CatBoost 训练快照 |
| `processed/future_grid_2026_2029.parquet` | 全量特征网格（供 agent_inference.py 加载） |
| `processed/future_grid_2027_2029.parquet` | 2027–2029 特征网格（按需推理用） |
| `processed/forecast_2026.parquet` | 2026 预测（二进制快照） |
| `processed/profiles.pkl` | 画像 lookup table |
| `processed/site_meta.parquet` | 站点元信息 |
| `processed/conformal.json` | Conformal 校准值（参考用，实际已硬编码 23.3） |
| `data_autobahn/forecast_2026_hourly.csv` | ★ 2026 小时级大合表（Agent + 前端读取） |
| `data_autobahn/forecast_2026_daily.csv` | 2026 逐日汇总（向后兼容） |
| `doc/MODEL.md` | 项目层面的模型总览 |
| `doc/CONSTRUCTION_DATA_ISSUE.md` | 施工数据问题调查 |
| `clean_outputs.sh` | 一键清除训练输出（重跑前使用） |
