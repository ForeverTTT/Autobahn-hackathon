"""
FastAPI 服务入口
提供 RESTful API
"""
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .orchestrator import Orchestrator
from .models import UserType


# ============ 请求模型 ============

class ChatRequest(BaseModel):
    """对话请求"""
    query: str
    user_type: Optional[str] = "traveler"


class PlanRequest(BaseModel):
    """计划请求"""
    date: str
    destination: Optional[str] = "salzburg"
    road: Optional[str] = "A8"
    user_type: Optional[str] = "traveler"


class ForecastRequest(BaseModel):
    """预测请求"""
    date: str
    road: Optional[str] = "A8"
    site_id: Optional[str] = None
    hours: Optional[List[int]] = None


# ============ API 创建 ============

def create_app() -> FastAPI:
    """创建 FastAPI 应用"""

    app = FastAPI(
        title="AlpineFlow AI",
        description="德国高速公路交通预测与出行助手",
        version="1.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局 Orchestrator
    orchestrator = Orchestrator()

    # ============ 路由 ============

    @app.get("/")
    async def root():
        """健康检查"""
        return {
            "service": "AlpineFlow AI",
            "status": "running",
            "version": "1.0.0",
            "time": datetime.now().isoformat(),
        }

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """
        对话接口

        自然语言查询，返回个性化建议
        """
        try:
            user_type = UserType(request.user_type) if request.user_type else None
            result = await orchestrator.process(request.query, user_type)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/plan")
    async def plan(request: PlanRequest):
        """
        出行计划接口

        返回完整出行计划和方案对比
        """
        try:
            query = f"我想在 {request.date} 去 {request.destination or 'salzburg'}"
            user_type = UserType(request.user_type) if request.user_type else UserType.TRAVELER
            result = await orchestrator.process(query, user_type)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/forecast")
    async def forecast(request: ForecastRequest):
        """
        预测接口

        返回指定日期的交通预测
        """
        try:
            from .agents import ForecastAgent
            from .models import AgentRequest

            agent = ForecastAgent()
            req = AgentRequest(
                query="forecast",
                date=request.date,
                road=request.road or "A8",
                site_id=request.site_id,
                hours=request.hours or list(range(6, 22)),
            )
            result = await agent.process(req)

            if result.success:
                return result.data
            else:
                raise HTTPException(status_code=500, detail=result.message)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/factors/{date}")
    async def get_factors(date: str, road: str = "A8"):
        """
        获取外部因素

        返回指定日期的所有影响因素
        """
        try:
            from .agents import ContextAgent, SearchAgent
            from .models import AgentRequest

            req = AgentRequest(query="factors", date=date, road=road)

            # 并行获取
            import asyncio
            context_agent = ContextAgent()
            search_agent = SearchAgent()

            context_result, search_result = await asyncio.gather(
                context_agent.process(req),
                search_agent.process(req),
            )

            factors = []
            if context_result.success:
                factors.extend(context_result.data.get("factors", []))
            if search_result.success:
                factors.extend(search_result.data.get("factors", []))

            return {
                "date": date,
                "road": road,
                "factors": factors,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/options/{date}")
    async def get_options(
        date: str,
        destination: str = "salzburg",
        user_type: str = "traveler"
    ):
        """
        获取出行方案对比

        返回多个出发时间的方案对比
        """
        try:
            query = f"我想在 {date} 去 {destination}"
            ut = UserType(user_type)
            result = await orchestrator.process(query, ut)

            options = result.get("options", [])
            return {
                "date": date,
                "destination": destination,
                "user_type": user_type,
                "options": [
                    {
                        "departure": o.departure_time,
                        "arrival": o.arrival_time,
                        "duration_min": o.travel_time_min,
                        "delay_min": o.delay_min,
                        "stress_index": o.stress_index,
                        "recommendation": o.recommendation,
                    }
                    for o in options
                ],
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# 直接运行
if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
