# external/ — 外部数据

这里的文件都是**已经采集好的**，直接读取即可，不需要重跑采集脚本。

---

## 文件清单

### 天气数据（来源：Open-Meteo 历史 API，AD Rosenheim 站）

**`weather_daily.parquet`** — 2018-01-01 到 2025-12-31，每天一行，共 2,922 行

| 列名 | 说明 |
|---|---|
| `date` | 日期 |
| `precip_mm` | 当日降水量（mm） |
| `snowfall_mm` | 当日降雪量（mm，水当量） |
| `low_vis_hours` | 当日低能见度小时数（低云量 ≥ 85% 的小时数，作为雾天代理） |
| `t_min_c` | 当日最低气温（°C） |
| `t_max_c` | 当日最高气温（°C） |
| `has_ice_risk` | bool，当日是否有结冰风险（降雪 > 0 或气温 < 0） |

**`weather_climatology.parquet`** — 按 day-of-year (1-366) 汇总的历史均值，共 366 行

| 列名 | 说明 |
|---|---|
| `doy` | 一年中第几天（1-366） |
| `precip_prob_wet` | 历史同期降雨概率（0-1） |
| `ice_risk_prob` | 历史同期结冰风险概率（0-1） |
| `low_vis_prob_foggy` | 历史同期低能见度概率（0-1） |
| `t_min_c_mean` | 历史同期最低气温均值（°C） |
| `t_max_c_mean` | 历史同期最高气温均值（°C） |

> **为什么用气候态而不是真实预报天气？**
> 因为我们要预测 2026-2029，不可能提前知道真实天气。气候态（历史同期均值）是合理的替代——它捕捉了"7 月一般比 1 月暖"这类季节规律。

> **注意**：Open-Meteo 对此区域不提供能见度数据，改用低云量（cloud_cover_low）作为雾天代理。

---

### 施工数据（来源：verkehr.autobahn.de API）

**`construction_sites_clean.csv`** — 每条施工项目一行，字段包括：road, title, km_start, km_end, is_2_plus_0, start_date, end_date 等

**`construction_daily.parquet`** — 按日期 × 走廊展开，每行一个 (date, road) 组合

| 列名 | 说明 |
|---|---|
| `date` | 日期 |
| `road` | `A8_Ost` 或 `A93_Sued` |
| `is_construction_active` | bool，当日该走廊是否有任何施工 |
| `is_2_plus_0_active` | bool，当日是否有 **2+0** 施工（对向借道，通行能力减约 50%） |

**当前已知的真 2+0 施工（截至 2026-06-20）：**

| 路段 | 走廊 | 开始 | 结束 |
|---|---|---|---|
| Eulenauer Filz — Im Moos | A8_Ost | 2025-08-27 | 2027-07-03 |
| Übersee — Grabenstätt | A8_Ost | 2026-03-21 | 2026-10-30 |
| Prien — Bernau am Chiemsee | A8_Ost | 2026-05-09 | 2026-07-13 |
| Rosenheim — Rohrdorf | A8_Ost | 2026-07-01 | 2026-07-17 |
| Reischenhart — Nicklheim | A93_Sued | 2026-04-18 | 2026-09-14 |
| Kirnstein — Wildbarren | A93_Sued | 2026-06-18 | 2026-06-27 |

> 2027-2029 的施工项目尚未在 API 中录入，该段的 `is_2_plus_0_active` 为 False。实际施工计划出来后需手动更新。

---

### 节庆数据（手工整理）

**`special_events_periods.csv`** — 每个节庆活动的日期段（约 70 行）

**`special_events_daily.csv`** — 按日期 × 走廊展开（约 1,859 行）

| 列名 | 说明 |
|---|---|
| `date` | 日期 |
| `event_name` | 活动名称 |
| `city` | 所在城市 |
| `impact_level` | `high` / `med` / `low` |
| `affects_a8_ost` | bool |
| `affects_a93_sued` | bool |
| `day_position` | `start` / `mid` / `end`（节庆的第几天） |
| `is_weekend` | bool |
| `status` | `confirmed`（年年有的固定节庆）/ `estimated`（估算日期） |

覆盖的活动：Oktoberfest、Frühlingsfest、Tollwood（夏/冬）、Salzburger Festspiele、Mozartwoche、Salzburger Christkindlmarkt、Rosenheimer Herbstfest、Rosenheimer Sommerfestival、Kufsteiner Operettensommer。

---

## 使用方式

训练代码（`src/features/build.py`）会自动读取这些文件并 join 到特征矩阵里。如果某个文件不存在，对应特征会填 0 而不会报错。

不要直接修改这些文件——如果需要更新施工数据，重跑 `python scripts/fix_construction_data.py`；如果需要更新节庆数据，编辑 `scripts/build_special_events.py` 里的 `EVENTS` 列表再重跑。
