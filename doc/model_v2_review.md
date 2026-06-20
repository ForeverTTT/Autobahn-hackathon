# model_notebook.ipynb (v2) 审查报告 —— 有没有 hack？真改善了吗？跟数据分析一致吗？

> 审查对象：`model/model_notebook.ipynb`（= `model/model_2.ipynb` 备份，二者 MD5 一致，**备份勿动**）
> 基线：`model/model.ipynb`（v1）
> 审查人：Claude（数据/模型审查）  日期：2026-06-20
> 证据来源：notebook 已执行的 cell 输出 + 直接查验 `data_autobahn/` 原始数据

---

## 0. 一句话结论

**点精度（MAE/MAPE）是真实但很小的改善（~1–5% 相对）；而表格里最抢眼的两项「PICP 69.5→80%」「MPIW 585→393」是不成立的——一个是同集校准的自欺（in-sample leakage），一个是用了错误的 v1 基线。另外发现一个会真正损害 2026–2029 预测质量的 bug：未来网格的 `tagestyp` 退化（暑假被当工作日）。这些都可修。**

整体判断：**没有恶意造假，但有两处"看起来变好其实没变"的误导性指标，和一处真实的部署 bug。** 修掉后这是个扎实的方案。

---

## 1. 真实的改善（这些是干净的，值得保留）✅

| 改动 | 评价 |
|---|---|
| **MultiQuantile 单模型**（`MultiQuantile:alpha=0.1,0.5,0.9` 取代 3 个独立分位模型） | ✅ 正确的架构升级：共享树天然防分位交叉、训练快 ~3×。保留。 |
| **历史画像仍只用训练集（2023–2024）聚合** | ✅ `build_profiles(train_df)` 无泄漏，符合 model.md §8.2「out-of-fold」原则。 |
| **新增假期距离特征**（`days_to/since_holiday`、`is_departure/return_wave_day`、`total_holiday_overlap`） | ✅ 有数据依据、方向正确（抓出发/返程波）。`days_since_holiday_end` 在 SHAP 单点归因里确实进了 Top12。 |
| **新增画像**（`prof_kfz_shs` 季节、`prof_lkw_sht`/`prof_v_sht` 日类型） | ✅ 合理。`prof_kfz_sht` 是 SHAP 第一驱动（+891）。 |
| **新增 WMAPE 指标** | ✅ 行业更稳健的指标，低流量小时不放大误差。好习惯。 |
| **speed_drop：训练集截尾、验证集保留 raw** | ✅ 诚实，验证集不被人为修饰。 |
| **点精度真实小幅提升** | ✅ kfz_h MAPE 16.4→**16.14**、MAE 137.1→**135.4**；sv_h MAPE 20.9→**19.9**；v_kfz 基本持平。真实但幅度小。 |

**结论：v2 的特征/架构工作是干净的，方向对的。问题集中在区间校准的呈现方式 + 未来推理的一致性。**

---

## 2. Hack / 误导性指标（必须修）🔴

### 2.1 🔴【最严重】PICP 80% 是"同集校准"自欺，不是真改善（数据泄漏）

evaluation cell（cell 44）里：

```python
residuals_lo = p10_raw - yk          # yk = 验证集真值
residuals_hi = yk - p90_raw
conf_scores  = np.maximum(residuals_lo, residuals_hi)
conf_quantile = np.quantile(conf_scores, target_q)   # ← 在验证集上算校准量
p10_cal = p10_raw - conf_quantile
p90_cal = p90_raw + conf_quantile
picp_cal = mean((yk >= p10_cal) & (yk <= p90_cal))    # ← 又在同一验证集上报覆盖率
```

**问题**：conformal 的覆盖率保证只在「校准集 ≠ 测试集」时成立。这里用 **2025 验证集** 同时做校准 *和* 报告，于是 `picp_cal` 被构造成恰好等于目标——输出就是干巴巴的 **`80.0%`**（这个"正好命中"本身就是 in-sample 的铁证）。

**真相**：模型**未校准的原始覆盖率 `picp_raw = 69.9%`**，和 v1 的 69.5% **几乎一样**。也就是说 **v2 的区间宽度其实没有变好**。CQR *方法本身*写对了（Romano et al. 的公式没问题），错在**用同一份数据校准又评估**。

> 对比表里"PICP 69.5 → 80.0 ✅ +10.5pt"= 拿 v1 的诚实数 去比 v2 的 in-sample 数，**不是同口径**。

**修法**（详见 next_steps §A）：把 2025 切成「校准半 / 测试半」（或按时间切前后半），在校准半算 `conf_quantile`，在测试半报 PICP；这样得到的才是可信的泛化覆盖率。

### 2.2 🔴【最严重】conformal 校准量根本没用到交付物

`conf_quantile`（实测 +23.5 辆/h）只在评估 cell 里算了打印，**从未写盘、从未应用到未来预测**。`build_future_grid` / cell 30 / `predict_grid`（cell 47）输出的 `kfz_h_p10/p90` 只做了单调性 `max` 约束，**仍是原始 ~69.9% 覆盖率的窄区间**。

→ 即便 §2.1 修成诚实校准，**前端拿到的区间仍未校准**。CLAUDE.md 里那条「[CRITICAL] Fix PICP」实际上**没有落到交付**。

**佐证**：盘上的 `processed/forecast_2026_2029.parquet`（mtime 10:44）MPIW=**328**，既不等于 raw 346 也不等于 cal 393 —— 说明它甚至是**更早的陈旧文件**，根本不是这版 notebook（12:46）生成的。

### 2.3 🟠 MPIW 对比用了错误的 v1 基线（585 vs 文档 365）

`V1_BASELINE["MPIW"] = 585.0`，但 v1 文档（CLAUDE.md）记录的 v1 MPIW 是 **365**。v2 raw=346、cal=393。

- 真实情况：区间宽度从 365 →（校准后）393，其实**略微变宽**。
- 对比表却显示"585 → 393 ▼192 ✅ 改善"——这是**用一个偏大的假基线，把'变宽'包装成'大幅收窄'**。

→ 必须把 `V1_BASELINE["MPIW"]` 改回真实值（或干脆重跑 v1 取数），否则对比表误导队友和评委。

### 2.4 🟡 hyperparameter_guide 关于 rsm 的说法没被数据支持

guide §1.5/§三 称 `rsm=0.8` 能让 PICP「69% → 75–80%」。但实测 **raw PICP = 69.9%**，rsm 并没有把区间显著拉宽。MultiQuantile 的分位间距由分位损失决定，列采样 `rsm` 对它影响很弱。这个说法应在 guide 里更正，别让人以为调 rsm 能解决覆盖率。

---

## 3. 与数据分析一致性 / 真实 bug（影响 2026–2029 交付质量）

### 3.1 🔴 未来网格 `tagestyp` 退化 —— 暑假被当成工作日（train/serve skew）

`build_future_grid`（cell 20）与 `predict_grid`（cell 47）都用：

```python
grid["tagestyp"] = np.where(grid["weekday"] == 7, "s", "w")   # 只有 s/w，永远没有 u
```

但模型是用**真实 tagestyp（w/s/u 三类）**训练的，而且 `prof_kfz_sht`（按 `tagestyp` 聚合）是 **SHAP 头号驱动、画像信号的主力**。后果：

- **未来所有暑假/学校假期工作日 → tagestyp 被写成 'w'** → `prof_kfz_sht` 取到「工作日画像」而非「假期画像」→ **系统性低估**。
- **落在工作日的公共假日 → 也被写成 'w'**（漏报 's'）。

这恰好打在**挑战最看重的夏季出行高峰日**上。

**已查证可修**（直接查原始数据）：
- holiday 表覆盖 **2023-01-01 ~ 2029-12-31**（2557 天），未来 1461 天的 `is_school_holiday_DE_BY` / `is_public_holiday_DE_BY` **全部非空**（school 365 天、public 52 天）。
- 用规则 **`s` if 周日 or 公共假日，elif 学校假期 → `u`，else `w`** 重建 tagestyp，对 2023–2025 的真实 tagestyp **准确率 99.91%（1096 天只错 1 天）**：

```
recon →     s     u     w
real s    195     0     0     （s 规则 100% 命中）
real u      0   227     0     （u ≡ 学校假期，100%）
real w      0     1   673
```

→ 这是**单点收益最高的修复**：未来网格用 holiday flags 重建 tagestyp，让暑假/假日恢复正确画像。（CLAUDE.md H3 也已验证 `u ≡ is_school_holiday_DE_BY`，与此完全吻合。）

### 3.2 🟢 施工特征 0.0% 重要性 —— 是正确的，不是 bug（但要写清局限）

直接查训练窗（2023–2024，731 天）：

| 特征 | 训练期取值 |
|---|---|
| `has_2_plus_0` | **全 0**（0/731 天） |
| `has_a93_construction` | **全 0** |
| `has_target_bbox_construction` | **全 0** |
| `two_plus_0_count` / `sum_closed_lanes` | **全 0** |
| `has_a8_construction` | 仅 28/731 天 |

→ 训练期里施工特征**几乎零方差**，CatBoost 学不到任何东西，0.0% 重要性**完全符合预期**，代码没坏。

**但要警示**：这意味着模型**根本无法表达 "2+0" 维修对容量减半的影响**（而 2+0 是挑战明确关心的场景）。这是**数据局限**，不是模型问题。对策见 next_steps §D（已知未来 2+0 封闭路段用领域规则后处理叠加）。

### 3.3 🟡 最终交付预测只用了 2023–2024，丢掉了 2025 一整年信号

`profiles` 和三个模型都只在训练集（2023–2024）上拟合，而 `predict_grid`/全量推理直接复用它们生成 2026–2029。但 model.md 和 hyperparameter_guide §2.1 都写明"**推理时画像应用全量 2023–2025**"。

→ 现状是**评估口径（2023-24 训练 / 2025 验证）被直接拿去当交付口径**，白白浪费 2025。正确做法是两段式：评估用切分；**交付前用全量 2023–2025 重训画像+模型再生成 forecast**（见 next_steps §C）。

---

## 4. 指标实测汇总（来自 notebook 实际输出，非文档转述）

| 指标 | v1（文档/诚实） | v2 raw（诚实） | v2 表格里展示 | 真实判断 |
|---|---|---|---|---|
| kfz_h MAE | 137.1 | **135.4** | 135.4 | ✅ 真改善（小） |
| kfz_h MAPE% | 16.4 | **16.14** | 16.14 | ✅ 真改善（小，-0.26pt）|
| kfz_h WMAPE% | — | **10.69** | 10.69 | 新增，参考 |
| sv_h MAPE% | 20.9 | **19.9** | 19.9 | ✅ 真改善 |
| v_kfz MAPE% | 7.5 | **7.49** | 7.49 | ➖ 基本持平 |
| **PICP%（原始）** | 69.5 | **69.9** | （未进对比表）| ➖ **没变** |
| **PICP%（表格）** | 69.5 | 69.9 | **80.0** | 🔴 in-sample 自欺 |
| **MPIW** | **365** | 346 / cal 393 | 用了 **585** 当 v1 | 🔴 假基线 |
| Peak Recall% | 88.1 | **88.1** | 88.1 | ➖ 持平 |

**Peak Recall top% 还有个小坑**：cell 44 用 `int((1-PEAK_QUANTILE)*100)` 算标签，PEAK_QUANTILE=0.90 → 显示"top9%"（应为 top10%，浮点 0.099999 取整）；对比表标题又硬写 top10%。无伤大雅，但前后不一致。

---

## 5. 审查结论速览

| # | 问题 | 级别 | 性质 |
|---|---|---|---|
| 2.1 | PICP 80% = 同集 conformal 自欺 | 🔴 | 误导指标 |
| 2.2 | conformal 校准未应用到交付预测 | 🔴 | 交付缺陷 |
| 3.1 | 未来网格 tagestyp 退化（暑假当工作日）| 🔴 | 真实 bug |
| 2.3 | MPIW 对比用错 v1 基线（585↔365）| 🟠 | 误导指标 |
| 3.3 | 交付预测未用全量 2023–2025 重训 | 🟠 | 次优 |
| 2.4 | guide 关于 rsm 提升 PICP 的说法 | 🟡 | 文档失实 |
| 3.2 | 施工 0% 重要性 | 🟢 | 正确，记为数据局限 |
| 4 | Peak top9%/top10% 文案不一致 | 🟢 | 文案 |

修复方案与代码见 **`doc/model_v2_next_steps.md`**。

---

## 6. ✅ 已应用的修复（A+B+E）+ 重跑结果

> 已直接改进 `model/model_notebook.ipynb` 并用 `.venv` 从头重跑刷新输出（`model_2.ipynb` 备份未动）。

**改了什么**
- **A 未来网格 tagestyp 重建**：新增 `derive_tagestyp()`，`build_future_grid` / `predict_grid` 在 `merge_conditional` 后用 holiday flags 重建 tagestyp（s>u>w）。暑假/假日不再被当工作日。
- **B conformal 诚实化 + 落盘 + 应用**：评估改为 split-conformal（2025 按时间前半校准/后半评估）；`conf_quantile` 存 `processed/conformal.json`；`predict_grid`（及 cell 30）把 P10/P90 各扩 `CONF_Q`，§4.0 复用时读回。
- **E 对比表诚实化**：`V1_BASELINE["MPIW"]` 585→365；同时报 raw/cal 两行 PICP；Peak 文案 top10%。

**重跑后的诚实指标（held-out 测试半）**

| 指标 | 修复前（误导）| 修复后（诚实）|
|---|---|---|
| PICP raw（未校准）| 隐去不报 | **71.4%** |
| PICP cal | 80.0（同集自欺）| **81.5%**（split-conformal，真实泛化）|
| MPIW | "585→393 大幅收窄✅"（假基线）| **365→393（略微变宽 ❌）**——这是换取真覆盖率的合理代价 |
| kfz_h MAPE% | 16.14 | 16.14（不变，真实小改善）|
| `conf_quantile` | 未落盘、未应用 | **+26.3 辆/h，已写 conformal.json 并应用到 forecast** |

**交付物核对**
- `processed/forecast_2026_2029.parquet` 已重生成（420,768 行），区间 **MPIW≈385**（已含 conformal），`p10≥0`。
- tagestyp 修复生效示例：`A8_Sbg_MQQ37` 8月日均 ≈63,653 vs 11月 ≈43,453（暑假峰值正确抬升 ~46%）。
- `processed/conformal.json` 新增。

**结论**：v2 的真实价值是 **(1) 区间现在真的校准到 ~80%（且落到交付）+ (2) 未来暑假/假日峰值不再系统性低估**；点精度是真实但很小的提升。对比表不再误导。剩余 C/D/F/G 见 next_steps，未做（需队友决定是否全量重训/加日聚合等）。
