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
    ChatSessionRegistry,
    handle_chat,
    handle_factors,
    handle_forecast,
    handle_options,
    handle_plan,
    handle_hourly_explanation,
    handle_batch_explanations,
)
from .calendar_data import calendar_traffic_loader


class ChatRequest(BaseModel):
    """对话请求。"""
    query: str
    user_type: Optional[str] = "traveler"
    session_id: Optional[str] = None


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
    chat_sessions = ChatSessionRegistry()

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
        """多轮自然语言查询，返回个性化出行计划或追问回答。"""
        try:
            return await handle_chat(
                chat_sessions,
                request.query,
                request.user_type,
                request.session_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/chat/{session_id}")
    async def clear_chat(session_id: str):
        """清除一个浏览器会话的聊天历史和计划上下文。"""
        cleared = await chat_sessions.clear(session_id)
        return {"success": True, "cleared": cleared, "session_id": session_id}

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

    @app.get("/api/calendar/daily")
    async def calendar_daily(year: int, month: int, road: str = "A8"):
        """Return daily average congestion scores for one calendar month."""
        try:
            return calendar_traffic_loader.query_month(year, month, road)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=str(e))

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

    @app.get("/api/explain/{date}/{hour}")
    async def explain_hour(
        date: str,
        hour: int,
        road: str = "A8",
        lang: str = "zh",
    ):
        """
        生成某小时交通状况的自然语言解释。

        Args:
            date: 日期 (YYYY-MM-DD)
            hour: 小时 (0-23)
            road: 道路 (A8, A93)
            lang: 语言 (zh=中文, en=English, de=Deutsch)

        Returns:
            {
                "date": "2026-07-25",
                "hour": 8,
                "road": "A8",
                "congestion_level": "moderate",
                "congestion_level_name": "中度拥堵",
                "congestion_score": 45,
                "flow": 2500,
                "speed": 95.5,
                "explanation": "8点交通中等拥堵，主要因为...",
                "factors": [...]
            }
        """
        try:
            return await handle_hourly_explanation(date, hour, road, lang)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/explain/{date}")
    async def explain_day(
        date: str,
        road: str = "A8",
        lang: str = "zh",
        hours: str = "6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21",
    ):
        """
        批量生成一天多个小时的交通解释。

        Args:
            date: 日期 (YYYY-MM-DD)
            road: 道路 (A8, A93)
            lang: 语言 (zh, en, de)
            hours: 小时列表，逗号分隔 (默认 6-21)

        Returns:
            {
                "date": "2026-07-25",
                "road": "A8",
                "explanations": [
                    {"hour": 6, "explanation": "...", ...},
                    {"hour": 7, "explanation": "...", ...},
                    ...
                ]
            }
        """
        try:
            hour_list = [int(h.strip()) for h in hours.split(",")]
            return await handle_batch_explanations(date, hour_list, road, lang)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
