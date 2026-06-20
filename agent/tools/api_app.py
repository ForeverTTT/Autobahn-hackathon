"""
FastAPI 服务入口工具
提供 RESTful API 的 create_app 工厂。
"""
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..orchestrator import Orchestrator
from .api_handlers import (
    handle_chat,
    handle_factors,
    handle_forecast,
    handle_options,
    handle_plan,
)


class ChatRequest(BaseModel):
    """对话请求。"""
    query: str
    user_type: Optional[str] = "traveler"


class PlanRequest(BaseModel):
    """计划请求。"""
    date: str
    destination: Optional[str] = "salzburg"
    road: Optional[str] = "A8"
    user_type: Optional[str] = "traveler"


class ForecastRequest(BaseModel):
    """预测请求。"""
    date: str
    road: Optional[str] = "A8"
    site_id: Optional[str] = None
    hours: Optional[List[int]] = None


def create_app() -> FastAPI:
    """创建 FastAPI 应用。"""
    app = FastAPI(
        title="AlpineFlow AI",
        description="德国高速公路交通预测与出行助手",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    orchestrator = Orchestrator()

    @app.get("/")
    async def root():
        """健康检查。"""
        return {
            "service": "AlpineFlow AI",
            "status": "running",
            "version": "1.0.0",
            "time": datetime.now().isoformat(),
        }

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """自然语言查询，返回个性化建议。"""
        try:
            return await handle_chat(orchestrator, request.query, request.user_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/plan")
    async def plan(request: PlanRequest):
        """返回完整出行计划和方案对比。"""
        try:
            return await handle_plan(
                orchestrator,
                request.date,
                request.destination,
                request.user_type,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/forecast")
    async def forecast(request: ForecastRequest):
        """返回指定日期的交通预测。"""
        try:
            return await handle_forecast(
                date=request.date,
                road=request.road,
                site_id=request.site_id,
                hours=request.hours,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/factors/{date}")
    async def get_factors(date: str, road: str = "A8"):
        """返回指定日期的所有影响因素。"""
        try:
            return await handle_factors(date, road)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/options/{date}")
    async def get_options(
        date: str,
        destination: str = "salzburg",
        user_type: str = "traveler",
    ):
        """返回多个出发时间的方案对比。"""
        try:
            return await handle_options(orchestrator, date, destination, user_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
