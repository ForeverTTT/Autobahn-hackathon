"""
LangGraph Agent Examples
使用示例
"""


def example_basic():
    """基础用法：使用规则引擎"""
    print("=" * 50)
    print("Example 1: Basic Usage (Rule-based)")
    print("=" * 50)

    from agent.langgraph import TrafficAgentGraph

    # 创建Agent
    agent = TrafficAgentGraph()

    # 获取预测
    result = agent.invoke(
        query="What's the traffic like?",
        date="2026-07-15",
        road="A8",
        user_type="tourist"
    )

    print(f"\nIntent: {result.get('intent')}")
    print(f"Date: {result.get('date')}")

    forecast = result.get("forecast", {})
    if forecast:
        print(f"\nPeak hour: {forecast.get('peak_hour')}:00")
        print("\nHourly predictions:")
        for pred in forecast.get("predictions", [])[:5]:
            print(f"  {pred['hour']:02d}:00 - {pred['p50']} vehicles ({pred['congestion_level']})")


def example_trip_plan():
    """出行规划"""
    print("\n" + "=" * 50)
    print("Example 2: Trip Planning")
    print("=" * 50)

    from agent.langgraph import TrafficAgentGraph

    agent = TrafficAgentGraph()

    result = agent.invoke(
        query="Plan my trip from Munich to Salzburg",
        date="2026-08-01",
        user_type="tourist"
    )

    plan = result.get("plan", {})
    if plan:
        print(f"\nRecommended departure: {plan.get('recommended_departure')}")
        print(f"Alternative times: {plan.get('alternative_departures')}")
        print(f"Estimated travel time: {plan.get('estimated_travel_time_min')} min")

        warnings = plan.get("warnings", [])
        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f"  {w.get('message')}")


def example_whatif():
    """What-if场景模拟"""
    print("\n" + "=" * 50)
    print("Example 3: What-if Simulation")
    print("=" * 50)

    from agent.langgraph import TrafficAgentGraph

    agent = TrafficAgentGraph()

    result = agent.invoke(
        query="What if it rains heavily?",
        date="2026-07-15",
        scenario={
            "type": "weather_change",
            "parameters": {"weather": "heavy_rain"}
        }
    )

    simulation = result.get("simulation", {})
    if simulation:
        print(f"\nScenario: {simulation.get('scenario_type')}")
        print(f"Total delay: {simulation.get('total_delay_minutes')} minutes")
        print(f"Recommendation: {simulation.get('recommendation')}")

        alternatives = simulation.get("alternatives", [])
        if alternatives:
            print("\nAlternatives:")
            for alt in alternatives:
                print(f"  - {alt['name']}: {alt['description']}")


def example_streaming():
    """流式输出"""
    print("\n" + "=" * 50)
    print("Example 4: Streaming Output")
    print("=" * 50)

    from agent.langgraph import TrafficAgentGraph

    agent = TrafficAgentGraph()

    print("\nStreaming events:")
    for event in agent.stream(
        query="Get traffic forecast",
        date="2026-07-20",
        road="A8"
    ):
        # event是每个节点的输出
        for node_name, node_output in event.items():
            print(f"  [{node_name}] completed")


def example_llm_chat():
    """LLM对话（需要API key）"""
    print("\n" + "=" * 50)
    print("Example 5: LLM Chat (requires API key)")
    print("=" * 50)

    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  OPENAI_API_KEY not set. Skipping LLM example.")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        return

    try:
        from agent.langgraph.llm_agent import LLMTrafficAgent

        agent = LLMTrafficAgent(provider="openai")

        # 多轮对话
        print("\nUser: What's the traffic like on A8 this Friday?")
        response1 = agent.chat(
            "What's the traffic like on A8 this Friday?",
            date="2026-07-17",
            thread_id="demo"
        )
        print(f"AI: {response1}\n")

        print("User: What about Saturday?")
        response2 = agent.chat(
            "What about Saturday?",
            date="2026-07-18",
            thread_id="demo"  # 同一个thread_id保持上下文
        )
        print(f"AI: {response2}")

    except ImportError as e:
        print(f"\n⚠️  LLM dependencies not installed: {e}")
        print("Install with: pip install langchain-openai")


def example_graph_visualization():
    """工作流可视化"""
    print("\n" + "=" * 50)
    print("Example 6: Graph Visualization")
    print("=" * 50)

    from agent.langgraph import TrafficAgentGraph

    agent = TrafficAgentGraph()

    # 获取Mermaid格式
    mermaid = agent.get_graph_mermaid()
    print("\nMermaid diagram:")
    print(mermaid)

    # 保存为PNG（需要额外依赖）
    try:
        png_bytes = agent.get_graph_image()
        if png_bytes:
            with open("agent_graph.png", "wb") as f:
                f.write(png_bytes)
            print("\n✅ Graph saved to agent_graph.png")
    except Exception as e:
        print(f"\n⚠️  Could not save PNG: {e}")


async def example_async():
    """异步用法"""
    print("\n" + "=" * 50)
    print("Example 7: Async Usage")
    print("=" * 50)

    from agent.langgraph import TrafficAgentGraph

    agent = TrafficAgentGraph()

    # 并行执行多个查询
    import asyncio

    tasks = [
        agent.ainvoke(query="Traffic forecast", date="2026-07-15"),
        agent.ainvoke(query="Traffic forecast", date="2026-07-16"),
        agent.ainvoke(query="Traffic forecast", date="2026-07-17"),
    ]

    results = await asyncio.gather(*tasks)

    print("\nParallel results:")
    for i, result in enumerate(results):
        date = result.get("date")
        forecast = result.get("forecast", {})
        peak = forecast.get("peak_hour", "?")
        print(f"  {date}: Peak hour at {peak}:00")


def run_all_examples():
    """运行所有示例"""
    print("\n🚗 AlpineFlow AI - LangGraph Agent Examples\n")

    example_basic()
    example_trip_plan()
    example_whatif()
    example_streaming()
    example_llm_chat()
    example_graph_visualization()

    # 运行异步示例
    import asyncio
    asyncio.run(example_async())

    print("\n" + "=" * 50)
    print("All examples completed!")
    print("=" * 50)
    print("\nTo start the API server:")
    print("  uvicorn agent.langgraph.api:create_app --factory --reload")


if __name__ == "__main__":
    run_all_examples()
