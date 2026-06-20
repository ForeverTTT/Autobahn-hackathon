"""
LangGraph Agent API Service
FastAPI接口
"""
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from .graph import TrafficAgentGraph, quick_forecast, quick_plan


# ============ Request Models ============

if HAS_FASTAPI:
    class QueryRequest(BaseModel):
        """查询请求"""
        query: str = Field(..., description="User query in natural language")
        date: Optional[str] = Field(None, description="Date YYYY-MM-DD")
        road: str = Field(default="A8", description="Highway A8 or A93")
        user_type: str = Field(default="tourist", description="User type")
        thread_id: str = Field(default="default", description="Session ID for memory")

    class ForecastRequest(BaseModel):
        """预测请求"""
        date: str = Field(..., description="Date YYYY-MM-DD")
        road: str = Field(default="A8")
        site_id: str = Field(default="A8_Rosenheim")
        hours: List[int] = Field(default=list(range(6, 22)))

    class WhatIfRequest(BaseModel):
        """What-if请求"""
        date: str = Field(...)
        scenario_type: str = Field(..., description="weather_change, accident, traffic_increase")
        parameters: Dict[str, Any] = Field(default={})

    class ChatRequest(BaseModel):
        """LLM聊天请求"""
        message: str = Field(...)
        date: Optional[str] = Field(None)
        road: str = Field(default="A8")
        user_type: str = Field(default="tourist")
        thread_id: str = Field(default="default")
        provider: str = Field(default="openai", description="LLM provider: openai, anthropic")


def create_app() -> "FastAPI":
    """创建FastAPI应用"""
    if not HAS_FASTAPI:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

    app = FastAPI(
        title="AlpineFlow AI - LangGraph Agent API",
        description="Multi-Agent Traffic Intelligence System powered by LangGraph",
        version="2.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Agent实例
    agent = TrafficAgentGraph(enable_memory=True)

    @app.get("/")
    async def root():
        return {
            "service": "AlpineFlow AI - LangGraph Agent",
            "version": "2.0.0",
            "framework": "LangGraph",
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/api/query")
    async def query(request: QueryRequest):
        """
        通用查询接口

        根据自然语言自动路由到合适的处理流程
        """
        try:
            result = await agent.ainvoke(
                query=request.query,
                user_type=request.user_type,
                date=request.date,
                road=request.road,
                thread_id=request.thread_id,
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/forecast")
    async def forecast(request: ForecastRequest):
        """获取交通预测"""
        try:
            result = await agent.ainvoke(
                query=f"What's the traffic forecast for {request.road}?",
                date=request.date,
                road=request.road,
                site_id=request.site_id,
                hours=request.hours,
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/plan")
    async def plan(request: QueryRequest):
        """获取出行计划"""
        try:
            result = await agent.ainvoke(
                query=f"Plan my trip on {request.road}",
                date=request.date,
                road=request.road,
                user_type=request.user_type,
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/whatif")
    async def what_if(request: WhatIfRequest):
        """What-if场景模拟"""
        try:
            result = await agent.ainvoke(
                query=f"What if {request.scenario_type}?",
                date=request.date,
                scenario={
                    "type": request.scenario_type,
                    "parameters": request.parameters,
                }
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """
        LLM对话接口

        使用LLM进行自然语言交互
        """
        try:
            from .llm_agent import LLMTrafficAgent

            llm_agent = LLMTrafficAgent(provider=request.provider)
            response = await llm_agent.achat(
                message=request.message,
                date=request.date,
                road=request.road,
                user_type=request.user_type,
                thread_id=request.thread_id,
            )
            return {"response": response}
        except ImportError as e:
            raise HTTPException(
                status_code=501,
                detail=f"LLM provider not available: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/stream")
    async def stream_query(
        query: str,
        date: str = None,
        road: str = "A8",
        user_type: str = "tourist"
    ):
        """
        流式输出接口

        使用Server-Sent Events返回实时进度
        """
        async def event_generator():
            for event in agent.stream(
                query=query,
                date=date,
                road=road,
                user_type=user_type,
            ):
                # 格式化为SSE
                import json
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )

    @app.get("/api/graph")
    async def get_graph():
        """
        获取Agent工作流图

        返回Mermaid格式的图定义
        """
        mermaid = agent.get_graph_mermaid()
        return {"mermaid": mermaid}

    @app.get("/api/calendar/{year}/{month}")
    async def get_calendar(year: int, month: int, road: str = "A8"):
        """获取月度交通日历"""
        import calendar

        _, days_in_month = calendar.monthrange(year, month)
        calendar_data = []

        for day in range(1, days_in_month + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"

            # 快速预测
            result = quick_forecast(date_str, road)
            forecast = result.get("forecast", {})
            predictions = forecast.get("predictions", [])

            # 计算主要拥堵等级
            if predictions:
                levels = [p.get("congestion_level", "moderate") for p in predictions]
                from collections import Counter
                level = Counter(levels).most_common(1)[0][0]
            else:
                level = "unknown"

            calendar_data.append({
                "date": date_str,
                "day": day,
                "congestion_level": level,
            })

        return {
            "year": year,
            "month": month,
            "road": road,
            "days": calendar_data,
        }

    return app


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动服务器"""
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
