# Tasks D, F, G — Implementation Tutorial

> 配套：`model_notebook.ipynb`
> 这些代码供手动修改 notebook 时参考，每个 task 独立、可直接插入对应 cell 位置。

---

## D. 🟠 施工/2+0 数据局限：领域规则后处理

**问题**：训练期（2023–2024）`has_2_plus_0` 全为 0，模型学不到 2+0 对容量的减半影响。
**对策**：对**已知的未来封闭/维修计划**做规则后处理，不硬塞特征。

### 插入位置

在 notebook 的 §6（全量推理）之后，加一个新 cell。放到 `forecast_2026_2029.parquet` 保存之前或之后都可以，推荐在保存后读取修改再写回。

### 代码

```python
# ========== D: 已知 2+0 / 封闭计划规则叠加 ==========
# 模型训练期 2+0 样本为 0，无法表达容量减半。对已知未来封闭路段做后处理。
# 数据来源：Die Autobahn GmbH 公告 / 施工计划表。此处为示例结构，请替换为真实数据。

# 格式：每条记录 = (road, direction, date_from, date_to, capacity_factor)
#   capacity_factor: 0.5 = 2+0 对向通行（双向共用单幅，容量减半）
#                    0.7 = 单车道封闭（容量降 30%）
#                    0.0 = 完全封闭（需要绕行 — 这种情况模型也处理不了，建议手工覆盖）
KNOWN_CLOSURES = [
    # 示例（请替换为真实公告数据）：
    # dict(road="A8", direction="Sbg", date_from="2026-07-15", date_to="2026-08-10",
    #      bab_km_min=104.0, bab_km_max=108.0, factor=0.5,
    #      label="A8 东部 2+0 维修 (km 104-108)"),
]

def apply_capacity_override(df, closures):
    """对已知封闭/2+0 路段做容量折减。
    df: 包含 road, direction, date, bab_km 的 DataFrame
    closures: list of dict(road, direction, date_from, date_to, bab_km_min, bab_km_max, factor, label)
    返回修改后的 df（原地修改 + 返回）。
    """
    if not closures:
        print("D: 无已知封闭计划，跳过容量后处理。")
        return df

    for c in closures:
        mask = (
            (df["road"] == c["road"])
            & (df["direction"] == c["direction"])
            & (df["date"].between(pd.Timestamp(c["date_from"]), pd.Timestamp(c["date_to"])))
        )
        # 可选：按里程桩号进一步过滤（如果 forecast 含 bab_km）
        if "bab_km" in df.columns and "bab_km_min" in c:
            mask = mask & (df["bab_km"] >= c["bab_km_min"]) & (df["bab_km"] <= c["bab_km_max"])

        n = mask.sum()
        if n > 0:
            factor = c.get("factor", 0.7)
            for col in ["kfz_h_p10", "kfz_h_p50", "kfz_h_p90", "sv_h_pred"]:
                if col in df.columns:
                    df.loc[mask, col] *= factor
            print(f"D: {c.get('label', c)} → {n:,} rows ×{factor:.1%}")
        else:
            print(f"D: {c.get('label', c)} → 0 rows matched (skip)")

    return df

# ★ 在保存 forecast 之后调用（或加载后修改再写回）
# 示例：
# forecast = pd.read_parquet(PROC_DIR / "forecast_2026_2029.parquet")
# forecast = apply_capacity_override(forecast, KNOWN_CLOSURES)
# forecast.to_parquet(PROC_DIR / "forecast_2026_2029.parquet", index=False)
print("D: 容量后处理函数就绪（KNOWN_CLOSURES 为空时无操作）")
```

### 注意事项
- 这个函数只在交付阶段跑，不影响训练和评估。
- `KNOWN_CLOSURES` 需要你们手动填写（来自 Autobahn 公告），我填的示例数据是假的。
- 文档/评审时要写明："模型训练期无 2+0 样本，已知封闭通过规则叠加处理。"

---

## F. 🟠 日聚合 + 颜色分级（前端日历直接要）

**CLAUDE.md 两条 CRITICAL，目前 notebook 没有。**

### 插入位置

在 §6 全量推理保存后，加一个新 cell。

### 代码

```python
# ========== F: 日聚合 + 颜色分级 ==========
# 前端日历 UI 需要：① 每日总流量 ② 峰值小时 ③ 颜色等级

# ---- F1: 日聚合 ----
daily = (
    forecast.groupby(["site_id", "road", "direction", "site_name", "date"])
    .agg(
        kfz_day_p50=("kfz_h_p50", "sum"),
        kfz_day_p10=("kfz_h_p10", "sum"),
        kfz_day_p90=("kfz_h_p90", "sum"),
        peak_hour=("kfz_h_p50", lambda s: int(s.values.argmax())),
        sv_day=("sv_h_pred", "sum"),
    )
    .reset_index()
)

# ---- F2: 每站点颜色阈值（基于 2023–2025 历史日总量分位数）----
# 用全量历史数据（非仅训练集），因为颜色分级反映长期交通水平
hist_daily = (
    traffic.dropna(subset=["kfz_h"])
    .groupby(["site_id", "date"])["kfz_h"]
    .sum()
    .reset_index()
)

# 每站点分位阈值：P40=green→yellow, P60=yellow→orange, P75=orange→red, P90=red→darkred
THRESHOLD_PERCENTILES = [0.40, 0.60, 0.75, 0.90]
COLOR_LABELS = ["green", "yellow", "orange", "red", "darkred"]

thresholds = (
    hist_daily.groupby("site_id")["kfz_h"]
    .quantile(THRESHOLD_PERCENTILES)
    .unstack()
)
thresholds.columns = [f"thr_p{int(p*100)}" for p in THRESHOLD_PERCENTILES]
print("Per-site daily flow thresholds (P40/P60/P75/P90):")
display(thresholds.round(0))

def to_color(row, thresholds=thresholds):
    """将日总流量映射到颜色等级。"""
    t = thresholds.loc[row["site_id"]]
    v = row["kfz_day_p50"]
    if v < t.iloc[0]:
        return "green"
    elif v < t.iloc[1]:
        return "yellow"
    elif v < t.iloc[2]:
        return "orange"
    elif v < t.iloc[3]:
        return "red"
    else:
        return "darkred"

daily["level"] = daily.apply(to_color, axis=1)

# 统计各颜色占比（合理性检查：绿色应最多，暗红应极少）
print("\nColor distribution across all sites & days:")
print(daily["level"].value_counts().reindex(COLOR_LABELS))

# ---- F3: 落盘 ----
DAILY_PARQUET = PROC_DIR / "forecast_daily_2026_2029.parquet"
daily.to_parquet(DAILY_PARQUET, index=False)
print(f"\n✔ Daily forecast saved: {DAILY_PARQUET} ({len(daily):,} rows)")
display(daily.head(10))
```

### 输出说明
- `forecast_daily_2026_2029.parquet`：每行 = 一个站点一天，列含 `kfz_day_p50`（预测日总流量）、`peak_hour`（峰值小时 0-23）、`level`（green/yellow/orange/red/darkred）。
- 前端读取这个文件即可渲染日历热力图。

---

## G. 🟢 边际提升（实验性，有时间再做）

以下 4 个改进均为可选实验。每个独立、可单独尝试。

### G1: 高峰小时加权训练（提升 Peak Recall）

**原理**：当前损失对所有小时一视同仁，但业务最关心峰值时段。给高峰行更高权重，让模型更关注峰值。

**插入位置**：在 §4.1 训练 cell 的 `make_pool` 调用处修改。

```python
# ========== G1 (可选): 高峰小时加权训练 ==========
# 给 kfz_h > 站点 P90 的行 2× 权重，让模型更关心拥堵高峰
# 插入到 train_pool / val_pool 创建之前

if "USE_PEAK_WEIGHT" in globals() and USE_PEAK_WEIGHT:
    # 计算每个站点的小时 P90 阈值（仅用训练集）
    site_p90 = (
        train_df.groupby("site_id")["kfz_h"]
        .quantile(0.90)
        .rename("site_p90")
    )
    train_df = train_df.merge(site_p90, on="site_id", how="left")
    val_df = val_df.merge(site_p90, on="site_id", how="left")

    train_weights = np.where(train_df["kfz_h"] > train_df["site_p90"], 2.0, 1.0)
    val_weights = np.where(val_df["kfz_h"] > val_df["site_p90"], 2.0, 1.0)

    train_pool = Pool(X_train, y_train, cat_features=cat_idx, weight=train_weights)
    val_pool = Pool(X_val, y_val, cat_features=cat_idx, weight=val_weights)
    print(f"G1: Peak weighting enabled — "
          f"{(train_weights > 1).mean():.1%} train / {(val_weights > 1).mean():.1%} val rows weighted 2×")
```

在超参数 cell (§1.1) 加开关：
```python
USE_PEAK_WEIGHT = False   # G1: 设为 True 启用高峰加权（可能提升 Peak Recall 1-3pt）
```

### G2: sv_h 直接回归（与占比法对比）

**原理**：当前占比法 `sv_h = lkw_ratio × kfz_h_p50` 会把 kfz 误差乘进去。直接回归 sv_h 可能更准，但丢失了"大车占比"的物理约束。

**插入位置**：在 §4.3 训练 cell 旁边，作为可切换的实验分支。

```python
# ========== G2 (可选): sv_h 直接回归 vs 占比法对比 ==========
# 取消下面注释以训练直接 sv_h 回归模型，与当前占比法对比 MAE/MAPE
if "SV_DIRECT_REGRESSION" in globals() and SV_DIRECT_REGRESSION:
    print("G2: Training direct sv_h regression model...")

    sv_features = FEATURES_LKW  # 复用 lkw 的特征集
    X_train_sv = train_df[sv_features].copy()
    X_val_sv = val_df[sv_features].copy()
    y_train_sv = train_df["sv_h"]
    y_val_sv = val_df["sv_h"]

    cat_idx_sv = [i for i, c in enumerate(sv_features) if c in CAT_FEATURES]
    for c in [sv_features[i] for i in cat_idx_sv]:
        X_train_sv[c] = X_train_sv[c].astype(str)
        X_val_sv[c] = X_val_sv[c].astype(str)

    train_pool_sv = Pool(X_train_sv, y_train_sv, cat_features=cat_idx_sv)
    val_pool_sv = Pool(X_val_sv, y_val_sv, cat_features=cat_idx_sv)

    sv_direct_params = {**CB_PARAMS, "loss_function": "RMSE", "eval_metric": "RMSE"}
    sv_direct_model = train_cb(train_pool_sv, val_pool_sv, sv_direct_params, "sv_h_direct")

    # 验证集评估
    sv_direct_pred = sv_direct_model.predict(X_val_sv)
    sv_ratio_pred = lkw_pred * kfz_for_sv  # 占比法（来自 §5 评估 cell）

    print(f"\nG2 sv_h 对比 (2025 val):")
    print(f"  占比法   MAE={mae(y_val_sv, sv_ratio_pred):.1f}  MAPE={mape(y_val_sv, sv_ratio_pred):.1f}%")
    print(f"  直接回归 MAE={mae(y_val_sv, sv_direct_pred):.1f}  MAPE={mape(y_val_sv, sv_direct_pred):.1f}%")
```

在超参数 cell 加开关：
```python
SV_DIRECT_REGRESSION = False   # G2: 设为 True 跑 sv_h 直接回归对比实验
```

### G3: v_kfz 模型加入流量预测特征

**原理**：速度下降与流量强相关（拥堵 = 高流量 → 低速）。当前 speed 模型只靠画像特征推断流量水平，不知道预测日具体有多堵。把 `kfz_h_p50_pred`（流量预测值）作为输入，speed 模型能看到"今天会有多少车"。

**插入位置**：§4.4 训练前。需要两步训练（先 kfz → 后 speed）。

```python
# ========== G3 (可选): v_kfz 模型加入 kfz_h 预测值作为特征 ==========
if "SPD_ADD_KFZ_PRED" in globals() and SPD_ADD_KFZ_PRED:
    print("G3: Adding kfz_h_p50_pred to speed model features...")

    # 在训练集上做 kfz 预测（用已训好的 kfz_model）
    X_kfz_train = train_df[FEATURES_KFZ].copy()
    for c in [col for col in CAT_FEATURES if col in FEATURES_KFZ]:
        X_kfz_train[c] = X_kfz_train[c].astype(str)
    train_df["kfz_p50_pred"] = predict_kfz_q(train_df, "p50", model=kfz_model)

    X_kfz_val = val_df[FEATURES_KFZ].copy()
    for c in [col for col in CAT_FEATURES if col in FEATURES_KFZ]:
        X_kfz_val[c] = X_kfz_val[c].astype(str)
    val_df["kfz_p50_pred"] = predict_kfz_q(val_df, "p50", model=kfz_model)

    # 扩展 speed 特征集
    FEATURES_SPD_V2 = FEATURES_SPD + ["kfz_p50_pred"]
    print(f"  speed features: {len(FEATURES_SPD)} → {len(FEATURES_SPD_V2)}")

    # 用 FEATURES_SPD_V2 代替 FEATURES_SPD 训练 spd_model
    # ... (训练代码同 §4.4，仅换特征集)
```

在超参数 cell 加开关：
```python
SPD_ADD_KFZ_PRED = False   # G3: 设为 True 让 speed 模型看到流量预测值
```

### G4: Conformal 分组校准（per-site 或 per-tagestyp）

**原理**：当前全局一个 `conf_quantile = +26.3 veh/h`。但不同站点/日类型的区间宽度需求不同——有的站点区间偏宽，有的偏窄。分组校准让每个组有独立的 `conf_quantile`，更贴。

**插入位置**：替换 §5 评估 cell 中的 conformal 段。

```python
# ========== G4 (可选): 分组 conformal 校准 ==========
# 用 tagestyp 分组（或 site_id），每组独立算 conf_quantile
if "CONFORMAL_GROUP_BY" in globals() and CONFORMAL_GROUP_BY:
    CONFORMAL_GROUP_COL = CONFORMAL_GROUP_BY  # e.g. "tagestyp" or "site_id"

    order = np.argsort(va_kfz["ts"].to_numpy())
    n = len(order); half = n // 2
    cal_idx, test_idx = order[:half], order[half:]

    conf_scores = np.maximum(p10_raw - yk, yk - p90_raw)
    groups = va_kfz[CONFORMAL_GROUP_COL].to_numpy().astype(str)

    # 每组独立算分位数
    conf_quantiles = {}
    for grp in np.unique(groups[cal_idx]):
        mask_cal = (groups[cal_idx] == grp)
        if mask_cal.sum() < 50:
            continue  # 样本太少跳过
        q = min(np.ceil((mask_cal.sum()+1)*CONFORMAL_COVERAGE)/mask_cal.sum(), 1.0)
        conf_quantiles[grp] = float(np.quantile(conf_scores[cal_idx][mask_cal], q))

    # 应用分组校准量
    p10_cal_g = p10_raw.copy()
    p90_cal_g = p90_raw.copy()
    for grp, cq in conf_quantiles.items():
        mask = groups == grp
        p10_cal_g[mask] -= cq
        p90_cal_g[mask] += cq

    yk_t = yk[test_idx]
    picp_cal_g = float(np.mean((yk_t >= p10_cal_g[test_idx]) & (yk_t <= p90_cal_g[test_idx]))*100)
    mpiw_cal_g = float(np.mean(p90_cal_g[test_idx] - p10_cal_g[test_idx]))

    print(f"G4: Grouped conformal by '{CONFORMAL_GROUP_COL}'")
    for grp, cq in conf_quantiles.items():
        n_grp = (groups == grp).sum()
        print(f"  {grp:6s}: conf_q={cq:+.1f}  (n={n_grp:,})")
    print(f"  PICP grouped cal: {picp_cal_g:.1f}%  MPIW: {mpiw_cal_g:.0f}")
```

在超参数 cell 加开关：
```python
CONFORMAL_GROUP_BY = None   # G4: 设为 "tagestyp" 或 "site_id" 启用分组校准（None=全局）
```

---

## 建议实施顺序

| 顺序 | Task | 预计时间 | 风险 |
|------|------|---------|------|
| 1 | **F** 日聚合+颜色 | 10 min | 低 — 纯后处理，不改模型 |
| 2 | **D** 容量后处理 | 5 min | 低 — 填入真实封闭数据即可 |
| 3 | **G1** 高峰加权 | 15 min | 中 — 需重训 kfz 模型，可能影响 MAPE |
| 4 | **G2-G4** | 实验 | 低 — 互不影响，可任选 |

F + D 属于交付必须项（前端日历需要），G 系列是锦上添花。
