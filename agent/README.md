# AlpineFlow AI Agent Layer

Agent layer for Autobahn traffic forecasting, explanation, trip planning, and local Graph RAG queries.

The current implementation is split into three clear parts:

1. `agent/api.py` - primary FastAPI service used by the app/demo.
2. `agent/graph_rag/` - local table-backed Graph RAG with a constrained Cypher-like query interface.
3. `agent/langgraph/` - optional LangGraph workflow and LLM tool layer.

The old generic `agent/rag/` vector RAG experiment has been removed. The active Graph RAG is local and table-backed.

---

## Current Architecture

```text
User / Frontend
    |
    v
agent/api.py
    |
    +-- OrchestratorAgent
    |      +-- ForecastAgent
    |      +-- ExplanationAgent
    |      +-- RetrievalAgent
    |      +-- SimulationAgent
    |      +-- GraphRAGAgent
    |
    +-- GraphRAG direct endpoints
           +-- processed/forecast_2026_2029.parquet
           +-- processed/site_meta.parquet
           +-- external/weather_*.parquet
           +-- external/construction_daily.parquet
```

`GraphRAG` is a virtual graph over local tables. It keeps small metadata/factor tables in memory and lazily loads forecast rows by date, so normal queries scan only a daily slice instead of materializing all forecast rows as graph nodes.

---

## Data Sources

| File | Used For |
|---|---|
| `processed/forecast_2026_2029.parquet` | Hourly A8/A93 forecasts for 2026-2029 |
| `processed/site_meta.parquet` | Site, road, direction, km, latitude, longitude |
| `external/weather_daily.parquet` | Historical daily weather factors |
| `external/weather_climatology.parquet` | Future weather baseline by day-of-year |
| `external/construction_daily.parquet` | Daily construction factors |

`PredictionDataLoader` defaults to the processed forecast parquet. The old `predictions/predictions.csv` is only a fallback sample file.

---

## Code Structure

```text
agent/
├── api.py                       # Primary FastAPI service
├── orchestrator.py              # Multi-agent coordinator
├── base.py                      # Agent base types
├── config.py                    # Configuration dataclasses
├── data_loader.py               # Forecast/external table loaders
├── congestion_score.py          # Congestion score calculation
├── travel_assistant.py          # Higher-level trip planning helper
├── example.py                   # Runnable examples for primary classes
│
├── agents/
│   ├── forecast_agent.py        # Reads processed forecasts, falls back to model/mock
│   ├── explanation_agent.py     # Rule-based explanation fallback
│   ├── retrieval_agent.py       # External event/construction retrieval fallback
│   ├── simulation_agent.py      # What-if simulation
│   └── graph_rag_agent.py       # Agent wrapper around GraphRAG
│
├── graph_rag/
│   ├── __init__.py
│   └── graph_rag.py             # Local table-backed GraphRAG + Cypher subset
│
└── langgraph/
    ├── graph.py                 # Optional LangGraph StateGraph
    ├── nodes.py                 # Workflow nodes, reusing GraphRAG for factors
    ├── tools.py                 # LLM tools, including query_traffic_graph
    ├── api.py                   # Optional LangGraph-only API
    ├── llm_agent.py             # Optional LLM chat agent
    └── example.py               # LangGraph examples
```

---

## Run The Primary API

```bash
pip install -r agent/requirements.txt
uvicorn agent.api:create_app --factory --reload --port 8000
```

Open `http://localhost:8000/docs` for Swagger.

Important endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /api/forecast` | Forecast by date/site/road/hour |
| `POST /api/plan` | Personalized trip plan |
| `POST /api/whatif` | What-if simulation |
| `POST /api/chat` | Natural language orchestration |
| `GET /api/calendar/{year}/{month}` | Monthly congestion calendar |
| `GET /api/graph/stats` | Local Graph RAG statistics |
| `POST /api/graph/query` | Cypher-like graph query |
| `GET /api/graph/factors` | Factors affecting a segment/date |
| `GET /api/graph/explain` | Forecast + factor explanation |

---

## Graph RAG Queries

Supported labels:

| Label | Meaning |
|---|---|
| `Site` | Measurement station metadata |
| `Road` | Road node such as A8/A93 |
| `Forecast` | Hourly forecast row, loaded lazily by date |
| `Factor` | Weather, construction, calendar/tourism factor |

Example Cypher-like query:

```cypher
MATCH (f:Forecast)
WHERE f.date = $date AND f.road = $road AND f.hour IN $hours
RETURN f.hour AS hour, f.kfz_h_p50 AS flow, f.v_kfz_p50 AS speed
ORDER BY f.hour
LIMIT 24
```

API request:

```bash
curl -X POST http://localhost:8000/api/graph/query \
  -H "Content-Type: application/json" \
  -d '{
    "cypher": "MATCH (f:Forecast) WHERE f.date = $date AND f.road = $road AND f.hour IN $hours RETURN f.hour AS hour, f.kfz_h_p50 AS flow LIMIT 3",
    "params": {"date": "2026-08-01", "road": "A8", "hours": [8, 9, 10]}
  }'
```

Performance rule: `Forecast` queries must include `date`. This lets the loader push filters into parquet and avoid scanning the full forecast table.

---

## Python Usage

```python
import asyncio
from agent import GraphRAG, OrchestratorAgent

async def main():
    graph = GraphRAG()
    await graph.initialize()
    rows = graph.query_cypher(
        """
        MATCH (f:Forecast)
        WHERE f.date = $date AND f.road = $road AND f.hour IN $hours
        RETURN f.hour AS hour, f.kfz_h_p50 AS flow
        LIMIT 3
        """,
        {"date": "2026-08-01", "road": "A8", "hours": [8, 9, 10]},
    )
    print(rows)

    orchestrator = OrchestratorAgent()
    await orchestrator.initialize()
    result = await orchestrator.process({
        "query": "forecast traffic on A8",
        "date": "2026-08-01",
        "road": "A8",
        "hours": [8, 9, 10],
    })
    print(result.data["graph_context"])

asyncio.run(main())
```

Run all examples:

```bash
python -m agent.example
```

---

## Optional LangGraph Layer

Use this when you want a StateGraph workflow or LLM tool-calling interface:

```python
from agent.langgraph import TrafficAgentGraph

agent = TrafficAgentGraph()
result = agent.invoke(
    query="Plan my trip from Munich to Salzburg",
    date="2026-08-01",
    road="A8",
    user_type="tourist",
)
```

Optional API:

```bash
uvicorn agent.langgraph.api:create_app --factory --reload --port 8001
```

The LangGraph tools include `query_traffic_graph`, which calls the same local Graph RAG implementation.
