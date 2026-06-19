# Autobahn 数据集说明（TUM Science Hackathon 2026）

> 挑战：**Automated Traffic Forecasting for Alpine Holiday Corridors — A8 East & A93 South**
> 主办方：Die Autobahn GmbH des Bundes（NL Südbayern）
> 目标：用历史交通数据 + 公开数据，**自动生成 2026–2029 每天、每方向、分时段的拥堵预测**，取代现在靠专家手工做的交通日历（Fahrkalender）。

---

## 0. 一句话总览

所有数据其实是**同一批 6 个高速测量点、3 年（2023–2025）、双向**的数据，从不同视角呈现。
统一主键 = **站点 × 方向（DE 通道 / Mch·Sbg·Ro·Kff）× 公里桩号 × 时间戳**。

- `locations.csv` = 空间字典（站名 → GPS / 公里）
- `vehicle_classes.png` = 字段字典（流量列 → 车型定义）
- `1min` / `DAUZ` = 输入特征（流量 + 速度）
- 天气 zip = 辅助特征
- Consyst `.7z` 图 = 拥堵标签（ground truth，仅 A8）
- 3 个 PDF = 任务说明

---

## 1. 文件清单与对应内容

### 📄 文档（挑战说明，非数据）

| 文件 | 内容 |
|---|---|
| `2026-06_TUM_Hackathon_Autobahn_Long_presentation.pdf` | **完整版挑战 PPT**：背景、走廊地图、目标、可用数据示例、主办方联系人 |
| `Autobahn.pdf` | 上面 PPT 的精简版（同一套幻灯片）|
| `Autobahn_Challenge_Traffic_Calendar (1).pdf` | **任务书**：背景、5 类用户故事、问题陈述 |

### 🗺️ 参考表（理解数据的字典）

| 文件 | 内容 |
|---|---|
| `A8_A93_MQ_locations.csv` | **测量站点位置表**（分号分隔，德式逗号小数）。字段：`site`(测量断面 MQ) / `unit`(检测器通道) / `Funktionsgruppe` / `Strecke`(路段) / `BAB-Km`(公里桩号) / `Longitude_WGS84` / `Latitude_WGS84`。把数据里的站名钉到地图坐标。|
| `Definition_Verhicle_Classes.png` | **车辆分类定义（德国 TLS 标准）**。`Kfz`=所有机动车，`Pkw`=小客车，`Lkw`=货车，**`SV`=Schwerverkehr 重型车（>3.5t，货车+大巴）**。用来读懂 `q_lkw / q_pkw / sv_h` 等列。|

### 🚗 交通实测数据（核心，来自高速感应线圈）

| 文件/文件夹 | 内容 |
|---|---|
| `2023-2025_1min_2+0_v/`（12 个 CSV，~1.1 GB）| **1 分钟粒度原始数据**。每文件约 157 万行，2023-01-01 → 2025-12-31。列：`devices`(站点) / `datum`(日期) / `t_start`(分钟起点) / `wochentag`(星期1-7) / `q_kfz`(机动车总流量) / `q_lkw`(货车数) / `q_pkw`(小客车数) / `v_kfz`(**平均车速 km/h**)。|
| `2023-2025_1min_2+0_v.zip` | 上面文件夹的压缩原包 |
| `DAUZ_2+0_1h_2023-2026/`（12 个 CSV，~19 MB）| **1 小时聚合数据**（DAUZ = Dauerzählstelle 永久计数站）。每文件约 2.6 万行 = 3 年×每小时。比 1min 多两列：`tagestyp`(**日类型**：`w`=工作日 / `s`=周六 / `u`=周日·节假日)、`kfz_h`(每小时车流)、`sv_h`(每小时重型车流)。**最适合直接拿来做日历式建模。**|
| `DAUZ_2+0_1h_2023-2026.zip` | 上面文件夹的压缩原包 |

> ⚠️ `1min` 的 12 个站和 `DAUZ` 的 12 个站**一一对应**，DAUZ 只是多了 DAUZ 数字前缀（见 §2 表）。两者是同一传感器的「细粒度原始版」vs「粗粒度建模版」。

### 🧊 拥堵可视化图（Consyst Plots，ground truth，仅 A8）

| 文件 | 内容 |
|---|---|
| `2023_ConsystPlots_A8(2).7z` | 2023 **下半年** A8-Ost 每日拥堵时空图 |
| `2023_ConsystPlots_A8(2)/`（已解压，736 张 PNG）| 同上已解压：每张 = 某天 / 某方向(Mch·Sbg) / 某路段(1·2) 的时空速度热力图（X=24 小时，Y=沿路位置，颜色=车速 绿→红，红框 `t=…h`=识别出的拥堵事件）|
| `2024_ConsystPlots_A8(1).7z` | 2024 上半年 A8-Ost 拥堵图 |
| `2024_ConsystPlots_A8(2).7z` | 2024 下半年 A8-Ost 拥堵图 |
| `2025_ConsystPlots_A8.7z` | 2025 全年 A8-Ost 拥堵图 |

> `(1)`/`(2)` = 上半年 / 下半年。**只有 A8，没有 A93。** 可作为预测模型的拥堵标签。

### ☁️ 天气数据（公开数据样例，可选但鼓励）

| 文件 | 内容 |
|---|---|
| `AirTemp_SurfaceTemp.zip` | 解压后在 `lt und fbt/`：**气温 LT（Lufttemperatur）+ 路面温度 FBT（Fahrbahntemperatur）**，1 分钟粒度，2023 / 2024 / 2025 各一文件；外加 3 张年度 PNG 图 + 站点位置 CSV。|

天气站 `WS_GMA_AD_Rosenheim_B15n_Sbg_H` 位于 **A8-Ost km54.6**（在 A8 的 km20 站与 km93 站之间）。位置表显示它其实还测降水(NS/NI)、湿度(RLF)、露点(TPT)、风向风速(WR/WGM)、路面状态(FBZ)等，但本 zip 只给了 LT + FBT。

---

## 2. 6 个物理测量点 × 双向（所有数据的主键映射）

| DAUZ 编号 | 站点（两个方向） | 路 | 公里 | 方向通道 |
|---|---|---|---|---|
| **9171** | MQB25_**Mch** ＋ MQQ37_**Sbg** | A8 | ~20 | Mch=DE33,34,35,36 / Sbg=DE1,2,3,4 |
| **9192** | MQQ209_**Mch** ＋ MQQ213_**Sbg** | A8 | ~93–95 | Mch=DE33,34 / Sbg=DE1,2 |
| **9194** | MQQ245_**Mch** ＋ MQQ245_**Sbg** | A8 | 106 | Mch=DE33,34 / Sbg=DE1,2 |
| **9190** | AD Inntal_**Ro** ＋ _**Kff** | A93 | 1.9 | Ro=DE1,2 / Kff=DE33,34 |
| **9629** | Gletschergarten_**Ro** ＋ _**Kff** | A93 | 12.4 | Ro=DE1,2 / Kff=DE33,34 |
| **9191** | Kiefersfelden_**Ro** ＋ _**Kff** | A93 | 25.0 | Ro=DE1,2 / Kff=DE33,34 |

**方向编码约定（连接数据 ↔ locations.csv 的钥匙）：**
- `DE1,2`(/3,4) 和 `DE33,34`(/35,36) = 同一地点的两个行车方向
- A8：`DE1,2`→**Sbg**（往萨尔茨堡/奥地利），`DE33,34`→**Mch**（往慕尼黑）
- A93：`DE1,2`→**Ro**（往罗森海姆/北），`DE33,34`→**Kff**（往基弗斯费尔登/边境/南）

> ⚠️ 接缝：A8 站名在 `locations.csv` 直接对得上；**A93 站在 locations.csv 里叫 `LVE_8138…` 编码**，靠嵌入编号+公里+纬度对应：LVE_8138**9190**=AD Inntal(km1.9 最北)，LVE_8339**9191**=Kiefersfelden(km25 最南/边境)，中间 km12.4=Gletschergarten。

---

## 3. 空间结构（沿路顺序）

```
A8-Ost（慕尼黑 → 奥地利/萨尔茨堡，公里递增）：
  km20 (9171) → km54.6 ☁️天气站 → km93–95 (9192) → km106 (9194) → 边境

A93-Sued（北 AD Inntal → 南 奥地利边境，公里递增）：
  km1.9 AD Inntal (9190) → km12.4 Gletschergarten (9629) → km25 Kiefersfelden (9191)
```
A93 在 AD Inntal 与 A8 交汇 → 两条路构成一个「度假走廊」。

---

## 4. 时间覆盖

| 数据 | 粒度 | 时间范围 |
|---|---|---|
| `1min` 流量+速度 | 1 分钟 | 2023-01-01 → 2025-12-31（满 3 年）|
| `DAUZ` 流量（含日类型）| 1 小时 | 2023-01-01 → 2025-12-31 |
| 天气 LT/FBT | 1 分钟 | 2023 / 2024 / 2025（分年文件）|
| Consyst 拥堵图 | 每天 1 张 | 2023 下半年（已解压）+ 2024 + 2025 |

---

## 5. 关系总图

```
                         【挑战目标】
            自动生成 2026–2029 每日/每方向/分时段 拥堵预测
                              ▲
                              │ 用历史规律训练
        ┌─────────────────────┴─────────────────────┐
   ── 输入特征 ──                                ── 学习目标/标签 ──
   流量+速度(1min / DAUZ-1h)                  Consyst 拥堵图(A8)
   + 日类型 tagestyp                            + 实测低速时段
   + 天气(温度…可扩展降水/风)
   + (鼓励)节假日/学校假期/边境限流
        │
        └──► 主键：站点(6点) × 方向(DE通道) × 时间戳
                  ↕ locations.csv  站点 → GPS/公里桩号
                  ↕ vehicle_classes.png  流量列 → 车型定义
```

**核心结论：** 这些不是互相独立的数据集，而是同一批 6 个测量点、3 年、双向的数据，用「站名 + DE 方向通道 + 公里桩号 + 时间戳」统一串联。
