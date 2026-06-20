# Autobahn 交通预测 — 技术方案

> **范围**：A8 East 和 A93 South 两条走廊，覆盖 2026-01-01 → 2029-12-31 每一天。
> **目标**：在 Hackathon 内做出可 demo 的端到端预测系统，对齐 Challenge 的 5 个用户故事和 5 条评分标准（plausibility, relevance, transparency, applicability, innovation）。
>
> 相关文档：
> - [CLAUDE.md](../CLAUDE.md) — 数据字典与字段说明
> - [docs/station_reliability_report.md](station_reliability_report.md) — 传感器可用性分析
> - [analysis_output/hypothesis_summary.md](../analysis_output/hypothesis_summary.md) — 关键假设实测结果
> - [analysis_output/station_map.png](../analysis_output/station_map.png) — 路网与测站位置图

---

## 0. 摘要

Challenge 要求：每日车流量估计 + 典型日内模式（早/午高峰）。颜色等级和置信度是 bonus。所以**核心输出三件**：① 日总车流量（含区间）；② 日内高峰时段；③ 颜色等级。

**关键节点**（4 个，每条走廊各 2 个方向选代表测站）：

| Corridor | 方向 | 代表测站 | 位置 |
|---|---|---|---|
| A8-Ost | outbound（→ Salzburg） | `MQQ37_Sbg_H` (km 20) | 慕尼黑入口 |
| A8-Ost | inbound（→ München） | `MQQ209_Mch_H` (km 93) | A8 中段 |
| A93-Süd | outbound（→ Kufstein） | `MQDZ_AD_Inntal_(S)_Kff` | A8×A93 分叉口 |
| A93-Süd | inbound（→ Rosenheim） | `MQDZ_AD_Inntal_(S)_Ro` | 同上 |

> 这 4 个测站的可靠性均属 Gold/Reliable 级（详见可靠性报告），位于用户最关注的入口/分叉处。
> 如需对全部 12 个测站出预测，只需在训练时用 `daily_station.parquet` 替换 `daily_corridor.parquet`（代码已预留接口，见 §7）。

**模型**：CatBoost 三分位回归（P10/P50/P90）。

**输出 schema**（最终交付的 `processed/forecast.parquet`）：

```
date            日期
road            走廊 (A8_Ost / A93_Sued)
direction       方向 (outbound / inbound)
volume_p10      日总车流量下界（10th percentile）
volume_p50      日总车流量预测中位数
volume_p90      日总车流量上界（90th percentile）
category        颜色等级 green / yellow / orange / red / dark_red
peak_start_hour 高峰时段开始（小时，0-23）
peak_end_hour   高峰时段结束（小时，0-23）
confidence      预测置信度 high / medium / low
```

---

## 1. 已完成工作 / 队友分工

| 任务 | 状态 | 产物 |
|---|---|---|
| DAUZ 小时数据可靠性分析 | ✅ 完成 | `docs/station_reliability_report.md`, `analysis_output/*.png` |
| 路网与测站位置可视化 | ✅ 完成 | `analysis_output/station_map.png` |
| 数据假设验证（速度上限、`tagestyp`、日内曲线粒度） | ✅ 完成 | `analysis_output/hypothesis_summary.md` |
| 天气数据采集（降水 / 低能见度代理 / 结冰风险） | ✅ 完成 | `external/weather_daily.parquet`, `external/weather_climatology.parquet` |
| Munich/Salzburg/Rosenheim/Kufstein 节庆日历 | ✅ 完成 | `external/special_events_daily.csv` |
| 施工数据 bug 修复（2+0 判别 + 正确归属 + 结束日期） | ✅ 完成 | `external/construction_daily.parquet`, `external/construction_sites_clean.csv` |
| 训练代码骨架 | ✅ 完成 | `src/` 下 5 个模块 |
| 队友：DAUZ 小时表整理与对齐 | 🟡 进行中 | 队友输出的 daily 表 |
| 队友：DE-BY/AT-SB/AT-TI 假期日历 | ✅ 已可用 | `Autobahn-hackathon/holidays/holiday_dates.csv` |

---

## 2. 数据假设验证

> **完整结果**：`analysis_output/hypothesis_summary.md`；**脚本**：`scripts/validate_data_hypotheses.py`

### 术语说明（给没看过原始数据的队友）

| 术语 | 含义 |
|---|---|
| `v_kfz` | 每分钟检测到的所有车辆的平均速度（km/h），来自 1-min 原始数据 |
| `tagestyp` | DAUZ 小时表自带的日类型标签：`w`=工作日, `s`=周日/法定节假日, `u`=度假高峰日（Urlaub） |
| `sv_h` | DAUZ 小时表中每小时重型车辆数（Schwerverkehr，>3.5t），单位 辆/时 |
| `q_lkw` | 1-min 原始表中每分钟卡车数，可汇总到小时级 |
| CV（变异系数） | 标准差 / 均值，反映组内波动大小。CV 越低 = 同一组内各天的曲线形状越接近 |
| DE-BY | Bayern（巴伐利亚，慕尼黑所在州）学校假期 |
| AT-SB | Salzburg（萨尔茨堡）学校假期 |
| AT-TI | Tirol（蒂罗尔，Kufstein 所在州）学校假期 |

### 验证结论

| # | 假设 | 实测 | 结论 |
|---|---|---|---|
| H1 | v_kfz 最大值 250 是传感器噪声 | p99=155.5 km/h, p99.9=173, p99.99=198 | **cap 在 180 km/h** |
| H2 | sv_h 与 q_lkw 差别很大 | r=0.985，比例中位数=0.94 | **两者在日级几乎可互换**；训练统一用 sv_h |
| H3 | `tagestyp=='u'` 不等同于 DE-BY 学校假期 | 152/152 个 'u' 天全部落在 DE-BY 学校假期内，无一例外 | **完全等价**；`tagestyp` 可直接作强特征 |
| H4 | 日内 24h 曲线按 (tagestyp, weekday) 分组效果如何 | CV=17.3% | 组内波动较大，可用但不精 |
| H4 | 加 **month（月份）** 维度 | CV=10.5% | **推荐分组** |
| H4 | 换成 holiday_edge（节前/节后）维度 | CV=16.9% | 无改善，放弃 |

> **H4 补充说明**：`peak_window.py` 实现时用了 **season**（4 个季节）而不是 month（12 个月），目的是保证每个组内有足够的训练天数（month 分组后每格只有约 15 天，season 约 60 天）。season 的 CV 略高于 month，但分组稳健性更好。

---

## 3. 数据合约（5 个 parquet）

下游模型只读这 5 个文件：

```
processed/daily_corridor.parquet      # 训练标签（日总车流量）
  → date, road, direction, daily_volume, sv_share, tagestyp, wochentag

processed/features.parquet            # 模型直接输入（=上面 + 所有工程特征）
  → date, road, direction, daily_volume, [34 个特征列]

processed/intraday_templates.parquet  # 24h 流量比例模板
  → station_label, tagestyp, wochentag, season, hour, share_mean

processed/peak_windows.parquet        # 高峰时段查表
  → station_label, tagestyp, wochentag, season, peak_start_hour, peak_end_hour

processed/forecast.parquet            # 最终交付（schema 见 §0）
```

外部数据（已落地，不需要重新采集）：

```
external/weather_climatology.parquet     # 366 个 doy × 8 列（历史均值，非实时）
external/construction_daily.parquet      # 每日施工状态 (date, road)
external/special_events_daily.csv        # 节庆影响分数 (date, road)
Autobahn-hackathon/holidays/holiday_dates.csv  # 假期日历（队友维护）
```

---

## 4. 模型：CatBoost 三分位回归

### 4.1 选型理由

**CatBoost** 是梯度提升树的一种实现，原生支持分类特征（road/direction/season），不需要手动 one-hot 编码。

**三分位回归**（Quantile Regression）：同时训练三个模型，分别对应 P10（乐观）、P50（中位预测）、P90（悲观），直接输出预测区间而不只是点估计。这比事后加 ±x% 更可靠，因为区间宽度会随着特征不确定性自动变化。

> 对比：TFT（Temporal Fusion Transformer）理论上更强，但训练复杂、超参敏感、数据量需求更大。我们的训练集只有约 2,400 行（4 个 corridor × ~600 天），CatBoost 在这个规模上更稳定，且训练时间在分钟级而非小时级。

### 4.2 训练数据准备

```
训练集：2024-02-01 → 2025-09-30（~600 天 × 4 corridor = ~2,400 行）
验证集：2025-10-01 → 2025-12-31（92 天 × 4 = 368 行）
标签：daily_volume（代表测站当日 kfz_h 之和）
清洁窗口：2024-02 起（Gletschergarten 2024-02 前未安装，不可用）
```

注意：训练集规模较小（~2,400 行），因此特征工程的质量比模型复杂度更重要。

### 4.3 特征列表（34 列）

```
# 走廊身份（分类特征）
road, direction

# 日历周期（数值 + 周期编码）
dow              # day-of-week，0=周一，6=周日
month            # 1-12
doy              # day-of-year，1-365
is_weekend       # 是否周末（周六或周日）
is_friday        # 是否周五（出行高峰前夜）
is_saturday      # 是否周六
is_sunday        # 是否周日
dow_sin, dow_cos      # 周期编码，避免 6→0 的不连续跳跃
month_sin, month_cos  # 同上
doy_sin, doy_cos      # 同上
season           # winter/spring/summer/autumn（分类特征）

# 假期（最强特征组）
is_school_holiday_DE_BY  # DE-BY 学校假期（= tagestyp 'u'，H3 验证）
is_school_holiday_AT_SB  # 萨尔茨堡学校假期
is_school_holiday_AT_TI  # 蒂罗尔学校假期
is_public_holiday_DE_BY  # DE-BY 法定节假日
is_public_holiday_AT_SB  # 萨尔茨堡法定节假日
is_public_holiday_AT_TI  # 蒂罗尔法定节假日
holiday_overlap_count    # 上述 6 个 flag 之和（同时重叠的假期数量）
days_to_holiday_start_DE_BY    # 距下一个假期开始天数（上限 60）
days_since_holiday_end_DE_BY   # 距上一个假期结束天数（上限 60）
is_school_start_day_DE_BY      # 是否 DE-BY 假期第一天
is_school_end_day_DE_BY        # 是否 DE-BY 假期最后一天

# 天气气候态（不是未来实况，是历史同期均值）
precip_prob_wet      # 历史同日期降雨概率（0-1）
ice_risk_prob        # 历史同日期结冰风险概率（0-1）
low_vis_prob_foggy   # 历史同日期低能见度概率（0-1）
t_min_c_mean         # 历史同日期最低气温均值（°C）
t_max_c_mean         # 历史同日期最高气温均值（°C）

# 施工
is_construction_active  # 该走廊当日是否有施工
is_2_plus_0_active      # 是否为 2+0 施工（对向借道，通行能力减半）

# 节庆
event_score          # 该走廊当日节庆影响分（高 3 / 中 2 / 低 1 之和）
any_event_high_impact  # 是否有高影响节庆
```

分类特征（CatBoost 需要指定）：`road, direction, season`。
如果使用全站模式（`daily_station.parquet`），还会自动加入 `station_label`。

> 未纳入的特征及理由：NL/IT/HR/CZ 假期（信号弱，且数据尚未整理）；Dosierung（奥方单日交通管制，无历史记录可学）；`is_first_saturday_of_holiday`（可通过 `dow + days_to_holiday_start` 让模型自己学到）。

### 4.4 训练设置（`src/models/catboost_quantile.py`）

| 参数 | 值 | 说明 |
|---|---|---|
| loss_function | `Quantile:alpha=0.1/0.5/0.9` | 三个模型各训一个分位数 |
| iterations | 2000 | 最大轮数，配合早停实际会更少 |
| learning_rate | 0.05 | 较小的学习率配合早停 |
| depth | 6 | 树深度 |
| early_stopping_rounds | 100 | 验证集 100 轮无改善即停 |
| random_seed | 42 | 可复现 |
| eval_set | val pool | 在验证集上做早停，防止过拟合 |

模型存于 `models/catboost_q10.cbm`, `catboost_q50.cbm`, `catboost_q90.cbm`。

### 4.5 潜在问题与 TODO

**已知风险：**

| 问题 | 影响 | 缓解方案 |
|---|---|---|
| 训练集只有 ~2,400 行，远小于典型 ML 任务 | 过拟合风险 | 早停 + 减少特征到最强核心子集；先看验证集 MAE |
| `processed/features.parquet` 可能有 NaN | 训练时报错 | `_ensure_features()` 里已做检查；数值列手动 `fillna(0)` |
| 分位数交叉（P90 < P50 的情况） | 输出不合理 | 推理后加一行 `p90 = max(p90, p50)`，`p10 = min(p10, p50)` |
| 队友 daily 表 schema 与合约不一致 | `build_features` 报 KeyError | 写 5 行适配函数对齐列名，不要改他们源数据 |
| 验证集仅 92 天（秋季） | 评估可能乐观 | 加一个留一季交叉验证（可选） |

**待完成（训练前必须确认）：**

- [ ] 跑 `python -m src.data.load_dauz`，检查 `processed/daily_corridor.parquet` 行数和 schema
- [ ] 跑 `python -m src.features.build`，检查 34 列是否全部有效，无全 NaN 列
- [ ] 安装 catboost：`pip install catboost`
- [ ] 跑 `python -m src.models.catboost_quantile train`，查看验证集 MAE
- [ ] 做 sanity check：暑假周六的 P50 应明显大于一月工作日的 P50

**训练后 sanity check 的参考量级（来自历史数据均值）：**

| 日类型 | 预期日车流（代表站，MQQ37 outbound） |
|---|---|
| 夏季周六（Urlaub） | ~30,000–40,000 辆/天 |
| 冬季工作日 | ~15,000–20,000 辆/天 |
| 法定节假日 | ~25,000–35,000 辆/天 |

（上面数字仅为量级参考，实际验证请对比历史数据均值。）

---

## 5. 日内高峰时段（模板方法）

**不训练第二个模型。**

基于 H4 实测结论，按 `(station, tagestyp, dow, season)` 4 维分组，在历史 DAUZ 小时数据上计算 24h 流量比例模板。**高峰时段 = 累积流量从 25% 到 75% 的时段**（"中央 50% 时段"）。

实现：`src/output/peak_window.py`（独立于模型，直接读原始 DAUZ CSV）。

典型高峰时段（根据 DAUZ 日类型分布）：

| 日类型 | 典型高峰时段 | 原因 |
|---|---|---|
| `w`（工作日） | 06:00–08:00 + 16:00–18:00 | 早晚通勤双峰 |
| `s`（周日/节假日） | 10:00–17:00 | 休闲出行单峰，中午最高 |
| `u`（度假高峰日） | 09:00–16:00 | 度假客人早于通勤者出发 |

---

## 6. 颜色等级与置信度

### 颜色等级

基于各走廊历史分位数，无独立分类器：

```
green:    < P40（低于历史 40% 分位数）
yellow:   P40–P60
orange:   P60–P75
red:      P75–P90
dark_red: > P90（超过历史 90% 分位数）
```

分位数从训练集计算，每条 (road, direction) 独立，存于 `src/output/store.py`。

### 置信度

```
rel_width = (P90 - P10) / P50      # 相对区间宽度
days_ahead = 预测日 - 今天

high:   rel_width < 0.20 且 days_ahead < 365
medium: rel_width < 0.35 或 days_ahead < 730
low:    其他
```

---

## 7. 代码结构与端到端命令

### 目录结构

```
src/
├── data/
│   └── load_dauz.py         # DAUZ CSV → daily_corridor.parquet / daily_station.parquet
├── features/
│   └── build.py             # 拼装 features.parquet（加假期/天气/施工/节庆）
├── models/
│   └── catboost_quantile.py # 训练 + 推理（P10/P50/P90）
└── output/
    ├── peak_window.py       # 日内 24h 模板 → peak_windows.parquet
    └── store.py             # 合并出最终 forecast.parquet

scripts/                     # 一次性数据采集脚本（已跑完，不需要重跑）
├── fetch_weather.py
├── build_special_events.py
├── fix_construction_data.py
├── plot_station_map.py
└── validate_data_hypotheses.py
```

### 端到端命令（按顺序）

```bash
# Step 0: 安装依赖（仅首次）
pip install catboost

# Step 1: 数据流水线
python -m src.data.load_dauz        # → processed/daily_corridor.parquet + daily_station.parquet
python -m src.features.build        # → processed/features.parquet

# Step 2: 训练（约 5-10 分钟）
python -m src.models.catboost_quantile train

# Step 3: 推理 + 输出
python -m src.models.catboost_quantile predict 2026-01-01 2029-12-31
python -m src.output.peak_window    # → processed/peak_windows.parquet
python -m src.output.store          # → processed/forecast.parquet + forecast.csv
```

### 如何切换到全站模式（12 个测站各自出预测）

```bash
# 把 daily_station.parquet 当作训练基础（而非 daily_corridor.parquet）
python -m src.features.build --corridor-path processed/daily_station.parquet
# 其余命令不变；模型会自动识别 station_label 列并将其加入特征
```

---

## 8. 待办与时间估算

### 立即可做（不依赖队友合表）

- [ ] **T1** 安装依赖：`pip install catboost streamlit` （5 min）
- [ ] **T2** 跑 `src/data/load_dauz.py`，确认 `daily_corridor.parquet` 列对齐（15 min）
- [ ] **T3** 跑 `src/features.build.py`，确认无 NaN 列（10 min）

### 训练日（Day 1 下午）

- [ ] **M1** 跑 `catboost_quantile train`，检查验证集 MAE（目标 MAPE ≤ 10%，30 min）
- [ ] **M2** 跑 `predict 2026-2029`，做 sanity check（15 min）
- [ ] **M3** 跑 `peak_window` + `store`，得到 `forecast.parquet`（10 min）

### 展示层（Day 2）

- [ ] **U1** Streamlit 月历 UI：按月铺格子，颜色 = category，hover 显示 P10/P50/P90（2 h）
- [ ] **U2** 单日详情：volume bar + 24h profile 曲线（1 h）
- [ ] **U3** 用户视角切换（旅客/居民/物流/管理）：本质是按 confidence/category 过滤（1 h）

### 可选提升

- [ ] **S1** SHAP top-3 特征解释（CatBoost 自带，约 10 行代码）
- [ ] **S2** 混淆矩阵 / 覆盖率检查：验证集上 P10–P90 实际覆盖率应接近 80%
- [ ] **S3** 加 NL/IT 假期特征（如果队友有数据）

---

## 9. 风险登记

| 风险 | 概率 | 缓解 |
|---|---|---|
| 队友 daily 表 schema 不一致 | 中 | 写适配函数对齐列名 |
| CatBoost MAE 过大（>15%） | 低 | 先用 dow/month/holiday_overlap 做 baseline；再加特征 |
| NaN 导致训练报错 | 中 | 在 `_ensure_features` 里加 `fillna(0/missing)` |
| Streamlit 没时间完成 | 中 | 退回静态 HTML（forecast.csv → matplotlib 月历） |
| 分位数交叉（P10 > P50） | 低 | 推理后加一行排序修正 |

---

## 10. 给评委的一句话定位

> 我们用 4 个关键节点的 2024-25 历史车流量，叠加跨州学校假期、实测施工 2+0 标志、节庆日历和 8 年气候态天气，训练 CatBoost 三分位回归，输出 2026-2029 每天 4 个方向的 P10/P50/P90 车流量、绿→深红等级和高峰时段，全部带置信度；专家规则被可解释的特征工程取代，公共部门拿到的不是一个黑箱数字，而是"为什么这天红"。
