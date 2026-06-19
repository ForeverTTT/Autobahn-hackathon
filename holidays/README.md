# A8 East / A93 South 节假日数据说明

本目录保存可能影响 **A8 East（慕尼黑—萨尔茨堡）** 和
**A93 South（罗森海姆—库夫施泰因）** 假日交通的公共假日与学校假期。

数据目标范围为 **2026-01-01 至 2029-12-31**。学校假期只保存当前已经发布或被
数据源收录的日期；未发布的未来日期不会被填成“无假期”，而是在
`coverage.csv` 中保留缺口。

## 文件

| 文件 | 内容 |
|---|---|
| `holiday_periods.csv` | 每行一个节假日或学校假期区间 |
| `holiday_scopes.csv` | 假期与州、省、学校假期区等地域范围的多对多关系 |
| `holiday_dates.csv` | 将区间展开到每天，方便按 `date` 与交通数据连接 |
| `coverage.csv` | 各国公共/学校假期数据目前覆盖到的日期 |
| `sources.csv` | 官方参考网页、交通相关性和地区优先级 |
| `traffic_windows_2026.csv` | 根据假期开始/结束叠加得到的 2026 重点交通窗口 |
| `update_holidays.py` | 从 OpenHolidays API 重新生成上述数据 |

## 覆盖地区

优先级数字越小，对两条公路的预期影响越大：

| 优先级 | 地区 | 原因 |
|---|---|---|
| 1 `core` | 德国、奥地利 | 道路所在地、主要客源地与直接过境地 |
| 2 `high` | 意大利、斯洛文尼亚、克罗地亚 | 布伦纳及东南方向主要目的地/返程来源 |
| 3 `medium` | 荷兰、比利时、捷克、波兰、匈牙利、斯洛伐克、瑞士 | 重要跨境客源或竞争性阿尔卑斯交通 |
| 4 `secondary` | 塞尔维亚、罗马尼亚、保加利亚 | 东南欧长途过境交通 |

## `holiday_periods.csv`

主要字段：

| 字段 | 说明 |
|---|---|
| `record_id` | OpenHolidays 记录 UUID，也是其他表的连接键 |
| `holiday_class` | `public_holiday`、`school_holiday`、`school_marker` 等 |
| `api_type` | 数据源原始类型，如 `Public`、`School`、`EndOfLessons` |
| `country_code` | ISO 3166-1 两位国家代码 |
| `traffic_priority` | 1–4 的交通相关性等级 |
| `start_date`, `end_date` | 包含首尾两日的 ISO 日期区间 |
| `duration_days` | 区间自然日数量 |
| `nationwide` | 是否全国适用 |
| `subdivision_count` | 适用的州、省、地区数量 |
| `group_count` | 学校假期区或学校类别数量 |
| `verification_status` | 当前为 `aggregated_official_calendar`，表示来自官方日历聚合数据，但没有逐行人工复核 |
| `retrieved_at` | UTC 抓取时间 |

`EndOfLessons` 和 `BackToSchool` 是学校日历边界标记，不应直接视作一段完整假期。

## `holiday_scopes.csv`

一个假期可能覆盖多个州或假期区，因此地域范围单独规范化：

| `scope_kind` | 含义 |
|---|---|
| `national` | 全国适用 |
| `subdivision` | 州、省、县、市等行政区 |
| `group` | 荷兰 North/Central/South、比利时语言共同体或特定学校类别 |
| `unspecified` | 数据源说明为地区性，但未给出机器可读地区代码 |

某些记录同时具有 `subdivision` 和 `group`。聚合时应先选定一种地域粒度，避免重复计数。

## `holiday_dates.csv`

推荐直接与日级交通数据连接：

```python
import pandas as pd

traffic = pd.read_csv("../data/daily_traffic.csv")
holiday_dates = pd.read_csv("holiday_dates.csv")

school = holiday_dates[
    holiday_dates["holiday_class"].eq("school_holiday")
].copy()

features = (
    school.groupby(["date", "traffic_priority"])
    .agg(active_holiday_records=("record_id", "nunique"))
    .reset_index()
)

traffic = traffic.merge(features, on="date", how="left")
```

重要字段：

- `day_index=0`：假期区间第一天。
- `days_to_end=0`：假期区间最后一天。
- `is_start_date` / `is_end_date`：可用于构造出发与返程波。
- `weekday_iso`：周一为 1，周日为 7。

若需要按州或学校假期区过滤，应通过 `record_id` 再连接 `holiday_scopes.csv`。

## 建议交通特征

简单的 `is_holiday` 不足以描述走廊交通，建议至少构造：

```text
active_school_holiday_count_by_priority
active_public_holiday_count_by_priority
days_to_next_school_holiday_start
days_since_school_holiday_start
is_first_friday_or_saturday_of_holiday
is_last_sunday_of_holiday
holiday_overlap_country_count
holiday_overlap_core_high_count
```

方向含义：

- 假期开始前的星期五和第一个星期六通常提高 A8 萨尔茨堡方向、
  A93 库夫施泰因方向的流量。
- 假期结束前最后一个星期日通常提高 A8 慕尼黑方向、
  A93 罗森海姆方向的返程流量。

`traffic_windows_2026.csv` 是基于假期叠加关系形成的分析结果，而不是政府发布的
交通预测。`assessment_status=analyst_derived` 用于明确区分它与官方日历记录。

## 覆盖与质量限制

1. `coverage.csv` 中 `latest_available_start_date` 是数据源当前保存的最晚记录，
   **不等于该学年已经完整发布**。
   `has_any_record_overlap_YYYY` 也只表示至少有一个区间与该年重叠，不能当作全年完整性标记。
2. 德国、荷兰和比利时等国已发布较长周期的校历；奥地利、意大利、斯洛文尼亚、
   克罗地亚及部分东南欧国家通常逐学年发布。
3. 意大利、德国、奥地利、瑞士、荷兰和比利时必须按地区处理，不能压成一个全国布尔值。
4. 学校、学校类别或地方政府可能存在例外日期。
5. OpenHolidays API 是机器可读聚合源。用于正式预测发布前，应优先按
   `sources.csv` 中的官方页面复核优先级 1–2 地区。
6. OpenHolidays 数据采用
   [Open Database License](https://github.com/openpotato/openholidaysapi.data/blob/main/LICENSE)；
   使用和再分发时应保留来源说明。

## 更新

脚本仅使用 Python 标准库：

```bash
python3 holidays/update_holidays.py
```

API 对较长日期范围有限制，因此脚本按自然年请求，再通过 `record_id` 去重。
建议每月自动更新一次，并在暑假、圣诞假期预测发布前额外运行一次。
