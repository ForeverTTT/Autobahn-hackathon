# 拜仁州、萨尔茨堡州、蒂罗尔州节假日数据

本目录只保存可能影响 **A8 East（慕尼黑—萨尔茨堡）** 和
**A93 South（罗森海姆—库夫施泰因）** 的以下三个地区：

| 地区代码 | 地区 |
|---|---|
| `DE-BY` | 德国拜仁州（Bavaria） |
| `AT-SB` | 奥地利萨尔茨堡州（Salzburg） |
| `AT-TI` | 奥地利蒂罗尔州（Tyrol） |

数据目标范围为 **2023-01-01 至 2029-12-31**。全国性法定假日只要适用于目标州，
就会映射到相应目标州；其他国家和德国、奥地利的其他州均不保留。
只适用于州内个别城市的地方假日也不保留，例如奥格斯堡和平节不会被当作拜仁全州假日。

学校假期只保存当前已经发布或被数据源收录的日期。尚未发布的未来日期不会被
填成“无假期”，应结合 `coverage.csv` 判断数据完整性。

## 文件

| 文件 | 内容 |
|---|---|
| `holiday_periods.csv` | 每行一个去重后的节假日或学校假期区间 |
| `holiday_scopes.csv` | 每个假期适用于三个目标州中的哪些州 |
| `holiday_dates.csv` | 按目标州展开到每天，可直接与交通数据连接 |
| `coverage.csv` | 每个目标州的公共/学校假期数据覆盖情况 |
| `sources.csv` | 三个目标州的机器数据源与官方核验来源 |
| `traffic_windows_2023_2029.csv` | 根据三个目标州学校假期自动推导的 2023–2029 交通窗口 |
| `update_holidays.py` | 重新下载和生成数据的脚本 |

## `holiday_periods.csv`

这是去重后的假期区间表。同一个奥地利全国假日同时适用于萨尔茨堡和蒂罗尔时，
这里只保存一条记录，具体适用州由 `holiday_scopes.csv` 表示。

主要字段：

| 字段 | 说明 |
|---|---|
| `record_id` | OpenHolidays UUID，也是其他表的连接键 |
| `holiday_class` | `public_holiday`、`school_holiday`、`school_marker` 等 |
| `api_type` | 数据源原始类型，如 `Public`、`School`、`EndOfLessons` |
| `start_date`, `end_date` | 包含首尾两日的 ISO 日期区间 |
| `duration_days` | 区间自然日数量 |
| `nationwide` | 该记录在所属国家是否全国适用 |
| `target_region_count` | 该记录适用于三个目标州中的几个 |
| `verification_status` | `aggregated_official_calendar` 表示来自官方日历聚合数据，未逐行人工复核 |
| `record_origin` | `api` 或 `statutory_calculation` |
| `retrieved_at` | UTC 抓取时间 |

`EndOfLessons` 和 `BackToSchool` 是学校日历边界标记，不应直接视作完整假期。

## `holiday_scopes.csv`

该表只允许出现以下 `region_code`：

```text
DE-BY
AT-SB
AT-TI
```

字段包括：

- `record_id`：连接 `holiday_periods.csv`。
- `country_code`：`DE` 或 `AT`。
- `region_code`：目标州代码。
- `region_name`：Bavaria、Salzburg 或 Tyrol。

## `holiday_dates.csv`

该表按照“日期 × 假期 × 目标州”展开。因此一个同时适用于萨尔茨堡和蒂罗尔的
奥地利全国假日，在同一天会有两行。

主要字段：

- `date`：连接交通数据的日期。
- `region_code`、`region_name`：无需再次连接地域表即可按州建模。
- `day_index=0`：假期第一天。
- `days_to_end=0`：假期最后一天。
- `is_start_date`、`is_end_date`：用于构造出发和返程波。
- `weekday_iso`：周一为 1，周日为 7。

使用示例：

```python
import pandas as pd

holidays = pd.read_csv("holidays/holiday_dates.csv")

features = (
    holidays[holidays["holiday_class"].isin(["school_holiday", "public_holiday"])]
    .groupby(["date", "region_code"])
    .agg(active_holidays=("record_id", "nunique"))
    .reset_index()
)
```

## `coverage.csv`

每个目标州包含两行：

- `dataset_type=public`
- `dataset_type=school`

因此正常情况下共 6 行。重要字段：

- `target_last_record_start`、`target_last_record_end`
- `target_record_count`
- `api_record_count`、`calculated_record_count`
- `coverage_status`：区分纯API记录和含法律规则计算记录的数据
- `has_any_record_overlap_2023` 至 `has_any_record_overlap_2029`

`has_any_record_overlap_YYYY=true` 只表示至少有一个区间与该年重叠，不代表该年
学校日历完整。例如跨年圣诞假期可能让下一年显示为 `true`，但下一年暑假仍未发布。

## `traffic_windows_2023_2029.csv`

该文件只使用拜仁、萨尔茨堡和蒂罗尔三个州的学校假期推导，覆盖 2023–2029。
每个长度不少于 3 天的学校假期都会生成：

- `departure`：假期开始附近的出发窗口；
- `return`：假期结束附近的返程窗口。

相互重叠或紧邻的三州窗口会被合并。`risk_level` 根据同时涉及的州数以及是否为
暑假确定。它仍然只是规则分析结果，不是政府发布的交通预测：

```text
assessment_status=rule_derived
```

## 建议交通特征

```text
is_school_holiday_DE_BY
is_school_holiday_AT_SB
is_school_holiday_AT_TI
is_public_holiday_DE_BY
is_public_holiday_AT_SB
is_public_holiday_AT_TI
three_region_holiday_overlap_count
days_to_next_school_holiday_start
is_first_holiday_friday_or_saturday
is_last_holiday_sunday
```

通常假期开始提高 A8 萨尔茨堡方向和 A93 库夫施泰因方向流量，假期结束则提高
A8 慕尼黑方向和 A93 罗森海姆方向返程流量。

## 数据来源与限制

- 机器数据来自 [OpenHolidays API](https://www.openholidaysapi.org/en/)。
- 拜仁官方核验来源为
  [巴伐利亚教育部](https://www.km.bayern.de/termine/ferien-und-feiertage)。
- 萨尔茨堡和蒂罗尔官方核验来源为
  [奥地利政府假期日历](https://www.oesterreich.gv.at/de/themen/bildung_und_ausbildung/schulen/3)。
- 奥地利 2029 年完整学校日历截至 2026-06-19 尚未逐项发布。数据集中2029年
  学期假、复活节假、圣灵降临节假、暑假、秋假、圣诞假及州纪念日依据现行
  [《Schulzeitgesetz 1985》第2条](https://ris.bka.gv.at/NormDokument.wxe?Abfrage=Bundesnormen&Gesetzesnummer=10009575&Paragraf=2)
  计算，并标记为 `calculated_from_current_law`，不冒充已发布日历。
- 地方学校和特定学校类型可能存在例外日期。
- 拜仁州的圣母升天节只在部分以天主教人口为主的市镇属于法定假日；数据源将其标为
  `DE-BY` 地区性假日，建模时不应把它解释成拜仁全州统一放假。
- OpenHolidays 数据采用
  [Open Database License](https://github.com/openpotato/openholidaysapi.data/blob/main/LICENSE)。

## 更新

```bash
python3 holidays/update_holidays.py
```

脚本只请求 `DE-BY`、`AT-SB` 和 `AT-TI`，按自然年下载后通过 UUID 去重，
并自动生成2023–2029交通窗口。
