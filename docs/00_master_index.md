# 学术论文工作流平台：总索引

## 项目目标

将现有 Claude Code 项目从"偏代码编写的 agent"改造成面向学术论文工作流的平台。系统架构采用"Claude Code orchestrator（TS 主壳）+ 外部 Python 论文 backend"，通过 MCP 协议桥接。Claude Code 不做 PDF 解析/embedding/检索/存储，只做意图理解→任务拆分→工具调度→结果组装→用户呈现。

核心能力链路：搜索论文 → 下载/解析/入库 → 检索证据 → 单篇分析 → 多篇比较 → 综述生成。

## 文档总览

| 文档 | 职责 | 主要受众 |
|------|------|---------|
| **01_architecture_and_boundaries** | 总体架构、职责边界、扩展机制角色、可改造角度总表、分阶段路线图、高层优先级建议 | 架构师、Tech Lead |
| **02_schema_and_tool_contracts** | 全部 15 个 schema 定义、状态机与失败恢复、10 个 MCP tool 接口契约、错误码体系、可观测性/日志设计、数据契约建议 | Backend 工程师、MCP 实现者 |
| **03_claude_code_adaptation** | 主 prompt 增补规则、CLAUDE.md/MEMORY.md 分层、7 个 skills 设计、6 个 subagents 设计、7 个 hooks 设计、settings/权限/plugin 打包 | Claude Code 侧工程师、Prompt 工程师 |
| **04_implementation_plan** | 代码级目录结构最终版、33 个模块改造清单（含工时）、MVP 5 步实施、5 层测试方案、8 条实施风险、执行排期 | 工程师、PM |

## 推荐阅读顺序

1. **01_architecture_and_boundaries** — 先理解整体边界和分层
2. **02_schema_and_tool_contracts** — 再看数据模型和 MCP 接口
3. **03_claude_code_adaptation** — 再看 Claude Code 侧怎么接入
4. **04_implementation_plan** — 最后看落地排期

## 推荐实施顺序

1. 先稳定 `02` 中的 P0 schema（Paper, Chunk, PaperStatus, IngestJob, RetrievalHit, ToolError）
2. 再按 `04` 的模块改造清单逐批实现 Python backend
3. 然后按 `03` 配置 Claude Code 侧（settings → CLAUDE.md → skills → hooks）
4. 最后跑 `04` 的 MVP 验收场景

## 文档间依赖

```
01_architecture → 定义边界 → 02_schema 和 03_adaptation 必须遵守
02_schema → 定义契约 → 03_adaptation 的 skill/hook prompt 依赖 tool 接口签名
02_schema → 定义契约 → 04_implementation 的代码实现依赖 schema + tool 契约
03_adaptation → 定义壳层 → 04_implementation 的 Claude Code 侧文件清单依赖此设计
```

## 关键约束（跨文档生效）

1. **不改 Claude Code `src/` 任何文件** — 所有改造通过 skill/agent/hook/MCP/plugin/CLAUDE.md 扩展机制完成
2. **TS 主壳 + Python backend** — PDF 解析、embedding、检索、存储全部在 Python backend，orchestrator 只通过 MCP tool 间接操作
3. **backend 自管状态，orchestrator 只查不写** — 入库状态、解析进度、索引状态全由 Python backend 管理
4. **MCP tool 输出永远不含 embedding 向量** — 向量太大且 agent 无法直接使用
5. **所有 ID 用 UUID v4，所有时间用 ISO 8601 UTC**
6. **`data/` 目录禁止 agent 直接读写** — 必须通过 MCP tool

## 分阶段目标

- **Phase 1 (MVP)**：端到端跑通 搜索→下载→解析→入库→检索→单篇分析
- **Phase 2 (增强)**：GROBID 高质量解析、引用图谱、多篇比较、Analysis MCP Server、Plugin 打包
- **Phase 3 (平台化)**：综述生成、多 agent 协作、服务化（HTTP transport）、Docker 部署、Marketplace 发布

## 后续使用方式

- **设计约束**：修改任何模块前，先查 `01` 确认是否在其职责边界内
- **实现依据**：写 Python backend 代码时，以 `02` 的 schema 和 tool 契约为唯一真相源
- **壳层配置**：写 skill/hook/CLAUDE.md 时，以 `03` 为蓝本
- **施工进度**：按 `04` 的模块清单和排期追踪进度
- **变更管理**：改 schema 或 tool 接口时，更新 `02` 并重新跑契约测试
