# analysis_output/ — 数据分析结果

这里是探索性分析的产物，**供参考，不进入训练流水线**。

---

## 文件说明

### `station_map.png` — 路网与测站位置图

A8-Ost（蓝）和 A93-Süd（红）的路网示意图，标注了 7 个测站和主要城市。

生成脚本：`scripts/plot_station_map.py`

---

### `hypothesis_summary.md` — 数据假设验证结果

对 4 个关键假设的实测结论，这些结论直接影响了特征工程和模型设计：

| 假设 | 结论 | 对代码的影响 |
|---|---|---|
| **H1** v_kfz 速度上限 | 建议 **cap 180 km/h**（p99=155, p99.9=173） | 1-min 数据清洗时过滤异常值 |
| **H2** sv_h ≈ q_lkw？ | **r=0.985**，两者在日级几乎等价 | 训练统一用 sv_h，不用 q_lkw |
| **H3** tagestyp='u' = DE-BY 学校假期？ | **100% 等价**，无一例外 | `is_school_holiday_DE_BY` 就是强特征 |
| **H4** 日内 24h 曲线分组粒度 | 按 **(tagestyp, weekday, month/season)** 分组，组内变异系数 **10.5%** | `src/output/peak_window.py` 的分组方式 |

完整数据和图表由 `scripts/validate_data_hypotheses.py` 生成。

---

## 术语速查

| 术语 | 含义 |
|---|---|
| `tagestyp` | DAUZ 数据自带的日类型：`w`=工作日，`s`=周日/节假日，`u`=学校假期高峰日 |
| `wochentag` | ISO 星期数：1=周一，7=周日 |
| `kfz_h` | 每小时总车辆数（Kraftfahrzeug，所有机动车） |
| `sv_h` | 每小时重型车辆数（Schwerverkehr，>3.5t，即卡车/货车） |
| `q_kfz` | 每分钟总车辆数（来自 1-min 数据，`kfz_h ≈ sum(q_kfz) × 60`） |
| `q_lkw` | 每分钟卡车数（来自 1-min 数据） |
| `v_kfz` | 每分钟检测车辆的平均速度（km/h） |
| `DE-BY` | Bavaria（巴伐利亚，慕尼黑所在州） |
| `AT-SB` | Salzburg（萨尔茨堡，奥地利） |
| `AT-TI` | Tirol（蒂罗尔，Kufstein 所在州，奥地利） |
| `2+0` | 双向借道施工：两向车流共用一条行车方向，通行能力减约 50% |
| CV（变异系数）| 标准差 / 均值，衡量组内分散程度。越低 = 同一组内各天的形状越一致 |

---

## 其他分析图（在本地 `analysis_output/`，未推入 git）

| 文件 | 内容 |
|---|---|
| `null_heatmap_*.png` | 各测站每月数据缺失率热图 |
| `hypothesis_h4_intraday_cv.png` | H4：不同分组粒度的 CV 对比图 |
| `hypothesis_h3_tagestyp_u.csv` | H3：'u' 天与 DE-BY 假期的对照表 |

可在本地跑 `python scripts/validate_data_hypotheses.py` 重新生成。
