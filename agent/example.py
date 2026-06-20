"""
Agent System Usage Examples
展示如何使用Agent系统的示例代码
"""
import asyncio
from datetime import datetime


async def example_forecast():
    """示例：获取交通预测"""
    from agent import OrchestratorAgent

    # 初始化
    orchestrator = OrchestratorAgent()
    await orchestrator.initialize()

    # 发送预测请求
    result = await orchestrator.process({
        "date": "2026-07-15",
        "road": "A8",
        "site_id": "A8_Rosenheim",
        "direction": "east",
        "hours": [8, 9, 10, 11, 12],
    })

    print("=== Traffic Forecast ===")
    if result.success:
        forecast = result.data.get("forecast", {})
        predictions = forecast.get("predictions", [])
        for pred in predictions:
            print(f"  {pred['hour']:02d}:00 - Volume: {pred['p50']} ({pred['congestion_level']})")

        print(f"\nPeak hour: {forecast.get('peak_hour')}:00")
    else:
        print(f"Error: {result.message}")


async def example_trip_plan():
    """示例：出行规划"""
    from agent import OrchestratorAgent

    orchestrator = OrchestratorAgent()
    await orchestrator.initialize()

    result = await orchestrator.process({
        "query": "Plan my trip from Munich to Salzburg",
        "date": "2026-08-01",
        "user_type": "tourist",
    })

    print("\n=== Trip Plan ===")
    if result.success:
        plan = result.data.get("plan", {})
        print(f"Recommended departure: {plan.get('recommended_departure')}")
        print(f"Estimated travel time: {plan.get('estimated_travel_time_min')} minutes")
        print(f"Estimated arrival: {plan.get('estimated_arrival')}")

        stress = plan.get("stress_index", {})
        print(f"\nStress Index: {stress.get('score')}/100 {stress.get('emoji')}")
        print(f"  {stress.get('description')}")

        print("\nTips:")
        for tip in plan.get("tips", []):
            print(f"  {tip}")
    else:
        print(f"Error: {result.message}")


async def example_what_if():
    """示例：What-if模拟"""
    from agent import OrchestratorAgent

    orchestrator = OrchestratorAgent()
    await orchestrator.initialize()

    # 模拟暴雨场景
    result = await orchestrator.process({
        "date": "2026-07-15",
        "site_id": "A8_Rosenheim",
        "scenario": {
            "type": "weather_change",
            "parameters": {"weather": "heavy_rain"}
        }
    })

    print("\n=== What-If Simulation: Heavy Rain ===")
    if result.success:
        simulation = result.data.get("simulation", {})
        sim_result = simulation.get("simulation_result", {})
        summary = sim_result.get("summary", {})

        print(f"Total delay: {summary.get('total_delay_minutes')} minutes")
        print(f"Average speed: {summary.get('average_speed_kmh')} km/h")
        print(f"Worst hour: {summary.get('worst_hour')}:00")

        recommendations = simulation.get("recommendations", {})
        print(f"\nRecommendation: {recommendations.get('message')}")

        print("\nAlternatives:")
        for alt in simulation.get("alternatives", [])[:2]:
            print(f"  - {alt['name']}: {alt['description']}")
            print(f"    Time saved: {alt['estimated_time_saved_min']} min")
    else:
        print(f"Error: {result.message}")


async def example_graph_rag():
    """示例：Graph RAG查询"""
    from agent import GraphRAG

    graph_rag = GraphRAG()
    await graph_rag.initialize()

    print("\n=== Graph RAG ===")

    # 查询图谱统计
    stats = graph_rag.get_statistics()
    print(f"Total nodes: {stats['total_nodes']}")
    print(f"Total edges: {stats['total_edges']}")
    print(f"Node types: {stats['node_types']}")

    # 查询影响因素
    factors = graph_rag.query_factors("A8_ROS", "2026-08-01")
    print(f"\nFactors affecting A8_ROS on 2026-08-01:")
    print(f"  Segment: {factors.get('segment', {}).get('properties', {}).get('name')}")
    print(f"  Events: {[e['properties']['name'] for e in factors.get('events', [])]}")

    # 获取用户相关信息
    user_info = graph_rag.get_user_relevant_info("tourist", "2026-08-01", "A8")
    print(f"\nInfo for tourist:")
    print(f"  Priorities: {user_info.get('priorities', [])}")


async def example_all():
    """运行所有示例"""
    await example_forecast()
    await example_trip_plan()
    await example_what_if()
    await example_graph_rag()


if __name__ == "__main__":
    print("AlpineFlow AI Agent System - Examples\n")
    print("=" * 50)

    asyncio.run(example_all())

    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nTo start the API server, run:")
    print("  python -m agent.api")
    print("  # or")
    print("  uvicorn agent.api:create_app --factory --reload")
