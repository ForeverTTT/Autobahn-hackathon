# scripts/ — 数据采集与验证脚本

这里的脚本分两类：**数据采集类**（已跑完，产物在 `external/`，不需要重跑）和**分析验证类**（可以随时重跑）。

---

## 已跑完，不需要重跑

以下脚本的产物已经在 `external/` 目录下。**直接用 `external/` 里的文件就好，不需要再执行。**

| 脚本 | 产物 | 说明 |
|---|---|---|
| `fetch_weather.py` | `external/weather_daily.parquet`<br>`external/weather_climatology.parquet` | 从 Open-Meteo 免费 API 拉取 AD Rosenheim 站 2018-2025 年逐小时天气，聚合为每日降雨/结冰/低能见度概率 |
| `build_special_events.py` | `external/special_events_daily.csv`<br>`external/special_events_periods.csv` | 手工整理的 Munich / Salzburg / Rosenheim / Kufstein 节庆日历（2023-2029），含 Oktoberfest、Festspiele 等 10 个活动 |
| `fix_construction_data.py` | `external/construction_daily.parquet`<br>`external/construction_sites_clean.csv` | 从 autobahn.de API 重新抓取施工数据，修复了 3 个 bug（详见下方），产出每日 (date, road) 级施工状态 |

### fix_construction_data.py 修复了什么

原版脚本 `fetch_construction_data.py` 存在 3 个 bug，导致几乎所有施工项目都被错误标记为 2+0：

1. **2+0 判断逻辑错误**：只要有"ARROW_UP + SEPARATE"就标 2+0，实际上还要求"行车方向车道数 = 0"
2. **施工结束日期缺失**：API 的 `endTimestamp` 字段通常为空，真实日期藏在德文描述文字里，需正则提取
3. **A8/A93 归属判断有误**：用了"先匹配者优先"而不是按坐标范围判断

修复后结果：**6 条真 2+0**（原来 134 条全标成 2+0），其中 A8 有 4 条，A93 有 2 条。

> 如果要重新抓取最新施工数据：`python scripts/fix_construction_data.py`
> 加 `--no-fetch` 参数可以只用缓存（`external/_autobahn_cache/`）重新解析，不调用 API。

---

## 可以重跑的分析脚本

| 脚本 | 产出 | 说明 |
|---|---|---|
| `validate_data_hypotheses.py` | `analysis_output/hypothesis_summary.md` 等 | 验证 4 个数据假设（见下方） |
| `plot_station_map.py` | `analysis_output/station_map.png` | 重新生成测站位置图 |

### validate_data_hypotheses.py 验证了什么

```bash
python scripts/validate_data_hypotheses.py          # 跑全部 4 个假设
python scripts/validate_data_hypotheses.py --only h3 h4  # 只跑 H3 H4
```

| 假设 | 结论 |
|---|---|
| **H1** v_kfz 速度上限 | p99=155 km/h，建议 cap 在 **180 km/h**（之前 160 太激进） |
| **H2** sv_h 和 q_lkw 是否一致 | 相关 **r=0.985**，比例中位数 0.94；两者基本等价，训练用 sv_h |
| **H3** tagestyp='u' 是否等于学校假期 | **100% 等价**，`u` 的 152 天全部落在 DE-BY 学校假期内 |
| **H4** 日内曲线最优分组粒度 | 按 **(tagestyp, weekday, season/month)** 分组，组内变异系数降到 **10.5%** |

---

## 队友的合表脚本

| 脚本 | 说明 |
|---|---|
| `merge_hourly_traffic.py` | 队友原版：合并 DAUZ 小时表 |
| `merge_minute_traffic.py` | 队友原版：合并 1-min 数据 |

这两个是队友维护的，不要动。训练代码用 `src/data/load_dauz.py` 直接读原始 CSV，不依赖这里的合表产物。
