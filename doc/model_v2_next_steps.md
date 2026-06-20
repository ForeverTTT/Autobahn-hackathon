# model v2 —— 接下来要做什么（带可落地代码）

> 配套：`doc/model_v2_review.md`（审查报告）
> 目标 notebook：`model/model_notebook.ipynb`（**不要动 `model_2.ipynb` 备份**）
> 优先级：🔴 必做（影响交付正确性/可信度） → 🟠 重要 → 🟢 加分

---

## 优先级总览

| 顺序 | 任务 | 级别 | 预计改动 | 收益 |
|---|---|---|---|---|
| A | 未来网格 `tagestyp` 重建 | 🔴 | ~12 行 | **暑假/假日峰值不再低估**——单点最高收益 |
| B | conformal 诚实化 + 写盘 + 应用到 forecast | 🔴 | ~30 行 | PICP 指标变可信，区间真的校准 |
| C | 交付前用全量 2023–2025 重训 | 🟠 | 开关 + 重跑 | 多用 1 年数据，提升泛化 |
| D | 施工/2+0 数据局限：领域规则后处理 | 🟠 | ~15 行 + 文档 | 能表达已知未来维修封闭 |
| E | 修对比表基线 + 文案 | 🟠 | ~3 行 | 不误导队友/评委 |
| F | 日聚合 + 颜色分级（前端要的）| 🟠 | ~25 行 | 日历 UI 直接可用 |
| G | 峰值加权、sv_h 直接回归、v_kfz 加流量特征 | 🟢 | 实验 | 边际提升 |

---

## A. 🔴 未来网格 `tagestyp` 重建（最高收益，必做）

**问题**：`build_future_grid` 和 `predict_grid` 里 `tagestyp = where(weekday==7,"s","w")`，永远没有 `u`，公共假日漏判 → 暑假被当工作日，画像取错 → 系统性低估峰值。

**已验证**：holiday 表覆盖到 2029，未来 flags 全非空；规则重建对 2023–2025 真实 tagestyp **准确率 99.91%**。

**改法**：加一个 helper，在 `merge_conditional` 之后（此时 holiday flags 已 join 进来）用 flags 重建 `tagestyp`。两个网格构建函数都改。

```python
def derive_tagestyp(df: pd.DataFrame) -> pd.Series:
    """用日历 + holiday flags 重建 tagestyp（s>u>w 优先级）。
    经 2023–2025 真值验证：准确率 99.91%。
      s = 周日 或 公共假日(DE-BY)
      u = 学校假期(DE-BY) 且非 s   （CLAUDE.md H3: u ≡ is_school_holiday_DE_BY）
      w = 其余
    要求 df 已含 weekday 和 is_public/school_holiday_DE_BY（merge_conditional 后）。
    """
    wd = df["weekday"].astype(int)
    pub = pd.to_numeric(df.get("is_public_holiday_DE_BY", 0), errors="coerce").fillna(0)
    sch = pd.to_numeric(df.get("is_school_holiday_DE_BY", 0), errors="coerce").fillna(0)
    out = np.where((wd == 7) | (pub == 1), "s",
                   np.where(sch == 1, "u", "w"))
    return pd.Series(out, index=df.index)
```

然后在两处把那行 `np.where(...,"s","w")` 删掉，改成：**先 `merge_conditional`（拿到 flags）→ 再 `derive_tagestyp`**。注意 `add_calendar` 不依赖 tagestyp，但 `apply_profiles` 的 `prof_*_sht` 依赖，所以顺序必须是：
```python
grid["tagestyp"] = "w"          # 占位，让 add_calendar/merge 跑通
grid = add_calendar(grid)
grid = merge_conditional(grid)              # 此处 join 进 holiday flags
grid["tagestyp"] = derive_tagestyp(grid)    # ★ 用 flags 重建真实 tagestyp
grid = apply_profiles(grid, profiles)       # 现在 prof_*_sht 取到正确画像
```

> 验证集（2025）用的是**真实 tagestyp**，所以不受影响；本修复只纠正未来推理，消除 train/serve skew。

---

## B. 🔴 conformal 诚实化 + 落到交付

**两个毛病**：(1) 同集校准又同集评估 → 80% 是自欺；(2) 校准量没用到 forecast。

**B1 — 诚实评估（split conformal）**：把 2025 按时间切两半，前半校准、后半报 PICP。

```python
# 在 cell 44，替换原来的 conformal 段
order = np.argsort(va_kfz["ts"].to_numpy())           # 按时间排
n = len(order); half = n // 2
cal_idx, test_idx = order[:half], order[half:]

conf_scores = np.maximum(p10_raw - yk, yk - p90_raw)  # CQR conformity
q = np.ceil((len(cal_idx)+1) * CONFORMAL_COVERAGE) / len(cal_idx)
conf_quantile = float(np.quantile(conf_scores[cal_idx], min(q, 1.0)))

# 在 held-out 的 test 半上报告——这才是可信泛化覆盖率
yk_t = yk[test_idx]
p10_cal = p10_raw[test_idx] - conf_quantile
p90_cal = p90_raw[test_idx] + conf_quantile
picp_cal = float(np.mean((yk_t >= p10_cal) & (yk_t <= p90_cal)) * 100)
mpiw_cal = float(np.mean(p90_cal - p10_cal))
picp_raw_test = float(np.mean((yk_t >= p10_raw[test_idx]) & (yk_t <= p90_raw[test_idx]))*100)
print(f"PICP raw(test半)={picp_raw_test:.1f}%  cal(test半)={picp_cal:.1f}%  Δ={conf_quantile:+.1f}")
```
> 预期：`picp_cal` 落在 ~78–82%（不再是死的 80.0），这才是诚实数字。

**B2 — 落盘并应用到 forecast**：把 `conf_quantile` 存起来，推理时把 P10/P90 各扩 `conf_quantile`。

```python
# 评估后保存
import json
(PROC_DIR / "conformal.json").write_text(json.dumps({"conf_quantile": conf_quantile,
                                                     "coverage": CONFORMAL_COVERAGE}))
CONF_Q = conf_quantile
```
在 `predict_grid`（cell 47）算完 p10/p90、做完单调约束后，加：
```python
out["kfz_h_p10"] = np.clip(out["kfz_h_p10"] - CONF_Q, KFZ_CLIP_MIN, None)
out["kfz_h_p90"] = out["kfz_h_p90"] + CONF_Q
```
> 这样前端区间才真正达到目标覆盖率。`CONF_Q` 在 §4.0 复用模型时也要从 `conformal.json` 读回。

---

## C. 🟠 交付前用全量 2023–2025 重训（两段式）

加一个开关，把"评估口径"和"交付口径"分开：

```python
DEPLOY_FULL_REFIT = True   # 评估完后置 True，重跑画像+模型再生成 forecast
```
- 评估阶段（§4.1–§5）：维持 train≤2024 / val=2025，用于诚实指标。
- 交付阶段（§6 全量推理之前）：`profiles = build_profiles(base[base["kfz_h"].notna()])`（全量），三个模型在全量上 `fit`（无 eval_set 或用末尾小段），再 `predict_grid`。
> 注意 Gletschergarten 2023 无数据——全量重训会自动多吃 2025，利好。

---

## D. 🟠 施工/2+0 数据局限：领域规则后处理

模型学不到 2+0（训练期全 0）。**别硬塞特征**，改为对**已知的未来施工/2+0 封闭日**做后处理：

```python
# 已知未来 2+0 / 封闭计划（来自 Autobahn 公告），对受影响 site+日期 乘容量折减
def apply_capacity_override(fc, closures):
    # closures: list of dict(road, from, to, factor=0.5)
    for c in closures:
        m = (fc["road"]==c["road"]) & (fc["date"].between(c["from"], c["to"]))
        for col in ["kfz_h_p10","kfz_h_p50","kfz_h_p90","sv_h_pred"]:
            fc.loc[m, col] *= c.get("factor", 0.7)
    return fc
```
并在 review/交付文档里写明："2+0 在 2023–2024 训练期无样本，模型主体不建模其影响；已知封闭通过规则叠加。"

---

## E. 🟠 修对比表基线 + 文案（cell 6 / cell 44 / cell 52）

```python
V1_BASELINE["MPIW"] = 365.0          # 改回 v1 文档真实值（原误写 585）
```
- 对比表 PICP 行注明："v2 为 split-conformal 在 held-out 半上的覆盖率，与 v1 同口径"。
- 同时报 `picp_raw`（未校准）一行，诚实展示"模型原生区间 ≈70%，靠 conformal 提到 80%"。
- Peak Recall 文案统一为 top10%（`int(round((1-PEAK_QUANTILE)*100))`）。

---

## F. 🟠 日聚合 + 颜色分级（前端日历直接要）

CLAUDE.md 里两条 CRITICAL，这版 notebook 还没有：

```python
# 1) 日聚合
daily = (forecast.groupby(["site_id","road","direction","site_name","date"])
         .agg(kfz_day_p50=("kfz_h_p50","sum"),
              kfz_day_p10=("kfz_h_p10","sum"),
              kfz_day_p90=("kfz_h_p90","sum"),
              peak_hour=("kfz_h_p50", lambda s: int(s.values.argmax())))
         .reset_index())

# 2) 每站点用 2023–2025 历史日总量分位定阈值（P40/P60/P75/P90）→ 颜色
hist_daily = (traffic.dropna(subset=["kfz_h"]).groupby(["site_id","date"])["kfz_h"].sum())
thr = hist_daily.groupby("site_id").quantile([.4,.6,.75,.9]).unstack()
def to_color(row):
    t = thr.loc[row["site_id"]]
    v = row["kfz_day_p50"]
    return ("green" if v<t[.4] else "yellow" if v<t[.6]
            else "orange" if v<t[.75] else "red" if v<t[.9] else "darkred")
daily["level"] = daily.apply(to_color, axis=1)
daily.to_parquet(PROC_DIR / "forecast_daily_2026_2029.parquet", index=False)
```

---

## G. 🟢 边际提升（有时间再做）

- **峰值加权**：`make_pool(..., weight=)` 给 `kfz_h > 站点P90` 的行 2× 权重 → 提 Recall、补高峰覆盖缺口。
- **sv_h 直接回归** 与占比法二选一对比（占比法会把 kfz 误差乘进去）。
- **v_kfz 加 `kfz_h_p50_pred` 特征**：拥堵降速与流量强相关，speed 模型现在看不到流量预测。
- **conformal 分组校准**：按 site 或 tagestyp 分组算 `conf_quantile`，比全局单值更贴。

---

## 重跑须知 ⚠️

改完 A/B/E 后 **notebook 必须从头跑一遍**（CatBoost 要重训，~几分钟），否则：
- cell 输出与新代码不一致；
- `processed/forecast_2026_2029.parquet` 仍是 **10:44 的陈旧文件**（当前盘上就是旧的，MPIW=328，对不上任何一版）。

跑完核对：`picp_cal` 不再是死的 80.0、forecast 的 MPIW ≈ raw+2×CONF_Q、暑假日 `tagestyp` 含 `u`。
