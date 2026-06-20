# CatBoost 调参指南 — Autobahn 交通预测 (model_2.ipynb v2)

## 快速诊断：先看这里

| 症状 | 最可能原因 | 优先动手的参数 |
|------|-----------|---------------|
| 验证 MAPE 高但训练 MAPE 低 | **过拟合** | `l2_leaf_reg` ↑，`min_data_in_leaf` ↑，`depth` ↓ |
| 训练验证 MAPE 都高 | **欠拟合** | `iterations` ↑，`depth` ↑，`learning_rate` ↓（更多迭代） |
| Loss 曲线在 2000 iter 末尾仍在下降 | **迭代数不够** | `iterations` → 3000–5000，`early_stopping_rounds` → 300 |
| Loss 曲线抖动剧烈 | **学习率太高** | `learning_rate` 0.02 → 0.01，`subsample` ↓ 0.7 |
| PICP < 80%（区间太窄） | **区间不够宽** | `rsm` ↓ 0.7（增加多样性），或直接做 conformal 校准 |
| PICP > 95%（区间太宽） | **区间虚胖** | `rsm` ↑ 0.9，重新跑 conformal 用更小 `CONFORMAL_COVERAGE` |
| 峰值 Recall 低（<85%） | 高峰时段样本权重不足 | 对 `kfz_h > p90` 行加权（`make_pool` 的 `weight` 参数） |
| sv_h MAPE 远高于 kfz_h | lkw_ratio 不稳定 | sv_h 独立直接回归对比；或用 `l2_leaf_reg` ↑ 稳定 ratio 预测 |

---

## 一、参数意义与调向

### 1.1 核心三角：`iterations × learning_rate × early_stopping_rounds`

```
当前 v2：iterations=2000, lr=0.02, early_stop=200
```

**规律**：`learning_rate × iterations` 决定"走了多远"，`early_stopping_rounds` 防止走过头。

- **`iterations`**：树的总数上限。实际最优树数由 early stopping 决定——只要验证 loss 连续 `early_stopping_rounds` 没有改善就停。建议始终设置 early stopping，让 `iterations` 成为安全上限而非精确目标。
  - 调高时机：loss 曲线末尾仍明显下降（best_iter 接近上限）
  - 下限：best_iter 应 ≥ 500 才说明模型学到足够信息

- **`learning_rate`**（当前 0.02）：步长。越小越稳，需要更多迭代。
  - 下调（→ 0.01）：loss 抖动、val/train gap 大；配合 `iterations=4000`
  - 上调（→ 0.03–0.05）：训练时间紧、快速原型验证；精度略降
  - **经验**：0.01–0.03 是交通类 tabular 数据的甜点区

- **`early_stopping_rounds`**（当前 200）：连续多少棵树 val 不改善则停。
  - lr 越小，提升曲线越平滑，需要更大的 patience。`lr=0.02` 对应 `rounds=150–250`

### 1.2 树的复杂度：`depth`（当前 8）

决定单棵树能捕获多少特征交叉。本任务的高阶交叉（假期×站点×时段×季节）需要足够的深度。

| depth | 叶子数 | 适用场景 |
|-------|--------|---------|
| 5–6 | 32–64 | 速度模型（v_kfz）：关系简单，防过拟合 |
| 7–8 | 128–256 | 流量模型（kfz_h）：需捕捉多维交叉 |
| 9–10 | 512–1024 | 样本极大时尝试；过深易过拟合 |

**流量模型 depth 调向**：
- 出现过拟合 → depth ↓ 到 7
- 验证集在假期峰值误差特别大 → depth ↑ 到 9（更复杂交叉）

### 1.3 正则化：`l2_leaf_reg`（当前 kfz: 3.0，spd: 15.0）

叶节点权重的 L2 惩罚。值越大，叶子权重越小，模型越保守。

- **kfz_h（3.0）**：样本量大（21 万行），可以较小正则。若过拟合出现，先尝试 5.0 → 8.0
- **v_kfz（15.0）**：速度-流量关系非线性但规律强，高正则防止学到噪声降速模式

调向：
```
过拟合（train好val差） → l2 ↑：3 → 5 → 10
欠拟合（train/val都差） → l2 ↓：3 → 2 → 1
```

### 1.4 叶节点最小样本量：`min_data_in_leaf`（当前 50）

防止叶子过少样本导致高方差预测。

- 本任务每个 `(site, hour, tagestyp)` 组合约有 400–1000 个训练样本，50 是合理下限
- 若对罕见事件（某节假日+某站点）预测不稳定，尝试 100–200
- **速度模型（200）**：降速关系数据分布更稀疏，设更大值

### 1.5 采样参数：`subsample` & `rsm`

| 参数 | 当前值 | 作用 |
|------|--------|------|
| `subsample` | 0.85 | 行采样（每棵树随机取 85% 行），减少方差 |
| `rsm` | 0.8 | **列采样**（kfz 专用），每次分裂随机取 80% 列，增加量化模型间多样性 → PICP 提升 |

**rsm 的关键作用**：MultiQuantile 三个分位共享树但分位间需要多样性。rsm < 1.0 让 P10/P50/P90 在不同特征子集上分裂，宽化区间宽度，PICP 从 69% → ~75–80%。

- PICP 仍低于目标 → `rsm` 0.8 → 0.65（更多随机性）
- 整体 MAPE 因 rsm 降低而升高 → 权衡取舍，或加 conformal 校准保底

---

## 二、特征工程调优（比超参更重要）

### 2.1 历史画像特征（最高杠杆）

历史画像贡献约 **64%** 的预测信号。调参收益远小于改进画像质量。

优先检查：
1. `prof_kfz_shd`（站点×小时×星期）是否存在大量缺失值？用全局中位数兜底的比例高意味着画像不稳定
2. 画像使用的是 **全量 2023–2025** 还是仅训练集（2023–2024）？推理时应用全量

**能显著提升精度的画像改进**（如果当前指标不够好）：
```python
# 当前没有的高价值画像：
prof_kfz_shdm  # 站点×小时×星期×月份（更细粒度，需样本量够）
prof_kfz_shdh  # 仅限有足够样本时，季节+假期类型组合
```

### 2.2 假期特征

假期贡献约 **3.7%** 但对峰值的影响极大。排查方向：
- `days_to_holiday_start` 在验证集高峰错误大 → 检查出发波窗口（7天）是否过窄/宽
- `is_departure_wave_day` 只抓周六 → 若夏季峰值在周五也高，扩展条件

---

## 三、MultiQuantile 专项：PICP 提升路线图

v2 使用 `MultiQuantile:alpha=0.1,0.5,0.9`，理论 PICP 目标 80%。实测路线：

```
Step 1: 跑通 MultiQuantile 训练，看 picp_raw（未校准）
    │
    ├── picp_raw > 75% → Split Conformal 校准通常能达 80%  ✅
    │
    └── picp_raw < 70% → 区间先天太窄，需要从模型层面调整
            │
            ├── rsm: 0.8 → 0.65（更多列随机性）
            ├── 加权：高峰小时行重 2×（高峰时段是主要覆盖缺口）
            └── 尝试更宽分位：alpha=0.05,0.5,0.95（更宽名义区间，再用 conformal 收窄）

Step 2: Split Conformal 校准
    # 在 1d12cb20 评估 cell 中，CONFORMAL_COVERAGE = 0.80 控制目标覆盖率
    # 调整 conf_quantile 影响区间宽度
    picp_cal 应略高于 80%（小样本修正使实际覆盖率保守）
```

---

## 四、速度模型专项：`CB_SPD_PARAMS`

车速模型目标是 `speed_drop = prof_v_p85 − v_kfz`，而非直接回归速度。

当前 v2 配置（depth=5, l2=15, min_leaf=200）比流量模型更保守——这是故意设计：
- 降速关系简单（拥堵时速度下降、施工时速度下降）
- 保守正则防止把噪声降速当作规律学进去

**调向**：
- v_kfz MAE > 8 km/h → 欠拟合；先检查 `prof_v_p85` 画像质量；若画像OK则 `depth` 5→6，`l2` 15→8
- v_kfz 验证集拥堵时段误差大 → `FEATURES_SPD` 加入 `kfz_h_p50_pred`（流量预测值，需先用 kfz 模型推算）

---

## 五、调参优先级清单

按预期收益排序：

```
🔴 最高优先级（影响全局）
  1. iterations: 若 best_iter ≈ 上限，增加到 3000–5000
  2. 历史画像质量: 缺失率、键的粒度
  3. rsm: 0.8 → 0.65（若 PICP 持续低于 75%）

🟡 中优先级（改善特定指标）
  4. depth 7→9（若峰值误差特别大）
  5. l2_leaf_reg 3→5（若过拟合明显）
  6. CONFORMAL_COVERAGE: 若 picp_cal 偏低，检查 conformal 校准逻辑

🟢 低优先级（微调）
  7. learning_rate 0.02→0.01（精度换速度）
  8. subsample 0.85→0.75（轻微过拟合时）
  9. min_data_in_leaf 50→100（预测不稳定时）
```

---

## 六、实验记录模板

每次调参请记录（防止忘记哪次改了什么）：

```
实验 #__  日期: ____
改动: [参数名] ___ → ___
原因: 观察到 [症状]
结果:
  kfz_h MAPE:   __%  (v1: 16.4%)
  PICP (cal):   __%  (目标: 80%)
  Peak Recall:  __%  (v1: 88.1%)
  best_iter:    ___
结论: 保留 / 回退
```

---

## 七、参数速查表

| 参数 | v2 当前值 | 建议范围 | 适用目标 |
|------|-----------|---------|---------|
| `iterations` | 2000 | 1500–5000 | kfz / lkw |
| `learning_rate` | 0.02 | 0.01–0.05 | 所有 |
| `depth` | 8 | 6–10 (kfz) / 5–7 (spd) | 各目标 |
| `l2_leaf_reg` | 3.0 | 1–15 (kfz) / 10–30 (spd) | 各目标 |
| `min_data_in_leaf` | 50 | 20–200 | kfz / lkw |
| `subsample` | 0.85 | 0.7–0.95 | 所有 |
| `rsm` | 0.8 | 0.6–0.95 | kfz MultiQuantile |
| `early_stopping_rounds` | 200 | 100–400 | 所有 |
| `CONFORMAL_COVERAGE` | 0.80 | 0.80–0.90 | calibration |
| `SPEED_DROP_CLIP_MIN/MAX` | -20/60 | ± 根据 EDA | spd |
