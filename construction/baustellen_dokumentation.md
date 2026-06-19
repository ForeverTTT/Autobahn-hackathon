# 🚧 A8 Ost & A93 Süd — 施工数据完整文档

> **项目**: Autobahn Traffic Forecasting — TUM Science Hackathon 2026
> **数据获取日期**: 2026-06-19
> **目标走廊**: A8 Ost (München ↔ Salzburg) & A93 Süd (Rosenheim ↔ Kufstein)

---

## 目录

1. [数据来源总览](#一数据来源总览)
2. [A8 Ost 当前施工现场](#二--a8-ost-münchen--salzburg-当前施工现场--api-实时数据)
3. [A93 Süd 当前施工现场](#三--a93-süd-rosenheim--kufstein-当前施工现场)
4. [夏季 2026 关键拥堵窗口](#四-夏季-2026-6-8月--关键拥堵窗口)
5. [车道配置分类法 (Verkehrsführung)](#五车道配置分类法-verkehrsführung)
6. [已知未来规划项目](#六-已知未来规划项目)
7. [生成的数据文件](#七-生成的数据文件)
8. [Python 工具脚本](#八-python-工具脚本)
9. [历史数据缺口与解决方案](#九-历史数据缺口与解决方案)
10. [对交通预测模型的关键启示](#十-对交通预测模型的关键启示)
11. [附录：原始 API 数据样例](#附录原始-api-数据样例)

---

## 一、数据来源总览

| 来源 | 类型 | 覆盖范围 | 访问方式 |
|------|------|----------|----------|
| **bund.dev Autobahn API** (`verkehr.autobahn.de`) | 实时/近期 Baustellen | 当前 ~2029 | 免费, 无需API Key, REST |
| **IHK Verkehrsausschuss Rosenheim** (2024-02-08) | 规划/政策 | 中长期规划 | PDF 会议纪要 |
| **Regierung von Oberbayern** Planfeststellungsbeschluss | 法定批复 | A8 6-streifiger Ausbau | 公开 PDF |
| **ASFINAG / BMIMI** (奥地利) | 跨境影响 | A10 连接走廊 | 新闻稿 + 项目页面 |
| **Mobilithek** (BASt / Autobahn GmbH) | DATEX2 实时 | 当前 (3-Minuten-Takt) | Push/Pull, SOAP, 需注册 |

### bund.dev API 端点

```
基础URL: https://verkehr.autobahn.de/o/autobahn/
├── /                          → 所有道路列表
├── /{roadId}/services/roadworks  → 施工现场
├── /{roadId}/services/closures   → 完全封闭
├── /{roadId}/services/warnings   → 交通警告
├── /{roadId}/services/webcams    → 摄像头
└── /{roadId}/services/parking    → 停车场

我们的目标:
  https://verkehr.autobahn.de/o/autobahn/A8/services/roadworks
  https://verkehr.autobahn.de/o/autobahn/A93/services/roadworks
```

### API 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `identifier` | string | 唯一施工ID (如 `2025-041538--vi-bs...`) |
| `title` | string | 路段名称 (如 `A8 \| Eulenauer Filz - Im Moos`) |
| `subtitle` | string | 方向 (如 `München -> Salzburg`) |
| `display_type` | string | `ROADWORKS` (长期) 或 `SHORT_TERM_ROADWORKS` (短期、warnkegel图标) |
| `coordinate` | {lat, long} | 施工起点GPS坐标 |
| `extent` | string | `"lat1,lon1,lat2,lon2"` 范围 |
| `startTimestamp` | ISO8601 | 开始时间 |
| `impact.symbols` | string[] | 车道配置符号 (关键!) |
| `impact.lower` | string | 下游参考点 |
| `impact.upper` | string | 上游参考点 |
| `impact.length` | number? | 施工长度 (km, 可能为null) |
| `impact.maxSpeed` | number? | 最高限速 (km/h) |
| `impact.maxWidth` | number? | 最大通行宽度 (m) |
| `description` | string[] | 人类可读描述 (含时间、位置、工作类型) |
| `future` | boolean | 是否为未来计划 |
| `isBlocked` | boolean | 是否完全阻断 |

---

## 二、🔥 A8 Ost (München ↔ Salzburg) 当前施工现场 — API 实时数据

**A8 Ost 有 5 组共 9 个 API 条目 (每组对应两个方向), 全部是 2+0 双向共用路基模式。**

### 2.1 Eulenauer Filz – Im Moos 🚨🚨🚨

```
API ID:      2025-041538 / 2025-041540 (双向各一个条目)
时间:        2025-08-27 → 2027-07-03
持续:        22 个月 (接近两年!!)
方向:        München → Salzburg / Salzburg → München 双方向
车道配置:    0 条本方向车道 + 3 条对向车道 (Vollsperrung Richtungsfahrbahn)
             ── München→Salzburg 方向车道完全封闭 ──
             全部交通通过 Salzburg→München 车道双向通行
限速:        未明确 (典型 60-80 km/h)
最大宽度:    11 m
GPS:         47.8217°N, 11.9771°E
KM估计:      90.5 – 95.0 (靠近 MQQ209 km 93.38 和 MQQ213 km 94.75)
工作类型:    Fahrbahnerneuerung / Erhaltung
附近测站:    MQQ209, MQQ213

描述:
    这是整个 A8 Ost 目标走廊中影响最大、持续时间最长的施工项目。
    从 2025 年 8 月到 2027 年 7 月，München→Salzburg 方向的主车道
    完!全!封!闭!。所有双向交通被迫挤在对向车道上。
    跨越 2026 和 2027 两个完整的夏季旅游高峰。
```

### 2.2 Übersee – Grabenstätt 🚨🚨

```
API ID:      2026-03xxxx (双向两个条目)
时间:        2026-03-21 → 2026-10-30
持续:        7.3 个月
方向:        München → Salzburg / Salzburg → München 双方向
车道配置:    2 条本方向 + 2 条对向车道 = 4 条车道双向共用一条路基 (2+2 bidirektional)
限速:        未明确 (典型 60-80 km/h)
GPS:         ~47.8°N, 12.3°E
KM估计:      82.0 – 88.0
工作类型:    Fahrbahnerneuerung (Langzeitbaustelle)

描述:
    长期 2+2 双向交通。3月底到10月底，完整覆盖整个 Sommerreisesaison 2026。
    这是通往萨尔茨堡边境前的最后一个长施工段之一。
    容量减少约 50-60%。
    注意: 10月30日结束日期恰好覆盖了 Herbstferien (秋假) 结束。
```

### 2.3 Prien – Bernau am Chiemsee 🚨

```
API ID:      2026-03xxxx (双向两个条目)
时间:        2026-05-09 → 2026-07-13
持续:        2.1 个月
方向:        München → Salzburg / Salzburg → München 双方向
车道配置:    2 条本方向 + 2 条对向车道 = 4 条双向共用 (2+2 bidirektional)
GPS:         ~47.8°N, 12.3°E
KM估计:      70.0 – 76.0
工作类型:    Fahrbahnerneuerung / Lärmschutz

描述:
    位于 A8 规划中的 6-streifiger Ausbau 路段 (Achenmühle – Bernauer Berg) 内。
    5月初到7月中旬。Pfingstferien (五旬节假期) 和 Sommerferien 初期受影响。
    注意与 #2.2 Übersee-Grabenstätt 的叠加效应：两者在 5-7月同时活跃！
```

### 2.4 Bad Reichenhall – Schwarzbach 🚨

```
API ID:      2026-06xxxx (双向两个条目, 但只抓到一个方向)
时间:        2026-06-08 → 2026-08-28
持续:        2.7 个月
方向:        München → Salzburg (Salzburg→München 方向条目需确认)
车道配置:    0 条本方向 + 2 条对向车道 (Vollsperrung Richtungsfahrbahn)
GPS:         ~47.73°N, 12.28°E
KM估计:      101.0 – 106.0
工作类型:    Fahrbahnerneuerung
附近测站:    MQQ245 (km 106.27) — 最靠近奥地利边境的测站!

描述:
    靠近奥地利边境的最后一段施工。München→Salzburg 方向车道完全封闭。
    2条对向车道承担全部双向交通。
    覆盖 Sommer-Hauptreisezeit (6月-8月)，包含暑假核心期。
    边境前的瓶颈效应极其严重——这是通往萨尔茨堡/Walserberg 的最后几公里。
```

### 2.5 Rosenheim – Rohrdorf

```
API ID:      2026-07xxxx (双向两个条目)
时间:        2026-07-01 → 2026-07-17
持续:        0.5 个月 (约2周)
方向:        München → Salzburg / Salzburg → München 双方向
车道配置:    1 条本方向 + 1 条对向 = 1+1 双向共用 (1+1 bidirektional)
GPS:         ~47.85°N, 12.1°E
KM估计:      59.0 – 63.0
工作类型:    Fahrbahninstandsetzung / Deckenerneuerung (典型短期刨铺)

描述:
    短期但位于关键位置——Rosenheim 是 A8 和 A93 的交汇枢纽 (AD Inntal)。
    1+1 配置容量极低 (正常容量的 ~25-35%)。
    恰逢 Sommerferien 开始前后的交通高峰期。
```

---

## 三、🔥 A93 Süd (Rosenheim ↔ Kufstein) 当前施工现场

### 3.1 Reischenhart – Nicklheim (DB EÜ Korrosionsschutz) 🚨

```
API ID:      2026-010459 (双向两个条目)
时间:        2026-04-18 → 2026-09-14
持续:        4.9 个月
方向:        Kiefersfelden → Rosenheim / Rosenheim → Kiefersfelden 双方向
车道配置:    2+2 双向共用一条路基 (komplexe Verkehrsführung)
            符号: CLOSED+BORDER_LEFT+CLOSED+CLOSED+SEPARATE+
                  ARROW_DOWN+ARROW_DOWN+SEPARATE+
                  ARROW_UP+BORDER_RIGHT+ARROW_UP
限速:        60 km/h
最大宽度:    5.2 m
GPS:         47.7620°N, 12.1054°E (Rosenheim→Kiefersfelden 方向)
             47.7675°N, 12.1002°E (Kiefersfelden→Rosenheim 方向)
工作类型:    DB EÜ Reischenhart BW19 Korrosionsschutz
             (德国铁路跨线桥 — Eisenbahnüberführung — 防腐处理)
附近测站:    MQDZ_AD_Inntal (Inntal 互通枢纽区)

描述:
    铁路桥防腐工程，双向都有复杂交通疏导。
    多条车道封闭 + 双向分离式使用同一路基。
    限速仅 60 km/h，宽度限制 5.2m（影响大型车辆）。
    位于 Inntaldreieck (A8/A93 交汇处) 附近 — 枢纽区施工影响放大。
    覆盖几乎整个 Sommerreise 周期 (4月中到9月中)。
```

### 3.2 Heuberg – Kiefersfelden (Fahrbahninstandhaltung)

```
API ID:      2026-030471
时间:        2026-06-22 → 2026-07-03 (仅日间 08:00-17:00)
持续:        11 天 (日间)
方向:        Rosenheim → Kiefersfelden
车道配置:    日间: 0 条本方向 + 1 条对向车道 + 硬路肩
            夜间及周末: 恢复正常
限速:        80 km/h
最大宽度:    4.0 m (非常窄!)
长度:        11.8 km (超长路段!)
GPS:         47.7209°N, 12.1413°E
工作类型:    Fahrbahninstandhaltung (路面维护)

描述:
    11.8 公里的超长日间施工段 — 几乎覆盖 A93 Süd 南部的一半。
    仅日间施工 (08-17h)，夜间和周末恢复正常。
    对工作日通勤有一定影响，对周末度假交通影响较小。
    4.0m 的最大通行宽度对大型车辆/Lkw 有较大限制。
    注意: 这是 SCHEDULED 条目 (有具体日期时间表)，不是 24/7 施工。
```

### 3.3 Kirnstein – Wildbarren

```
API ID:      2026-031043
时间:        2026-06-18 → 2026-06-27
持续:        9 天
方向:        Rosenheim → Kiefersfelden
车道配置:    0 条本方向 + 2 条对向车道 (fahrstreifenbezogen)
限速:        80 km/h
最大宽度:    6.5 m
长度:        ~1 km
GPS:         47.6978°N, 12.1615°E
工作类型:    Fahrbahnerneuerung (Kurzzeit)

描述:
    短期施工 (9天)，位于 A93 南部靠近 Kiefersfelden 段。
    双车道全封闭借用对向。
    与 #3.2 Heuberg-Kiefersfelden 有时间重叠 (6月22-27日)。
```

### 3.4 关于 Nicklheim – Reischenhart (对向条目)

```
API ID:      2026-010459 (对向条目)
    这是 #3.1 的对向版本:
    - 方向: Rosenheim → Kiefersfelden
    - 符号: ARROW_DOWN+BORDER_LEFT+ARROW_DOWN+SEPARATE+
            ARROW_UP+ARROW_UP+SEPARATE+
            CLOSED+CLOSED+BORDER_RIGHT+CLOSED
    - 相同的日期范围和 GPS 坐标
    - 同一座 DB 铁路桥，另一侧的交通疏导方案
```

---

## 四、⏰ 夏季 2026 (6-8月) — 关键拥堵窗口

### 月度活跃 2+0 施工数量时间线

```
2026-01: █        1个现场 (仅 Eulenauer Filz)
2026-02: █        1个现场
2026-03: ██       2个现场 (+Übersee 开工)
2026-04: ███      3个现场 (+Reischenhart 开工)
2026-05: ████     4个现场 (+Prien 开工)
2026-06: ███████  7个现场 ← 峰值开始 (+Bad Reichenhall, +2个A93短期) 🚨
2026-07: ███████  7个现场 ← 绝对峰值 (+Rosenheim短期) 🚨🚨🚨
2026-08: ████     4个现场 (Rosenheim/Prien/Kirnstein/Heuberg 陆续结束)
2026-09: ███      3个现场 (Übersee/Reischenhart 还在)
2026-10: ██       2个现场 (Übersee 到10/30)
2026-11: █        1个现场
2026-12: █        1个现场
2027-01~06: █     1个现场 (Eulenauer Filz 持续中)
2027-07: █        1个现场 → 结束 (Eulenauer Filz 7月3日结束)
```

### 叠加分析

**2026年6-7月: 这是极端拥堵叠加期**:
- A8 有 **4-5 个 2+0 路段** 同时施工
- A93 有 **2-3 个 2+0 路段** 同时施工
- 覆盖全部 **Sommerferien** (巴伐利亚暑假通常 7月底-9月初)
- 加上通往 **奥地利/意大利/克罗地亚** 的假日交通
- **7个2+0现场同时活跃是极端异常情况** — 通常只有 1-2 个

**2026年6-7月的活跃 2+0 站点完整列表**:
```
A8  Eulenauer Filz – Im Moos          (22个月, 0+3)
A8  Rosenheim – Rohrdorf              (2周, 1+1)
A8  Prien – Bernau am Chiemsee        (2月, 2+2)
A8  Übersee – Grabenstätt             (7月, 2+2)
A8  Bad Reichenhall – Schwarzbach     (2.7月, 0+2)
A93 Kirnstein – Wildbarren            (9天, 0+2)
A93 Heuberg – Kiefersfelden           (11天日间, 0+1)
A93 Reischenhart – Nicklheim          (5月, 2+2)
─────────────────────────────────────────
总计: 8 个施工段 (8个2+0)
```

---

## 五、车道配置分类法 (Verkehrsführung)

### 5.1 分类体系

| 类型 | 描述 | 容量影响 | 典型限速 | API 符号示例 |
|------|------|----------|----------|-------------|
| **2+0 Vollsperrung** | 一条方向车道 **完全封闭**。全部双向交通在对向车道通行。0条本方向+对向车道承载全部车流。 | **-50~75%** | 60-80 km/h | `SEPARATE + ARROW_UP + ARROW_UP + ARROW_UP` |
| **2+0 Teilweise** | 一条方向车道部分封闭。复杂交通疏导，部分车道借用对向。有 SEPARATE 隔离双向车流。 | **-30~50%** | 60-80 km/h | `ARROW_DOWN + ... + SEPARATE + ... + ARROW_UP + ... + CLOSED` |
| **Fahrstreifensperrung** | 仅关闭 1-2 条车道。**无**借用对向车道。剩余车道保持本方向通行。 | **-25~50%** | 80-100 km/h | `SEPARATE + ARROW_UP + CLOSED + BORDER_RIGHT` |
| **Tagesbaustelle** | 仅日间施工 (典型 08:00-17:00)。夜间及周末恢复正常。 | 日间减少; 夜间/周末正常 | 80 km/h | 变化 (通常1条车道关闭) |

### 5.2 2+0 详细子类型

#### 5.2.1 2+0 Vollsperrung — 完整封闭型

**特征**: 一条 Richtungsfahrbahn (方向行车道) 完全封闭施工。全部交通被导流到对向车道。

**子配置**:
```
(a) 0+3 型 (Eulenauer Filz):
    本方向: 0 条车道 (完全封闭)
    对向借用: 3 条车道 (Salzburg→München 方向独占对向车道)
    实际: München→Salzburg 车流被完全赶到 Gegenfahrbahn
    符号: SEPARATE | ARROW_UP | ARROW_UP | ARROW_UP | BREAKDOWN_LANE
    
(b) 0+2 型 (Bad Reichenhall):
    本方向: 0 条车道
    对向借用: 2 条车道
    符号: SEPARATE | ARROW_UP | ARROW_UP | BORDER_RIGHT | CLOSED

(c) 1+1 型 (Rosenheim):
    本方向: 1 条车道
    对向借用: 1 条车道
    容量: 正常的 ~25-35%
    符号: CLOSED | BORDER_LEFT | ... | SEPARATE | ARROW_DOWN | ARROW_UP | BORDER_RIGHT
```

#### 5.2.2 2+0 Teilweise — 部分借用型

**特征**: 不是完全封闭，而是多条车道关闭后剩余车道与对向共用。

**典型配置** (Reischenhart DB EÜ):
```
符号: ARROW_DOWN | BORDER_LEFT | ARROW_DOWN | SEPARATE |
      ARROW_UP | ARROW_UP | SEPARATE |
      CLOSED | CLOSED | BORDER_RIGHT | CLOSED

解读 (从 Kiefersfelden → Rosenheim 方向看):
  左侧: 2条本方向车道 (ARROW_DOWN)
  隔离: SEPARATE (物理分隔)
  中间: 2条对向车道 (ARROW_UP) ← 对向来车用
  隔离: SEPARATE
  右侧: 3条车道关闭 (CLOSED) + 路肩关闭
```

#### 5.2.3 Fahrstreifensperrung — 车道关闭型

**特征**: 仅关闭本方向的部分车道。对向不受影响。无需借用对向。

**典型配置**:
```
符号: SEPARATE | ARROW_UP | CLOSED | BORDER_RIGHT | BREAKDOWN_LANE
解读: 分隔带 | 1条本方向车道 | 1条关闭 | 路缘 | 硬路肩

或:
符号: SEPARATE | CLOSED | ARROW_UP | ARROW_UP | BORDER_RIGHT | CLOSED
解读: 分隔带 | 1条关闭 | 2条本方向车道 | 路缘 | 1条关闭
```

#### 5.2.4 Tagesbaustelle — 日间施工型

**特征**: 夜间和周末拆除施工设施，恢复全部车道。仅工作日日间有限制。

**典型配置** (Heuberg – Kiefersfelden):
```
日间: SEPARATE | ARROW_UP | CLOSED | BORDER_RIGHT | BREAKDOWN_LANE
      分隔带 | 0条本方向 | 1条对向 | 路缘 | 硬路肩 (0+1)
夜间/周末: 完全恢复正常 2+2 或 3+3
```

### 5.3 影响符号 (Impact Symbols) 解码规则

从 API 的 `impact.symbols` 字段解码：

| API 符号 | 含义 | 说明 |
|----------|------|------|
| `ARROW_DOWN` | 本方向开放车道 (Fahrtrichtung) | 车流方向与查看方向一致 |
| `ARROW_UP` | 对向交通使用的车道 (Gegenrichtung) | **出现这个就是 2+0 的标志** |
| `SEPARATE` | 物理隔离带 (Mittelstreifen / Leitwand) | 双向车流之间的分隔 |
| `CLOSED` | 封闭车道 (gesperrt) | 因施工关闭 |
| `BORDER_LEFT` | 左侧路缘/护栏 | 道路左边界 |
| `BORDER_RIGHT` | 右侧路缘/护栏 | 道路右边界 |
| `BREAKDOWN_LANE` | 硬路肩/紧急停车带 (Standstreifen) | 部分可用于通行 |

**排列顺序**: 从左到右 = 从道路左侧边界到右侧边界 (顺驾驶方向观察)

**2+0 检测规则**:
- `ARROW_UP` 数量 > 0 **且** 存在 `SEPARATE` → 2+0 双向交通
- `ARROW_UP` 数量 > 0 **但无** `SEPARATE` → 可能为单车道交替通行
- `ARROW_UP` 数量 = 0 **且** `CLOSED` 数量 > 0 → 单纯车道关闭
- `ARROW_UP` 数量 = 0 **且** `CLOSED` 数量 = 0 → 正常通行

---

## 六、📋 已知未来规划项目

这些项目来自研究 (IHK会议、Planfeststellungsbeschluss、新闻)，不一定出现在实时 API 中。

### 6.1 A8 6-streifiger Ausbau Achenmühle – Bernauer Berg

```
道路:        A8 Ost
路段:        Achenmühle (km 67.7) → Bernauer Berg (km 75.6)
方向:        双向 (München ↔ Salzburg)
类型:        Kapazitätsausbau (von 4 auf 6 Fahrstreifen)
状态:        ✅ Planfestgestellt (Planfeststellungsbeschluss 31.01.2024)
批复机关:    Regierung von Oberbayern
批复文号:    4354.32-01-2-3
计划开工:    尚未确定 (预计最早 2027)
计划完工:    2030er Jahre

关键工程内容:
  - 6-streifiger Ausbau 双向 (je 3 Fahrstreifen + Standstreifen)
  - Tunnel Frasdorf in Troglage (地下式隧道)
  - Lärmschutzanlagen (声屏障)
  - Brückenbauwerke BW 111 – BW 123 (13座桥梁)
      incl. 位于 Thal, Söllhuben, Prien, Umrathshausen
  - Entwässerungsmaßnahmen (排水系统)
  - Anschlussstelle Frasdorf (Rampen ein-/zweistreifig)
  - Landschaftspflegerischer Begleitplan (景观保护)
  - FFH-Verträglichkeitsprüfung + Artenschutz (物种保护)

施工期间交通疏导 (预估):
  - 主体施工期间: 2+0 Verkehrsführung
  - 不会是简单的 2+0，而是分阶段切换
  - Tunnel Frasdorf 施工时需要特殊交通疏导方案

来源:
  Regierung von Oberbayern, Planfeststellungsbeschluss vom 31.01.2024
  https://www.regierung.oberbayern.bayern.de/mam/dokumente/bereich3/pfb/
```

### 6.2 A8 Brückensanierungsprogramm (23座桥梁)

```
道路:        A8 Ost
路段:        Gesamte A8 Ost (km ~50 – 110)
方向:        双向 (abschnittsweise)
类型:        Brückenerhaltung (桥梁维修)
状态:        🔄 In Planung/Vorbereitung (滚动计划)
计划开工:    2024–2028 (rollierend, 逐个进行)
计划完工:    2028+

关键信息:
  - 23座桥梁被 Autobahn GmbH 评定为 "dringend sanierungsbedürftig"
     (迫切需要修复)
  - 来源: Josef Seebacher (Autobahn GmbH), IHK Verkehrsausschuss 08.02.2024
  - 短期维护策略: 逐座桥梁修复，每座 2-12 个月
  - 施工期间: 大部分为 Fahrstreifeneinengung (车道收窄)
    或 1+1 pro Richtung (每方向1车道)
  - 具体情况取决于每座桥梁的施工方案

对交通预测的影响:
  - 这是一个滚动计划，需要跟踪每座桥梁的实际施工时间
  - 23座桥梁的位置分布在整个 A8 Ost 走廊上
  - 如果 2-3 座桥同时施工，叠加效应会非常显著

来源:
  IHK Verkehrsausschuss Rosenheim, 08.02.2024
  (Josef Seebacher, Autobahn GmbH des Bundes)
```

### 6.3 A8 长期全线扩建 (远期规划)

```
道路:        A8 Ost
路段:        AK München-Süd → Staatsgrenze Salzburg/Walserberg
类型:        Kapazitätsausbau
状态:        📋 远期规划 (langfristig)

Autobahn GmbH 的三阶段策略 (来源: IHK 2024):
  1. Kurzfristig (短期): Erhaltung (维护保养)
     └─ 当前正在进行: 23座桥梁 + Fahrbahnerneuerung
  
  2. Mittelfristig (中期): Vereinzelte Ausbaumaßnahmen (个别扩建)
     └─ Achenmühle – Bernauer Berg (6-streifig, Planfestgestellt)
  
  3. Langfristig (长期): Vollständiger Ausbau auf 6 und 8 Spuren
     bis zur Staatsgrenze bei Salzburg
     └─ 全线 6-8 车道扩建
     └─ 时间: 2030s – 2040s

交通量背景:
  - AK München Süd 和 AD Inntal 高峰日达 150,000 Fahrzeuge/Tag
  - 这是欧洲最繁忙的假日交通走廊之一
```

### 6.4 A10 奥地利侧施工 (跨境影响)

```
道路:        A10 Tauernautobahn (Salzburg ↔ Villach)
类型:        Tunnelsanierung / Verkehrsmanagement
影响:        直接影响 A8/A93 的跨境交通流

(a) Tunnelsanierung Tauern- und Katschbergtunnel
    状态:     📋 计划中
    计划:     Herbst 2027 – 2032
    特点:     夏季旅游季停工 (Sommerreiseverkehr: Arbeiten ruhen)
             冬季: einröhrige Verkehrsführung mit Gegenverkehr
             可能引入额外 Lkw-Fahrverbote
    来源:     IHK Verkehrsausschuss Rosenheim 08.02.2024

(b) Brentenbergtunnel Sanierung (nach Lkw-Brand)
    状态:     ✅ 已完工 (18.06.2026)
    时间:     2026-02-23 → 2026-06-18
    事件:     Lkw-Brand am 09.01.2026 zerstörte erste 120m
    费用:     ~4.5 Mio €
    当前:     Wieder ohne Einschränkungen befahrbar
    来源:     SN.at / ASFINAG Juni 2026

(c) Multifunktionales Transitmanagement (7-Punkte-Programm)
    状态:     🔄 In Umsetzung
    宣布:     BMIMI November 2025
    投资:     ~40 Mio €
    内容:
      1. Intelligente Verkehrsbeeinflussung (VBA) Walserberg–Golling
      2. Erneuerung Sensorik/Anzeigetafeln (~50 Sensorstandorte)
      3. Effizientes Verkehrsmanagement (Vorbereitung Tunnelsanierung)
      4. Ramp Metering (Zuflussdosierung / Gatekeeper-Ampeln)
      5. Kontrollmaßnahmen (intensive Verkehrsüberwachung)
      6. Optimierte Fahrverbote (Lkw-Fahrverbotskalender,
         Überholverbote, Nachtfahrverbote)
      7. Verkehrsinfo & Prognosen (grenzüberschreitend mit Deutschland)
```

### 6.5 ASFiNAG Dosierung (奥地利侧交通管制)

```
位置:        Grenzübergang Walserberg (A1) / A10 Knoten Salzburg
类型:        Ramp Metering + Abfahrtsdosierung
状态:        🔄 Teil des 7-Punkte-Programms (ab 2026)

关键日期类型 (需要在预测模型中纳入):
  - Sommer-Samstage: 最重要的 Dosierungstage
    (通往亚得里亚海/克罗地亚的假日交通)
  - Winter-Samstage: Ski-Saison Dosierung
  - Pfingst-Samstage: 五旬节大周末

对 A8/A93 的影响:
  - Dosierung 导致 A10 入口处车辆积压
  - 积压向上游传导到 A8/A93 (在德国境内)
  - 尤其是在 Grenzübergang Walserberg 之前
  - 即使 A8/A93 本身没有施工，Dosierung 也会制造拥堵

建议获取 ASFiNAG Dosierungstage 官方日历 2026-2029。
```

### 6.6 不在目标走廊内的参考项目 (供参考)

```
A93 Nord (Regensburg – Hof 区域):

(a) Brückenneubau Bw 144c (Schwarzenfeld – Schloßberg)
    时间:     2026-03-10 → 2027-03-01 (1年)
    长度:     1.4 km
    宽度:     max 5.5 m
    限速:     100 km/h
    类型:     Brückenneubau
    2+0:      Nein
    说明:     不在目标走廊，但作为桥梁新建的参考案例

(b) Brückenneubau Bw 104a Waldnaabbrücke
    (Neustadt – Windischeschenbach)
    时间:     2026-03-16 → 2029-08-29 (近3.5年!)
    长度:     1.4 km
    宽度:     max 5.8 m
    限速:     80 km/h
    2+0:      JA
    说明:     长期 2+0 交通疏导的极端案例
             复杂符号: CLOSED+BORDER_LEFT+CLOSED+CLOSED+
                      SEPARATE+ARROW_DOWN+ARROW_DOWN+
                      SEPARATE+ARROW_UP+BORDER_RIGHT+ARROW_UP
             作为 3.5 年 2+0 的参考 — 说明这种配置可以长期维持!
```

---

## 七、📁 生成的数据文件

所有文件位于 `data/construction/` 目录：

| 文件名 | 内容 | 格式 |
|--------|------|------|
| `roadworks_all_2026-06-19.csv` | 全德国 A8 (107条) + A93 (27条) = 134条施工现场 | CSV |
| `roadworks_target_corridors_2026-06-19.csv` | **目标走廊筛选结果**: A8:9条, A93:4条 = 13条 | CSV |
| `known_projects_2026-06-19.csv` | 10个已知规划/历史项目 (含跨境的) | CSV |
| `known_projects_target_2026-06-19.csv` | 7个与目标走廊相关的已知项目 | CSV |
| `construction_timeline_2026-06-19.csv` | 2026-01 → 2027-12 月度时间线 (18个月) | CSV |
| `lane_config_analysis_2026-06-19.json` | 完整车道配置分析 (JSON) | JSON |
| `summary_2026-06-19.json` | API 数据抓取摘要 | JSON |

### CSV 字段说明 (roadworks_target_corridors)

| 列名 | 说明 |
|------|------|
| `road` | 道路编号 (A8 / A93) |
| `identifier` | API 唯一施工 ID |
| `title` | 路段名称 |
| `subtitle` | 原始方向文本 (如 " München -> Salzburg") |
| `direction` | 解析后的方向 |
| `display_type` | ROADWORKS / SHORT_TERM_ROADWORKS |
| `coordinate_lat` | GPS 纬度 |
| `coordinate_lon` | GPS 经度 |
| `impact_lower` | 下游参考点 |
| `impact_upper` | 上游参考点 |
| `length_km` | 施工长度 (km) |
| `max_speed_kph` | 最高限速 (km/h) |
| `max_width_m` | 最大通行宽度 (m) |
| `start_date` | 开始日期 (ISO8601) |
| `end_date` | 结束日期 (ISO8601, 从description解析) |
| `lane_config_type` | 车道配置类型 |
| `lane_config_desc` | 车道配置人类可读描述 |
| `total_lanes` | 总车道数 |
| `open_lanes` | 开放车道数 |
| `closed_lanes` | 封闭车道数 |
| `is_2_plus_0` | 是否为 2+0 双向共用路基 |
| `has_breakdown_lane` | 是否有硬路肩 |
| `raw_symbols` | 原始 API 车道符号 |
| `target_corridor` | 目标走廊名称 (A8_Ost / A93_Sued) |
| `in_a8_ost_corridor` | 是否在 A8 Ost 目标走廊地理范围内 |
| `in_a93_sued_corridor` | 是否在 A93 Süd 目标走廊地理范围内 |

---

## 八、Python 工具脚本

### 8.1 `fetch_construction_data.py` — 数据抓取脚本

```bash
# 运行方式
.venv/bin/python fetch_construction_data.py
```

**功能**:
1. 从 bund.dev API (`verkehr.autobahn.de`) 拉取 A8 + A93 的全部 roadworks/closures/warnings
2. 解析每条施工的 `impact.symbols` 字段 → 解码车道配置
3. 从 `description` 文本中提取开始/结束日期
4. 按地理坐标 (Bounding Box) 筛选目标走廊
5. 同时加载 "已知项目" (从研究中手动收集的规划/历史项目)
6. 输出 CSV + JSON 到 `data/construction/`

**关键函数**:
- `decode_lane_config(symbols)` → 车道配置分类
- `extract_dates(entry)` → 日期提取 (含 description 文本正则解析)
- `is_in_target_bbox(lat, lon)` → 地理筛选
- `build_known_projects_df()` → 已知项目数据集

### 8.2 `analyze_construction_lanes.py` — 车道分析脚本

```bash
# 运行方式
.venv/bin/python analyze_construction_lanes.py
```

**功能**:
1. 构建目标走廊施工的结构化摘要 (build_target_construction_summary)
2. 生成月度时间线 (compute_timeline_overlap)
3. 识别关键拥堵窗口 (叠加分析)
4. 测量站影响映射 (每个测站附近的施工)
5. 车道配置分类法文档 (build_lane_config_taxonomy)
6. 输出: JSON + CSV

### 8.3 依赖包

```
requests  (HTTP 请求)
pandas    (数据处理)
numpy     (数值计算)
```

安装: `.venv/bin/pip install requests pandas`

---

## 九、⚠️ 历史数据缺口与解决方案

### 9.1 核心问题

**bund.dev API 和 Mobilithek DATEX2 都只提供实时/近期数据，不提供历史 Baustellen 数据。**

- bund.dev API: 只返回当前激活的 + 未来计划的施工现场
- Mobilithek: 3-Minuten-Takt 推送当前状态，无历史归档功能
- 没有公开的 "Baustellenkalender 2023-2025" 下载

### 9.2 三条补全路径

#### 路径 1: 反向工程 via 交通数据本身 🔬 (推荐, 你们可以自己实现)

**原理**: 你们的 1-min/1h 交通数据 (2023-2025) 已经包含了 2+0 施工的影响痕迹。

**检测算法思路**:
```python
# 伪代码
def detect_2_plus_0_from_traffic_data(df_1min, station_id):
    """
    通过交通数据异常检测 2+0 施工期
    
    信号:
    1. v_kfz 突然降到 60-80 km/h 区间 (正常 A8 自由流 ~120-130)
    2. q_kfz 大幅下降 → 容量受限的表现
    3. 某个方向的流量异常减少 + 对向流量可能增加
       (车流被引导到对向车道)
    4. 持续时间 > 2天 (排除事故等短期事件)
    5. 日间影响 > 夜间 (排除普通高峰拥堵)
    """
    signals = {
        'speed_drop': df['v_kfz'] < 80,           # 速度骤降
        'flow_drop': df['q_kfz'] < threshold,      # 流量低于正常
        'duration': consecutive_days > 2,           # 持续 > 2天
        'daytime_pattern': daytime > nighttime,      # 日间模式
    }
    return classify(signals)
```

**优势**:
- 不需要外部数据
- 可以直接集成到现有 pipeline
- 可以检测到 API 中没有记录的施工

**劣势**:
- 需要区分施工 vs 事故 vs 极端天气
- 阈值设定需要领域知识
- 无法区分 2+0 vs 单纯车道关闭

#### 路径 2: 向 Autobahn GmbH 直接申请 📧 (最可靠)

**联系方式**:
```
Autobahn GmbH des Bundes
Niederlassung Südbayern
(前 Autobahndirektion Südbayern)

请求内容:
  - Historische Baustellendaten für A8 Ost + A93 Süd
  - Zeitraum: 2023-01-01 bis heute
  - 需要字段: 路段, 方向, 时间, 交通疏导模式 (2+0/normal/...)
  - 目的: TUM Science Hackathon 2026, akademische Forschung
  
说明:
  他们内部肯定有这些数据。作为联邦公司，数据公开是法律义务
  (Informationsfreiheitsgesetz / Umweltinformationsgesetz)。
  学术用途通常会被积极配合。
```

**可能的回复时间**: 1-4 周

#### 路径 3: MDM / Mobilithek 订阅 📡

```
Mobilithek (mobilithek.info):
  - 需要注册账号
  - DATEX2 SituationPublication 订阅
  - Push- oder Pull-Verfahren (SOAP/REST)
  - 免费 (für öffentliche Stellen und Forschung)
  
限制:
  - 不提供历史归档 (需要自己持续采集)
  - 从现在开始订阅 → 积累未来数据
  - 历史数据可能需要特殊申请
  
MDM (Mobilitäts Daten Marktplatz):
  - 可能有一些归档数据
  - 联系: https://www.mdm-portal.de
```

### 9.3 当前可用的历史施工锚点

即使没有完整历史数据，我们有一些锚点：

| 时间 | 事件 | 来源 |
|------|------|------|
| 2023-01-01 → 2025-12-31 | 3年完整交通数据 (你们的 1-min/1h) | 项目数据 |
| 2024-01-31 | A8 Achenmühle–Bernauer Berg Planfeststellungsbeschluss | Regierung v. Oberbayern |
| 2024-02-08 | IHK 会议: 23座桥梁急需修复 | IHK Verkehrsausschuss |
| 2024-12-04 | A8 Einöd Traglasteinschränkung 开始 | API |
| 2025-08-27 | A8 Eulenauer Filz 施工开始 (至今仍在进行) | API |
| 2025-11-14 | A8 Neunkirchen Schallschutzarbeiten 开始 | API |
| 2025-11-17 | A8 Enztalquerung Pforzheim PBK 新闻 | autobahn.de |

---

## 十、🚨 对交通预测模型的关键启示

### 10.1 Eulenauer Filz – Im Moos 是最大的单一因素

```
为什么这个项目如此重要:

1. 持续时间: 2025-08 → 2027-07, 22个月, 跨越3个日历年
2. 位置: 位于 MQQ209 (km 93.38) 和 MQQ213 (km 94.75) 之间
   - 这是 A8 Ost 测站网络的核心区域
   - 这两个测站的 2025-2027 数据会严重偏离正常模式
3. 配置: 0+3 (München→Salzburg 完全封闭)
   - 容量下降至正常的 20-25%
4. 覆盖: 2026 + 2027 两个完整的 Sommerreise 周期
   + Weihnachten/Ostern/Pfingsten 全部受影响
5. 预测影响:
   - 对这个路段的任何交通预测都必须乘以 ~0.25 的容量因子
   - 直到 2027-07-03
```

### 10.2 2026 年夏季容量崩溃

```
正常 A8 Ost 容量 (MQQ209/213 区域):
  正常: 2+2 Fahrstreifen + Standstreifen = ~4000-4500 Fzg/h/Richtung
  
2026年6-7月 综合容量:
  Eulenauer Filz:        0+3 → ~800-1000 Fzg/h (München→Salzburg)
  Übersee–Grabenstätt:   2+2 bidirektional → ~1800-2000 Fzg/h 双向合计
  Prien–Bernau:          2+2 bidirektional → ~1800-2000 Fzg/h 双向合计
  Bad Reichenhall:       0+2 → ~600-800 Fzg/h (München→Salzburg)
  Rosenheim–Rohrdorf:    1+1 → ~800-1000 Fzg/h 双向合计

  叠加效应: 这些施工段在空间上是串联的 (在同一条路上)
  → 最窄的瓶颈决定了整条路的通行能力
  → Eulenauer Filz 0+3 是整个 A8 Ost 的限制因素
  → 夏季周末需求 (~3000-4000 Fzg/h) >> 容量 (~800-1000 Fzg/h)
  → 必然出现大规模拥堵
```

### 10.3 容量降低的定量标定

```
配置类型               容量 (相对正常)    说明
─────────────────────────────────────────────────────────
正常 2+2               100%              ~4000-4500 Fzg/h/Richtung
正常 3+3               100%              ~5500-6000 Fzg/h/Richtung
2+0 2+2 bidirektional   40-50%           ~1800-2000 Fzg/h 双向合计
2+0 1+1 bidirektional   25-35%           ~800-1000 Fzg/h 双向合计
2+0 0+2 (对向借用)      20-30%           ~600-800 Fzg/h (借用方向)
2+0 0+3 (对向借用)      20-30%           ~600-800 Fzg/h (借用方向)
Fahrstreifensperrung    50-75%           取决于关闭几条车道
Tagesbaustelle          100% (夜间)      ~4000-4500 Fzg/h 夜间/周末

注意: 这些是初步标定值，需要根据实际交通数据验证。
```

### 10.4 测站施工影响映射

```
测站          KM      当前施工影响
───────────────────────────────────────────────────────
MQB25         20.09   无直接影响 (位于 A8 Ost 北端, 近慕尼黑)
MQQ37         20.17   无直接影响 (位于 A8 Ost 北端, 近慕尼黑)
MQQ209        93.38   ⚠️ Eulenauer Filz (km 90.5-95.0) 直接覆盖!
                       ⚠️ Übersee–Grabenstätt (km 82-88) 上游影响
MQQ213        94.75   ⚠️ Eulenauer Filz (km 90.5-95.0) 直接覆盖!
                       ⚠️ Übersee–Grabenstätt (km 82-88) 上游影响
MQQ245        106.27  ⚠️ Bad Reichenhall (km 101-106) 直接覆盖!
                       ⚠️ 最靠近边境, 边境瓶颈效应
MQDZ_AD_Inntal  —     ⚠️ Reischenhart–Nicklheim DB EÜ (A93)
                       ⚠️ 枢纽区施工, A8/A93 交汇影响放大
MQDZ_Kiefersfelden —  ⚠️ Kirnstein–Wildbarren (A93 南端)
                       ⚠️ Heuberg–Kiefersfelden (A93 南端)
```

### 10.5 对 Fahrkalender 预测的建议权重

```
对于每个预测日，需要考虑:
1. 是否有活跃的 2+0 路段 → capacity_factor *= 0.25~0.5
2. 是否在 Sommerferien/Samstage → demand_factor *= 1.5~2.5
3. 是否有 ASFiNAG Dosierung → border_delay += 30-90 min
4. 是否有多个 2+0 叠加 → 取最窄瓶颈的 capacity_factor
5. 日间/夜间区分 → Tagesbaustelle 只影响日间
6. 天气叠加 → 雨雪天 + 2+0 = 更严重的速度下降

建议在预测模型中添加一个 "construction_impact_index" (CII):
  CII = Σ(1 / open_lanes_ratio_i × length_i × overlap_factor_i)
  
  其中:
  - open_lanes_ratio = 开放车道数/正常车道数
  - overlap_factor = 施工段重叠程度
  - CII 越高 → 拥堵越严重
```

---

## 附录：原始 API 数据样例

### A.1 A8 目标走廊条目范例 (Eulenauer Filz – Im Moos)

```json
{
  "identifier": "2025-041538--vi-bs.2025-08-27_00-00-00-000_003.de0",
  "icon": "123",
  "isBlocked": "false",
  "future": false,
  "extent": "47.821654,11.977114,47.821692,11.981611",
  "point": "47.821654,11.977114",
  "startLcPosition": "150",
  "impact": {
    "lower": "Im Moos",
    "upper": "Eulenauer Filz",
    "symbols": [
      "SEPARATE",
      "ARROW_UP",
      "ARROW_UP",
      "ARROW_UP",
      "BREAKDOWN_LANE"
    ]
  },
  "display_type": "ROADWORKS",
  "subtitle": " München -> Salzburg",
  "title": "A8 | Eulenauer Filz - Im Moos",
  "startTimestamp": "2025-08-27T00:00:00+02:00",
  "coordinate": {
    "lat": 47.821654019785484,
    "long": 11.977113970798099
  },
  "description": [
    "Zeitraum dieser Bauphase:",
    "Beginn: 27.08.25 um 00:00 Uhr",
    "Ende: 03.07.27 um 00:00 Uhr",
    "(Ende der Gesamtmaßnahme: 03.07.27)",
    "",
    "A8: München -> Salzburg, zwischen Eulenauer Filz und 1.4 km vor Im Moos",
    "",
    "Länge: konnte nicht ermittelt werden | Maximale Durchfahrtsbreite: 11 m",
    "",
    "A8 Parkplatz Eulenauer Filz"
  ],
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [11.977114, 47.821654],
      [11.977600, 47.821557],
      [11.978074, 47.821503],
      [11.978656, 47.821428],
      [11.980828, 47.821476],
      [11.981298, 47.821618],
      [11.981405, 47.821635],
      [11.981611, 47.821692]
    ]
  }
}
```

**解读**:
- `display_type: "ROADWORKS"` → 长期施工 (非短期)
- `startTimestamp: "2025-08-27"` → 已开始近10个月
- `description[3]: "Ende: 03.07.27"` → 还要持续一年
- `impact.symbols: ["SEPARATE", "ARROW_UP", "ARROW_UP", "ARROW_UP", "BREAKDOWN_LANE"]`
  → 隔离带 + 3条对向车道 + 硬路肩
  → **0条本方向车道!** → München→Salzburg 完全封闭
- `geometry` → 8个GPS坐标点定义施工范围
- `maxWidth: 11m` → 对大型车辆足够宽

### A.2 A93 目标走廊条目范例 (Reischenhart – Nicklheim)

```json
{
  "identifier": "2026-010459--vi-bs.2026-04-18_23-00-00-000.devi-zus.2026-04-07_00-00-00-000_002.de3",
  "icon": "123",
  "isBlocked": "false",
  "future": false,
  "extent": "47.761972,12.105438,47.767570,12.100388",
  "point": "47.761972,12.105438",
  "impact": {
    "lower": "Nicklheim",
    "upper": "Reischenhart",
    "symbols": [
      "ARROW_DOWN", "BORDER_LEFT", "ARROW_DOWN",
      "SEPARATE",
      "ARROW_UP", "ARROW_UP",
      "SEPARATE",
      "CLOSED", "CLOSED", "BORDER_RIGHT", "CLOSED"
    ]
  },
  "display_type": "ROADWORKS",
  "subtitle": " Kiefersfelden -> Rosenheim",
  "title": "A93 | Reischenhart - Nicklheim",
  "startTimestamp": "2026-04-18T23:00:00+02:00",
  "coordinate": {
    "lat": 47.761972,
    "long": 12.105438
  },
  "description": [
    "Zeitraum dieser Bauphase:",
    "Beginn: 18.04.26 um 23:00 Uhr",
    "Ende: 14.09.26 um 00:00 Uhr",
    "(Ende der Gesamtmaßnahme: 14.09.26)",
    "",
    "A93: Kiefersfelden -> Rosenheim, zwischen Reischenhart und Nicklheim",
    "",
    "Länge: 0.73 km | Maximale Durchfahrtsbreite: 5.2 m",
    "",
    "DB EÜ Reischenhart BW19 Korrosionsschutz"
  ]
}
```

**解读**:
- `description[8]: "DB EÜ Reischenhart BW19 Korrosionsschutz"`
  → 德国铁路 (DB) 跨线桥 (EÜ = Eisenbahnüberführung) 防腐工程
- `impact.symbols` 有 **2个 SEPARATE** → 两次物理隔离
  → 这意味着三条独立的车道组 (本方向 / 对向 / 施工区)
- `length: 0.73 km` → 准确长度
- `maxWidth: 5.2 m` → 限制大型车辆

### A.3 非目标走廊参考条目 (Neustadt – Windischeschenbach, 3.5年 2+0)

```json
{
  "title": "A93 | Neustadt an der Waldnaab - Windischeschenbach",
  "subtitle": " Weiden -> Hof",
  "startTimestamp": "2026-03-16T00:00:00+01:00",
  "description": [
    "Beginn: 16.03.26 um 00:00 Uhr",
    "Ende: 29.08.29 um 00:00 Uhr",      ← 3.5 年!
    "A93 Brückenneubau Bw 104 a Waldnaabbrücke"
  ],
  "impact": {
    "symbols": [
      "CLOSED", "BORDER_LEFT", "CLOSED", "CLOSED",
      "SEPARATE",
      "ARROW_DOWN", "ARROW_DOWN",
      "SEPARATE",
      "ARROW_UP", "BORDER_RIGHT", "ARROW_UP"
    ],
    "maxSpeed": 80,
    "maxWidth": 5.8
  }
}
```

**解读**:
- 3.5 年 2+0 交通疏导 → 证明了 2+0 可以长期维持
- `CLOSED+CLOSED+CLOSED` → 3条车道封闭 (几乎半个路基)
- `ARROW_DOWN+ARROW_DOWN` + `ARROW_UP+ARROW_UP` → 2+2 双向配置
- `maxSpeed: 80` → 限速
- 这个案例说明: Brückenneubau = 长期 2+0 (以年计)

---

## 文档版本

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-06-19 | v1.0 | 初始版本，基础 API 抓取 + 分析 |
| 下次更新 | — | 应包含: ASFiNAG Dosierung 日历, 历史施工反向工程结果 |

---

*本文档由 `fetch_construction_data.py` 和 `analyze_construction_lanes.py` 自动生成数据 + 手动研究汇总而成。*
*详细解释参见上方每个章节的完整说明。*
