# SubAgent 处理逻辑详解

本文档详细说明 AlpineFlow AI 各个 SubAgent 的处理逻辑和数据流。

---

## 目录

- [总体工作流](#总体工作流)
- [1. parse_intent_node 意图解析](#1-parse_intent_node-意图解析)
- [2. route_node 路由决策](#2-route_node-路由决策)
- [3. forecast_node 预测节点](#3-forecast_node-预测节点)
- [4. explain_node 解释节点](#4-explain_node-解释节点)
- [5. retrieve_node 检索节点](#5-retrieve_node-检索节点)
- [6. simulate_node 模拟节点](#6-simulate_node-模拟节点)
- [7. generate_response_node 响应生成](#7-generate_response_node-响应生成)
- [执行路径](#执行路径)
- [Congestion Score 计算](#congestion-score-计算)

---

## 总体工作流

```
用户请求 (query, date, road, user_type)
    │
    ▼
┌─────────────────┐
│ 1. parse_intent │  解析意图：forecast/plan/whatif/explain
│    输入: query  │
│    输出: intent │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   2. route      │  路由决策
│ 输入: intent    │
│ 输出: next_step │
└────────┬────────┘
         │
    ┌────┴────────────────┐
    ▼                     ▼
┌────────────────┐   ┌─────────────────┐
│ 并行路径        │   │ 串行路径         │
│ (forecast/plan)│   │ (whatif/compare)│
│                │   │                 │
│ ┌─────────┐   │   │ ┌─────────┐    │
│ │forecast │   │   │ │forecast │    │
│ └─────────┘   │   │ └────┬────┘    │
│ ┌─────────┐   │   │      ▼         │
│ │explain  │   │   │ ┌─────────┐    │
│ └─────────┘   │   │ │simulate │    │
│ ┌─────────┐   │   │ └─────────┘    │
│ │retrieve │   │   │                 │
│ └─────────┘   │   │                 │
└───────┬────────┘   └────────┬───────┘
        │                     │
        └──────────┬──────────┘
                   ▼
         ┌─────────────────┐
         │ 3. generate     │  汇总结果，生成最终响应
         │ 输入: 各Agent结果│
         │ 输出: response  │
         └────────┬────────┘
                  │
                  ▼
             最终响应 (JSON)
```

---

## 1. parse_intent_node 意图解析

### 功能
分析用户查询文本，识别用户意图。

### 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| query | string | 用户原始查询文本 |

### 处理逻辑

```python
def parse_intent(query: str) -> str:
    query = query.lower()

    # 优先级从高到低匹配
    if contains(query, ["if", "what if", "假如", "如果", "would happen"]):
        return "whatif"      # What-if 场景模拟

    elif contains(query, ["plan", "trip", "travel", "when should", "best time", "规划"]):
        return "plan"        # 出行规划

    elif contains(query, ["why", "reason", "explain", "为什么", "原因"]):
        return "explain"     # 解释原因

    elif contains(query, ["compare", "vs", "versus", "比较"]):
        return "compare"     # 方案对比

    else:
        return "forecast"    # 默认：交通预测
```

### 输出
| 字段 | 类型 | 说明 |
|------|------|------|
| intent | string | 识别的意图 |
| next_step | string | 下一步路由 |

### 意图类型

| Intent | 说明 | 触发词示例 |
|--------|------|-----------|
| `forecast` | 交通预测 | "traffic", "congestion", "busy" |
| `plan` | 出行规划 | "plan trip", "best time to leave" |
| `whatif` | 场景模拟 | "what if it rains", "如果下雨" |
| `explain` | 原因解释 | "why is it busy", "为什么堵" |
| `compare` | 方案对比 | "compare routes", "A8 vs A93" |

---

## 2. route_node 路由决策

### 功能
根据意图决定执行哪条处理路径。

### 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| intent | string | 解析的意图 |

### 处理逻辑

```python
def route(intent: str) -> str:
    routes = {
        "forecast": "parallel_agents",   # 并行执行 forecast + explain + retrieve
        "plan":     "parallel_agents",
        "explain":  "parallel_agents",
        "whatif":   "forecast_first",    # 先预测，再模拟
        "compare":  "forecast_first",
    }
    return routes.get(intent, "parallel_agents")
```

### 输出
| 字段 | 类型 | 可选值 |
|------|------|--------|
| next_step | string | `parallel_agents` / `forecast_first` |

### 路由分支说明

| 路径 | 执行方式 | 适用场景 |
|------|---------|---------|
| `parallel_agents` | 并行执行 forecast + explain + retrieve | 需要综合信息 |
| `forecast_first` | 串行执行 forecast → simulate | 模拟需要预测基准 |

---

## 3. forecast_node 预测节点

### 功能
预测指定日期、路段的小时级交通流量和拥堵等级。

### 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 日期 YYYY-MM-DD |
| site_id | string | 站点 ID |
| hours | List[int] | 预测小时列表 |

### 处理逻辑

```python
def forecast(date: str, site_id: str, hours: List[int]) -> Dict:
    predictions = []

    for hour in hours:
        # Step 1: 基础流量
        base_volume = 800  # 辆/小时

        # Step 2: 时段系数
        if 7 <= hour <= 9:        # 早高峰
            multiplier = 1.8
        elif 16 <= hour <= 18:    # 晚高峰
            multiplier = 2.0
        elif 10 <= hour <= 15:    # 白天
            multiplier = 1.4
        elif 5 <= hour <= 6:      # 清晨
            multiplier = 0.8
        else:                     # 夜间
            multiplier = 0.5

        # Step 3: 周末调整
        if is_weekend(date):
            if 9 <= hour <= 14:   # 周末出游高峰
                multiplier *= 1.3
            else:
                multiplier *= 0.8

        # Step 4: 计算分位数
        p50 = base_volume * multiplier
        p10 = p50 * 0.75   # 乐观估计
        p90 = p50 * 1.35   # 悲观估计

        # Step 5: 拥堵等级判定
        congestion_level = get_congestion_level(p50)

        predictions.append({
            "hour": hour,
            "p10": p10,
            "p50": p50,
            "p90": p90,
            "congestion_level": congestion_level
        })

    # Step 6: 汇总统计
    peak_hour = max(predictions, key=lambda x: x["p50"])["hour"]

    return {
        "predictions": predictions,
        "peak_hour": peak_hour,
        "daily_summary": calculate_summary(predictions)
    }
```

### 拥堵等级判定

| 流量 (p50) | 等级 | 颜色 | 说明 |
|-----------|------|------|------|
| < 800 | `smooth` | 🟢 | 畅通 |
| 800-1200 | `light` | 🟡 | 轻微拥堵 |
| 1200-1600 | `moderate` | 🟠 | 中度拥堵 |
| 1600-2000 | `heavy` | 🔴 | 严重拥堵 |
| ≥ 2000 | `critical` | ⚫ | 极度拥堵 |

### 输出
```json
{
  "predictions": [
    {"hour": 8, "p10": 1080, "p50": 1440, "p90": 1944, "congestion_level": "moderate"},
    {"hour": 9, "p10": 1080, "p50": 1440, "p90": 1944, "congestion_level": "moderate"},
    ...
  ],
  "peak_hour": 17,
  "daily_summary": {
    "total_volume": 25680,
    "avg_hourly_volume": 1070,
    "max_hourly_volume": 1600,
    "min_hourly_volume": 400
  }
}
```

---

## 4. explain_node 解释节点

### 功能
分析影响交通的因素，生成可解释的归因报告。

### 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 日期 YYYY-MM-DD |

### 处理逻辑

```python
def explain(date: str) -> Dict:
    factors = []

    # Factor 1: 公共假期
    if date in PUBLIC_HOLIDAYS:
        factors.append({
            "type": "public_holiday",
            "name": PUBLIC_HOLIDAYS[date],
            "impact": "high",
            "magnitude": 0.40,  # +40% 流量
            "description": f"Public holiday ({name}) - expect higher traffic"
        })

    # Factor 2: 周末效应
    weekday = get_weekday(date)
    if weekday == "Friday":
        factors.append({
            "type": "weekend",
            "name": "Friday",
            "impact": "moderate",
            "magnitude": 0.15,  # +15%
            "description": "Friday afternoon - weekend departure traffic"
        })
    elif weekday == "Sunday":
        factors.append({
            "type": "weekend",
            "name": "Sunday",
            "impact": "moderate",
            "magnitude": 0.20,  # +20%
            "description": "Sunday afternoon - weekend return traffic"
        })

    # Factor 3: 季节因素
    month = get_month(date)
    if month in [6, 7, 8]:  # 夏季
        factors.append({
            "type": "season",
            "name": "Summer",
            "impact": "high",
            "magnitude": 0.30,  # +30%
            "description": "Summer season - high tourist traffic towards Alps"
        })
    elif month in [12, 1, 2]:  # 冬季
        factors.append({
            "type": "season",
            "name": "Winter",
            "impact": "moderate",
            "magnitude": 0.20,  # +20%
            "description": "Winter season - ski traffic towards Austria"
        })

    # Factor 4: 学校假期 (可扩展)
    # Factor 5: 天气 (可扩展)

    # 生成解释文本
    explanation = generate_explanation_text(date, factors)

    return {
        "factors": factors,
        "explanation": explanation,
        "date": date
    }
```

### 因素类型

| 类型 | 影响程度 | 流量变化 |
|------|---------|---------|
| `public_holiday` | high | +30% ~ +50% |
| `school_holiday` | high | +20% ~ +40% |
| `weekend` (Fri/Sun) | moderate | +15% ~ +25% |
| `season` (Summer) | high | +25% ~ +35% |
| `season` (Winter) | moderate | +15% ~ +25% |
| `weather` (bad) | varies | -10% ~ +20% |
| `event` (major) | high | +20% ~ +60% |

### 输出
```json
{
  "factors": [
    {
      "type": "weekend",
      "name": "Friday",
      "impact": "moderate",
      "magnitude": 0.15,
      "description": "Friday afternoon - weekend departure traffic"
    },
    {
      "type": "season",
      "name": "Summer",
      "impact": "high",
      "magnitude": 0.30,
      "description": "Summer season - high tourist traffic towards Alps"
    }
  ],
  "explanation": "On Friday, July 15, 2026:\n• Friday afternoon - weekend departure traffic\n• Summer season - high tourist traffic towards Alps"
}
```

---

## 5. retrieve_node 检索节点

### 功能
检索外部实时信息：施工、活动、事故等。

### 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 日期 |
| road | string | 高速公路 (A8/A93) |

### 处理逻辑

```python
def retrieve(date: str, road: str) -> Dict:
    constructions = []
    events = []
    warnings = []

    # 检索施工信息
    for construction in CONSTRUCTION_DATABASE:
        if construction.start <= date <= construction.end:
            if construction.road == road:
                constructions.append({
                    "id": construction.id,
                    "road": construction.road,
                    "location": construction.location,
                    "description": construction.description,
                    "impact": construction.impact  # low/moderate/high
                })

    # 检索活动信息
    for event in EVENT_DATABASE:
        if event.start <= date <= event.end:
            if road in event.affected_roads:
                events.append({
                    "id": event.id,
                    "name": event.name,
                    "type": event.type,  # festival/sports/cultural
                    "impact_level": event.impact
                })

    # 生成警告
    for item in constructions + events:
        if item.impact in ["high", "very_high"]:
            warnings.append({
                "type": item.type,
                "severity": item.impact,
                "message": format_warning(item)
            })

    return {
        "constructions": constructions,
        "events": events,
        "warnings": warnings,
        "date": date,
        "road": road
    }
```

### 数据源

| 数据类型 | 来源 | 更新频率 |
|---------|------|---------|
| 施工信息 | Autobahn API | 每日 |
| 活动信息 | 本地数据库 | 每周 |
| 事故信息 | 实时 API | 实时 |
| 假期日历 | OpenHolidays API | 年度 |

### 输出
```json
{
  "constructions": [
    {
      "id": "C001",
      "road": "A8",
      "description": "Bridge renovation - right lane closed",
      "impact": "moderate"
    }
  ],
  "events": [
    {
      "id": "E001",
      "name": "Salzburg Festival",
      "type": "cultural",
      "impact_level": "high"
    }
  ],
  "warnings": [
    {
      "type": "event",
      "severity": "high",
      "message": "🎭 Salzburg Festival in progress - high traffic expected"
    }
  ]
}
```

---

## 6. simulate_node 模拟节点

### 功能
What-if 场景分析，模拟不同条件下的交通状况。

### 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| scenario | Dict | 场景定义 |
| forecast_result | Dict | 基准预测 |

### 场景类型

| 场景 | 参数 | 说明 |
|------|------|------|
| `weather_change` | `{"weather": "heavy_rain"}` | 天气变化 |
| `accident` | `{"lanes_blocked": 2}` | 事故 |
| `traffic_increase` | `{"percent": 20}` | 流量增加 |
| `construction` | `{"lanes_closed": 1}` | 施工 |

### 处理逻辑

```python
def simulate(scenario: Dict, forecast: Dict) -> Dict:
    scenario_type = scenario.get("type", "weather_change")
    parameters = scenario.get("parameters", {})
    base_predictions = forecast.get("predictions", [])

    simulated = []

    for pred in base_predictions:
        hour = pred["hour"]
        base_volume = pred["p50"]
        base_speed = 120  # km/h

        # 计算速度修正系数
        speed_modifier = 1.0

        if scenario_type == "weather_change":
            weather = parameters.get("weather", "clear")
            weather_factors = {
                "clear": 1.00,
                "cloudy": 0.98,
                "light_rain": 0.90,
                "heavy_rain": 0.75,
                "snow": 0.60,
                "ice": 0.50
            }
            speed_modifier = weather_factors.get(weather, 1.0)

        elif scenario_type == "accident":
            lanes_blocked = parameters.get("lanes_blocked", 1)
            # 每封闭一条车道，速度下降30%
            speed_modifier = 1.0 - (lanes_blocked * 0.30)

        elif scenario_type == "traffic_increase":
            increase_pct = parameters.get("percent", 0)
            # 流量增加导致速度下降
            speed_modifier = 1.0 - (increase_pct / 200)

        # 计算模拟速度
        sim_speed = max(20, base_speed * speed_modifier)

        # 计算延误 (100km 行程)
        base_time = 100 / base_speed * 60  # 分钟
        sim_time = 100 / sim_speed * 60
        delay_min = sim_time - base_time

        simulated.append({
            "hour": hour,
            "base_volume": base_volume,
            "simulated_speed_kmh": round(sim_speed, 1),
            "delay_minutes": round(max(0, delay_min), 1)
        })

    # 汇总
    total_delay = sum(s["delay_minutes"] for s in simulated)

    # 生成替代方案
    alternatives = generate_alternatives(total_delay)

    # 生成建议
    recommendation = generate_recommendation(total_delay)

    return {
        "scenario_type": scenario_type,
        "parameters": parameters,
        "hourly_results": simulated,
        "total_delay_minutes": round(total_delay, 1),
        "alternatives": alternatives,
        "recommendation": recommendation
    }
```

### 天气影响系数

| 天气 | 速度系数 | 预计延误 (100km) |
|------|---------|-----------------|
| clear | 1.00 | 0 min |
| cloudy | 0.98 | ~1 min |
| light_rain | 0.90 | ~6 min |
| heavy_rain | 0.75 | ~17 min |
| snow | 0.60 | ~33 min |
| ice | 0.50 | ~50 min |

### 建议生成逻辑

| 总延误 | 建议 |
|--------|------|
| < 15 min | ✅ Proceed with your trip |
| 15-45 min | ⚠️ Consider adjusting departure time |
| > 45 min | ❌ Consider alternative plans |

### 输出
```json
{
  "scenario_type": "weather_change",
  "parameters": {"weather": "heavy_rain"},
  "hourly_results": [
    {"hour": 8, "base_volume": 1440, "simulated_speed_kmh": 90.0, "delay_minutes": 16.7},
    ...
  ],
  "total_delay_minutes": 28.5,
  "alternatives": [
    {
      "id": "early_departure",
      "name": "Early Departure",
      "description": "Leave 2-3 hours earlier",
      "estimated_time_saved_min": 20
    }
  ],
  "recommendation": "Moderate delays expected. Consider adjusting departure time."
}
```

---

## 7. generate_response_node 响应生成

### 功能
汇总各 Agent 结果，生成最终个性化响应。

### 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| intent | string | 意图 |
| user_type | string | 用户类型 |
| forecast_result | Dict | 预测结果 |
| explanation_result | Dict | 解释结果 |
| retrieval_result | Dict | 检索结果 |
| simulation_result | Dict | 模拟结果 |

### 处理逻辑

```python
def generate_response(state: AgentState) -> Dict:
    intent = state["intent"]
    user_type = state["user_type"]

    response = {
        "intent": intent,
        "user_type": user_type,
        "date": state["date"],
        "road": state["road"]
    }

    # 根据意图组装响应
    if intent == "forecast":
        response["forecast"] = state["forecast_result"]
        response["external_factors"] = state["retrieval_result"]
        response["explanation"] = state["explanation_result"]

    elif intent == "plan":
        forecast = state["forecast_result"]
        predictions = forecast.get("predictions", [])

        # 找出最佳出发时间 (smooth 或 light 的小时)
        best_hours = [
            p["hour"] for p in predictions
            if p["congestion_level"] in ["smooth", "light"]
        ]
        recommended = best_hours[0] if best_hours else 7

        response["plan"] = {
            "recommended_departure": f"{recommended:02d}:00",
            "alternative_departures": [f"{h:02d}:00" for h in best_hours[:3]],
            "estimated_travel_time_min": 90,
            "warnings": state["retrieval_result"].get("warnings", [])
        }
        response["forecast"] = forecast

    elif intent == "whatif":
        response["simulation"] = state["simulation_result"]
        response["base_forecast"] = state["forecast_result"]

    elif intent == "explain":
        response["explanation"] = state["explanation_result"]
        response["forecast"] = state["forecast_result"]

    # 添加个性化
    response["personalization"] = get_personalization(user_type)

    return response
```

### 用户类型个性化

| user_type | focus | priority |
|-----------|-------|----------|
| `tourist` | best travel experience | scenic route, comfortable timing |
| `resident` | avoiding local congestion | quick commute, familiar routes |
| `logistics` | delivery efficiency | punctuality, fuel economy |
| `tourism_business` | customer arrival patterns | peak visitor times, preparation |
| `authority` | traffic management | congestion prevention, resource allocation |

---

## 执行路径

### 路径 A: parallel_agents（并行执行）

**适用意图**: `forecast`, `plan`, `explain`

```
route (intent=forecast/plan/explain)
  │
  ▼
parallel_agents_node
  │
  ├── forecast_node()   →  forecast_result
  │
  ├── explain_node()    →  explanation_result
  │
  └── retrieve_node()   →  retrieval_result
  │
  ▼
合并所有结果
  │
  ▼
generate_response_node
  │
  ▼
final_response
```

### 路径 B: forecast_first（串行执行）

**适用意图**: `whatif`, `compare`

```
route (intent=whatif/compare)
  │
  ▼
forecast_first_node
  │
  ├── Step 1: forecast_node()
  │              │
  │              ▼
  │         forecast_result
  │              │
  └── Step 2: simulate_node(forecast_result)
                   │
                   ▼
              simulation_result
  │
  ▼
generate_response_node
  │
  ▼
final_response
```

**为什么串行？**
`simulate_node` 需要 `forecast_result` 作为基准来计算延误和对比。

---

## Congestion Score 计算

详见 `congestion_score.py`

### 输入数据

| 数据 | 权重 | 说明 |
|------|------|------|
| 流量 (kfz_h) | 25% | 小时车流量 |
| 大车占比 (lkw_ratio) | 10% | 重型车比例 |
| 平均车速 (v_kfz) | 30% | 平均速度 |
| 容量利用率 | 20% | 流量/容量 |
| 外部因素 | 15% | 假期/天气/活动 |

### 输出

| Score | Level | 颜色 | 建议 |
|-------|-------|------|------|
| 0-20 | Smooth | 🟢 | 畅通 |
| 20-40 | Light | 🟡 | 轻微拥堵 |
| 40-60 | Moderate | 🟠 | 中度拥堵 |
| 60-80 | Heavy | 🔴 | 严重拥堵 |
| 80-100 | Critical | ⚫ | 极度拥堵 |
