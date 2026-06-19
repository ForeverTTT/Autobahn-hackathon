# 数据目录说明（`data/`）

> Autobahn Hackathon · A8 East / A93 South 走廊历史数据  
> 数据来源：Die Autobahn GmbH des Bundes  
> 时间范围：2023-01-01 至 2026-01-01（部分子集按年切分）

---

## 目录总览

```
data/
├── A8_A93_MQ_locations.csv              # 交通计数站位置元数据
├── Definition_Verhicle_Classes.png      # 车型分类标准图（TLS）
├── 2023-2025_1min_2+0_v/                # 1 分钟粒度交通流量（FG1 · Kurz）
│   └── 2023-2025_1min_2+0_v/
│       └── *.csv                        # 12 个断面 × 方向
├── DAUZ_2+0_1h_2023-2026/               # 1 小时粒度交通流量（FG1 · Lang）
│   └── DAUZ_2+0_1h_2023-2026/
│       └── *.csv                        # 12 个断面 × 方向
└── AirTemp_SurfaceTemp/                 # 气温 & 路面温度（FG3）
    └── lt und fbt/
        ├── Location_LT und FBT_*.csv    # 气象传感器位置
        ├── FG3_WUD_LT_*.csv               # 气温（Lufttemperatur）
        ├── FG3_WUD_FBT_*.csv            # 路面温度（Fahrbahntemperatur）
        └── 2023.png / 2024.png / 2025.png  # 可视化图表
```

| 文件夹 | 大小（约） | 核心用途 |
|---|---|---|
| `2023-2025_1min_2+0_v` | ~1.1 GB | 精细日内曲线、高峰识别、分钟级建模 |
| `DAUZ_2+0_1h_2023-2026` | ~19 MB | 日/小时聚合、快速探索、长期趋势 |
| `AirTemp_SurfaceTemp` | ~73 MB | 天气特征、冬季路面结冰风险 |
| 根目录元数据 | <1 MB | 站点坐标、车型分类对照 |

---

## 通用命名规则

### 文件名结构

以交通数据为例：

```
FG1_Kurz_MQ_Gletschergarten_Kff,DE33,34_agg1min_2023-01-01_bis_2026-01-01.csv
│   │    │  │                │   │         │      └─ 结束日期
│   │    │  │                │   │         └─ 起始日期
│   │    │  │                │   └─ 检测器/车道编号
│   │    │  │                └─ 行驶方向
│   │    │  └─ 计数站名称（Messquerschnitt）
│   │    └─ 数据类型前缀（MQ / MQDZ / MQQ…）
│   └─ Kurz（短周期原始）或 Lang（长周期聚合）
└─ Funktionsgruppe 功能组编号
```

| 片段 | 含义 |
|---|---|
| `FG1` | Funktionsgruppe 1 — 标准交通流量统计 |
| `FG3` | Funktionsgruppe 3 — 气象/环境传感器 |
| `Kurz` | 短周期原始数据（1 分钟） |
| `Lang` | 长周期聚合数据（1 小时） |
| `MQ` | Messquerschnitt，常规定数断面 |
| `MQDZ` | 边境管制（Dosierung）计数断面 |
| `agg1min` / `agg1h` | 按 1 分钟 / 1 小时聚合 |
| `2+0` | TLS 车型分类级别：2 类（Pkw-ähnlich + Lkw-ähnlich），无「未分类」附加类 |

### 方向代码

| 代码 | 含义 | 典型场景 |
|---|---|---|
| `Kff` | 朝 Kiefersfelden 方向 | A93 南下，去阿尔卑斯 |
| `Ro` | 朝 Rosenheim 方向 | A93 北上，返程 |
| `Mch_H` | 朝 München 方向 | A8 西/北向 |
| `Sbg_H` | 朝 Salzburg 方向 | A8 东/南向，去奥地利 |

### 路段代码（`Strecke` 列）

| 代码 | 含义 |
|---|---|
| `A8-Ost_Mch` | A8 东段，慕尼黑侧 |
| `A8-Ost_Sbg` | A8 东段，萨尔茨堡侧 |
| `A93-Sued_Kff` | A93 南段，Kiefersfelden 方向 |
| `A93-Sued_Ros` | A93 南段，Rosenheim 方向 |

### 星期编码（`wochentag`）

`1` = 周一，`2` = 周二，…，`7` = 周日

---

## 根目录文件

### `A8_A93_MQ_locations.csv`

交通计数站（FG1）的**位置元数据**，用于地图标注、断面合并、按 corridor 分组。

**格式**：`;` 分隔

```
site;unit;Funktionsgruppe;Strecke;BAB-Km;Longitude_WGS84;Latitude_WGS84
```

| 列 | 含义 | 示例 |
|---|---|---|
| `site` | 计数站 ID | `MQQ245_Sbg_H` |
| `unit` | 单个检测器/车道单元 | `DETQ245_Sbg_H1` |
| `Funktionsgruppe` | 功能组 | `1` |
| `Strecke` | 所属路段 | `A8-Ost_Sbg` |
| `BAB-Km` | 高速公路公里桩 | `106,27` |
| `Longitude_WGS84` | 经度 | `12.733…` |
| `Latitude_WGS84` | 纬度 | `47.830…` |

### `Definition_Verhicle_Classes.png`

德国 TLS（*Technische Lieferbedingungen für Streckenstationen*）标准下的**车型分类对照图**。

本数据集使用 **`2+0` 分类**（2 类 + 0 附加）：

| 分类 | 德文 | 说明 |
|---|---|---|
| Pkw-ähnlich | 小客车类 | 含 Pkw、Lieferwagen 等 |
| Lkw-ähnlich | 货车类 | 含 Lkw > 3.5t、Busse、Pkw mit Anhänger 等（Schwerverkehr, SV） |

对应 CSV 列：`q_pkw`（小客车类）、`q_lkw`（货车类）、`q_kfz`（合计）。

---

## `2023-2025_1min_2+0_v/` — 1 分钟交通流量

### 文件夹含义

| 部分 | 含义 |
|---|---|
| `2023-2025` | 数据覆盖年份（实际至 2026-01-01） |
| `1min` | 1 分钟时间粒度 |
| `2+0_v` | 2+0 车型分类的数据集版本 |

### 文件列表（12 个 CSV）

| 文件名关键词 | 路段 | 方向 | 说明 |
|---|---|---|---|
| `MQ_Gletschergarten` | A93 | Kff / Ro | Gletschergarten 断面 |
| `MQDZ_Kiefersfelden_(S)` | A93 边境 | Kff / Ro | Kiefersfelden 管制站 |
| `MQDZ_AD Inntal_(S)` | A93 边境 | Kff / Ro | Inntal 管制站 |
| `MQB25_Mch_H` | A8 | Mch_H | km 20 附近 |
| `MQQ37_Sbg_H` | A8 | Sbg_H | km 20 附近 |
| `MQQ209_Mch_H` | A8 | Mch_H | km 93 附近 |
| `MQQ213_Sbg_H` | A8 | Sbg_H | km 95 附近 |
| `MQQ245_Mch_H` | A8 | Mch_H | km 106 附近（边境） |
| `MQQ245_Sbg_H` | A8 | Sbg_H | km 106 附近（边境） |

### 数据格式

**分隔符**：`;`  
**表头**：

```
devices;datum;t_start;wochentag;q_kfz;q_lkw;q_pkw;v_kfz
```

| 列 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `devices` | string | 计数站 + 检测器 ID | `MQ_Gletschergarten_Kff,DE33,34` |
| `datum` | date | 日期（`DD.MM.YYYY`） | `10.08.2025` |
| `t_start` | time | 该分钟起始时刻 | `05:31:00` |
| `wochentag` | int | 星期几（1–7） | `7` |
| `q_kfz` | int | 该分钟总车流量（辆） | `16` |
| `q_lkw` | int | 该分钟货车类车流量 | `3` |
| `q_pkw` | int | 该分钟小客车类车流量 | `13` |
| `v_kfz` | float | 该分钟平均车速（km/h） | `121.5` |

**示例行**：

```
MQ_Gletschergarten_Kff,DE33,34;10.08.2025;05:31:00;7;16;3;13;121.5
```

**缺失值**：`null` — 通常表示该分钟无车辆通过（速度无法计算）或传感器短暂离线。

**行数**：每个文件约 157 万行（3 年 × 365 天 × 1440 分钟）。

### 推荐使用方式

- 聚合为 **hourly**：对 `q_*` 求和，对 `v_kfz` 取加权平均
- 聚合为 **daily**：对 hourly 再求和
- 用于绘制 **24 小时流量曲线**、识别早/晚高峰

---

## `DAUZ_2+0_1h_2023-2026/` — 1 小时交通流量

### 文件夹含义

| 部分 | 含义 |
|---|---|
| `DAUZ` | 德语 *Dauer* 的缩写，表示长周期/持久聚合数据 |
| `2+0` | 同上，2+0 车型分类 |
| `1h` | 1 小时时间粒度 |
| `2023-2026` | 数据覆盖年份 |

### 与 1 分钟数据的关系

- **同一组 12 个断面**，方向一一对应
- 文件名中 `FG1_Lang` 对应 1 分钟数据的 `FG1_Kurz`
- 额外包含站点编号前缀（如 `9629`、`9171`），与 `devices` 列一致
- 体积极小（~19 MB），适合快速 EDA 和日级建模

### 数据格式

**分隔符**：`;`  
**表头**：

```
devices;datum;t_start;wochentag;tagestyp;kfz_h;sv_h
```

| 列 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `devices` | string | 计数站 + 检测器 ID | `9629_MQ_Gletschergarten_Kff,DE33,34` |
| `datum` | date | 日期（`DD.MM.YYYY`） | `01.02.2024` |
| `t_start` | time | 该小时起始时刻 | `07:00:00` |
| `wochentag` | int | 星期几（1–7） | `4` |
| `tagestyp` | char | 日类型 | `w` 或 `s` |
| `kfz_h` | int | 该小时总车流量（辆） | `1508` |
| `sv_h` | float | 该小时平均车速（km/h） | `409` |

**`tagestyp` 取值**：

| 值 | 含义 |
|---|---|
| `w` | Werktag（工作日） |
| `s` | Sonn- und Feiertag（周日及公共假日） |

**示例行**：

```
9629_MQ_Gletschergarten_Kff,DE33,34;01.02.2024;07:00:00;4;w;1508;409
```

**行数**：每个文件约 2.6 万行（3 年 × 365 天 × 24 小时）。

### 推荐使用方式

- 直接用于 **日级/小时级** 交通预测建模
- 与 1 分钟数据交叉校验：`sum(1min q_kfz) ≈ kfz_h`
- 不需要精细日内曲线时的**首选数据源**

---

## `AirTemp_SurfaceTemp/` — 气温与路面温度

### 文件夹含义

气象环境传感器数据（FG3），目前仅包含 **Rosenheim B15n** 一处站点的：

- **LT**（*Lufttemperatur*）：气温
- **FBT**（*Fahrbahntemperatur*）：路面/道面温度

子文件夹 `lt und fbt` = Lufttemperatur und Fahrbahntemperatur。

### 文件列表

| 文件 | 内容 |
|---|---|
| `Location_LT und FBT_AD Rosenheim_B15n.csv` | 传感器位置元数据 |
| `FG3_WUD_LT_AD_Rosenheim_B15n_Sbg_H_agg1min_2023-…csv` | 2023 年气温（按年切分） |
| `FG3_WUD_LT_…_2024-…csv` | 2024 年气温 |
| `FG3_WUD_LT_…_2025-…csv` | 2025 年气温 |
| `FG3_WUD_FBT_…`（同上 3 个年份） | 路面温度 |
| `2023.png` / `2024.png` / `2025.png` | 温度时序可视化 |

> 气象数据按**自然年**切分为 3 个文件（2023、2024、2025），与交通数据的单文件 2023–2026 不同。

### 位置元数据格式

**文件**：`Location_LT und FBT_AD Rosenheim_B15n.csv`

```
site;unit;Funktionsgruppe;Strecke;BAB-Km;Longitude_WGS84;Latitude_WGS84
```

| 列 | 示例 |
|---|---|
| `site` | `WS_GMA_AD_Rosenheim_B15n_Sbg_H` |
| `unit` | `WUD_LT_AD_Rosenheim_B15n_Sbg_H` |
| `Funktionsgruppe` | `3` |
| `Strecke` | `A8-Ost_Sbg` |
| `BAB-Km` | `54,6` |

该站点位于 A8 东段 km 54.6，Rosenheim 附近，萨尔茨堡方向。

### 气温数据格式（LT）

**分隔符**：`;`  
**表头**：

```
t_start;lt
```

| 列 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `t_start` | datetime | 时间戳（`YYYY-MM-DD HH:MM:SS`） | `2023-01-01 00:05:04` |
| `lt` | float | 气温（°C） | `11.3` |

**示例行**：

```
2023-01-01 00:05:04;11.3
```

### 路面温度数据格式（FBT）

**分隔符**：`;`  
**表头**：

```
t_start;fbt
```

| 列 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `t_start` | datetime | 时间戳 | `2023-01-01 00:05:04` |
| `fbt` | float | 路面温度（°C） | `6.4` |

**示例行**：

```
2023-01-01 00:05:04;6.4
```

**行数**：每个年份文件约 52 万行（1 分钟粒度）。

### 推荐使用方式

- 按日期聚合为日均/日最低/日最高温度
- 作为天气特征与交通数据按 `date` join
- 未来预测（2026–2029）应使用**气候态均值**而非真实预报值

---

## 建模建议：如何选择数据集

| 目标 | 推荐数据源 | 聚合方式 |
|---|---|---|
| 日级车流量预测 | `DAUZ_2+0_1h` | 对 `kfz_h` 按日求和 |
| 小时级高峰识别 | `DAUZ_2+0_1h` | 直接使用 hourly |
| 精细日内曲线 | `2023-2025_1min_2+0_v` | 1min → hourly → daily |
| 车型结构分析 | `2023-2025_1min_2+0_v` | 使用 `q_pkw` / `q_lkw` |
| 天气影响 | `AirTemp_SurfaceTemp` | 日均温 join 到 daily 表 |
| 地图/空间分析 | `A8_A93_MQ_locations.csv` | 按 `site` 关联 |

### 标准建模单元（corridor）

建议按 **道路 + 方向** 建立 4 个序列：

```
A8E_out   = A8-Ost  → Salzburg 方向（Sbg_H 系列）
A8E_in    = A8-Ost  → München 方向（Mch_H 系列）
A93S_out  = A93-Süd → Kiefersfelden 方向（Kff 系列）
A93S_in   = A93-Süd → Rosenheim 方向（Ro 系列）
```

同一 corridor 下多个断面的流量可求和或取代表站点。

---

## 数据读取示例（Python）

```python
import pandas as pd

# 1 分钟交通数据
df_1min = pd.read_csv(
    "data/2023-2025_1min_2+0_v/2023-2025_1min_2+0_v/"
    "FG1_Kurz_MQ_Gletschergarten_Kff,DE33,34_agg1min_2023-01-01_bis_2026-01-01.csv",
    sep=";",
    na_values=["null"],
)
df_1min["datetime"] = pd.to_datetime(
    df_1min["datum"] + " " + df_1min["t_start"], format="%d.%m.%Y %H:%M:%S"
)

# 1 小时交通数据
df_1h = pd.read_csv(
    "data/DAUZ_2+0_1h_2023-2026/DAUZ_2+0_1h_2023-2026/"
    "FG1_Lang_9629_MQ_Gletschergarten_Kff,DE33,34_agg1h_2023-01-01_bis_2026-01-01.csv",
    sep=";",
    na_values=["null"],
)

# 气温数据
df_lt = pd.read_csv(
    "data/AirTemp_SurfaceTemp/lt und fbt/"
    "FG3_WUD_LT_AD_Rosenheim_B15n_Sbg_H_agg1min_2023-01-01_bis_2024-01-01.csv",
    sep=";",
    parse_dates=["t_start"],
)

# 站点位置
locations = pd.read_csv("data/A8_A93_MQ_locations.csv", sep=";")
```

---

## 注意事项

1. **`data/` 已在 `.gitignore` 中排除**，不会推送到 Git 远程仓库；克隆后需自行获取数据。
2. **日期格式不统一**：交通数据用 `DD.MM.YYYY`，气象数据用 `YYYY-MM-DD HH:MM:SS`，读取时需分别处理。
3. **`null` 缺失值**：读取时建议 `na_values=["null"]`。
4. **1 分钟数据体积大**（~1.1 GB），处理时注意内存；优先用 hourly 数据做探索。
5. **气象数据仅覆盖一个站点**（Rosenheim B15n），不代表整个走廊；建模时可作参考或需补充外部 DWD 数据。
