# 01：总体架构与职责边界

> 本文档定义系统的四层架构、各组件职责边界、扩展机制角色分配、18 个可改造角度、分阶段路线图、项目目录结构草案，以及高层优先级建议。
>
> 关联文档：[00_master_index](00_master_index.md) · [02_schema_and_tool_contracts](02_schema_and_tool_contracts.md) · [03_claude_code_adaptation](03_claude_code_adaptation.md) · [04_implementation_plan](04_implementation_plan.md)

---

## 1. 总体架构

### 1.1 核心设计原则

Claude Code 主体保持 **orchestrator** 角色，只做"理解意图 → 拆任务 → 调工具 → 组合结果 → 呈现给用户"。所有论文领域的重计算（PDF 解析、embedding、检索、分析）全部外推到独立 backend，通过 MCP / tool 协议桥接。

**为什么不应该把所有能力塞进主 agent：**

1. **token 经济性**：PDF 解析、chunk 切分、embedding 计算不需要 LLM 参与，塞进 agent 上下文是纯浪费
2. **运行时隔离**：Python 科学计算生态（PyMuPDF、GROBID、sentence-transformers）不应侵入 TS 主进程
3. **可替换性**：检索引擎可从本地 FAISS 升级到 Milvus/Qdrant，不应牵动 orchestrator
4. **并发模型不同**：ingest 是批量 I/O 密集型，analysis 是 LLM 密集型，orchestrator 是交互密集型——三者调度模型完全不同
5. **Claude Code 原始架构已为此设计**：MCP server、AgentTool、lifecycle hooks、plugin system 四套扩展机制足以支撑外部能力接入

### 1.2 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户交互层 (User Layer)                    │
│  CLI / VSCode Extension / Web UI (future)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              编排层 (Orchestrator Layer)                      │
│                                                              │
│  Claude Code 主体 (TS)                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Skills   │ │ Subagents│ │ Hooks    │ │ Task Router   │  │
│  │ (论文域) │ │ (专项)   │ │ (生命周期)│ │ (意图→工具)   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ MCP Client (连接下层所有 backend)                      │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ MCP Protocol (stdio / SSE / HTTP)
┌──────────────────────────▼──────────────────────────────────┐
│              能力层 (Capability Layer)                        │
│                                                              │
│  ┌────────────────┐ ┌─────────────────┐ ┌────────────────┐ │
│  │ Ingest Server  │ │ Retrieval Server│ │ Analysis Server│ │
│  │ (Python)       │ │ (Python)        │ │ (Python)       │ │
│  │                │ │                 │ │                │ │
│  │ - PDF 下载     │ │ - 向量检索      │ │ - 单篇分析     │ │
│  │ - PDF 解析     │ │ - 全文检索      │ │ - 多篇比较     │ │
│  │ - 结构化抽取   │ │ - 混合排序      │ │ - 证据抽取     │ │
│  │ - 去重/校验    │ │ - 引用图谱查询  │ │ - 综述生成     │ │
│  │ - embedding    │ │ - 过滤/聚合     │ │ - 图表分析     │ │
│  │ - 入库         │ │                 │ │                │ │
│  └───────┬────────┘ └───────┬─────────┘ └───────┬────────┘ │
└──────────┼──────────────────┼───────────────────┼───────────┘
           │                  │                   │
┌──────────▼──────────────────▼───────────────────▼───────────┐
│              存储层 (Storage Layer)                           │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ PDF 文件 │ │ SQLite/  │ │ 向量库   │ │ 文件缓存      │  │
│  │ 存储     │ │ Postgres │ │ FAISS/   │ │ (解析中间态)  │  │
│  │          │ │ (元数据) │ │ Qdrant   │ │               │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 各层职责明细

| 组件 | 职责 | 不应该做的事 |
|------|------|-------------|
| **Claude Code 主体** | 意图理解、任务拆分、工具调度、结果组装、用户交互、会话管理 | 不做 PDF 解析、不做 embedding 计算、不存论文数据 |
| **Ingest Backend** | PDF 下载/解析/结构化/去重/校验/embedding/入库、批量 pipeline 管理 | 不做意图理解、不直接面向用户 |
| **Retrieval Backend** | 向量检索、全文检索、混合排序、引用图谱查询、结果过滤与聚合 | 不做分析推理、不做 PDF 解析 |
| **Analysis Backend** | 单篇深度分析、多篇比较、证据链抽取、综述框架生成（可调用 LLM） | 不做检索、不做 ingest |

### 1.4 扩展机制角色分配

| 机制 | 在论文平台中的角色 | 理由 |
|------|-------------------|------|
| **Skills** | 面向用户的高层论文命令入口（`/search-papers`, `/ingest`, `/analyze`, `/review`, `/compare`） | skill = 带 prompt + 工具约束的命令，天然适合封装"论文搜索""综述生成"等用户意图 |
| **Subagents** | 长时间/多步论文任务的执行者（如：批量 ingest agent、深度分析 agent、综述写作 agent） | AgentTool 支持独立上下文 + 工具子集 + 后台运行，适合论文场景的重任务 |
| **Hooks** | 论文工作流的生命周期衔接（ingest 完成后触发索引更新、分析完成后自动摘要） | lifecycle hooks 已支持 PostToolUse / TaskCompleted 等事件 |
| **MCP Server** | Ingest/Retrieval/Analysis 三个 Python backend 的协议层——每个 backend 暴露为一个 MCP server | MCP 是 Claude Code 调用外部工具的标准协议，Python backend 实现 MCP server 即可被主体无缝调用 |
| **Plugin** | 将整个论文平台能力打包为一个可安装的 plugin（包含 skills + agents + hooks + MCP server configs） | plugin 是 Claude Code 的分发单元，论文能力应作为 plugin 安装，而非侵入主代码 |
| **Prompts/CLAUDE.md** | 注入论文领域知识、工作流规范、输出格式约束 | CLAUDE.md 是 project-level 指令注入点，适合放论文平台的行为规范 |

### 1.5 数据流示意

```
用户: "搜索 2024 年关于 LLM agent 的论文，下载前 20 篇，分析方法论趋势"

Orchestrator 拆解:
  ├─ Step 1: 调 Retrieval MCP → search_papers("LLM agent", year=2024, limit=20)
  │   └─ 返回: [{title, url, abstract, ...}, ...]
  ├─ Step 2: 调 Ingest MCP → batch_ingest(urls=[...])
  │   └─ 返回: {ingested: 18, failed: 2, paper_ids: [...]}
  ├─ Step 3: 调 Analysis MCP → trend_analysis(paper_ids=[...], focus="methodology")
  │   └─ 返回: {trends: [...], evidence: [...], summary: "..."}
  └─ Step 4: Orchestrator 组装最终回答，呈现给用户
```

---

## 2. 可改造角度总表

### 2.1 主 Prompt / System Prompt

| 维度 | 说明 |
|------|------|
| **为什么要改** | 当前 system prompt（`src/constants/prompts.ts`, 54KB）完全面向软件工程，需要注入论文领域的意图识别、任务拆分策略、输出格式规范 |
| **改到什么程度** | 追加论文领域 prompt section，不替换原有 SE 能力 |
| **推荐怎么改** | 利用 `systemPromptSection()` 机制新增 `paperWorkflowSection`，通过 plugin 注入而非修改 `prompts.ts` 源码；论文领域的 few-shot examples 放 CLAUDE.md |
| **不要过深** | 不要重写整个 system prompt，保持对 SE 场景的兼容 |

### 2.2 CLAUDE.md / MEMORY.md

| 维度 | 说明 |
|------|------|
| **为什么要改** | 需要注入论文工作流的行为规范（如何处理搜索请求、如何呈现论文元数据、引用格式约束等） |
| **改到什么程度** | 项目级 `.claude/CLAUDE.md` 写入论文平台规范；MEMORY.md 用于记忆用户的论文偏好（关注领域、常用数据库、引用风格） |
| **推荐怎么改** | CLAUDE.md 通过 plugin 的 instructions 注入；MEMORY.md 通过现有 auto-memory 机制自动积累 |
| **不要过深** | 不改 CLAUDE.md 的加载机制本身（`src/utils/claudemd.ts`） |

### 2.3 Skills

| 维度 | 说明 |
|------|------|
| **为什么要改** | 论文平台的核心用户入口。需要新增 5-8 个论文域 skill |
| **改到什么程度** | 新增 bundled skills 或 disk-loaded skills，每个 skill 定义 prompt + allowedTools + model 约束 |
| **推荐怎么改** | Phase 1 用 `.claude/skills/` 目录下的 markdown skill；Phase 2 迁移为 bundled skill 获得更好的打包体验 |
| **不要过深** | 不改 skill 加载机制本身（`src/skills/loadSkillsDir.ts`） |

### 2.4 Subagents

| 维度 | 说明 |
|------|------|
| **为什么要改** | 论文的批量 ingest、深度分析、综述生成都是长时间多步任务，需要专用 agent 类型 |
| **改到什么程度** | 在 `.claude/agents/` 下新增论文域 agent 定义（ingest-agent, analysis-agent, review-agent），限定各自可用工具集 |
| **推荐怎么改** | 利用 `loadAgentsDir.ts` 的现有机制，agent 定义为 markdown 文件 + frontmatter 元数据 |
| **不要过深** | 不改 AgentTool 核心执行逻辑（`src/tools/AgentTool/runAgent.ts`） |

### 2.5 Hooks

| 维度 | 说明 |
|------|------|
| **为什么要改** | 需要在 ingest/analysis 完成后触发后续动作（索引刷新、通知、自动摘要等） |
| **改到什么程度** | 在 settings.json 的 hooks 配置中注册论文域 hook（PostToolUse 拦截论文工具、TaskCompleted 触发后处理） |
| **推荐怎么改** | Phase 1 用 shell command hook 调 Python 脚本；Phase 2 升级为 agent hook 获得更灵活的后处理 |
| **不要过深** | 不改 hook 事件机制本身（`src/utils/hooks.ts`），只使用已有的 hook 事件类型 |

### 2.6 MCP Server / Tools

| 维度 | 说明 |
|------|------|
| **为什么要改** | 这是改造的**核心桥梁**。三个 Python backend 必须各自暴露为 MCP server，才能被 Claude Code 主体调用 |
| **改到什么程度** | 新建 3 个 MCP server（ingest / retrieval / analysis），每个暴露 5-10 个 tool |
| **推荐怎么改** | 用 `mcp` Python SDK 实现 server 端；在 `.claude/settings.json` 的 `mcpServers` 配置中注册；Phase 1 用 stdio transport，Phase 2 可升级为 SSE/HTTP |
| **不要过深** | 不改 MCP client 本身（`src/services/mcp/client.ts`），只做 server 端开发 + 配置注册 |

### 2.7 插件打包结构

| 维度 | 说明 |
|------|------|
| **为什么要改** | 论文平台能力应作为一个完整 plugin 分发，而非散落在各处 |
| **改到什么程度** | 打包为一个 plugin，包含：skills + agents + hooks config + MCP server configs + CLAUDE.md instructions |
| **推荐怎么改** | Phase 1 先以松散文件组织开发；Phase 2 整合为 plugin 格式（参考 `src/types/plugin.ts` 的 `LoadedPlugin` 结构） |
| **不要过深** | Phase 1 不需要上 marketplace，本地 plugin 即可 |

### 2.8 Settings / 权限策略

| 维度 | 说明 |
|------|------|
| **为什么要改** | 论文工具需要网络访问（下载 PDF）、文件系统写入（存储论文）、外部服务调用权限 |
| **改到什么程度** | 在 projectSettings 中预配置论文工具的权限白名单，避免每次弹窗确认 |
| **推荐怎么改** | `.claude/settings.json` 中 `permissions.allow` 添加论文相关 MCP tool 名称 |
| **不要过深** | 不改权限引擎本身（`src/utils/permissions/`） |

### 2.9 Runtime 调度逻辑

| 维度 | 说明 |
|------|------|
| **为什么要改** | 论文 ingest 是长时间批量任务，需要利用后台任务机制（LocalShellTask / LocalAgentTask） |
| **改到什么程度** | 让论文 skill 自动将批量 ingest 分派为后台 task，通过 TodoWrite 追踪进度 |
| **推荐怎么改** | 在 skill prompt 中指导 agent 使用 `run_in_background` + TaskOutput 轮询模式 |
| **不要过深** | 不改 task 调度引擎（`src/tasks/`），只利用现有机制 |

### 2.10 Task Routing

| 维度 | 说明 |
|------|------|
| **为什么要改** | orchestrator 需要根据用户意图将论文请求路由到正确的工具链（搜索→ingest→retrieval→analysis） |
| **改到什么程度** | 通过 system prompt 中的 routing 指令实现，不需要硬编码 router |
| **推荐怎么改** | 在 CLAUDE.md 和 skill prompt 中明确定义 routing 规则（"当用户要搜论文时调 retrieval MCP 的 search_papers"等） |
| **不要过深** | 不新增独立 router 模块，LLM 本身就是最好的 router |

### 2.11 输出协议

| 维度 | 说明 |
|------|------|
| **为什么要改** | 论文场景的输出格式与代码场景不同（需要表格、引用格式、BibTeX、结构化摘要等） |
| **改到什么程度** | 定义论文域的 output style（利用 `outputStylesPath` plugin 机制） |
| **推荐怎么改** | 在 plugin 中定义论文专用 output style；在 skill prompt 中约束输出格式 |
| **不要过深** | 不改输出渲染引擎 |

### 2.12 文件系统与缓存

| 维度 | 说明 |
|------|------|
| **为什么要改** | 需要规划论文 PDF 存储路径、解析缓存、embedding 缓存、检索索引的目录结构 |
| **改到什么程度** | 定义统一的数据目录规范（`.paper-workspace/` 或用户自定义路径） |
| **推荐怎么改** | Python backend 管理自己的数据目录；orchestrator 只通过 MCP tool 间接操作，不直接读写论文数据文件 |
| **不要过深** | orchestrator 不应该知道论文数据的内部存储结构 |

### 2.13 日志、状态追踪、失败恢复

| 维度 | 说明 |
|------|------|
| **为什么要改** | 批量 ingest 可能部分失败，需要断点续传；长时间分析需要进度追踪 |
| **改到什么程度** | Python backend 维护自己的任务状态和日志；MCP tool 暴露 status/retry 接口 |
| **推荐怎么改** | backend 用 SQLite 记录任务状态；MCP 暴露 `get_task_status`、`retry_failed` 等 tool |
| **不要过深** | 不在 orchestrator 层重建任务状态管理 |

### 2.14 数据 Schema

| 维度 | 说明 |
|------|------|
| **为什么要改** | 需要定义论文元数据、chunk、embedding、引用关系等数据模型 |
| **改到什么程度** | 本阶段只定义概念模型（Paper, Section, Chunk, Citation, Figure），不展开字段 |
| **推荐怎么改** | Python backend 内部定义并管理 schema；MCP tool 的输入输出用 JSON schema 约束 |
| **不要过深** | orchestrator 不需要知道存储层 schema 细节 |

### 2.15 检索层

| 维度 | 说明 |
|------|------|
| **为什么要改** | 检索是论文平台的核心能力——支持语义检索、关键词检索、混合检索、引用图谱检索 |
| **改到什么程度** | 作为独立 MCP server 实现，暴露 `search_papers`、`search_chunks`、`find_citations`、`find_similar` 等 tool |
| **推荐怎么改** | Phase 1 用 FAISS + SQLite FTS5；Phase 2 可换 Qdrant/Milvus + Elasticsearch |
| **不要过深** | 检索引擎选型不锁死，通过 MCP 接口抽象隔离 |

### 2.16 分析层

| 维度 | 说明 |
|------|------|
| **为什么要改** | 分析是最终价值输出——单篇摘要、多篇比较、方法论趋势、综述框架 |
| **改到什么程度** | 作为独立 MCP server 实现，内部可调用 LLM API 完成深度分析 |
| **推荐怎么改** | Phase 1 分析逻辑由 orchestrator 的 subagent 承担（利用 Claude 自身能力）；Phase 2 将可复用的分析 pipeline 下沉到 Python backend |
| **不要过深** | 不要在 Phase 1 就把所有分析都推到 backend——先利用 LLM 原生能力，再逐步结构化 |

### 2.17 多 Agent 协作层

| 维度 | 说明 |
|------|------|
| **为什么要改** | 复杂论文任务（如"生成综述"）需要多个 agent 协作：一个检索、一个分析、一个写作 |
| **改到什么程度** | Phase 1 用串行 subagent 调度；Phase 2 利用 coordinator mode 实现并行协作 |
| **推荐怎么改** | 利用已有的 `coordinatorMode` 和 `TeamCreateTool` 机制（推测：这些是 feature-gated 的高级能力） |
| **不要过深** | Phase 1 不需要多 agent 并行，串行 skill→subagent 链足够 |

### 2.18 后续 SDK / 服务化迁移预留

| 维度 | 说明 |
|------|------|
| **为什么要改** | 论文平台可能需要作为服务暴露（Web API、批量任务 API），而非仅 CLI 交互 |
| **改到什么程度** | 本阶段只预留接口边界，不实际实现 |
| **推荐怎么改** | Python backend 从一开始就设计为可独立部署的 HTTP 服务（FastAPI），MCP 只是其中一种接入方式 |
| **不要过深** | 不要在 Phase 1 就做 Web UI 或 REST API |

---

## 3. 分阶段路线图

### Phase 1：最小可用版本（MVP）

**目标**：端到端跑通"搜索 → 下载 → 解析 → 入库 → 检索 → 简单分析"的完整链路

**必做项**：
1. **Ingest MCP Server (Python)**
   - PDF 下载器（支持 arXiv、Semantic Scholar 直链）
   - PDF 解析器（PyMuPDF + 基本结构化抽取）
   - 元数据提取（title、authors、abstract、year）
   - chunk 切分（按段落/section）
   - embedding 计算（sentence-transformers 本地模型）
   - SQLite 元数据存储 + FAISS 向量索引
   - MCP stdio server 实现（5-8 个 tool）

2. **Retrieval MCP Server (Python)**
   - 语义检索（FAISS top-k）
   - 关键词检索（SQLite FTS5）
   - 混合排序（RRF 或简单加权）
   - MCP stdio server 实现（3-5 个 tool）

3. **Claude Code 侧**
   - 3-5 个论文 skill（`/search-papers`, `/ingest-paper`, `/query-papers`, `/analyze-paper`, `/paper-status`）
   - 1 个 ingest subagent 定义（后台批量 ingest）
   - `.claude/settings.json` 中注册 MCP server
   - `.claude/CLAUDE.md` 注入论文工作流基本规范

**可暂缓项**：
- 引用图谱
- 图表抽取与分析
- 多篇比较
- 综述生成
- Plugin 打包
- Web 学术搜索引擎集成（Google Scholar、PubMed 等）
- 精细的失败恢复

**风险点**：
- PDF 解析质量参差不齐（双栏、扫描件、数学公式），Phase 1 先覆盖 arXiv 等高质量 PDF
- MCP stdio server 启动/通信延迟，需要实测
- embedding 模型选型影响检索质量，Phase 1 用 `all-MiniLM-L6-v2` 快速验证

**验收标准**：
- 用户输入 `/search-papers "transformer attention mechanism"` → 返回论文列表
- 用户输入 `/ingest-paper <arxiv-url>` → PDF 下载、解析、入库成功
- 用户输入 `/query-papers "what are the main attention variants?"` → 从已入库论文中检索并返回相关 chunk + 来源
- 用户输入 `/analyze-paper <paper-id>` → 返回结构化摘要（方法、贡献、局限）
- 批量 ingest 10 篇论文，成功率 > 80%

---

### Phase 2：增强版本

**目标**：提升解析质量、检索精度、分析深度，支持多篇论文的复杂工作流

**必做项**：
1. **Ingest 增强**
   - 集成 GROBID 做高质量论文结构化解析（title、abstract、body sections、references、figures/tables）
   - 引用关系抽取与入库（citation graph）
   - 图表抽取（figure/table 截图 + caption 结构化）
   - 去重机制（DOI / title+author 模糊匹配）
   - 批量 ingest pipeline：断点续传、失败重试、进度上报
   - 支持更多来源（Semantic Scholar API、PubMed、本地 PDF 批量导入）

2. **Retrieval 增强**
   - 引用图谱查询（`find_cited_by`, `find_references`, `citation_path`）
   - 按 section type 过滤检索（只搜方法部分 / 只搜实验结果）
   - 时间范围、作者、venue 等元数据过滤
   - 检索结果去重与聚合

3. **Analysis Backend (Python MCP Server)**
   - 单篇深度分析 pipeline（方法论拆解、实验设计评估、局限性识别）
   - 多篇比较框架（方法对比矩阵、性能对比表）
   - 证据链抽取（claim → evidence → source chunk → paper）
   - 分析结果缓存

4. **Claude Code 侧增强**
   - 新增 skill：`/compare-papers`, `/extract-evidence`, `/citation-graph`
   - 新增 analysis subagent（深度分析专用 agent，限定工具集）
   - review subagent（综述初稿生成 agent）
   - lifecycle hooks：ingest 完成后自动触发索引刷新
   - 论文专用 output style（表格、BibTeX、结构化摘要格式）

**可暂缓项**：
- 综述全文生成（需要更成熟的多 agent 协作）
- Plugin marketplace 发布
- Web UI
- 多用户/团队协作

**风险点**：
- GROBID 部署复杂度（Java 服务），需要 Docker 化
- 引用图谱可能导致数据量急剧增长
- 多篇比较的 prompt 设计需要大量迭代

**验收标准**：
- GROBID 解析成功率 > 90%（以 arXiv CS 论文为基准）
- 引用图谱查询：给定一篇论文，能返回其引用和被引论文列表
- 多篇比较：给定 3-5 篇相关论文，生成方法对比矩阵
- 批量 ingest 50 篇论文，全流程端到端成功

---

### Phase 3：平台化版本

**目标**：成为可分发、可扩展、可服务化的学术论文工作流平台

**必做项**：
1. **Plugin 打包与分发**
   - 将论文能力整合为标准 Claude Code plugin
   - Plugin manifest、版本管理、自动更新
   - 支持通过 marketplace 安装

2. **服务化**
   - Python backend 支持 HTTP/SSE transport（不仅 stdio）
   - 可部署为独立服务（Docker Compose）
   - 支持远程 MCP server 连接

3. **综述生成 pipeline**
   - 多 agent 协作：检索 agent + 分析 agent + 写作 agent
   - 利用 coordinator mode 编排
   - 支持用户交互式修改综述大纲

4. **可扩展检索引擎**
   - 支持切换到 Qdrant / Milvus / Elasticsearch
   - 检索引擎适配层抽象

5. **高级分析能力**
   - 研究趋势时间线分析
   - 研究空白识别
   - 方法论演进图谱

**可暂缓项**：
- Web UI（可作为独立项目）
- 多用户权限管理
- 论文推荐系统
- 与 Zotero / Mendeley 集成

**风险点**：
- Plugin 打包格式可能随 Claude Code 版本演进而变化
- 多 agent 协作的稳定性和成本控制
- 服务化后的认证与安全

**验收标准**：
- Plugin 一键安装，`claude plugin install paper-workflow` 后即可使用所有论文能力
- Docker Compose 一键部署完整 backend
- 综述生成：给定主题，自动搜索 → ingest → 分析 → 生成 3000 字以上的结构化综述草稿
- 远程 MCP server 连接稳定，延迟 < 500ms

---

## 4. 项目目录结构草案

```
paper-workflow/
├── .claude/                          # Claude Code 项目配置根目录
│   ├── CLAUDE.md                     # 论文工作流行为规范
│   ├── settings.json                 # MCP server 注册、权限配置、hooks
│   ├── settings.local.json           # 本地覆盖（API keys 等，gitignored）
│   │
│   ├── skills/                       # 论文域 skills（markdown + frontmatter）
│   │   ├── search-papers.md
│   │   ├── ingest-paper.md
│   │   ├── query-papers.md
│   │   ├── analyze-paper.md
│   │   ├── compare-papers.md         # Phase 2
│   │   ├── extract-evidence.md       # Phase 2
│   │   ├── generate-review.md        # Phase 3
│   │   └── paper-status.md
│   │
│   ├── agents/                       # 论文域 subagent 定义
│   │   ├── ingest-agent.md           # 批量 ingest 专用 agent
│   │   ├── analysis-agent.md         # 深度分析专用 agent
│   │   └── review-agent.md           # 综述写作专用 agent (Phase 2+)
│   │
│   └── memory/                       # auto-memory（用户论文偏好）
│       └── MEMORY.md
│
├── backend/                          # Python 论文处理 backend
│   ├── pyproject.toml                # Python 项目配置（uv/poetry）
│   ├── README.md
│   │
│   ├── common/                       # 共享模块
│   │   ├── __init__.py
│   │   ├── config.py                 # 配置管理（路径、模型、数据库）
│   │   ├── models.py                 # 数据模型定义（Paper, Section, Chunk, Citation）
│   │   ├── db.py                     # 数据库连接管理
│   │   └── logging.py               # 统一日志
│   │
│   ├── ingest/                       # Ingest 模块
│   │   ├── __init__.py
│   │   ├── mcp_server.py             # MCP server 入口（stdio transport）
│   │   ├── downloader.py             # PDF 下载器（arXiv, Semantic Scholar, 通用 URL）
│   │   ├── parser.py                 # PDF 解析（PyMuPDF 基础解析）
│   │   ├── grobid_parser.py          # GROBID 高质量解析 (Phase 2)
│   │   ├── structurer.py             # 结构化抽取（metadata, sections, chunks）
│   │   ├── deduplicator.py           # 去重（DOI / 模糊匹配）
│   │   ├── embedder.py               # embedding 计算
│   │   ├── indexer.py                # 入库（SQLite + FAISS 写入）
│   │   └── pipeline.py              # ingest pipeline 编排（单篇 / 批量）
│   │
│   ├── retrieval/                    # Retrieval 模块
│   │   ├── __init__.py
│   │   ├── mcp_server.py             # MCP server 入口
│   │   ├── vector_search.py          # 向量检索（FAISS）
│   │   ├── text_search.py            # 全文检索（SQLite FTS5）
│   │   ├── hybrid_search.py          # 混合检索 + 排序
│   │   ├── citation_graph.py         # 引用图谱查询 (Phase 2)
│   │   └── filters.py               # 元数据过滤与聚合
│   │
│   ├── analysis/                     # Analysis 模块
│   │   ├── __init__.py
│   │   ├── mcp_server.py             # MCP server 入口 (Phase 2)
│   │   ├── single_paper.py           # 单篇分析 pipeline
│   │   ├── comparison.py             # 多篇比较 (Phase 2)
│   │   ├── evidence.py               # 证据链抽取 (Phase 2)
│   │   └── trend.py                  # 趋势分析 (Phase 3)
│   │
│   ├── search/                       # 外部论文搜索
│   │   ├── __init__.py
│   │   ├── arxiv.py                  # arXiv API
│   │   ├── semantic_scholar.py       # Semantic Scholar API
│   │   └── base.py                   # 搜索接口抽象
│   │
│   └── storage/                      # 存储层
│       ├── __init__.py
│       ├── sqlite_store.py           # SQLite 元数据 + FTS
│       ├── faiss_store.py            # FAISS 向量索引
│       └── file_store.py             # PDF / 缓存文件管理
│
├── data/                             # 运行时数据目录（gitignored）
│   ├── pdfs/                         # 原始 PDF 文件
│   ├── parsed/                       # 解析中间结果缓存
│   ├── db/                           # SQLite 数据库文件
│   ├── index/                        # FAISS 索引文件
│   └── logs/                         # 运行日志
│
├── configs/                          # 配置文件
│   ├── default.yaml                  # 默认配置（路径、模型、参数）
│   └── prompts/                      # 分析用 prompt 模板（Phase 2）
│       ├── single_paper_analysis.txt
│       ├── comparison_template.txt
│       └── review_outline.txt
│
├── tests/                            # 测试
│   ├── backend/
│   │   ├── test_ingest/
│   │   ├── test_retrieval/
│   │   ├── test_analysis/
│   │   └── test_search/
│   ├── integration/                  # 端到端集成测试
│   │   ├── test_mcp_ingest.py
│   │   ├── test_mcp_retrieval.py
│   │   └── test_e2e_workflow.py
│   └── fixtures/                     # 测试用 PDF 和数据
│       ├── sample_papers/
│       └── expected_outputs/
│
├── scripts/                          # 工具脚本
│   ├── setup.sh                      # 环境初始化（Python venv、依赖安装、FAISS 索引初始化）
│   ├── start_servers.sh              # 启动所有 MCP server
│   └── seed_test_data.py             # 灌入测试论文数据
│
├── docker/                           # Docker 化（Phase 2+）
│   ├── Dockerfile.backend
│   ├── Dockerfile.grobid             # GROBID 服务 (Phase 2)
│   └── docker-compose.yaml
│
└── plugin/                           # Plugin 打包（Phase 3）
    ├── manifest.json                 # Plugin manifest
    ├── skills/                       # 复制自 .claude/skills/
    ├── agents/                       # 复制自 .claude/agents/
    └── README.md
```

---

## 5. 高层优先级建议

### 最先该动（Week 1-2）

1. **Python Ingest MCP Server**——这是一切的基础。没有论文入库，后续能力全部空转。先实现最简的：下载 PDF → PyMuPDF 解析 → chunk 切分 → embedding → SQLite + FAISS 入库 → MCP stdio server 暴露 5 个 tool
2. **Python Retrieval MCP Server**——紧跟 ingest 之后。语义检索 + 关键词检索 + 混合排序，暴露 3 个 tool
3. **`.claude/settings.json` 注册 MCP server**——让 Claude Code 能发现并调用上述 backend
4. **2-3 个核心 skill**（`/ingest-paper`, `/query-papers`, `/search-papers`）——让用户有入口触发论文工作流

### 中期该动（Week 3-6）

5. **CLAUDE.md 论文域规范**——指导 orchestrator 如何拆解论文任务、如何呈现结果
6. **Ingest subagent**——后台批量 ingest 能力
7. **外部搜索集成**（arXiv API, Semantic Scholar API）
8. **Analysis skill + 利用 LLM 原生能力做单篇分析**（Phase 1 的分析不需要独立 backend，orchestrator 直接基于检索到的 chunk 做分析）
9. **基本测试覆盖**——MCP server 的 tool 级测试 + 端到端集成测试

### 最后再动（Week 7+）

10. GROBID 集成（高质量解析）
11. 引用图谱
12. 独立 Analysis MCP Server
13. 多篇比较、综述生成
14. Plugin 打包
15. Docker 化部署
16. 服务化（HTTP transport）

### 最危险的误区

1. **"大一统 agent" 陷阱**——把 PDF 解析、embedding、检索全塞进 Claude Code 的 system prompt 或 tool 里。这会导致 token 爆炸、TS/Python 生态割裂、不可维护。**一定坚持 orchestrator + external backend 架构**

2. **过早优化解析质量**——Phase 1 不要追求完美的 PDF 解析。PyMuPDF 能覆盖 70% 的 arXiv 论文。先跑通链路，再逐步引入 GROBID

3. **过早搞多 agent 协作**——串行 skill → subagent 链在 Phase 1 完全够用。过早引入 coordinator mode / team agent 会增加调试复杂度

4. **改 Claude Code 核心代码**——不要修改 `src/` 下的任何文件。所有改造应通过 skill / agent / hook / MCP / plugin / CLAUDE.md 这些**扩展机制**完成。改核心代码意味着无法跟随上游更新

5. **schema 过度设计**——Phase 1 用最简 schema（Paper + Chunk 两张表就够）。引用关系、图表、section 层级等留到 Phase 2 按需加字段

6. **忽视 MCP server 的启动和通信开销**——stdio transport 的 Python 进程启动有冷启动延迟（1-3s），需要在 Phase 1 就评估是否影响用户体验，必要时做进程常驻

7. **在 orchestrator 层管理论文数据状态**——论文的入库状态、解析进度、索引状态全部应由 Python backend 管理。orchestrator 只通过 MCP tool 查询状态，不自己维护状态
