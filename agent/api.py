"""
Agent API Service
FastAPI接口，暴露Agent能力给前端
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    # Provide mock classes for import to work
    class BaseModel:
        pass

from .orchestrator import OrchestratorAgent
from .graph_rag import GraphRAG
from .config import default_config


# ============ Request/Response Models ============

class ForecastRequest(BaseModel):
    """预测请求"""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    road: str = Field(default="A8", description="Highway (A8 or A93)")
    site_id: str = Field(default="A8_Rosenheim", description="Site identifier")
    direction: str = Field(default="east", description="Direction (east/west)")
    hours: List[int] = Field(default=list(range(6, 22)), description="Hours to predict")


class TripPlanRequest(BaseModel):
    """出行规划请求"""
    date: str = Field(..., description="Travel date")
    origin: str = Field(default="Munich", description="Origin city")
    destination: str = Field(default="Salzburg", description="Destination city")
    user_type: str = Field(default="tourist", description="User type")
    preferred_departure: Optional[str] = Field(None, description="Preferred departure time")


class WhatIfRequest(BaseModel):
    """What-if模拟请求"""
    date: str = Field(..., description="Date for simulation")
    site_id: str = Field(default="A8_Rosenheim", description="Site identifier")
    scenario_type: str = Field(..., description="Scenario type: weather_change, traffic_increase, accident, construction")
    parameters: Dict[str, Any] = Field(default={}, description="Scenario parameters")


class ChatRequest(BaseModel):
    """自然语言查询请求"""
    query: str = Field(..., description="Natural language query")
    date: Optional[str] = Field(None, description="Optional date context")
    user_type: str = Field(default="tourist", description="User type for personalization")


# ============ API Service ============

def create_app() -> "FastAPI":
    """创建FastAPI应用"""
    if not HAS_FASTAPI:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

    app = FastAPI(
        title="AlpineFlow AI Agent API",
        description="Multi-Agent Traffic Intelligence System",
        version="1.0.0",
    )

    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 初始化Agent系统
    orchestrator = OrchestratorAgent(default_config)
    graph_rag = GraphRAG()

    @app.on_event("startup")
    async def startup():
        """启动时初始化"""
        await orchestrator.initialize()
        await graph_rag.initialize()
        print("✅ Agent system initialized")

    @app.get("/")
    async def root():
        """根路径"""
        return {
            "service": "AlpineFlow AI Agent API",
            "version": "1.0.0",
            "status": "running",
        }

    @app.get("/health")
    async def health():
        """健康检查"""
        status = await orchestrator.health_check()
        return {
            "status": "healthy" if status["all_healthy"] else "degraded",
            "details": status,
        }

    @app.post("/api/forecast")
    async def forecast(request: ForecastRequest):
        """
        获取交通预测

        返回指定日期、路段的小时级交通预测
        """
        result = await orchestrator.process({
            "date": request.date,
            "road": request.road,
            "site_id": request.site_id,
            "direction": request.direction,
            "hours": request.hours,
        })

        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)

        return result.data

    @app.post("/api/plan")
    async def plan_trip(request: TripPlanRequest):
        """
        生成出行计划

        根据日期和用户类型，生成个性化出行建议
        """
        result = await orchestrator.process({
            "query": f"Plan trip from {request.origin} to {request.destination}",
            "date": request.date,
            "user_type": request.user_type,
        })

        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)

        return result.data

    @app.post("/api/whatif")
    async def what_if(request: WhatIfRequest):
        """
        What-if场景模拟

        模拟不同情景下的交通状况
        """
        result = await orchestrator.process({
            "date": request.date,
            "site_id": request.site_id,
            "scenario": {
                "type": request.scenario_type,
                "parameters": request.parameters,
            }
        })

        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)

        return result.data

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """
        自然语言交互

        支持自由形式的交通问题查询
        """
        result = await orchestrator.process({
            "query": request.query,
            "date": request.date or datetime.now().strftime("%Y-%m-%d"),
            "user_type": request.user_type,
        })

        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)

        return result.data

    @app.get("/api/calendar/{year}/{month}")
    async def get_calendar(
        year: int,
        month: int,
        road: str = Query(default="A8")
    ):
        """
        获取月度交通日历

        返回指定月份每天的拥堵预测
        """
        from datetime import date
        import calendar

        _, days_in_month = calendar.monthrange(year, month)
        calendar_data = []

        for day in range(1, days_in_month + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"

            # 简化预测（实际应调用完整预测）
            result = await orchestrator.forecast_agent.process({
                "date": date_str,
                "site_id": f"{road}_Rosenheim",
                "hours": [8, 9, 10, 16, 17, 18],  # 高峰时段
            })

            if result.success and result.data:
                summary = result.data.get("daily_summary", {})
                level = summary.get("main_congestion_level", "moderate")
            else:
                level = "unknown"

            calendar_data.append({
                "date": date_str,
                "day": day,
                "weekday": date(year, month, day).strftime("%A"),
                "congestion_level": level,
            })

        return {
            "year": year,
            "month": month,
            "road": road,
            "days": calendar_data,
        }

    @app.get("/api/graph/stats")
    async def graph_stats():
        """获取知识图谱统计"""
        return graph_rag.get_statistics()

    @app.get("/api/graph/factors")
    async def get_factors(
        segment_id: str = Query(...),
        date: str = Query(...)
    ):
        """查询影响因素"""
        return graph_rag.query_factors(segment_id, date)

    @app.get("/api/graph/explain")
    async def explain_congestion(
        segment_id: str = Query(...),
        date: str = Query(...),
        hour: int = Query(...)
    ):
        """解释拥堵原因"""
        return graph_rag.explain_congestion(segment_id, date, hour)

    return app


# ============ CLI Entry Point ============

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动API服务器"""
    if not HAS_FASTAPI:
        print("❌ FastAPI not installed. Run: pip install fastapi uvicorn")
        return

    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
