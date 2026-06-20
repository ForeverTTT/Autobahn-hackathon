# AlpineFlow AI · Project Architecture and Product Plan

> **From Traffic Forecasting to Traffic Decision-Making**
> An end-to-end Autobahn traffic intelligence platform spanning data, models, agents, and user experience.

```mermaid
flowchart LR
    DATA[Multi-Source Data] --> PRED[Dual-Engine Forecasting<br/>CatBoost × TFT] --> REASON[Graph Reasoning<br/>Multi-Agent × Graph RAG] --> DECISION[Personalized Decisions]

    classDef s fill:#0ea5e9,stroke:#0369a1,color:#ffffff;
    class DATA,PRED,REASON,DECISION s;
```

### Our Goals

1. **Human Mobility Intelligence** — Understand why people travel and predict future demand.
2. **Traffic Digital Twin** — Simulate what will happen with a digital twin and test solutions in advance.
3. **Multi-Agent Optimization** — Let AI decide how each person should travel while optimizing the entire transportation ecosystem.



---

## 1. Four-Layer Architecture Overview

The entire system consists of four vertically integrated layers. Each layer provides capabilities to the one above it, ultimately turning them into decisions for different users in the frontend.

```mermaid
flowchart TB
    subgraph L1["① Data Processing Layer · Data Layer"]
        D1[Historical Traffic Flow Data]
        D2[Holiday Calendar]
        D3[Weather · Air Temperature · Road Temperature]
        D4[Roadworks · Special Events]
        D1 & D2 & D3 & D4 --> DE[Cleaning · Alignment · Feature Engineering<br/>Historical Profiles + Conditional Features]
    end

    subgraph L2["② Model Layer"]
        M1[CatBoost]
        M2[TFT<br/>Temporal Fusion Transformer]
        M1 & M2 --> MF[Ensemble Forecasting Engine<br/>Point Estimates + Intervals + Confidence]
    end

    subgraph L3["③ Agent Layer"]
        A1[Multi-Agent System<br/>Agent Collaboration]
        A2[Graph RAG<br/>Graph-Based Knowledge Modeling]
        A1 <--> A2
    end

    subgraph L4["④ Frontend Experience Layer"]
        F1[Traffic Calendar]
        F2[Traffic Details<br/>24h / Road Segment]
        F3[Explainable AI]
        F4[Personalized Assistant]
        F5[Autobahn Digital Twin]
    end

    L1 ==> L2 ==> L3 ==> L4

    classDef l1 fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
    classDef l2 fill:#dcfce7,stroke:#16a34a,color:#14532d;
    classDef l3 fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef l4 fill:#fae8ff,stroke:#a21caf,color:#701a75;
    class D1,D2,D3,D4,DE l1;
    class M1,M2,MF l2;
    class A1,A2 l3;
    class F1,F2,F3,F4,F5 l4;
```

---

## 2. Data Processing Layer

Transform raw data from multiple heterogeneous sources and time granularities into features that models can consume directly.

```mermaid
flowchart LR
    R1[Hourly Traffic Flow] --> P[Standardization<br/>Timestamp Alignment · Outlier Removal]
    R2[Air/Road Temperature<br/>Minute-Level] --> P
    R3[Holidays/Weather/Roadworks/Events<br/>Daily] --> P
    P --> H[Historical Profile Features<br/>Station × Hour × Weekday/Month/Day Type]
    P --> C[Conditional Features<br/>Holidays · Weather · Roadworks · Events]
    H & C --> X[(Feature Matrix<br/>No Lags · No Recursion · Leakage-Proof)]

    classDef raw fill:#f1f5f9,stroke:#64748b,color:#0f172a;
    classDef proc fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
    class R1,R2,R3 raw;
    class P,H,C,X proc;
```

- **Historical profiles**: Condense the primary traffic flows from 2023–2025 into typical profiles that serve as the forecasting baseline.
- **Conditional shifts**: Holidays, weather, roadworks, and events only adjust the baseline, making their effects explainable and attributable.

---

## 3. Model Layer (CatBoost × TFT Dual Engine)

We use a dual-engine ensemble of **gradient-boosted trees and a temporal Transformer**, combining strong structured-feature representation with long-range temporal dependencies.

```mermaid
flowchart TB
    X[(Feature Matrix)] --> CB & TFT

    subgraph CB_BOX["CatBoost Engine · Strong on Structured Data"]
        CB[Quantile Regression] --> CBO[P10 / P50 / P90<br/>Native Intervals + Peak Detection]
    end

    subgraph TFT_BOX["TFT Engine · Strong on Time Series"]
        TFT[Temporal Fusion Transformer] --> TFTO[Long-Range Dependencies<br/>Variable Importance · Interpretable Attention]
    end

    CBO & TFTO --> FUSE{Fusion Layer<br/>Weighted Ensemble / Stacking}
    FUSE --> OUT[Final Forecast<br/>Traffic Volume · Heavy Vehicles · Speed + Confidence]

    classDef cb fill:#dcfce7,stroke:#16a34a,color:#14532d;
    classDef tft fill:#cffafe,stroke:#0891b2,color:#155e75;
    classDef fuse fill:#fde68a,stroke:#d97706,color:#78350f;
    class CB,CBO cb;
    class TFT,TFTO tft;
    class FUSE,OUT fuse;
```

| Engine | Strengths | Outputs |
|---|---|---|
| **CatBoost** | Categorical features, sparse events, and quantile intervals | P10/P50/P90 forecasts + peak-hour detection |
| **TFT** | Long-range time series and multivariable attention | Temporal trends + variable-level interpretability |
| **Fusion Layer** | Combines complementary strengths | More stable point estimates + more reliable uncertainty |

> The dual-engine architecture not only improves accuracy but also provides both **intervals (CatBoost)** and **attention-based attribution (TFT)**, laying the foundation for explainable AI in the upper layers.

---

## 4. Agent Layer (Multi-Agent × Graph RAG)

The **multi-agent system** collaborates on decision-making, while a **graph database (Graph RAG)** models roads, events, forecasts, and users as a knowledge graph. This enables AI agents to learn Autobahn traffic patterns from real-world data.

```mermaid
flowchart TB
    Q[User Question / Decision Request] --> ORC[Orchestrator Agent<br/>Coordination and Routing]

    subgraph AGENTS["Multi-Agent System"]
        ORC --> PA[Forecasting Agent<br/>Calls the Model Layer]
        ORC --> EA[Explanation Agent<br/>Attributes Contributing Factors]
        ORC --> RA[Retrieval Agent<br/>Web Search · Roadworks/Events]
        ORC --> SA[Simulation Agent<br/>What-If Digital Twin]
    end

    PA & EA & RA & SA <--> GR[(Graph RAG<br/>Graph-Based Knowledge Modeling)]

    GR --> ANS[Structured Recommendations<br/>Plan Comparison · Travel Stress Index]
    ANS --> U[Frontend Experience Layer]

    classDef orc fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef ag fill:#fff7ed,stroke:#ea580c,color:#7c2d12;
    classDef gr fill:#ede9fe,stroke:#7c3aed,color:#4c1d95;
    class ORC orc;
    class PA,EA,RA,SA ag;
    class GR,ANS gr;
```

**Graph RAG knowledge modeling** — Represent the transportation world as a graph that supports reasoning:

```mermaid
flowchart LR
    ROAD((Autobahn/Road Segment<br/>A8 · A93)) -- passes through --> SEG((Bottleneck Segment<br/>Rosenheim))
    DAY((Date)) -- triggers --> EVENT((Holiday/Event))
    EVENT -- affects --> SEG
    WEATHER((Weather)) -- affects --> SEG
    SEG -- predicts --> FC((Congestion Level))
    USER((User Profile<br/>Traveler/Resident/Logistics)) -- cares about --> FC

    classDef node fill:#ede9fe,stroke:#7c3aed,color:#4c1d95;
    class ROAD,SEG,DAY,EVENT,WEATHER,FC,USER node;
```

- **Multi-Agent**: Coordination, forecasting, explanation, retrieval, and simulation agents each have distinct responsibilities and work together to generate well-reasoned plans.
- **Graph RAG**: Graph relationships capture why congestion occurs, where it occurs, and who is affected, making recommendations traceable and explainable.

---

## 5. Frontend Experience Layer · Tied to the Architecture

The frontend is not an isolated UI—**every product feature directly uses capabilities from a specific architectural layer**, creating a strong architecture-to-experience connection.

```mermaid
flowchart LR
    subgraph BACK["Backend Capabilities"]
        B1[Model Layer<br/>Forecasts + Intervals]
        B2[Agent Layer<br/>Explanations + Recommendations]
        B3[Agent Layer<br/>Simulation + Retrieval]
    end

    subgraph FRONT["Frontend Features"]
        P1[Traffic Calendar<br/>Which Days Are Congested]
        P2[Traffic Details<br/>When · Which Segment]
        P3[Explainable AI<br/>Why Congestion Occurs]
        P4[Personalized Assistant<br/>What Should I Do]
        P5[Autobahn Digital Twin<br/>What If...]
        P6[Smart Alert<br/>Proactive Notifications]
    end

    B1 --> P1 & P2
    B2 --> P3 & P4
    B3 --> P4 & P5
    B1 --> P6
    B2 --> P6

    classDef back fill:#dcfce7,stroke:#16a34a,color:#14532d;
    classDef front fill:#fae8ff,stroke:#a21caf,color:#701a75;
    class B1,B2,B3 back;
    class P1,P2,P3,P4,P5,P6 front;
```

**Five user groups, one architecture, different decisions**:

```mermaid
flowchart LR
    PLAT((AlpineFlow<br/>One Engine))
    PLAT --> T[👨‍👩‍👧 Travelers<br/>Best Departure Time]
    PLAT --> R[🏠 Residents<br/>Avoid Local Peaks]
    PLAT --> L[🚚 Logistics<br/>On Time · Fewer Delays]
    PLAT --> H[🏨 Tourism Industry<br/>Visitor Flow Forecast]
    PLAT --> G[🚦 Traffic Authorities<br/>Proactive Management]

    classDef plat fill:#a21caf,stroke:#701a75,color:#ffffff;
    classDef user fill:#fae8ff,stroke:#a21caf,color:#701a75;
    class PLAT plat;
    class T,R,L,H,G user;
```

### Product Features

**1. Traffic Calendar** — Answers: Which days will be congested?

- Select an Autobahn, direction, and date.
- Calendar colors show future congestion risk: 🟢 Smooth → 🔴 Critical.

**2. Traffic Detail** — Answers: When and where will congestion occur?

- **Daily Forecast**: Daily congestion level / estimated traffic volume / forecast confidence.
- **24h Traffic Prediction**: Hourly congestion / peak congestion time / recommended departure time.
- **Segment Map**: Displays congestion across different Autobahn segments and identifies bottleneck areas.

**3. Explainable AI** — Answers: Why will congestion occur?

- Analyzes contributing factors such as holidays, weekend travel, and historically similar dates.
- Makes forecasts trustworthy.

**4. Personalized Assistant (AI Agent)** — Answers: What should I do?

- Forecasting model + web search for roadworks and scheduled events.
- Generates recommendations, travel-plan comparisons, and a Travel Stress Index for different users:
  - 👨‍👩‍👧 Traveler → Recommend the best departure date and time.
  - 🏠 Resident → Avoid local traffic disruption.
  - 🚚 Logistics → Optimize transportation schedules and reduce delays.
  - 🏨 Tourism → Forecast visitor peaks and adjust operations.
  - 🚦 Authority → Prepare traffic-management measures and issue guidance in advance.
- Plans must be complete and include predicted travel time starting from departure in Munich.
- Users can save a plan and enable Traffic Impact Notifications. If weather or other factors later affect the trip, the system automatically generates a new plan.

**5. Autobahn Digital Twin (AI Traffic Digital Twin + What-If Simulation)** — Simulates future traffic conditions in real time.

- Users can ask questions directly, such as, “Can I still travel if it rains tomorrow?”
- AI provides a recommendation, reasons with a traffic simulation visualization, and alternative plans.

**6. Smart Alert** — Proactive notifications.

- Better travel windows / changes in delay risk / high-risk traffic days.

**7. Feedback**

- After a trip, users can review and rate that day’s traffic conditions, allowing the model to adjust dynamically based on confidence.

---

### Future Plan

**1. AI Traffic Digital Twin (Autobahn Digital Twin)** — Focused on technical innovation.

- Create a virtual A8 Autobahn: `Real A8 → AI Model → Virtual A8`.
- Simulate: `+20% tourists` / `+heavy rain` / `+accident`.
- Result: `Rosenheim bottleneck appears at 09:30. Queue length: 8 km`.
- Suitable for traffic authorities and hackathon pitches.

**2. Traffic Memory (Personal Traffic Memory)** — AI learns user habits.

- Previously: `You always drive Munich → Salzburg on Friday evening`.
- Future proactive alert: `Your usual trip next Friday will face a 45-minute delay. Leave 2 hours earlier?`

**3. Traffic Crowd Forecast (When Will Others Leave?)** — Users want to know when everyone else is leaving so they can avoid the crowd.

- Display: `People like you: 45% leave between 08:00–10:00 🔴 / 15% leave before 06:00 🟢`.
- Then recommend: `Beat the crowd: Leave at 05:45`.
- Community: Users submit their planned travel times. Aggregated results help others travel outside peak periods.

---
