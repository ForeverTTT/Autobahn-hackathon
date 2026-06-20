Q: 看一下这个catboost模型的文档和 jupyter notebook 代码、输出（被脚本压成 md 了，要不然输出太长爆上下文）。你需要作为一个 reviewer，检查这个代码和metric。我现在的一些疑问：1. PICP 的结果和其他的训练结果没有欺骗，是一个好的结果，对吗？2. 速度预测的误差仍然很大，为什么，怎么办？3. 23-24/25 这个训练/测试set split 不科学是已经知道的问题，导致了construction信息模型学不到。修路信息有关的问题和信息汇总也在 md 里给你了。这个问题有解决的方案吗？4. review之后，告诉我下一步要做什么，有什么重大缺陷or急需要解决的问题（影响小的细节可以忽略，这是 hackathon 题目，时间有限）。  

A: 这套方案在工程和逻辑上的完成度非常高。用画像（Profile）代替自回归（Lag）特征来处理 4 年跨度的纯条件预测，是一个非常聪明的 Hackathon 策略，避开了多步递归预测带来的误差爆炸。

作为 Reviewer，我来逐一解答你的四个核心疑问，并给出针对 Hackathon 冲刺期的行动建议。

---

### 1. PICP 的结果没有“欺骗”，这是一个非常真实且优秀的指标

**你的直觉是对的，没有作弊。**
在时序预测中，最常见的作弊就是用测试集去算校准分位数（in-sample calibration）。但你的代码里明确使用了 Split Conformal 策略：验证集（2025）被按时间顺序切成了两半。前半部分用来计算 `conf_quantile`（+23.3 veh/h），后半部分（完全没见过的数据）用来测试覆盖率。

在后半部分测试集上，未经校准的覆盖率是 71.9%，经过校准后达到了 81.1%。这个结果精准命中了 80% 的预设目标，在严格的 hold-out 验证下是完全可信的。对于一个没有实时数据输入的长期预测模型，能给出这样可靠的置信区间，是非常亮眼的成果。

---

### 2. 车速预测误差“仍然很大”？其实并不大，但有优化的空间

**先纠正一个观念：5.7 km/h 的 MAE 真的不大。**
在没有任何前置小时实测速度（Lag = 0）、直接预测未来几年的前提下，平均误差只有 5.7 km/h，MAPE 只有 7.3%。对于限速 120-130 km/h 或者无最高限速的德国高速来说，这个误差在工业界绝对是可用水平。

**为什么你会觉得误差大（或者觉得表现不好）？**
重点在于 **RMSE 是 9.45 km/h**，且最大真实降速可能高达几百，但模型预测被截断了。这说明模型在绝大多数正常通畅时间预测得很准，但**漏掉了极其严重的拥堵降速瞬间**。
这是因为：

* **误差级联**：你的速度模型把 `kfz_p50_pred`（预测流量）作为了输入。预测流量本身就带有 135 veh/h 的误差，当真实的极端车流峰值被抹平时，速度模型自然也学不到断崖式的降速。
* **树模型的平滑性**：CatBoost 基于 RMSE 优化，它倾向于给出“保守的均值”。而交通流理论中，车速在临界密度前是平缓的，一旦越过临界点会瞬间崩溃（相变）。

**快速解决方案（Hackathon 级别）：**

* **改变量级限制**：把 `CB_SPD_PARAMS` 里的 `loss_function` 和 `eval_metric` 从 RMSE 改为分位数损失（比如 P20）。你不需要预测“平均”速度，你需要模型在流量高时敢于预测出“低速”。
* **非线性放大**：不要只喂 `kfz_p50_pred`，可以喂一个衍生的超载特征，比如 $\max(0, \text{kfz\_p50\_pred} - \text{capacity})$，强迫模型注意到“流量溢出”的物理意义。

---

### 3. 施工数据在 2023-2024 缺失的致命伤与解法

这个问题在你的数据验证报告里已经实锤了：API 没有 2023-2024 年的目标路段历史施工记录。因为训练集里 `has_2_plus_0 == 0`，模型完全没见过施工，导致施工特征的重要性为 0%。

**解决思路：别让机器学习了，用规则强压（Rule-based Overrides）**
Hackathon 讲究务实，既然数据缺失是客观事实，不要试图用复杂的迁移学习。实施后处理策略即可：

1. **流量打折**：在预测出 `kfz_h_p50` 后，写一个映射函数。如果未来（2026-2029）该网格有 `has_2_plus_0 == 1` 或封闭车道数大于 0，直接对预测流量乘以一个物理容量衰减系数（比如 0.6 或 0.7）。
2. **强制降速**：只要遇到施工标识，不管流量多少，强制将 `v_kfz_pred` 压制在 80 km/h 以下（德国高速典型施工限速）。
3. **解释性对齐**：在生成逐日因子归因表时，如果触发了上述规则，强制在 `factors` 字符串里把 `CO`（Construction）拉到首位。

---

### 4. 评审后的下一步：Hackathon 冲刺优先级

别在这套代码里抠微小的超参了，重点解决对最终交付影响最大的“业务逻辑”和“未用尽的数据”。

**🔴 优先级 1（最高）：合并 2025 年数据进行全量重训**
你现在的模型是用 2023-2024 训练，2025 用于验证。这在实验阶段很棒，但在输出 2026-2029 最终预估前，**必须把 2025 的数据放进训练集重新跑一遍**。

* 原因：Gletschergarten 站点是 2024 年才上线的。如果不使用 2025 年的数据，这个站点的画像（Profile）极度缺乏，这对于预测未来的影响极大。

**🟡 优先级 2：实现施工硬编码降级规则（Rule-based Override）**
按上一段说的，直接在输出 `forecast_2026_2029.csv` 之前，写一段 10 行以内的 Pandas 处理逻辑，根据未来的施工排期强制修改车流和车速上限。

**🟢 优先级 3：清理故事线，包装 TFT**
目前文档里提到 TFT 还没融合。如果是我的话，我会果断在答辩里把双塔结构包装成：**"CatBoost as Robust Baseline + TFT for Deep Panel Signals"**。即使最终交付的 CSV 是纯 CatBoost 生成的，也可以展示 TFT 的实验结果证明你们尝试了 SOTA 时序模型，这在黑客松里是非常加分的。

User Note: TFT 已经宣告破产，数据太少无法收敛。这部分也可以在 docs 里记录好。

1. 接着，检查一下现在有没有bugs，跑都能跑通的，就是怕有些细节出问题。另外，TFT 已经破产，专注于决策树。2. 在这个代码基础上，写出修改的代码(修改训练集和测试集的distribution这个优先级最高的)，标明要改哪儿。你要给我文档式说明。 

A: 放弃 TFT 专注于 CatBoost 是一个非常明智的黑客松决策。在时间有限的情况下，把单轨道的逻辑打磨到极致，远比弄一个半成品的双轨道融合要靠谱得多。

你现在的 Pipeline 完整度很高，因子归因（Ablation）和未来网格生成的逻辑都能跑通。作为 Reviewer，我先指出新代码里潜藏的 **2 个业务逻辑 Bug**（不会报错，但会影响预测和解释质量），然后为你提供 **全量重训（2023-2025）的修改方案**。

---

### 1. 现有代码的逻辑 Bug 检查

你的代码在跑通上没有问题，但在业务逻辑上有几个极易被忽视的坑：

#### Bug 1：因子消融（Ablation）时，气温被置为 `0.0` 违背物理常识

在 `[Code Cell 49]` 的 `compute_factor_matrix` 函数中，你对特征归零的逻辑是：

```python
X[c] = "__NEUTRAL__" if c in cats else 0.0

```

* **问题所在**：对于 `holiday` 或 `construction`，`0.0` 代表“没有发生”，非常完美。但对于温度特征（`lt_mean`, `fbt_mean`），把它们强行置为 `0.0` 意味着“冰点/严寒”。如果原本气温是 25°C，你为了看天气的贡献把它改成 0°C，模型会以为突发降温，从而得出荒谬的交通流量变化，导致天气因子（`WE`）被严重扭曲。
* **修复方法**：在 `[Code Cell 49]` 中，将连续特征的 Neutral 状态区分开，温度使用均值（如 10.0°C 或全局 Median）。

#### Bug 2：车速模型的 G3 流量特征存在微小的 Train-Serve Skew

* 在训练时 `[Code Cell 26]`，喂给车速模型的 `kfz_p50_pred` 是原始预测值（没有经过 P10/P50/P90 单调性修复）。
* 在未来网格推理时 `[Code Cell 50]`，喂给车速模型的 `kfz_p50_pred` 是经过 `np.maximum` 单调性约束截断后的值。
* **影响**：极小，只会影响极个别分位数交叉的异常样本。如果你追求完美，可以在 `[Code Cell 26]` 加上单调性修复再赋值给 `kfz_p50_pred`。

---

### 2. 最高优先级：全量数据重训（2023-2025）的文档式修改方案

要将 2025 年合并进训练集，最大的挑战是：**Split Conformal 校准必须要有未见过的 held-out 数据**。如果 2025 也参与了训练，再用 2025 算 `conf_quantile`，就会产生严重的数据穿越，导致你交付的置信区间过窄（不安全）。

**最优策略**：将 `TRAIN_END` 推迟到 2025 年底，切出 2025 年最后三个月作为 `early_stopping` 的验证集。同时，**硬编码使用上次 hold-out 算出来的 Conformal 量（`23.3`）**，放弃在全量数据上重算。

你需要修改以下 3 个 Cell：

#### 修改点 1：调整超参数与时间切分

**定位：** `[Code Cell 7]`
**修改动作：** 修改 `TRAIN_END` 和 `VAL_START`。将 2025 年纳入训练，并留出最后 3 个月防止过拟合。

```python
# --- 时序切分（Final Retrain 模式）---
# 训练集吃满 2023 ~ 2025，解决 Gletschergarten 站 2024 年缺数据的问题
TRAIN_END = pd.Timestamp("2025-12-31 23:59:59")   
# 切出最后 3 个月（避开暑假，包含秋冬）作为 Early Stopping 的验证集
VAL_START = pd.Timestamp("2025-10-01 00:00:00")    

# ... (保持原本其他参数不变) ...

# 开启强制重训，确保你的本地 .cbm 会被覆写
FORCE_RETRAIN = True

```

#### 修改点 2：修复因子消融的物理逻辑 Bug

**定位：** `[Code Cell 49]`
**修改动作：** 替换 `_predict` 函数内的特征掩码逻辑，保护温度特征不被置为绝对零度。

```python
# 在 compute_factor_matrix 函数中修改 _predict：
    def _predict(df, cols_to_zero):
        X = df[features].copy()
        for c in cols_to_zero:
            if c not in X.columns:
                continue
            if c in cats:
                X[c] = "__NEUTRAL__" 
            elif c in ['lt_mean', 'fbt_mean', 'fbt_min']:
                # 温度的 Neutral 状态：使用一个温和的秋季/春季气候态 (10°C)，避免触发冰雪逻辑
                X[c] = 10.0 
            else:
                X[c] = 0.0  # holiday, events, construction 归零是合理的
        return np.clip(kfz_model.predict(X)[:, 1], KFZ_CLIP_MIN, None)  # P50 = col 1

```

#### 修改点 3：锁定 Conformal 校准值（防止数据泄漏）

**定位：** `[Code Cell 46]` (或 `[Code Cell 50]`)
**修改动作：** 因为现在 2025 绝大部分已经是训练集了，再用 `val_kfz` 去算校准会骗自己。直接在预测交付阶段固定之前验证好的泛化补偿。

```python
# 在 [Code Cell 50] predict_grid 函数中，找到应用 conformal 校准量的地方，改成硬编码：

    # B2: 应用 conformal 校准量
    # ⚠️ 警告：因为 2025 已并入训练集，不能再用 in-sample 算覆盖率。
    # 这里直接使用前期在 2025 完全 hold-out 时测算出的泛化扩宽量 (+23.3)
    _cq = 23.3 
    
    out["kfz_h_p10"] = np.clip(out["kfz_h_p10"] - _cq, KFZ_CLIP_MIN, None)
    out["kfz_h_p90"] = out["kfz_h_p90"] + _cq

```

---

按照上述步骤修改并重新运行 Notebook 即可完成 Final Retrain，生成的预测将是最终交付版本，并且涵盖了对 2024 年新建站点的充足学习。

如果你把这几个地方改完并跑通了生成新的 `forecast_2026_2029.csv`，我们下一步是不是要把之前讨论过的“施工强行降级（Rule-based Overrides）”规则加上，把那个因为没历史数据导致学不到的修路特征用人工规则补齐？

User: 现在有新需求：Agent 那边需要每小时的影响因子分布，我们现在做的是每天的。要改。但是怎么改呢？我的想法：尽量少往 model_notebook.ipynb 的代码里加东西，把它后面生成 forecast + factors 表格的代码提出来，写一个单独的 python 代码，反正模型都存着可以调。也就是说，这部分逻辑直接解藕，model_notebook 纯训练。前端需要快速反应 2026 的数据，所以要生成好了。表合并，新的表头：site_id,road,direction,site_name,date,hour,kfz_h_p10,kfz_h_p50,kfz_h_p90,sv_h_pred,v_kfz_pred,interval_width,relative_interval_width,reason。然后27-29年的预测数据，可以由Agent调用Python代码生成。你评估这个方案好不好，代码量是否大。 

A: 你这个思路非常清晰，**解耦（Decoupling）是工程化落地最正确的一步！** 将繁重的推理和解释逻辑从 Jupyter Notebook 中剥离出来，让 Notebook 专心做数据清洗和模型训练，把推理封装成一个标准的 API 或命令行工具供 Agent 随时调用，这正是生产级机器学习系统的标准玩法。

### 对你方案的评估

1. **好不好？** **极好。** 如果把 4 年（420,768 行）每小时的 `reason` 全塞进一张表，文件体积会轻松突破 100-150MB，前端加载和 Agent 读取都会卡顿。预生成 2026 年（前端立刻要用的），然后 2027-2029 留给 Agent 按需动态调用（On-demand），完美平衡了响应速度和存储空间。
2. **代码量大不大？** **非常小。** 从“按天汇总因子”改成“每小时因子分布”，逻辑上反而**变简单了**。你不需要再做按天的 `groupby` 和流量加权汇总，只需对每一行预测的消融结果算百分比即可。

---

### 极简架构设计

为了让这个 Python 脚本最轻、最快，**不要让脚本从头去读取那 6 张原始 CSV 表做 join**。

**最佳实践是：**

1. 在 Notebook 训练完之后，把构建好的未来特征网格（只包含 `hour`, `weekday`, `is_holiday`, 历史画像等特征，不含预测结果）直接存成一个压缩比极高的 `future_grid_2026_2029.parquet`。
2. Python 脚本只需要读取这一个 Parquet 文件和 `.cbm` 模型，用几十行代码就能跑出任何一天的结果。

---

### 实施步骤与代码

#### 第一步：在 Notebook 最后加两行代码（导出特征网格）

在你的 `model_notebook.ipynb` 的第 6 节开头，原本有构建网格的代码，你在它后面加一行保存特征：

```python
# 构建未来网格 (420,768 rows)
future_grid = build_future_grid(pd.date_range("2026-01-01", "2029-12-31"))

# 【新增】将纯特征网格保存下来，供脱机的 Python 脚本极速加载
future_grid.to_parquet(PROC_DIR / "future_grid_2026_2029.parquet", index=False)

```

*(保存后，你可以把 Notebook 里面原来冗长的预测和因子归因代码全部删掉，Notebook 到此为止。)*

#### 第二步：新建独立脚本 `agent_inference.py`

在项目根目录（或 `scripts/` 目录下）创建这个文件。它支持被 Agent 通过命令行调用（例如 `python agent_inference.py --year 2026` ），也支持作为 Python 模块被 Agent 内部 `import`。

```python
import argparse
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

warnings.filterwarnings("ignore")

# =====================================================================
# 1. 配置与特征定义 (对齐 Notebook)
# =====================================================================
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data_autobahn"
PROC_DIR = ROOT / "processed"
MODEL_DIR = ROOT / "models"

KFZ_CLIP_MIN = 0.0
LKW_RATIO_CLIP_MIN = 0.0
SPEED_CLIP_MIN = 20.0
SPEED_CLIP_MAX = 160.0

# 特征清单 (必须与训练时严格一致)
CALENDAR = ["hour", "weekday", "month", "doy", "week_of_year", "is_weekend", "is_friday", "is_saturday", "is_sunday", "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos", "doy_sin", "doy_cos"]
STATIC_NUM = ["bab_km", "longitude", "latitude"]
STATIC_CAT = ["site_id", "road", "direction", "site_name", "tagestyp", "season"]
HOLIDAY = ["is_school_holiday_DE_BY", "is_school_holiday_AT_SB", "is_school_holiday_AT_TI", "is_public_holiday_DE_BY", "is_public_holiday_AT_SB", "is_public_holiday_AT_TI", "school_holiday_count", "public_holiday_count", "is_holiday_start", "is_holiday_end", "in_traffic_window", "days_to_holiday_start", "days_since_holiday_end", "total_holiday_overlap", "is_departure_wave_day", "is_return_wave_day"]
HOLIDAY_CAT = ["window_direction", "window_risk_level", "a8_direction", "a93_direction"]
WEATHER = ["w_precip", "w_snow", "w_lowvis", "w_tmin", "w_tmax", "w_ice"]
WEATHER_CAT = ["weather_source"]
TEMP = ["lt_mean", "fbt_mean", "fbt_min"]
CONSTRUCTION = ["has_a8_construction", "has_a93_construction", "a8_construction_count", "a93_construction_count", "has_2_plus_0", "two_plus_0_count", "max_closed_lanes", "sum_closed_lanes", "has_target_bbox_construction"]
EVENTS = ["has_special_event", "active_event_count", "max_impact_level", "impact_score", "affects_a8_ost", "affects_a93_sued", "has_munich_event", "has_salzburg_event", "has_rosenheim_event", "has_kufstein_event", "has_confirmed_event", "has_estimated_event"]
PROF_KFZ = ["prof_kfz_shd", "prof_kfz_sht", "prof_kfz_shm", "prof_kfz_p90", "prof_kfz_shs"]
PROF_LKW = ["prof_lkw_shd", "prof_lkw_sht"]
PROF_V = ["prof_v_shd", "prof_v_p85", "prof_v_sht"]

COND = HOLIDAY + HOLIDAY_CAT + WEATHER + WEATHER_CAT + TEMP + CONSTRUCTION + EVENTS
CAT_FEATURES = STATIC_CAT + HOLIDAY_CAT + WEATHER_CAT

FEATURES_KFZ = CALENDAR + STATIC_NUM + STATIC_CAT + PROF_KFZ + COND
FEATURES_LKW = CALENDAR + STATIC_NUM + STATIC_CAT + PROF_KFZ + PROF_LKW + COND
FEATURES_SPD = CALENDAR + STATIC_NUM + STATIC_CAT + PROF_KFZ + PROF_V + COND + ["kfz_p50_pred"]

# 归因分组
EXPLANATION_GROUPS = {
    "Station & Location": ["site_id", "road", "direction", "site_name"] + STATIC_NUM,
    "Historical Patterns": PROF_KFZ,
    "Calendar & Season": CALENDAR + ["season"],
    "Holiday Effect": HOLIDAY + HOLIDAY_CAT + ["tagestyp"],
    "Weather & Road": WEATHER + WEATHER_CAT + TEMP,
    "Special Events": EVENTS,
    "Construction": CONSTRUCTION,
}

FACTOR_DISPLAY = {
    "Station & Location": "Road Segment and Detector Attributes",
    "Historical Patterns": "Historical Traffic Baseline",
    "Calendar & Season": "Date and Time Pattern",
    "Holiday Effect": "Holiday Effect",
    "Weather & Road": "Weather and Temperature",
    "Special Events": "Special Events",
    "Construction": "Construction Impact",
}

# =====================================================================
# 2. 核心推理与归因函数
# =====================================================================
class TrafficPredictor:
    def __init__(self):
        print("Loading models...")
        self.kfz_model = CatBoostRegressor().load_model(str(MODEL_DIR / "kfz_h" / "multi.cbm"))
        self.lkw_model = CatBoostRegressor().load_model(str(MODEL_DIR / "sv_h" / "lkw_ratio.cbm"))
        self.spd_model = CatBoostRegressor().load_model(str(MODEL_DIR / "v_kfz" / "speed_drop.cbm"))
        
        _cf = PROC_DIR / "conformal.json"
        self.conf_q = float(json.loads(_cf.read_text())["conf_quantile"]) if _cf.exists() else 25.0

        print("Loading feature grid...")
        self.base_grid = pd.read_parquet(PROC_DIR / "future_grid_2026_2029.parquet")
        self.base_grid["date"] = pd.to_datetime(self.base_grid["date"])

    def predict_and_explain(self, start_date: str, end_date: str) -> pd.DataFrame:
        """为指定日期范围生成预测和小时级归因"""
        mask = (self.base_grid["date"] >= start_date) & (self.base_grid["date"] <= end_date)
        df = self.base_grid[mask].copy()
        if df.empty:
            raise ValueError(f"No data found in feature grid for {start_date} to {end_date}")

        print(f"Running inference for {len(df)} rows...")
        
        # 1. kfz_h 推理 (P10/P50/P90)
        X_kfz = df[FEATURES_KFZ].copy()
        for c in [c for c in CAT_FEATURES if c in FEATURES_KFZ]:
            X_kfz[c] = X_kfz[c].astype(str)
            
        kfz_preds = self.kfz_model.predict(X_kfz)
        df["kfz_h_p10"] = np.clip(kfz_preds[:, 0] - self.conf_q, KFZ_CLIP_MIN, None)
        df["kfz_h_p50"] = np.clip(kfz_preds[:, 1], KFZ_CLIP_MIN, None)
        df["kfz_h_p90"] = kfz_preds[:, 2] + self.conf_q
        
        # 单调性约束
        df["kfz_h_p50"] = np.maximum(df["kfz_h_p10"], df["kfz_h_p50"])
        df["kfz_h_p90"] = np.maximum(df["kfz_h_p50"], df["kfz_h_p90"])

        # 2. sv_h 推理
        X_lkw = df[FEATURES_LKW].copy()
        for c in [c for c in CAT_FEATURES if c in FEATURES_LKW]:
            X_lkw[c] = X_lkw[c].astype(str)
        lkw_ratio = np.clip(self.lkw_model.predict(X_lkw), LKW_RATIO_CLIP_MIN, None)
        df["sv_h_pred"] = lkw_ratio * df["kfz_h_p50"]

        # 3. v_kfz 推理 (需要 G3 流量特征)
        df["kfz_p50_pred"] = df["kfz_h_p50"]
        X_spd = df[FEATURES_SPD].copy()
        for c in [c for c in CAT_FEATURES if c in FEATURES_SPD]:
            X_spd[c] = X_spd[c].astype(str)
        speed_drop = self.spd_model.predict(X_spd)
        df["v_kfz_pred"] = np.clip(df["prof_v_p85"] - speed_drop, SPEED_CLIP_MIN, SPEED_CLIP_MAX)

        # 区间与置信度
        df["interval_width"] = df["kfz_h_p90"] - df["kfz_h_p10"]
        df["relative_interval_width"] = df["interval_width"] / (df["kfz_h_p50"] + 1.0)

        # 4. 小时级因子归因 (Ablation)
        print("Computing hourly feature ablation...")
        contrib_matrix = []
        group_names = list(EXPLANATION_GROUPS.keys())
        
        for gname in group_names:
            X_abl = X_kfz.copy()
            for c in EXPLANATION_GROUPS[gname]:
                if c in X_abl.columns:
                    if c in CAT_FEATURES:
                        X_abl[c] = "__NEUTRAL__"
                    elif c in ['lt_mean', 'fbt_mean', 'fbt_min']:
                        X_abl[c] = 10.0 # 避免把气温归零导致突发冰雪逻辑
                    else:
                        X_abl[c] = 0.0
            
            abl_preds = np.clip(self.kfz_model.predict(X_abl)[:, 1], KFZ_CLIP_MIN, None)
            delta = np.abs(df["kfz_h_p50"].to_numpy() - abl_preds)
            contrib_matrix.append(delta)
            
        # 转换为百分比并生成 reason 字符串
        mat = np.column_stack(contrib_matrix)
        tot = mat.sum(axis=1, keepdims=True)
        tot[tot < 1e-9] = 1.0
        pct = mat / tot * 100.0

        display_names = [FACTOR_DISPLAY[g] for g in group_names]
        reasons = []
        for row in pct:
            order = np.argsort(row)[::-1]
            parts = [f"{display_names[j]}: {row[j]:.1f}%" for j in order if row[j] >= 1.0]
            reasons.append("；".join(parts))
            
        df["reason"] = reasons

        # 5. 格式化输出
        out_cols = [
            "site_id", "road", "direction", "site_name", "date", "hour",
            "kfz_h_p10", "kfz_h_p50", "kfz_h_p90", "sv_h_pred", "v_kfz_pred",
            "interval_width", "relative_interval_width", "reason"
        ]
        
        final_df = df[out_cols].copy()
        for col in ["kfz_h_p10", "kfz_h_p50", "kfz_h_p90", "sv_h_pred", "interval_width"]:
            final_df[col] = final_df[col].round(0).astype(int)
        final_df["v_kfz_pred"] = final_df["v_kfz_pred"].round(1)
        final_df["relative_interval_width"] = final_df["relative_interval_width"].round(4)
        final_df["date"] = final_df["date"].dt.strftime("%Y-%m-%d")

        return final_df

# =====================================================================
# 3. CLI 接口
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate hourly forecast with reasons")
    parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--out", type=str, default="forecast_hourly.csv", help="Output CSV name")
    args = parser.parse_args()

    predictor = TrafficPredictor()
    result = predictor.predict_and_explain(args.start, args.end)
    
    out_path = DATA_DIR / args.out
    result.to_csv(out_path, index=False)
    print(f"✔ Successfully generated {len(result)} rows -> {out_path}")

```

### 怎么给 Agent 调用？

Agent 可以通过两种方式极速拿到数据：

1. **命令行调用**（比如 Agent 需要预生成整个 2026 年）：
```bash
python agent_inference.py --start 2026-01-01 --end 2026-12-31 --out forecast_2026_hourly.csv

```


2. **作为函数内嵌调用**（如果前端用户在地图上点选了 2028-07-04）：
```python
from agent_inference import TrafficPredictor

predictor = TrafficPredictor() # 初始化一次驻留内存

# 瞬间返回结果 DataFrame
df = predictor.predict_and_explain("2028-07-04", "2028-07-04")

```
代码我帮你把 Bug 1（温度归零问题）也顺手修了，用这个方案跑出来的归因会比原来更加合理。你想先自己把这个 Python 脚本加进去跑通，还是我们现在就讨论一下如何用你刚刚合并进去的 2025 年数据跑出全新的权重？