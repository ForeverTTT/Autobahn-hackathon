# AlpineFlow 项目文档

本目录只维护与当前仓库实现直接对应的文档。最后核对日期：**2026-06-20**。

## 文档入口

| 文档 | 内容 |
|---|---|
| [SOLUTION.md](SOLUTION.md) | 系统架构、产品能力、当前完成度、API 与运行方式 |
| [DATA.md](DATA.md) | 原始数据、加工数据、外部数据、字段口径与质量结论 |
| [MODEL.md](MODEL.md) | CatBoost 交付模型、TFT 实验、评估指标、产物与限制 |

## 参考材料

| 文件 | 内容 |
|---|---|
| [material/2026-06_TUM_Hackathon_Autobahn_Long_presentation.pdf](material/2026-06_TUM_Hackathon_Autobahn_Long_presentation.pdf) | 8 页挑战背景与数据介绍 |
| [material/Autobahn_Challenge_Traffic_Calendar.pdf](material/Autobahn_Challenge_Traffic_Calendar.pdf) | 4 页任务书与用户场景 |
| [station_map.png](station_map.png) | A8 East / A93 South 测站示意图 |

## 当前实现状态

| 模块 | 状态 | 说明 |
|---|---|---|
| 数据整理 | 已完成 | 2023–2025 历史数据和 2023–2029 条件数据已合并 |
| CatBoost 预测 | 已完成 | 已生成 2026–2029、12 站、小时级预测 |
| TFT | 实验完成 | 有 notebook、训练日志和 checkpoint，未进入交付预测 |
| Agent 后端 | 已实现 | FastAPI、多 Agent、本地表驱动 GraphRAG |
| Web 前端 | Demo 可运行 | 日历、地图、角色选择已完成，目前使用前端规则生成 Demo 状态 |
| 前后端联调 | 待完成 | Web 尚未读取预测 CSV，也未调用 Agent API |
| 实时联网数据 | 待完成 | Agent 当前使用本地快照和少量内置样例，不是实时交通服务 |

详细边界见 [SOLUTION.md](SOLUTION.md)。
