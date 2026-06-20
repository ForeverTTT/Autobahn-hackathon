# Factor Grouping Review — 影响因子归因方案评审与改进

> **Audience**: 模型开发者 & Agent 开发者
> **Status**: ✅ 已实施 (2026-06-20) — notebook Cell 16/48/50 已更新，`forecast_2026_2029_daily.csv` 已生成
> **依赖**: `model_notebook.ipynb` Cell 16 (特征定义 + FACTOR_DISPLAY), Cell 48 (ablation 函数), Cell 50 (日聚合 + 输出 forecast_2026_2029_daily.csv)

---

## 1. 问题陈述

当前 `factor_attribution_daily.csv` 使用 6 组 ablation 归因方案（TT/CA/HO/WE/EV/CO）。在实际使用中暴露出两个问题：

### 问题 A：TT 组过于庞大，遮蔽了其他因子的可见度

```
当前均值：TT=82.8%  CA=7.6%  HO=4.5%  WE=4.2%  EV=0.8%  CO=0.0%
```

"Typical Traffic" 占据了绝对主导地位。这虽然统计上正确（历史画像确实是最强特征），但从**可解释性**角度看，用户看到 "TT=83%" 得不到任何有用信息——"这个路段通常就是这样" 不是一个有洞察力的解释。

更关键的是，TT 组内部混杂了两类完全不同的信息：

| 子类 | 特征 | 回答的问题 |
|------|------|-----------|
| **历史流量画像** (5个) | `prof_kfz_shd, prof_kfz_sht, prof_kfz_shm, prof_kfz_p90, prof_kfz_shs` | "根据3年数据，这个小时通常有多少车？" |
| **站点地理位置** (7个) | `bab_km, longitude, latitude, site_id, road, direction, site_name` | "这个传感器在哪里？是哪条路、哪个方向？" |

前者是**数据驱动的模式**（从历史流量中学到的），后者是**物理属性**（传感器装在什么地方）。把它们拆开，可以回答一个关键问题：

> "模型的预测，多大程度来自'背下来了这个站的历史规律'，多大程度来自'知道这个站在慕尼黑附近所以车多'？"

这正是用户关心的：**赤裸的流量数据对决策树的影响，并没有看起来那么高**。

### 问题 B：`tagestyp` 的归属错误

当前 `tagestyp`（日类型：w/s/u）被归在 **Calendar (CA)** 组。但 `derive_tagestyp()` 的逻辑是：

```python
tagestyp = "s" if (weekday==7 or public_holiday==1) else "u" if school_holiday==1 else "w"
```

- `w`（工作日）：纯日历（周一至周五）→ 放 CA 合理
- `s`（周日/公共假日）：周日是日历，公共假日是假日 → **跨 CA 和 HO**
- `u`（学校假期）：100% 假日驱动 → **应该归 HO**

这意味着：当我们做 HO ablation（抹掉所有假日特征），模型仍然通过 `tagestyp='u'` 保留了一部分假日信息。同样，当我们做 CA ablation，模型的 `tagestyp` 被设为 `__NEUTRAL__`，损失的不只是"今天是几号"，还有"今天是不是假期"的信号。

**结论**：当前的 CA/HO 分割**系统性地低估了假日效应**——部分假日信号被泄漏到了 Calendar 组。

---

## 2. 完整特征清单（82个特征逐一审查）

以下是 `FEATURES_KFZ` 的全部 82 个特征，按语义重新分类：

### 2.1 时间/日历类（17个）— 回答"什么时候"

| # | 特征 | 类型 | 含义 | 所属 |
|---|------|------|------|------|
| 1 | `hour` | int | 小时 0-23 | 纯时间 |
| 2 | `weekday` | int | ISO星期 1-7 | 纯时间 |
| 3 | `month` | int | 月份 1-12 | 纯时间 |
| 4 | `doy` | int | 年内的第几天 1-366 | 纯时间 |
| 5 | `week_of_year` | int | ISO年内第几周 | 纯时间 |
| 6 | `is_weekend` | 0/1 | 是否周末 | 纯时间 |
| 7 | `is_friday` | 0/1 | 是否周五 | 纯时间 |
| 8 | `is_saturday` | 0/1 | 是否周六 | 纯时间 |
| 9 | `is_sunday` | 0/1 | 是否周日 | 纯时间 |
| 10 | `hour_sin` | float | sin(2π×hour/24) | 周期编码 |
| 11 | `hour_cos` | float | cos(2π×hour/24) | 周期编码 |
| 12 | `dow_sin` | float | sin(2π×(dow-1)/7) | 周期编码 |
| 13 | `dow_cos` | float | cos(2π×(dow-1)/7) | 周期编码 |
| 14 | `month_sin` | float | sin(2π×month/12) | 周期编码 |
| 15 | `month_cos` | float | cos(2π×month/12) | 周期编码 |
| 16 | `doy_sin` | float | sin(2π×doy/365.25) | 周期编码 |
| 17 | `doy_cos` | float | cos(2π×doy/365.25) | 周期编码 |

**关键观察**：这些特征不包含任何交通信息——它们是**纯时间戳的数学变换**。无论这个站在哪里、流量多少，这些值都一样。模型只能通过"在8am的流量通常比3am高"这样的关联来利用它们，而这个关联完全是通过与 profile 特征的交互学到的。

### 2.2 站点/地理类（7个）— 回答"在哪里"

| # | 特征 | 类型 | 含义 | 所属 |
|---|------|------|------|------|
| 18 | `bab_km` | float | 高速公路公里标 | 物理位置 |
| 19 | `longitude` | float | 经度 | 物理位置 |
| 20 | `latitude` | float | 纬度 | 物理位置 |
| 21 | `site_id` | cat | 站点唯一ID（如 `A8_Mch_MQB25_Mch_H`） | 站点身份 |
| 22 | `road` | cat | 道路：`A8` 或 `A93` | 站点身份 |
| 23 | `direction` | cat | 方向：`Mch/Sbg/Ro/Kff` | 站点身份 |
| 24 | `site_name` | cat | 站点名称（如 `MQB25_Mch_H`） | 站点身份 |

**关键观察**：`site_id` 是一个**超强特征**——它唯一标识了12个站点。CatBoost 会为每个 `site_id` 学习一个隐式的"截距项"，这等价于模型学到了"MQB25（慕尼黑附近）的流量基础水平高于 MQQ245（萨尔茨堡边境）"。但这不是从流量数据中学到的模式——这是模型对"位置身份"的直接记忆。

**把 site_id 和 prof_kfz_* 拆开的意义**：`site_id` 告诉模型"这是哪里"（身份），`prof_kfz_shd` 告诉模型"这里通常有多少车"（模式）。两者都在回答"典型流量是什么样的"，但前者是**身份驱动的先验**，后者是**数据驱动的模式**。

### 2.3 历史流量画像类（5个）— 回答"通常有多少车"

| # | 特征 | 类型 | 含义 | 计算方式 |
|---|------|------|------|---------|
| 25 | `prof_kfz_shd` | float | 本站×小时×周几 的kfz_h中位数 | 训练集 groupby(site, hour, weekday).median() |
| 26 | `prof_kfz_sht` | float | 本站×小时×日类型 的kfz_h中位数 | 训练集 groupby(site, hour, tagestyp).median() |
| 27 | `prof_kfz_shm` | float | 本站×小时×月份 的kfz_h中位数 | 训练集 groupby(site, hour, month).median() |
| 28 | `prof_kfz_p90` | float | 本站×小时×周几 的kfz_h P90 | 训练集 groupby(site, hour, weekday).quantile(0.90) |
| 29 | `prof_kfz_shs` | float | 本站×小时×季节 的kfz_h中位数 | 训练集 groupby(site, hour, season).median() |

**关键观察**：
- 这些是**从历史数据聚合得到的统计量**，不是原始传感器读数
- 它们已经是"压缩过的知识"——3年×12站×24小时×7天=数万条原始数据，被压缩成5个数字
- **profiles 已经隐含了站点身份**：`prof_kfz_shd` 对 MQB25（慕尼黑附近）和对 MQQ245（萨尔茨堡边境）在相同时刻的值完全不同
- 这意味着：即使抹掉 `site_id`，模型通过 profile 值仍然知道"这是一个高流量站"
- **反之亦然**：即使抹掉所有 profile 特征，模型通过 `site_id` 仍然知道"MQB25 在慕尼黑附近，流量基础高"

### 2.4 日类型/季节类（2个）— 当前跨组归属有争议

| # | 特征 | 类型 | 含义 | 当前归属 | 建议归属 |
|---|------|------|------|---------|---------|
| 30 | `tagestyp` | cat | w=工作日, s=周日/公假, u=学校假期 | Calendar | **Holiday** |
| 31 | `season` | cat | winter/spring/summer/autumn | Calendar | Calendar ✓ |

**`tagestyp` 归属论证**：
- 对未来日期（2026-2029），`tagestyp` 由 `derive_tagestyp()` 根据 `(weekday, public_holiday_DE_BY, school_holiday_DE_BY)` 计算，**100% 确定性地从假日特征派生**
- `u`（学校假期，占20.7%天）完全是假日信息
- `s` 中的公共假日部分也是假日信息
- 唯一"日历"成分是 `s` 中的普通周日——但模型在 CA 中已有 `is_sunday=1, weekday=7, is_weekend=1`，信息不丢失
- **结论**：`tagestyp` 应该归入 Holiday 组，使 HO 成为"所有假日相关信号的共同体"

### 2.5 假日/旅游类（20个）— 回答"放假了吗"

| # | 特征 | 类型 | 含义 |
|---|------|------|------|
| 32 | `is_school_holiday_DE_BY` | 0/1 | 巴伐利亚学校假期 |
| 33 | `is_school_holiday_AT_SB` | 0/1 | 萨尔茨堡州学校假期 |
| 34 | `is_school_holiday_AT_TI` | 0/1 | 蒂罗尔州学校假期 |
| 35 | `is_public_holiday_DE_BY` | 0/1 | 巴伐利亚公共假日 |
| 36 | `is_public_holiday_AT_SB` | 0/1 | 萨尔茨堡公共假日 |
| 37 | `is_public_holiday_AT_TI` | 0/1 | 蒂罗尔公共假日 |
| 38 | `school_holiday_count` | int | 有几个州在放学校假期(0-3) |
| 39 | `public_holiday_count` | int | 有几个州在放公共假日(0-3) |
| 40 | `is_holiday_start` | 0/1 | 假期第一天 |
| 41 | `is_holiday_end` | 0/1 | 假期最后一天 |
| 42 | `in_traffic_window` | 0/1 | 是否在高流量窗口内 |
| 43 | `days_to_holiday_start` | int | 距假期开始还有几天(0-30) |
| 44 | `days_since_holiday_end` | int | 距假期结束已过几天(0-30) |
| 45 | `total_holiday_overlap` | int | 假日重叠度(school+public count, 0-6) |
| 46 | `is_departure_wave_day` | 0/1 | 出发波峰日(假期开始前周六) |
| 47 | `is_return_wave_day` | 0/1 | 返回波峰日(假期结束后周日) |
| 48 | `window_direction` | cat | 流量窗口方向 |
| 49 | `window_risk_level` | cat | 窗口风险等级 |
| 50 | `a8_direction` | cat | A8方向流量特征 |
| 51 | `a93_direction` | cat | A93方向流量特征 |

**关键观察**：假日特征群是模型中最"智能"的部分——它不只看"今天是不是假日"，还看"离假日还有几天""几个州同时放假""是不是出发波峰"。这些特征是领域专家知识的编码。在 ablation 中，抹掉这一组等于告诉模型"假设我们对假日一无所知"。

### 2.6 天气/路况类（10个）— 回答"天气怎么样"

| # | 特征 | 类型 | 含义 |
|---|------|------|------|
| 52 | `w_precip` | float | 降水量(mm) |
| 53 | `w_snow` | float | 降雪量(mm) |
| 54 | `w_lowvis` | float | 低能见度小时数 |
| 55 | `w_tmin` | float | 日最低气温(°C) |
| 56 | `w_tmax` | float | 日最高气温(°C) |
| 57 | `w_ice` | float | 结冰风险 |
| 58 | `weather_source` | cat | 数据来源：observed / climatology |
| 59 | `lt_mean` | float | 小时平均气温(°C) |
| 60 | `fbt_mean` | float | 小时平均路面温度(°C) |
| 61 | `fbt_min` | float | 小时最低路面温度(°C) |

**关键观察**：对未来日期，这些主要是**气候平均值**（climatology），不是实际天气预报。因此 WE 的 ablation 效应反映的是"这个月/小时的典型天气偏离中性状态多少"，而不是"明天会不会下雨"。

### 2.7 特殊事件类（12个）— 回答"有活动吗"

| # | 特征 | 类型 | 含义 |
|---|------|------|------|
| 62 | `has_special_event` | 0/1 | 当天有特殊事件 |
| 63 | `active_event_count` | int | 活跃事件数 |
| 64 | `max_impact_level` | int | 最大影响等级 |
| 65 | `impact_score` | float | 综合影响评分 |
| 66 | `affects_a8_ost` | 0/1 | 影响A8东走廊 |
| 67 | `affects_a93_sued` | 0/1 | 影响A93南走廊 |
| 68 | `has_munich_event` | 0/1 | 慕尼黑有活动 |
| 69 | `has_salzburg_event` | 0/1 | 萨尔茨堡有活动 |
| 70 | `has_rosenheim_event` | 0/1 | 罗森海姆有活动 |
| 71 | `has_kufstein_event` | 0/1 | 库夫施泰因有活动 |
| 72 | `has_confirmed_event` | 0/1 | 有已确认的活动 |
| 73 | `has_estimated_event` | 0/1 | 有预估的活动 |

### 2.8 施工/道路工程类（9个）— 回答"在修路吗"

| # | 特征 | 类型 | 含义 |
|---|------|------|------|
| 74 | `has_a8_construction` | 0/1 | A8有施工 |
| 75 | `has_a93_construction` | 0/1 | A93有施工 |
| 76 | `a8_construction_count` | int | A8施工数量 |
| 77 | `a93_construction_count` | int | A93施工数量 |
| 78 | `has_2_plus_0` | 0/1 | 有2+0单幅双向通行 |
| 79 | `two_plus_0_count` | int | 2+0配置数量 |
| 80 | `max_closed_lanes` | int | 最多关闭车道数 |
| 81 | `sum_closed_lanes` | int | 关闭车道总数 |
| 82 | `has_target_bbox_construction` | 0/1 | 目标区域有施工 |

---

## 3. 当前方案 vs 改进方案

### 3.1 当前 6-Group 方案

```
┌─────────────────────────────────────────────────────────┐
│ TT (Typical Traffic) — 12 features, 均值 82.8%           │
│   PROF_KFZ (5) + STATIC_NUM (3) + site_id/road/dir/name │
│   ❌ 混淆了"历史模式"和"地理位置"                          │
├─────────────────────────────────────────────────────────┤
│ CA (Calendar) — 19 features, 均值 7.6%                   │
│   CALENDAR (17) + tagestyp + season                      │
│   ❌ tagestyp 包含假日信息，泄漏了 HO 信号                  │
├─────────────────────────────────────────────────────────┤
│ HO (Holiday) — 20 features, 均值 4.5%                    │
│   HOLIDAY (16) + HOLIDAY_CAT (4)                         │
│   ❌ 缺少 tagestyp，假日效应被低估                         │
├─────────────────────────────────────────────────────────┤
│ WE (Weather) — 10 features, 均值 4.2%                    │
│ EV (Events) — 12 features, 均值 0.8%                     │
│ CO (Construction) — 9 features, 均值 0.0%                │
└─────────────────────────────────────────────────────────┘
```

### 3.2 改进 7-Group 方案

```
┌─────────────────────────────────────────────────────────┐
│ SL (Station & Location) — 7 features                     │
│   bab_km, longitude, latitude, site_id, road, direction, │
│   site_name                                              │
│   → "这个传感器装在哪里？是哪条路？"                       │
│   → 预期均值：15-25%                                     │
├─────────────────────────────────────────────────────────┤
│ HP (Historical Patterns) — 5 features                    │
│   prof_kfz_shd, prof_kfz_sht, prof_kfz_shm,              │
│   prof_kfz_p90, prof_kfz_shs                             │
│   → "根据3年历史数据，这个小时通常有多少车？"              │
│   → 预期均值：55-65%                                     │
├─────────────────────────────────────────────────────────┤
│ CA (Calendar & Season) — 18 features                     │
│   CALENDAR (17) + season                                 │
│   → "今天是几月几号星期几？什么季节？"                    │
│   → 纯时间信号，不再包含假日信息                          │
├─────────────────────────────────────────────────────────┤
│ HO (Holiday Effect) — 21 features                        │
│   HOLIDAY (16) + HOLIDAY_CAT (4) + tagestyp              │
│   → "放假了吗？几个州同时放？是出发日吗？"                │
│   → 完整的假日信号，不再泄漏到 CA                         │
├─────────────────────────────────────────────────────────┤
│ WE (Weather) — 10 features (不变)                        │
│ EV (Events) — 12 features (不变)                         │
│ CO (Construction) — 9 features (不变)                    │
└─────────────────────────────────────────────────────────┘
```

### 3.3 核心变化总结

| 变化 | 旧方案 | 新方案 | 理由 |
|------|--------|--------|------|
| TT → SL + HP | 12个特征混在一起 | 拆成 SL(7) + HP(5) | 分离"地理位置身份"和"历史数据模式" |
| tagestyp 归属 | CA (Calendar) | HO (Holiday) | tagestyp 对未来的值由假日标志派生，应归入假日效应 |
| 分组数 | 6 | 7 | 多一组，但每组语义更纯 |

---

## 4. 预期效果

### 4.1 新的均值分布（预测）

```
Factor                         旧均值    新均值(预测)   变化
─────────────────────────────────────────────────────────
TT (旧) / SL+HP (新)           82.8%     ~78-82%       略降（tagestyp移出）
  ├─ SL (Station Location)      —        ~15-25%       新增
  └─ HP (Historical Patterns)   —        ~55-65%       新增
CA (Calendar)                   7.6%     ~5-7%         降低（tagestyp移出，纯时间）
HO (Holiday)                    4.5%     ~6-10%        升高（tagestyp加入，假日信号完整）
WE (Weather)                    4.2%     ~4%           基本不变
EV (Events)                     0.8%     ~1%           基本不变
CO (Construction)               0.0%     ~0%           不变
```

### 4.2 关键日期的预期变化

| 日期 | 旧方案 | 新方案预期 |
|------|--------|-----------|
| 🎄 **圣诞前夜** (12/24) | TT=71%, CA=16%, HO=5% | SL≈15%, HP≈55%, CA≈5%, **HO≈18%** ← 假日效应大幅提升 |
| 🏖️ **夏季周六** (8月) | TT=67%, CA=10%, HO=4% | SL≈15%, HP≈55%, CA≈5%, **HO≈12%** ← 出发波峰可见 |
| 📅 **普通周三** (3月) | TT=91%, CA=5%, HO=1% | SL≈18%, HP≈70%, CA≈6%, HO≈1% ← 普通日变化不大 |

### 4.3 新的叙事能力

拆分后，Agent 层可以讲出更好的故事：

**旧方案**（不拆分）：
> "今日典型流量占预测的83%，日历占8%，假日占5%。"
> → 用户感受："所以...就是很正常？"

**新方案**（拆分后）：
> "该路段因位于慕尼黑-萨尔茨堡走廊（地理位置贡献18%），历史数据显示该时段通常车流密集（历史模式贡献60%），加上巴伐利亚和蒂罗尔同时放假引发的出发波峰（假日效应贡献15%），今日预测为重度拥堵。"
> → 用户感受："原来如此，因为是暑假出发日。"

---

## 5. 理论依据：为什么拆分 TT 是正确的

### 5.1 两类信息有本质区别

| 维度 | 站点地理位置 (SL) | 历史流量画像 (HP) |
|------|------------------|-------------------|
| **信息来源** | 传感器安装位置（物理事实） | 2023-2025历史数据聚合（数据事实） |
| **泛化方式** | 模型学到"慕尼黑附近=车多"的先验 | 模型学到"这个站周一8am=1434 veh/h"的模式 |
| **时间敏感性** | 不随时间变化 | 随训练数据更新而变化 |
| **可解释性** | "因为这条路本身就忙" | "因为历史上这个时段都忙" |
| **用户感知** | 常识性认知 | 数据驱动的证据 |

两者回答不同的用户问题：
- SL 回答：**"这条路本身就很忙吗？"**
- HP 回答：**"历史数据支持这个预测吗？"**

### 5.2 信息冗余但不是完全重叠

有人可能质疑：`prof_kfz_shd` 已经包含站点信息了（因为 key 里有 site_id），拆开有意义吗？

**有意义**，因为两者的 ablation 产生不同的预测变化：

- **Ablate SL（抹掉站点身份）**：模型不知道这是哪个站，但仍有 profile 值。模型看到一个 `prof_kfz_shd=1434`（MQB25的典型值），但不知道这个值来自慕尼黑附近的站。模型可能将其当作"某个未知中等偏上流量的站"来处理。预测会变化，但幅度有限——因为 profile 值本身已经传递了大部分信息。

- **Ablate HP（抹掉历史画像）**：模型知道这是 MQB25（慕尼黑附近、A8、往慕尼黑方向），但不知道这个站在周一8am通常有多少车。模型必须纯粹从 site_id + calendar 来推断流量。预测变化会很大——因为它失去了最直接的流量参考值。

- **Ablate 两者（原TT的效果）**：预测崩塌到接近全局均值，变化最大。

这三种 ablation 产生的 △prediction 量级不同，说明 SL 和 HP 提供的是两种**可分离**的信息。拆分后，我们能分别量化它们的边际贡献。

---

## 6. 实施记录（已完成）

### 6.1 修改 `EXPLANATION_GROUPS` 和 `FACTOR_ABBR`（Cell 16）

已在 notebook Cell 16 中更新为 7 组方案。同时新增 `FACTOR_DISPLAY` 映射，将内部组名映射为 SHAP 兼容的 Agent 显示名称：

```python
FACTOR_DISPLAY = {
    "Station & Location":       "Road Segment and Detector Attributes",
    "Historical Patterns":      "Historical Traffic Baseline",
    "Calendar & Season":        "Date and Time Pattern",
    "Holiday Effect":           "Holiday Effect",
    "Weather & Road":           "Weather and Temperature",
    "Special Events":           "Special Events",
    "Construction":             "Construction Impact",
}
```

### 6.2 修改 `daily_factor_attribution()`（Cell 48）

- 函数签名从 `(grid, contribs, group_names, abbr, min_pct=1.0)` 改为 `(grid, contribs, group_names, min_pct=0.1)`
- 输出列从 `factors`（缩写码）改为 `原因`（SHAP 兼容全名 + 1 位小数百分比）
- 分隔符从 `;` 改为 `；`（中文分号）
- 新增 `site_name` 列（Agent 所需）
- 格式：`"Historical Traffic Baseline: 68.0%；Date and Time Pattern: 11.6%；..."`

### 6.3 修改 pipeline（Cell 50）

- 新增日聚合步骤：从小时级 forecast groupby 到日级（sum/mean），四舍五入到 int/float
- 输出文件名从 `factor_attribution_daily.csv` 改为 `forecast_2026_2029_daily.csv`
- 合并日聚合 + 因子归因 → 保持 Agent 读取的列顺序

### 6.4 验证清单

- [x] Assert 完整性：82 特征恰好被覆盖一次
- [x] 输出格式与 `add_daily_forecast_reasons.py` 的 `原因` 列一致（Agent 零改动）
- [x] `forecast_2026_2029_daily.csv` 包含全部 13 列（日聚合 + `原因`）
- [x] `doc/FACTOR_CONTRIBUTIONS.md` 已全面重写为 7 组方案
- [x] `doc/MODEL.md` 已更新文件引用
- [x] `CLAUDE.md` 已更新项目状态

---

## 7. 与 SHAP 方法的简要对比

`add_daily_forecast_reasons.py` 的 SHAP 方案已经将 "Historical Traffic Baseline" 和 "Road Segment and Detector Attributes" 分开（7组），思路与本文案一致。但 SHAP 方案存在以下问题：

| 问题 | SHAP 方案 | 本文案 Ablation |
|------|----------|----------------|
| 聚合方式 | 简单求和（午夜=正午） | ✅ 流量加权聚合 |
| 假日信号 | tagestyp 不在任何组中 | ✅ tagestyp 归入 HO |
| 理论框架 | Shapley值（将贡献分散到共线特征） | ✅ Counterfactual（整组移除） |
| Construction | 17,532行全部为0.0000% | ✅ 可检测特征扰动 |

详见 `FACTOR_CONTRIBUTIONS.md` 第 "How It's Calculated" 节 —— ablation 的 counterfactual 语义更适合向终端用户解释。

---

## 8. 开放问题

1. **SL 组的实际贡献可能低于预期**：因为 `prof_kfz_*` 是按 site_id 聚合的，profile 值本身已经隐含了站点身份。如果 SL 贡献 < 10%，说明"地理位置"的信息几乎完全被 profile 吸收了——这也是一个有价值的发现。

2. **是否需要进一步拆分 CA**？将"时刻"（hour, hour_sin/cos）和"日期"（weekday, month, doy等）分开？对小时级归因可能有意义，但对日级归因（当前 target）意义不大。

3. **tagestyp 中的 's'（周日）问题**：普通周日归因到 HO 是否合理？可考虑只在 `derive_tagestyp` 为未来日期额外输出一个 `tagestyp_is_pure_calendar` 标志。但当前设计下，普通周日的 HO 贡献不会高（因为 holiday 特征全为0，只有 tagestyp='s'），实际影响很小。

---

## 9. 版本记录

- **v2 (2026-06-20)**：方案已实施。Notebook Cell 16/48/50 已更新，新增 `FACTOR_DISPLAY` 映射，`daily_factor_attribution()` 输出 SHAP 兼容格式，Cell 50 新增日聚合并输出 `forecast_2026_2029_daily.csv`。`doc/FACTOR_CONTRIBUTIONS.md` 全面重写。`doc/MODEL.md` 和 `CLAUDE.md` 已同步更新。
- **v1 (2026-06-20)**：初稿。提出 TT→SL+HP 拆分方案，tagestyp 归属修正，7组方案。
