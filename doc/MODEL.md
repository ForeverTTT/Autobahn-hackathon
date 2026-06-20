# 模型说明

当前可交付预测由 **CatBoost v2** 生成。TFT 已完成训练实验并保存 checkpoint，但尚未与 CatBoost 融合，也没有生成当前 Agent 使用的交付文件。

## 1. 文件与角色

| 文件/目录 | 角色 |
|---|---|
| `model/model_notebook.ipynb` | 当前 CatBoost v2 训练、评估和 2026–2029 推理 |
| `model/tft.ipynb` | 多目标 Temporal Fusion Transformer 实验 |
| `model/model.md` | 模型设计背景和特征方案 |
| `model/compressed_notebook.md` | `model_notebook.ipynb` 的文本化审阅副本 |
| `model/compress_notebook.py` | 重新生成压缩审阅副本 |
| `model/review_notes.md` | 对 conformal、速度误差、施工和全量重训的审阅建议 |
| `models/kfz_h/multi.cbm` | 总流量 MultiQuantile 模型 |
| `models/sv_h/lkw_ratio.cbm` | 重型车占比模型 |
| `models/v_kfz/speed_drop.cbm` | 速度下降模型 |
| `models/snapshots/` | CatBoost 训练快照和训练日志 |
| `models/tft/` | TFT 日志和 checkpoint |
| `data_autobahn/forecast_2026_2029.csv` | 当前交付预测，Agent 默认读取 |

`processed/` 是 notebook 的中间产物目录，已被 `.gitignore` 忽略，因此不能假定其中的 parquet、profile 或 conformal JSON 存在于其他机器。

## 2. CatBoost v2

### 2.1 预测任务

| 目标 | 方法 | 输出 |
|---|---|---|
| `kfz_h` | CatBoost MultiQuantile | P10 / P50 / P90 |
| `sv_h` | 预测 `sv_h / kfz_h` 比例，再乘 `kfz_h_p50` | 重型车流量 |
| `v_kfz` | 预测相对自由流速度画像的 `speed_drop` | 平均车速 |

速度模型额外使用 `kfz_p50_pred`，显式表达流量升高与速度下降的关系。

### 2.2 核心思路

模型不是递归预测未来四年，而是把历史观测压缩为可查表的画像特征：

```text
历史小时流量
  → site × hour × weekday/tagestyp/month/season 画像
  → 日历、假期、天气气候态、施工、活动修正
  → 任意未来日期的直接预测
```

因此：

- 不使用 lag 特征。
- 不依赖前一小时预测。
- 2026–2029 每个小时可以独立构造特征。
- 长期预测中的“天气”表示气候态，不是真实预报。

### 2.3 特征组

| 特征组 | 示例 |
|---|---|
| 日历 | hour、weekday、month、doy、周期编码、周末/周五/周日 |
| 站点静态 | site_id、road、direction、site_name、经纬度、公里桩 |
| 历史画像 | site × hour × weekday/tagestyp/month/season 的中位数或分位数 |
| 假期 | 三州公共/学校假期、起止日、交通窗口、出发/返程方向 |
| 天气 | 降水、降雪、低能见度、温度、结冰风险、数据来源 |
| 施工 | A8/A93 施工、2+0、关闭车道、目标区域施工 |
| 活动 | 活动数量、影响等级、城市和走廊影响 |

历史画像是主信号；条件特征主要用于在画像上做可解释偏移。

## 3. 训练与校准

当前 notebook 的评估切分：

```text
训练：2023-01-01 至 2024-12-31
验证：2025-01-01 至 2025-12-31
推理：2026-01-01 至 2029-12-31
```

画像只用训练段构建，再应用到验证段，避免验证泄漏。

总流量模型使用单个 MultiQuantile CatBoost 同时预测三个分位数。推理后执行单调修正，保证：

```text
P10 ≤ P50 ≤ P90
```

2025 验证集按时间再拆分为校准段与测试段，进行 split conformal 校准。notebook 记录的全局校准量约为 `+26.3 veh/h`。

## 4. 评估结果

`model/model_notebook.ipynb` 中保存的 2025 hold-out 结果：

| 指标 | v1 | v2 |
|---|---:|---:|
| `kfz_h` MAE | 137.1 veh/h | 135.4 veh/h |
| `kfz_h` RMSE | 238.7 | 235.4 |
| `kfz_h` MAPE | 16.4% | 16.1% |
| `kfz_h` WMAPE | — | 10.7% |
| `sv_h` MAE | 24.5 veh/h | 23.7 veh/h |
| `sv_h` RMSE | 41.9 | 40.5 |
| `sv_h` MAPE | 20.9% | 19.9% |
| `v_kfz` MAE | 5.9 km/h | 5.7 km/h |
| `v_kfz` RMSE | 9.6 | 9.5 |
| `v_kfz` MAPE | 7.5% | 7.3% |
| P10–P90 原始覆盖率 | 69.5% | 71.4% |
| P10–P90 校准后覆盖率 | — | 81.5% |
| 校准后平均区间宽度 | 365 veh/h | 393 veh/h |
| Top-10% 峰值召回率 | 88.1% | 88.1% |

覆盖率提升主要来自 conformal 校准，不应归因于 `rsm` 等普通超参数调整。

## 5. 交付预测

文件：`data_autobahn/forecast_2026_2029.csv`

已核对：

- 420,768 行。
- 12 个站点。
- 2026-01-01 至 2029-12-31，共 1,461 天。
- 每站每天 24 行。
- `(site_id, date, hour)` 无重复。
- 没有分位数交叉。

当前字段：

```text
site_id, road, direction, site_name, date, hour,
kfz_h_p10, kfz_h_p50, kfz_h_p90,
sv_h_pred, v_kfz_pred, interval_width, relative_interval_width
```

`relative_interval_width = interval_width / (p50 + 1)`，供 Agent 解释预测不确定性。Agent 代码也能用 P10/P50/P90 动态重算。

## 6. TFT 实验

`model/tft.ipynb` 构建了多目标 TFT，同时预测 `kfz_h`、`sv_h` 和 `v_kfz`，输入覆盖：

- 静态站点特征。
- 已知未来日历和条件特征。
- 历史观测特征。
- 连续小时面板和缺测回填标记。

仓库中存在：

- `models/tft/checkpoints/tft-epoch=02-val_loss=119.308.ckpt`
- `models/tft/checkpoints/tft-epoch=08-val_loss=112.102.ckpt`
- 两组 Lightning 日志和超参数文件。

最后一条完整日志记录的验证指标约为：

| 目标 | MAE | RMSE |
|---|---:|---:|
| `kfz_h` | 131.9 | 206.8 |
| `sv_h` | 26.3 | 40.4 |
| `v_kfz` | 5.4 | 8.7 |

这些指标来自 TFT 自身的多步验证流程，与 CatBoost notebook 的评估采样和校准不完全一致，不能直接据此宣布 TFT 优于 CatBoost。

当前没有：

- TFT 训练数据集序列化文件。
- `tft_best.ckpt` 统一导出。
- TFT 的 2026–2029 交付预测。
- CatBoost × TFT 融合产物。

因此系统架构应表述为“CatBoost 交付 + TFT 实验”，而不是已经上线的双引擎融合。

## 7. 已知限制

### 最终模型未全量重训 2025

2025 用于独立验证，没有重新并入当前 CatBoost 交付模型。这样评估更可信，但少用了约一年的训练数据，尤其影响 2024 才上线的 Gletschergarten。

### 施工特征的训练信号弱

训练窗口中的 `2+0` 样本为零，模型无法仅靠数据学习容量减半的效果。施工表已经修正了早期过度识别 2+0 的问题，但未来已知施工进入条件表后，输出仍不能被当作精确的车道容量模拟。

### 远期天气和施工存在结构性不确定性

- 未来天气使用气候态。
- 2027–2029 尚未发布的施工在表中通常为 0。
- 预测区间主要刻画模型误差，不包含所有未来政策、事故和施工变化。

### 交付依赖中间结果复制

notebook 写入被忽略的 `processed/`，而 Agent 读取 `data_autobahn/forecast_2026_2029.csv`。重新训练后需要显式更新交付 CSV 和模型文件。

根目录的 `clean_outputs.sh` 可清理 CatBoost 模型、快照和 `processed/` 中间产物。它是破坏性清理脚本，运行前应先使用：

```bash
bash clean_outputs.sh --dry
```

## 8. 运行

CatBoost 环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter lab model/model_notebook.ipynb
```

TFT 需要额外安装 notebook 中列出的 `torch`、`lightning` 和 `pytorch-forecasting`。

建议执行顺序：

1. 运行数据加载与检查。
2. 构建训练段画像。
3. 训练 CatBoost 三个任务。
4. 在 2025 验证并执行 split conformal。
5. 生成 2026–2029 全网格。
6. 检查行数、主键、缺失和分位数单调性。
7. 将最终 CSV 更新到 `data_autobahn/forecast_2026_2029.csv`。
