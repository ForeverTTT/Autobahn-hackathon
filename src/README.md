# src/ — 训练与推理流水线

这里是模型的完整代码。**按顺序跑 5 条命令就能得到最终预测文件。**

---

## 快速开始

```bash
pip install catboost

# 1. 原始 DAUZ CSV → 每日车流量表
python -m src.data.load_dauz

# 2. 拼装所有特征
python -m src.features.build

# 3. 训练 CatBoost（P10 / P50 / P90 三个分位数）
python -m src.models.catboost_quantile train

# 4. 对 2026-2029 出预测
python -m src.models.catboost_quantile predict 2026-01-01 2029-12-31

# 5. 合并高峰时段 + 颜色等级 → 最终交付文件
python -m src.output.peak_window
python -m src.output.store
```

输出：`processed/forecast.parquet` 和 `processed/forecast.csv`

---

## 模块说明

### `data/load_dauz.py` — 读原始数据

读 `data/DAUZ_2+0_1h_2023-2026/` 里的 12 个 CSV，聚合为每日车流量。

产出两个文件：

| 文件 | 内容 | 行数 |
|---|---|---|
| `processed/daily_corridor.parquet` | 4 个关键节点，每天 4 行（**训练默认用这个**） | ~2,400 |
| `processed/daily_station.parquet` | 全部 12 个测站，每天 12 行（全站模式用） | ~7,200 |

关键列：`date, road, direction, daily_volume, tagestyp, wochentag`

> **tagestyp**：`w`=工作日，`s`=周日/法定节假日，`u`=学校假期高峰日（验证过：`u` 与 DE-BY 学校假期 100% 等价）

---

### `features/build.py` — 拼装特征

读 `daily_corridor.parquet`，合并所有外部数据，产出 `processed/features.parquet`（34 个特征列）。

合并的外部数据（已在 `external/` 下，不需要重新采集）：

| 来源 | 特征 |
|---|---|
| `Autobahn-hackathon/holidays/holiday_dates.csv` | DE-BY / AT-SB / AT-TI 学校假期 + 法定节假日 |
| `external/weather_climatology.parquet` | 历史同期降雨概率、结冰风险、温度均值 |
| `external/construction_daily.parquet` | 当日该走廊是否有施工 / 是否 2+0 |
| `external/special_events_daily.csv` | 节庆影响分数（Oktoberfest 等） |

如果某个文件不存在，对应特征列会填 0，不会报错。

---

### `models/catboost_quantile.py` — 训练 + 推理

同时训练 3 个 CatBoost 模型，对应 P10（低）/ P50（中位）/ P90（高）。

- 训练集：`2024-02-01 → 2025-09-30`
- 验证集：`2025-10-01 → 2025-12-31`
- 模型保存到 `models/catboost_q10.cbm`，`q50.cbm`，`q90.cbm`

训练完打印验证集 MAE，目标 ≤ 10% MAPE。

推理时读 `features.parquet`，过滤指定日期范围，输出 `processed/forecast_<start>_<end>.parquet`。

---

### `output/peak_window.py` — 日内高峰时段

**不训练模型**。直接读历史 DAUZ 小时数据，按 `(测站, 日类型, 星期, 季节)` 分组，计算 24h 流量分布模板，找出累积流量从 25% 到 75% 的时段作为"高峰时段"。

产出：`processed/peak_windows.parquet`

---

### `output/store.py` — 合并输出

把预测结果 + 高峰时段模板 + 颜色阈值合在一起，输出最终 `forecast.parquet`。

**最终输出列：**

```
date, road, direction,
volume_p10, volume_p50, volume_p90,
category,           # green / yellow / orange / red / dark_red
peak_start_hour,    # 高峰开始（小时）
peak_end_hour,      # 高峰结束（小时）
confidence          # high / medium / low
```

颜色等级基于训练集历史分位数（P40/P60/P75/P90），无独立分类器。

---

## 如何扩展到全部 12 个测站

默认只对 4 个关键节点出预测（见 `doc/final_plan.md §0`）。要对全部 12 站出预测：

```bash
python -m src.features.build --corridor-path processed/daily_station.parquet
# 后续 train / predict / store 命令不变
# 模型会自动把 station_label 加入特征
```

---

## 常见报错

| 错误 | 原因 | 解决 |
|---|---|---|
| `KeyError: missing feature column` | features.parquet 某列缺失 | 检查对应外部文件是否存在 |
| `ModuleNotFoundError: catboost` | 没装 | `pip install catboost` |
| `No forecast_*.parquet found` | 没跑 predict | 先跑第 4 步 |
| 训练时 MAE 很大（> 5,000）| 数据量太少或特征有问题 | 先检查 features.parquet 有没有全 NaN 列 |
