#!/usr/bin/env python3
"""
预生成交通解释 CSV 文件

使用与 API 相同的 Agent 获取数据，调用 LLM 生成解释。

用法:
    python scripts/generate_explanations.py --start-date 2026-07-01 --end-date 2026-07-31 --lang en

生成的 CSV 保存到 data_autobahn/explanations_{lang}.csv
"""
import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.models import AgentRequest
from agent.tools.llm_client import generate


# 拥堵等级翻译
LEVEL_NAMES = {
    "zh": {
        "smooth": "畅通",
        "light": "轻度拥堵",
        "moderate": "中度拥堵",
        "heavy": "严重拥堵",
        "critical": "极度拥堵",
    },
    "en": {
        "smooth": "Smooth",
        "light": "Light congestion",
        "moderate": "Moderate congestion",
        "heavy": "Heavy congestion",
        "critical": "Critical congestion",
    },
    "de": {
        "smooth": "Flüssig",
        "light": "Leichter Stau",
        "moderate": "Mittlerer Stau",
        "heavy": "Starker Stau",
        "critical": "Sehr starker Stau",
    },
}


async def generate_llm_explanation(
    date: str,
    hour: int,
    road: str,
    lang: str,
    level_name: str,
    congestion_score: float,
    flow: float,
    speed: float,
    factor_descriptions: list,
) -> str:
    """调用 LLM 生成解释"""

    if lang == "zh":
        prompt = f"""请用要点形式解释以下交通状况原因：

日期: {date}
时间: {hour}:00
道路: {road}
拥堵等级: {level_name}
拥堵指数: {congestion_score}/100
流量: {flow:.0f} 辆/小时
平均车速: {speed:.1f} km/h

影响因素:
{chr(10).join(factor_descriptions) if factor_descriptions else "无特殊因素"}

要求:
- 用 2-4 个要点解释原因
- 每个要点以 "•" 开头
- 每个要点一行，简洁明了
- 提及具体数据（如流量、车速）
- 提及主要影响因素

示例格式:
• 施工影响：A8多处施工封闭车道
• 流量较高：4500辆/小时，接近高峰
• 假期因素：暑假期间出行增多"""
        system = "你是交通状况解释助手，用要点形式解释交通原因。每个要点简洁有力。"

    elif lang == "en":
        prompt = f"""Explain the following traffic condition in bullet points:

Date: {date}
Time: {hour}:00
Road: {road}
Congestion Level: {level_name}
Congestion Score: {congestion_score}/100
Traffic Flow: {flow:.0f} vehicles/hour
Average Speed: {speed:.1f} km/h

Factors:
{chr(10).join(factor_descriptions) if factor_descriptions else "No special factors"}

Requirements:
- Use 2-4 bullet points to explain
- Start each point with "•"
- One point per line, concise
- Include specific data (flow, speed)
- Mention key factors

Example format:
• Construction: Multiple lane closures on A8
• High volume: 4500 veh/h, near peak
• Holiday effect: Summer vacation increases travel"""
        system = "You are a traffic explanation assistant. Use bullet points to explain traffic conditions."

    else:  # de
        prompt = f"""Erklären Sie die folgende Verkehrssituation in Stichpunkten:

Datum: {date}
Zeit: {hour}:00
Straße: {road}
Staustufe: {level_name}
Stauindex: {congestion_score}/100
Verkehrsfluss: {flow:.0f} Fahrzeuge/Stunde
Durchschnittsgeschwindigkeit: {speed:.1f} km/h

Einflussfaktoren:
{chr(10).join(factor_descriptions) if factor_descriptions else "Keine besonderen Faktoren"}

Anforderungen:
- Verwenden Sie 2-4 Stichpunkte
- Beginnen Sie jeden Punkt mit "•"
- Ein Punkt pro Zeile, prägnant
- Nennen Sie konkrete Daten (Fluss, Geschwindigkeit)
- Erwähnen Sie wichtige Faktoren

Beispielformat:
• Baustelle: Mehrere Fahrspuren auf A8 gesperrt
• Hohes Volumen: 4500 Fzg/h, nahe Spitze
• Ferieneffekt: Sommerferien erhöhen Reiseverkehr"""
        system = "Sie sind ein Verkehrserklärungs-Assistent. Verwenden Sie Stichpunkte zur Erklärung."

    try:
        explanation = await generate(prompt, system=system)
        return explanation.strip()
    except Exception as e:
        print(f"    [ERROR] LLM 调用失败: {e}")
        return ""


async def process_hour(
    date: str,
    hour: int,
    road: str,
    lang: str,
    forecast_agent,
    context_agent,
    search_agent,
) -> dict:
    """处理单个小时，使用与 API 相同的 Agent"""

    # 构建请求
    forecast_request = AgentRequest(
        query="hourly explain",
        date=date,
        road=road,
        hours=[hour],
        granularity="hourly",
    )
    context_request = AgentRequest(
        query="context",
        date=date,
        road=road,
        hours=[hour],
    )

    # 并行调用 Agent
    forecast_result, context_result, search_result = await asyncio.gather(
        forecast_agent.process(forecast_request),
        context_agent.process(context_request),
        search_agent.process(context_request),
    )

    # 提取预测数据
    prediction = None
    if forecast_result.success:
        forecast_data = forecast_result.data.get("forecast")
        if forecast_data:
            if isinstance(forecast_data, dict):
                predictions = forecast_data.get("predictions", [])
            elif hasattr(forecast_data, "predictions"):
                predictions = forecast_data.predictions
            else:
                predictions = []

            if predictions:
                for pred in predictions:
                    pred_hour = pred.get("hour") if isinstance(pred, dict) else getattr(pred, "hour", None)
                    if pred_hour == hour:
                        prediction = pred if isinstance(pred, dict) else pred.__dict__
                        break
                if not prediction and predictions:
                    first = predictions[0]
                    prediction = first if isinstance(first, dict) else first.__dict__

    # 整理因素
    factors = []
    factor_descriptions = []

    if context_result.success:
        for f in context_result.data.get("factors", []):
            factor_info = {
                "type": getattr(f, "type", "unknown"),
                "name": getattr(f, "name", ""),
                "description": getattr(f, "description", ""),
                "impact": getattr(f, "impact", "neutral"),
            }
            factors.append(factor_info)
            if factor_info["name"] and factor_info["description"]:
                factor_descriptions.append(f"{factor_info['name']}: {factor_info['description']}")

    if search_result.success:
        for f in search_result.data.get("factors", []):
            factor_info = {
                "type": getattr(f, "type", "unknown"),
                "name": getattr(f, "name", ""),
                "description": getattr(f, "description", ""),
                "impact": getattr(f, "impact", "neutral"),
            }
            factors.append(factor_info)
            if factor_info["name"] and factor_info["description"]:
                factor_descriptions.append(f"{factor_info['name']}: {factor_info['description']}")

    # 提取数值
    congestion_level = prediction.get("congestion_level", "unknown") if prediction else "unknown"
    congestion_score = prediction.get("congestion_score", 0) if prediction else 0
    flow = prediction.get("kfz_h_p50", 0) if prediction else 0
    speed = prediction.get("v_kfz", 0) if prediction else 0

    level_name = LEVEL_NAMES.get(lang, LEVEL_NAMES["en"]).get(congestion_level, congestion_level)

    # 调用 LLM 生成解释
    explanation = await generate_llm_explanation(
        date=date,
        hour=hour,
        road=road,
        lang=lang,
        level_name=level_name,
        congestion_score=congestion_score,
        flow=flow,
        speed=speed,
        factor_descriptions=factor_descriptions[:5],  # 最多 5 个因素
    )

    return {
        "date": date,
        "hour": hour,
        "road": road,
        "lang": lang,
        "congestion_level": congestion_level,
        "congestion_level_name": level_name,
        "congestion_score": round(congestion_score, 1),
        "flow": round(flow),
        "speed": round(speed, 1),
        "explanation": explanation,
    }


async def main():
    parser = argparse.ArgumentParser(description="预生成交通解释 CSV")
    parser.add_argument("--start-date", required=True, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--road", default="A8", help="道路 (A8, A93)")
    parser.add_argument("--lang", default="en", choices=["zh", "en", "de"], help="语言")
    parser.add_argument("--hours", default="6-22", help="小时范围 (如 6-22)")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--batch-size", type=int, default=5, help="并发批次大小")
    args = parser.parse_args()

    # 解析参数
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    hour_start, hour_end = map(int, args.hours.split("-"))
    hours = list(range(hour_start, hour_end + 1))

    output_path = args.output or str(
        project_root / "data_autobahn" / f"explanations_{args.lang}.csv"
    )

    print(f"=== 预生成交通解释 ===")
    print(f"日期范围: {args.start_date} ~ {args.end_date}")
    print(f"道路: {args.road}")
    print(f"语言: {args.lang}")
    print(f"小时范围: {hours[0]}:00 ~ {hours[-1]}:00")
    print(f"输出文件: {output_path}")
    print(f"并发批次: {args.batch_size}")
    print()

    # 初始化 Agent（复用实例）
    from agent.agents import ForecastAgent, ContextAgent, SearchAgent

    forecast_agent = ForecastAgent()
    context_agent = ContextAgent()
    search_agent = SearchAgent()

    # 准备输出
    results = []
    current_date = start_date
    total_days = (end_date - start_date).days + 1
    day_count = 0

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_count += 1
        print(f"[{day_count}/{total_days}] 处理日期: {date_str}")

        # 分批处理小时（控制并发）
        for i in range(0, len(hours), args.batch_size):
            batch_hours = hours[i:i + args.batch_size]

            tasks = [
                process_hour(
                    date=date_str,
                    hour=h,
                    road=args.road,
                    lang=args.lang,
                    forecast_agent=forecast_agent,
                    context_agent=context_agent,
                    search_agent=search_agent,
                )
                for h in batch_hours
            ]

            batch_results = await asyncio.gather(*tasks)

            for result in batch_results:
                results.append(result)
                print(f"  {result['hour']:02d}:00 - {result['congestion_level_name']} - score={result['congestion_score']}")

        current_date += timedelta(days=1)

    # 写入 CSV
    print(f"\n写入 CSV: {output_path}")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "hour", "road", "lang",
            "congestion_level", "congestion_level_name", "congestion_score",
            "flow", "speed", "explanation"
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"完成! 共生成 {len(results)} 条记录")


if __name__ == "__main__":
    asyncio.run(main())
