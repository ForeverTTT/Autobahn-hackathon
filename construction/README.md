# A8 / A93 施工历史与计划数据

本目录整理德国 Autobahn GmbH 官网和 Internet Archive 中与 **A8、A93** 有关的
施工项目、规划程序和施工公告，研究范围为 **2023-01-01 至 2026-06-20**。

主要入口：

- 当前官网：[Projektübersicht](https://www.autobahn.de/planen-bauen/projektuebersicht)
- 历史页面：[Internet Archive / Wayback Machine](https://web.archive.org/)

## 重要结论

Wayback 中可用的统一 `Projektübersicht` 页面最早始于 **2024-06-20**，没有找到
2023 年统一项目总览快照。2023 年当时仍大量使用 `/suedbayern/`、
`/nordbayern/`、`/west/` 等地区站结构。

因此数据分成两层：

1. 项目总览中的主要工程及状态历史。
2. Wayback 检出的施工公告和旧地区站页面，用于补充2023年及已下线内容。

不能把“Wayback没有存档”解释成“当时没有工程”。

## 文件

| 文件 | 内容 |
|---|---|
| `projects.csv` | 项目总览中的A8/A93主项目，以及2023年旧站规划项目 |
| `overview_observations.csv` | 每次历史/当前总览页面观察到的项目状态 |
| `historical_events.csv` | 人工筛选的2023年重要施工事件 |
| `archive_records.csv` | CDX检出的全部施工相关候选URL索引 |
| `sources.csv` | 官网、Wayback及关键快照来源 |
| `raw/cdx_YYYY.json` | Wayback返回的年度原始索引 |
| `collect_construction.py` | 重新采集和生成数据的脚本 |

当前版本包含：

- 25个主项目/规划项目（A8：21，A93：4）；
- 59条项目总览状态观察；
- 10条人工筛选的旧站重点施工事件；
- 425条Wayback施工相关候选记录（A8：312，A93：113）。

## `projects.csv`

一行代表一个主项目。主要字段：

- `road`：A8或A93。
- `record_type`：
  - `project_overview`：在统一项目总览中观察到；
  - `planning`：2023年旧地区站中的规划审批项目。
- `latest_status`：最新观察到的官网状态，如 `In Planung`、`In Umsetzung`、
  `Abgeschlossen`。
- `status_history`：多个快照中的状态变化。
- `first_overview_observation`：首次在已采集总览快照中出现的日期。
- `archive_first_capture`：对应项目URL在本次CDX索引中的最早存档。
- `description`：当前项目详情页的官方摘要；旧规划页可能为空。
- `evidence_level`：证据来自总览快照还是旧规划页面。

`first_overview_observation` 不是开工日期，只是“在所选快照中首次看见”的日期。

## `overview_observations.csv`

一行代表“某天的项目总览中出现了某项目”。

可以用它分析：

- 项目何时加入或退出官网列表；
- 状态从 `In Planung` 变成 `In Umsetzung` 的时间范围；
- 当前页面与历史页面之间的变化。

Wayback并非每天存档，因此状态变化只能定位到两个快照之间。

## `historical_events.csv`

保存2023年旧地区站中较重要的施工事件，例如：

- A8 Kirchheim-Ost—Aichelberg路面更新和互通扩建；
- A8 Neunkirchen基本更新；
- A8 Landertalbrücke、Mangfallbrücke等桥梁工程；
- A93 Eichelbachbrücke替换；
- A93 Weiden-Nord—Weiden-Süd路面和桥梁维修；
- A93 Schwarzenfeld—Schwandorf路面更新。

`event_date` 优先取页面内的 `datePublished`；页面没有发布日期时才使用Wayback抓取日。
该表严格保留事件日期落在2023–2026范围内的记录。它是重点事件摘要，不是完整URL
清单；完整候选范围见 `archive_records.csv`。

## `archive_records.csv`

这是覆盖范围最广的索引表。脚本通过CDX搜索URL中明确出现A8/A93的页面，再按
施工关键词过滤。

字段：

- `record_kind`：project、planning、construction_notice或project_update。
- `first_capture_timestamp` / `last_capture_timestamp`
- `capture_count`
- `wayback_url`
- `review_status=candidate_url_filtered`

该表是候选索引，不表示每条记录都已经人工确认，也可能包含同一工程的多条更新、
旧URL重定向版本和临时交通组织公告。建模时不要直接把行数当作施工项目数量。

## 范围限制

1. 官网项目总览是主要工程库，不包含每一次夜间封路和日常养护。
2. Wayback抓取不连续，统一总览在2023年缺失。
3. `archive_records.csv` 只收集URL中能明确识别A8/A93且包含施工关键词的页面；
   标题完全不含道路编号的旧页面可能漏检。
4. 当前官网可能继续更新，数据快照时间为2026-06-20。
5. Fahrkalender、虫害处理、应急演练、充电站和招聘页面已排除。

## 更新

首次运行或强制刷新Wayback索引：

```bash
python3 construction/collect_construction.py --refresh-cdx
```

后续使用已有原始索引更新当前官网：

```bash
python3 construction/collect_construction.py
```
