# 05 Execution Backlog

## A. Backlog Overview

本 backlog 的目标是把 [04_implementation_plan.md](04_implementation_plan.md) 拆成后续执行模型可单轮施工的最小任务单，并把 [01_architecture_and_boundaries.md](01_architecture_and_boundaries.md)、[02_schema_and_tool_contracts.md](02_schema_and_tool_contracts.md)、[03_claude_code_adaptation.md](03_claude_code_adaptation.md) 中的架构、契约、壳层边界固化为执行约束。

使用方式：
- 一次只领取并执行一个 `TASK-XX`。
- 执行前先核对本任务的 `Inputs / Dependencies` 与 `Out of Scope`。
- 执行后按 `Acceptance Criteria` 自检，不满足则不要继续后续任务。
- 若发现 `04` 的描述与 `01-03` 有冲突，以 `01-03` 为准，并仅提出最小修正建议。

阅读与执行顺序：
- 先读 `01` 理解边界，再读 `02` 锁定 schema / tool 契约，再读 `03` 锁定 Claude Code 侧接入方式，最后按本 backlog 顺序执行。
- 本 backlog 只展开当前可执行的 MVP / Phase 1 任务，以及为其服务的必要测试与壳层接入。
- `04` 中明确“先不碰”或属于 Phase 2 / Phase 3 的内容，在本文件中只作为禁止抢跑项，不进入当前可执行任务序列。
- 为了减少会话数，本 backlog 同时提供两种视图：
- `TASK-XX` 视图：最小可执行、可审查、可回滚单位。
- `Task Group / Session Pack` 视图：把同类任务收拢，供需要减少会话数时参考。

总体依赖关系：
- Foundation → Storage → Search Slice → Fetch Slice → Ingest Slice → Retrieval Slice → Claude Shell → Analysis Skill → Hardening。
- `backend/common/`、状态机、存储层是后续 ingest / retrieval 的前置。
- `search_papers` 先于 `paper-search` skill。
- `fetch_pdf`、`ingest_paper`、`get_ingest_status` 先于 `paper-ingest` / `paper-status`。
- `retrieve_evidence` 先于 `paper-evidence` 与 `paper-analyze`。

约束依据文档：
- 导航：`00_master_index.md`
- 架构边界：`01_architecture_and_boundaries.md`
- Schema / 状态机 / Tool 契约：`02_schema_and_tool_contracts.md`
- Claude Code 壳层适配：`03_claude_code_adaptation.md`
- 拆分来源：`04_implementation_plan.md`

当前 backlog 明确不展开为执行任务的内容：
- 独立 Analysis MCP Server
- GROBID、引用图谱、图表抽取
- compare / synthesize tool 与相关 skills / agents
- Plugin 打包、Docker、HTTP transport、Marketplace
- `src/` 下任何 Claude Code 核心源码改动

## B. Execution Rules

- 以 `01-03.md` 作为设计约束与验收依据，`04.md` 只作为实施来源，不得反向覆盖 `01-03.md`。
- `00_master_index.md` 仅作导航，不作为实现真相源。
- 不得擅自扩展总体架构，不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者。
- 不得修改模块职责边界：ingest / retrieval / analysis 通过 backend 分层，Claude Code 只做编排与呈现。
- 不得擅自修改 schema、状态机、错误码命名规范、tool 输入输出字段、hook 触发逻辑。
- 一次只执行一个 task；未完成当前 task 的验收，不得提前实现其后继任务。
- 若某 task 需要新增字段或接口，必须先证明不违反 `02`，否则只输出最小修正建议，不得直接改契约。
- 不得引入 Phase 2 / Phase 3 能力来“顺手优化”当前 task。
- 不得修改 Claude Code `src/` 任何文件；Claude 侧改造只能落在 `.claude/` 扩展层。
- 不得让 agent 直接读写 `data/pdfs/`、`data/db/`、`data/index/`；论文数据操作必须通过 MCP tool。
- Phase 1 的单篇分析保持在 orchestrator skill 侧完成，不创建独立 Analysis MCP Server。
- `models.py` 应是 backend 数据模型的唯一真相源；tool 返回应从模型序列化产生，不手写漂移字段。
- 发生冲突时只允许做最小修正，不允许借机重构目录、替换技术路线、重写 prompt 体系。

## C. Task List

### C0. Task Groups

为避免 task 看起来过于分散，先按工作性质归类。后续执行时，可以先选组，再在组内按依赖顺序推进。

| Group | 名称 | 包含 Task | 目标 |
|------|------|-----------|------|
| `G1` | 项目骨架与共享基础 | `TASK-01` ~ `TASK-06` | 建立目录、工程壳、共享模型、错误协议、配置、数据库初始化、状态机 |
| `G2` | 存储与搜索底座 | `TASK-07` ~ `TASK-12` | 文件存储、SQLite/FAISS、arXiv 搜索、最小 search MCP + Claude 搜索入口 |
| `G3` | Ingest 核心链路 | `TASK-13` ~ `TASK-23` | 下载、解析、结构化、chunk、embedding、去重、索引、pipeline、ingest tools、批量 ingest、Claude ingest 入口 |
| `G4` | Retrieval 与证据工作流 | `TASK-24` ~ `TASK-27` | retrieval 核心、retrieve_evidence MCP、论文规则、evidence skill、单篇分析 skill |
| `G5` | 测试与收尾 | `TASK-28` | 契约、集成、质量、冒烟收尾 |

### C1. Recommended Session Packs

保留 `TASK-XX` 的独立验收边界，但为了减少会话数量，推荐按下面的 `Session Pack` 开会话。一个会话只做一个 `Session Pack`，会话内再按 task 顺序逐个完成并逐个自检。

| Session Pack | 包含 Task | 适用条件 | 说明 |
|-------------|-----------|---------|------|
| `SP-01` | `TASK-01` | 必做起步包 | 单独执行，专门校验执行模型是否会越界 |
| `SP-02` | `TASK-02` + `TASK-03` | 推荐合并 | 都属于共享契约层，且 `TASK-03` 紧跟 `TASK-02` |
| `SP-03` | `TASK-04` + `TASK-05` | 推荐合并 | 都是基础设施层，配置/日志/DB 初始化耦合较低但同属地基 |
| `SP-04` | `TASK-06` | 必须单独 | 状态机是高风险边界，不建议合并 |
| `SP-05` | `TASK-07` + `TASK-08` + `TASK-09` | 可合并 | 同属存储层，可在一个会话内完成文件、SQLite、FAISS 底座 |
| `SP-06` | `TASK-10` + `TASK-11` + `TASK-12` | 可合并 | 同属 search slice，从 provider 到 MCP 到 Claude 入口 |
| `SP-07` | `TASK-13` + `TASK-14` | 推荐合并 | 下载与解析骨架天然连续 |
| `SP-08` | `TASK-15` + `TASK-16` | 推荐合并 | 结构化与 chunk 切分同属文本加工阶段 |
| `SP-09` | `TASK-17` + `TASK-18` + `TASK-19` | 可合并 | embedding、去重、索引写入同属入库前后半段 |
| `SP-10` | `TASK-20` | 必须单独 | 单篇 ingest pipeline 是高风险核心链路 |
| `SP-11` | `TASK-21` + `TASK-22` + `TASK-23` | 可合并 | ingest tools、batch_ingest、Claude ingest 入口同属 ingest 对外暴露层 |
| `SP-12` | `TASK-24` + `TASK-25` | 推荐合并 | retrieval 核心与 MCP 暴露天然成组 |
| `SP-13` | `TASK-26` + `TASK-27` | 推荐合并 | 论文规则、evidence 呈现、单篇分析都属于 Claude 壳层收口 |
| `SP-14` | `TASK-28` | 单独收尾 | 测试与冒烟验证单独做，避免与实现掺在一起 |

### C2. Session Pack Guardrails

- `Session Pack` 只是为了减少会话数量，不改变 `TASK-XX` 的独立边界。
- 同一个会话包内，必须按 task 顺序执行，不能跳过前置 task。
- 同一个会话包内，每完成一个 task，都要先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个。
- 以下 task 仍建议单独会话，不应并入其它包：
- `TASK-01`
- `TASK-06`
- `TASK-20`
- `TASK-28`
- 如果一个 `Session Pack` 中途发现与 `01-03.md` 冲突，应立即停在当前 task，不得继续推进包内后续 task。

### C3. Individual Tasks

#### Task 01
- Task ID: `TASK-01`
- Title: 初始化目录骨架与基础工程文件
- Objective: 建立不违背 `01-03` 的最小目录与工程骨架，供后续任务逐步落位。
- Scope: 创建 `backend/`、`configs/`、`scripts/`、`tests/`、`.claude/` 基础目录与必要占位文件；补充 `.gitignore`；创建 `backend/pyproject.toml` 最小依赖声明。
- Out of Scope: 任何业务实现；任何 MCP tool 逻辑；任何 `.claude` 规则正文；任何 `src/` 改动。
- Inputs / Dependencies: `01` 第 1、3、4、5 节；`04` 第 1、2、6 节。
- Files to Modify: `.gitignore`、`backend/pyproject.toml`、`backend/__init__.py`、`backend/common/__init__.py`、`backend/ingest/__init__.py`、`backend/retrieval/__init__.py`、`backend/search/__init__.py`、`backend/storage/__init__.py`、`configs/default.yaml`、`scripts/setup.sh`、`.claude/` 目录骨架。
- Implementation Notes: 只搭骨架，不预填未来 Phase 2/3 的复杂实现；可创建空目录但不要创建误导性的功能文件。
- Acceptance Criteria: 基础目录可见；Python 工程可安装最小依赖；`.gitignore` 已覆盖 `data/`、数据库文件、`.claude/settings.local.json`；未引入任何超出 MVP 的实现。
- Risks / Guardrails: 不要趁机创建 `backend/analysis/mcp_server.py`；不要引入 Docker / plugin / Web UI 骨架。
- Suggested Next Task: `TASK-02`

#### Task 02
- Task ID: `TASK-02`
- Title: 定义 P0 共享数据模型
- Objective: 在 `backend/common/models.py` 中落地 Phase 1 必需的 Pydantic 模型。
- Scope: `Paper`、`Author`、`Section`、`Chunk`、`IngestJob`、`IngestError`、`IngestOptions`、`RetrievalHit`、`AnalysisTask`、`AnalysisResult`、`ToolError` 的 Phase 1 字段。
- Out of Scope: `Figure`、`Table`、`Reference`、`CompareResult`、`SynthesisResult` 等 Phase 2/3 模型；任何存储逻辑。
- Inputs / Dependencies: `02` 第 1 节、`02` 第 5.1 节；`01` 第 2.14、2.16 节。
- Files to Modify: `backend/common/models.py`
- Implementation Notes: 严格按 `02` 字段命名；所有 ID 用 UUID v4；时间字段保留 ISO 8601 UTC 约定；MCP 可见对象不得暴露 embedding 向量。
- Acceptance Criteria: 模型字段与 `02` 对齐；P0 模型可被后续模块导入；Phase 2/3 字段未被提前实现为必填项。
- Risks / Guardrails: 最容易犯错是自创字段、改字段名、把内部字段暴露给 orchestrator；禁止这样做。
- Suggested Next Task: `TASK-03`

#### Task 03
- Task ID: `TASK-03`
- Title: 建立统一错误码与 ToolError 工厂
- Objective: 固化 backend 统一错误返回格式与错误码常量。
- Scope: 定义错误码常量、`ToolError` 构造辅助、retryable 映射、通用系统错误。
- Out of Scope: 具体业务模块的重试实现；任何 server / tool handler。
- Inputs / Dependencies: `02` 第 3 节；`04` 第 4.3、5 节；依赖 `TASK-02`。
- Files to Modify: `backend/common/errors.py`
- Implementation Notes: 命名遵循 `{DOMAIN}_{SPECIFIC_ERROR}`；错误返回结构必须与 `02` 完全一致。
- Acceptance Criteria: 能统一构造 `ToolError`；可区分 retryable / non-retryable；未出现散落的手写 error dict 方案。
- Risks / Guardrails: 不要发明第二套异常协议；不要把人类可读错误和调试详情混成同一个字段。
- Suggested Next Task: `TASK-04`

#### Task 04
- Task ID: `TASK-04`
- Title: 建立配置与结构化日志基础设施
- Objective: 提供 backend 级配置读取与 JSON 日志能力。
- Scope: 路径配置、模型名配置、数据库路径、数据目录约定、structlog 或等价 JSON logger 初始化。
- Out of Scope: 具体模块日志埋点；健康检查脚本；任何业务行为。
- Inputs / Dependencies: `02` 第 4 节；`04` 第 5 节、第 6 节；依赖 `TASK-01`。
- Files to Modify: `backend/common/config.py`、`backend/common/logging_config.py`、`configs/default.yaml`
- Implementation Notes: 启动时只做最小初始化；不要在配置层绑定具体工具流程；日志格式要服务 ingest / retrieval 诊断。
- Acceptance Criteria: 配置可从默认文件和环境变量读取；日志初始化可被后续模块复用；不要求任何业务输出。
- Risks / Guardrails: 不要在此任务里偷塞数据库建表或模型加载；不要在 server 启动时预加载 embedding 模型。
- Suggested Next Task: `TASK-05`

#### Task 05
- Task ID: `TASK-05`
- Title: 实现 SQLite 初始化与最小 migration 框架
- Objective: 为 backend 提供幂等的数据库初始化入口。
- Scope: 建立 `papers`、`sections`、`chunks`、`ingest_jobs`、`parse_metrics`、`paper_traces` 等 Phase 1 必需表的 DDL 与 schema version 机制。
- Out of Scope: CRUD 查询实现；FTS5 检索逻辑；分析结果持久化扩展。
- Inputs / Dependencies: `02` 第 1 节、第 4.2 节、第 4.2(C) 节；`04` 第 2、5 节；依赖 `TASK-02`、`TASK-04`。
- Files to Modify: `backend/common/db.py`
- Implementation Notes: 保持表结构围绕 `02` 的模型最小落地；先保证幂等初始化，再考虑后续 migration。
- Acceptance Criteria: 初始化函数可重复运行；表结构覆盖当前 MVP 所需实体；未引入 Phase 2/3 专属表。
- Risks / Guardrails: 不要把 FTS、FAISS 元数据、分析缓存一次性塞满；不要在数据库层重写业务状态机。
- Suggested Next Task: `TASK-06`

#### Task 06
- Task ID: `TASK-06`
- Title: 实现 PaperStatus 状态机并补齐单元测试
- Objective: 把 ingest 状态转移规则固化为可验证的骨架。
- Scope: `PaperStatus` 枚举、合法转移校验、非法转移异常、`failed -> queued` 重试入口、状态机测试。
- Out of Scope: pipeline 编排；批量任务调度；具体错误恢复实现。
- Inputs / Dependencies: `02` 第 2 节；`04` 第 4.5、4.8 节；依赖 `TASK-02`、`TASK-03`。
- Files to Modify: `backend/ingest/state_machine.py`、`tests/unit/test_state_machine.py`
- Implementation Notes: 以 `02` 的状态机图和合法转移表为唯一依据；测试先覆盖所有合法与非法转移。
- Acceptance Criteria: 单测覆盖核心合法/非法路径；不存在跳过中间状态的“便捷通道”。
- Risks / Guardrails: 不要新增自定义状态；不要把 job 状态和 paper 状态混在一个枚举里。
- Suggested Next Task: `TASK-07`

#### Task 07
- Task ID: `TASK-07`
- Title: 实现 PDF 文件存储层
- Objective: 提供 PDF 文件路径规范、hash 命名与去重保存能力。
- Scope: 根据 SHA-256 存储 PDF、路径生成、存在性检查、返回相对路径。
- Out of Scope: 网络下载；解析；数据库写入。
- Inputs / Dependencies: `01` 第 2.12 节；`02` `Paper.pdf_path` / `pdf_hash` 字段；依赖 `TASK-04`。
- Files to Modify: `backend/storage/file_store.py`
- Implementation Notes: 存储层只管理文件，不理解 ingest 业务；路径相对于 `data/pdfs/`。
- Acceptance Criteria: 可根据字节流或本地文件保存并返回规范路径；重复内容不会重复落盘。
- Risks / Guardrails: 不要在文件存储层直接操作数据库；不要泄露绝对内部路径给 orchestrator 契约。
- Suggested Next Task: `TASK-08`

#### Task 08
- Task ID: `TASK-08`
- Title: 实现 SQLite 元数据存储层
- Objective: 为 `Paper`、`Section`、`Chunk`、`IngestJob` 提供最小 CRUD 与映射能力。
- Scope: 插入、更新、按 `paper_id` / `job_id` 查询、基础列表查询、模型与行记录互转。
- Out of Scope: FTS5 全文检索；向量检索；复杂聚合统计。
- Inputs / Dependencies: `02` P0 schema；依赖 `TASK-02`、`TASK-05`。
- Files to Modify: `backend/storage/sqlite_store.py`
- Implementation Notes: 接口优先服务 ingest / status 查询，不必提前做通用 ORM。
- Acceptance Criteria: 能持久化并读回 Paper / Section / Chunk / IngestJob；模型字段不丢失；后续工具可直接复用。
- Risks / Guardrails: 不要在 store 层塞入状态机或检索排序逻辑；不要为未来 Phase 2 过度抽象。
- Suggested Next Task: `TASK-09`

#### Task 09
- Task ID: `TASK-09`
- Title: 实现 FAISS 索引存储层
- Objective: 提供向量索引的创建、加载、追加与查询能力。
- Scope: create / add / search / save / load；索引文件路径管理；空索引处理。
- Out of Scope: embedding 生成；混合排序；检索过滤。
- Inputs / Dependencies: `01` 第 2.15 节；`02` `Chunk.embedding` 约束；依赖 `TASK-04`。
- Files to Modify: `backend/storage/faiss_store.py`
- Implementation Notes: 保持接口最小；不要让 orchestrator 感知向量细节。
- Acceptance Criteria: 索引可持久化并重新加载；空索引时有稳定返回；未通过 MCP 暴露 embedding。
- Risks / Guardrails: 不要把检索排序逻辑写到 store；不要锁死未来替换引擎的能力。
- Suggested Next Task: `TASK-10`

#### Task 10
- Task ID: `TASK-10`
- Title: 实现 arXiv 搜索 provider
- Objective: 提供 MVP 所需的外部论文搜索能力。
- Scope: `search_papers` 所需的 arXiv API 封装、结果字段映射、最小 provider 单测。
- Out of Scope: Semantic Scholar；多源聚合；自动 ingest。
- Inputs / Dependencies: `02` `search_papers` 契约；`04` Step 1；依赖 `TASK-02`。
- Files to Modify: `backend/search/base.py`、`backend/search/arxiv_provider.py`、`tests/unit/test_arxiv_provider.py`
- Implementation Notes: 结果映射字段名必须对齐 `SearchResult` 契约；`already_ingested` 可以后续由 tool handler 补充。
- Acceptance Criteria: provider 能返回标题、作者、年份、摘要、URL、pdf_url 等最小字段；单测可 mock 外部响应。
- Risks / Guardrails: 不要提前实现 `s2_provider.py`；不要在 provider 中直接访问 MCP 层。
- Suggested Next Task: `TASK-11`

#### Task 11
- Task ID: `TASK-11`
- Title: 建立 ingest MCP server 最小骨架并开放 `search_papers`
- Objective: 先打通“搜索论文”这一条最短可验证链路。
- Scope: `backend/ingest/mcp_server.py` 最小 server 入口、`backend/ingest/tools.py` 的 `search_papers` handler、server 启动与 tool 注册。
- Out of Scope: `fetch_pdf`、`ingest_paper`、`batch_ingest`、`get_ingest_status`。
- Inputs / Dependencies: `02` `search_papers` tool 契约；依赖 `TASK-08`、`TASK-10`。
- Files to Modify: `backend/ingest/mcp_server.py`、`backend/ingest/tools.py`
- Implementation Notes: handler 只负责参数校验、provider 调用、库内是否已存在标记；不要塞入下载逻辑。
- Acceptance Criteria: MCP server 可列出 `search_papers`；工具输出字段与 `02` 对齐；无契约外字段。
- Risks / Guardrails: 不要把 ingest server 变成“大一统 server”；不要同时实现其它 tool。
- Suggested Next Task: `TASK-12`

#### Task 12
- Task ID: `TASK-12`
- Title: 接入 Claude Code 的搜索入口
- Objective: 让 Claude Code 可以通过 skill 调用 `search_papers`。
- Scope: 最小 `.claude/settings.json`、权限白名单中的 `search_papers`、`paper-search.md` skill。
- Out of Scope: 其它 skill、hooks、CLAUDE.md 主规则、retrieval server 注册。
- Inputs / Dependencies: `03` 第 1 节、第 3.1 节、第 6.1 节；依赖 `TASK-11`。
- Files to Modify: `.claude/settings.json`、`.claude/skills/paper-search.md`
- Implementation Notes: 只接入搜索能力；skill prompt 遵循 `03` 的职责边界，不负责 ingest 或分析。
- Acceptance Criteria: Claude 侧能发现 `paper-search` skill；settings 只注册已存在的 MCP server/tool；无多余权限。
- Risks / Guardrails: 不要在此任务里引入批量 ingest、hooks 或全套规则文件。
- Suggested Next Task: `TASK-13`

#### Task 13
- Task ID: `TASK-13`
- Title: 实现 PDF 下载器与 `fetch_pdf` tool
- Objective: 打通“给定 URL 下载 PDF 到本地”的独立能力。
- Scope: 下载器、重试、Content-Type 校验、大小限制、hash 校验、`fetch_pdf` handler 与 tool 注册、下载器单测。
- Out of Scope: 解析入库；状态机编排；批量下载。
- Inputs / Dependencies: `02` `fetch_pdf` 契约；`02` 失败恢复表；依赖 `TASK-03`、`TASK-07`、`TASK-11`。
- Files to Modify: `backend/ingest/downloader.py`、`backend/ingest/tools.py`、`backend/ingest/mcp_server.py`、`tests/unit/test_downloader.py`
- Implementation Notes: 下载器返回的本地路径应来自 `file_store`；tool 错误必须走统一 `ToolError`。
- Acceptance Criteria: `fetch_pdf` 能返回 `{success, pdf_path, file_size_bytes, pdf_hash, already_exists}`；重复下载命中去重；单测覆盖超时/非 PDF/过大文件。
- Risks / Guardrails: 不要把下载完成自动升级为 ingest；不要把 URL 来源逻辑写死为 arXiv 专用。
- Suggested Next Task: `TASK-14`

#### Task 14
- Task ID: `TASK-14`
- Title: 实现 PDF 解析器骨架
- Objective: 从本地 PDF 产出 Phase 1 所需的原始解析结果。
- Scope: PyMuPDF 文本提取、页码映射、页数统计、原始文本输出、解析器单测。
- Out of Scope: 元数据抽取；section 识别；OCR；GROBID。
- Inputs / Dependencies: `02` `ParseResult` 基础字段；`04` Step 3；依赖 `TASK-13`。
- Files to Modify: `backend/ingest/parser.py`、`tests/unit/test_parser.py`
- Implementation Notes: 解析器只负责“提取”，不负责结构化理解；保留 parser_used、page_count、raw_text 等信息。
- Acceptance Criteria: 能对 fixture PDF 输出非空文本和正确页数；单测覆盖基本完整性。
- Risks / Guardrails: 不要在此任务实现 GROBID fallback；不要把 section/type 分类提前混入 parser。
- Suggested Next Task: `TASK-15`

#### Task 15
- Task ID: `TASK-15`
- Title: 实现元数据抽取与章节结构化
- Objective: 把解析结果转成 `Paper` 元数据与 `Section[]`。
- Scope: 标题、作者、摘要、年份基础抽取；section 切分；`SectionType` 基础分类；解析质量基准测试骨架。
- Out of Scope: figure / table / references；高级元数据回填；引用图谱。
- Inputs / Dependencies: `02` `Section` 与 `Paper` 字段；依赖 `TASK-02`、`TASK-14`。
- Files to Modify: `backend/ingest/structurer.py`、`tests/quality/test_parse_quality.py`
- Implementation Notes: Phase 1 以“够用”优先；分类枚举只允许 `02` 里的集合。
- Acceptance Criteria: 对基准 PDF 能抽出非空 title、至少若干 section，并识别出关键 section type 子集。
- Risks / Guardrails: 不要为了提高精度引入外部 API 回填或 GROBID；不要扩展 `SectionType` 枚举。
- Suggested Next Task: `TASK-16`

#### Task 16
- Task ID: `TASK-16`
- Title: 实现 chunk 切分器
- Objective: 生成满足检索需要的最小 chunk 单元。
- Scope: 512 token / 128 overlap 切分、顺序索引、section 上下文冗余字段、chunker 单测。
- Out of Scope: embedding；向量写入；重排。
- Inputs / Dependencies: `02` `Chunk` 字段与 5.2 节建议；依赖 `TASK-15`。
- Files to Modify: `backend/ingest/chunker.py`、`tests/unit/test_chunker.py`
- Implementation Notes: Phase 1 固定切分参数，不做可配置化扩展。
- Acceptance Criteria: chunk 数量合理、overlap 正确、chunk 顺序稳定、单测覆盖边界情况。
- Risks / Guardrails: 不要擅自调整 chunk 大小或 overlap；不要把 embedding 维度信息塞进切分器。
- Suggested Next Task: `TASK-17`

#### Task 17
- Task ID: `TASK-17`
- Title: 实现 embedding 生成器
- Objective: 为 chunk 提供后续向量检索所需 embedding。
- Scope: sentence-transformers 延迟加载、batch embedding、空文本保护、基础异常映射。
- Out of Scope: 向量索引写入；query embedding；模型切换策略。
- Inputs / Dependencies: `01` Phase 1 风险点；`02` `Chunk.embedding` 约束；依赖 `TASK-04`、`TASK-16`。
- Files to Modify: `backend/ingest/embedder.py`
- Implementation Notes: 启动时不预加载模型；模型名来自配置层。
- Acceptance Criteria: 输入 chunk 文本后可返回稳定维度向量；空文本路径处理明确；未把向量暴露到 MCP 输出。
- Risks / Guardrails: 不要在此任务实现 reindex 或多模型切换；不要把模型下载放到 server 冷启动路径。
- Suggested Next Task: `TASK-18`

#### Task 18
- Task ID: `TASK-18`
- Title: 实现去重器
- Objective: 在入库前处理 DOI / 标题级重复冲突。
- Scope: DOI 精确匹配、标题近似匹配、已存在论文判定、dedup 单测。
- Out of Scope: 批量去重策略优化；跨来源合并；复杂作者标准化。
- Inputs / Dependencies: `02` `Paper`、`PaperSource` 与错误码；依赖 `TASK-08`。
- Files to Modify: `backend/ingest/deduplicator.py`、`tests/unit/test_deduplicator.py`
- Implementation Notes: Phase 1 优先实现稳定的 `skip_if_exists` 路径，不做复杂实体合并。
- Acceptance Criteria: 能识别 DOI 重复与高相似标题重复；重复时返回可供 tool 使用的判定结果。
- Risks / Guardrails: 不要在去重器里直接修改 paper 状态；不要为了模糊匹配引入沉重依赖。
- Suggested Next Task: `TASK-19`

#### Task 19
- Task ID: `TASK-19`
- Title: 实现索引写入器
- Objective: 把结构化论文与向量结果统一写入 SQLite 与 FAISS。
- Scope: `Paper` / `Section` / `Chunk` 元数据写库、向量写索引、计数回写、最小一致性处理。
- Out of Scope: pipeline 调度；状态轮询；reindex。
- Inputs / Dependencies: `TASK-08`、`TASK-09`、`TASK-17`。
- Files to Modify: `backend/ingest/indexer.py`
- Implementation Notes: indexer 负责“落盘”，不负责决定何时落盘；计数更新需对齐 `Paper.chunk_count` / `section_count`。
- Acceptance Criteria: 一次调用可完成 paper/section/chunk 与向量写入；索引与数据库引用关系一致。
- Risks / Guardrails: 不要把下载/解析逻辑回灌进 indexer；不要直接对外暴露内部向量详情。
- Suggested Next Task: `TASK-20`

#### Task 20
- Task ID: `TASK-20`
- Title: 实现单篇 ingest pipeline
- Objective: 把下载、解析、结构化、切分、embedding、入库串成单篇状态机流程。
- Scope: 单篇论文状态流转、阶段日志、trace 写入、失败映射、force reparse / skip existing 基础支持。
- Out of Scope: `batch_ingest`；后台调度器；多 worker 并发优化。
- Inputs / Dependencies: `02` 状态机与失败恢复；依赖 `TASK-06`、`TASK-13`、`TASK-14`、`TASK-15`、`TASK-16`、`TASK-17`、`TASK-18`、`TASK-19`。
- Files to Modify: `backend/ingest/pipeline.py`
- Implementation Notes: pipeline 只实现 Phase 1 必需流；每个阶段进出都写结构化日志；状态转移必须走 state_machine。
- Acceptance Criteria: 给定单篇 URL 或本地 PDF 可完成 `queued -> ready` 全链路；失败时带 `error_code` / `stage`。
- Risks / Guardrails: 不要把 batch 逻辑混进来；不要绕过状态机直接写 `ready`。
- Suggested Next Task: `TASK-21`

#### Task 21
- Task ID: `TASK-21`
- Title: 开放 `ingest_paper` 与 `get_ingest_status`
- Objective: 让 ingest pipeline 通过 MCP tool 可被 orchestrator 查询和调用。
- Scope: `ingest_paper` handler、`get_ingest_status` handler、tool 注册、最小契约测试与 ingest 集成测试起点。
- Out of Scope: `batch_ingest`；Claude 侧 skill；分析能力。
- Inputs / Dependencies: `02` `ingest_paper` / `get_ingest_status` 契约；依赖 `TASK-20`。
- Files to Modify: `backend/ingest/tools.py`、`backend/ingest/mcp_server.py`、`tests/contract/test_ingest_mcp_contract.py`、`tests/integration/test_ingest_e2e.py`
- Implementation Notes: 返回值来自模型序列化；单篇 ingest 可先走同步编排 + 异步语义输出，不要求复杂队列系统。
- Acceptance Criteria: `ingest_paper` 返回 `job_id` 与 `queued/skipped`；`get_ingest_status` 可按 `job_id` / `paper_id` 查询；至少有基础契约测试。
- Risks / Guardrails: 不要把 `analyze_paper` 偷塞进 ingest server；不要在 contract test 里放宽字段要求。
- Suggested Next Task: `TASK-22`

#### Task 22
- Task ID: `TASK-22`
- Title: 实现 `batch_ingest` 后端入口
- Objective: 在不引入复杂调度系统的前提下提供批量 ingest 能力。
- Scope: `batch_ingest` handler、批量输入去重、跳过详情、job 级进度更新。
- Out of Scope: source-hunter；多 agent 协调；自动重试策略细化；用户确认逻辑。
- Inputs / Dependencies: `02` `batch_ingest` 契约；依赖 `TASK-21`。
- Files to Modify: `backend/ingest/tools.py`、`backend/ingest/mcp_server.py`
- Implementation Notes: 先提供稳定的批量 job 表示；用户确认放到 Claude 侧 hook。
- Acceptance Criteria: `batch_ingest` 能返回 `job_id`、`queued_count`、`skipped_count`、`skipped_urls`；进度可通过 `get_ingest_status` 观察。
- Risks / Guardrails: 不要在这一步实现自定义 queue 框架；不要绕过单篇 pipeline 重写一套批处理内核。
- Suggested Next Task: `TASK-23`

#### Task 23
- Task ID: `TASK-23`
- Title: 接入 Claude Code 的 ingest 入口与批量操作 agent
- Objective: 让用户能够通过 Claude 侧入口执行单篇/批量 ingest 并查看状态。
- Scope: 扩展 `.claude/settings.json` 注册 ingest 相关权限与 hooks；新增 `paper-ingest.md`、`paper-status.md`、`ingest-operator.md`；加入 `post-ingest-verify` 与 `pre-batch-confirm`。
- Out of Scope: `source-hunter`、`evidence-miner`、`paper-analyst`；独立分析 backend；compare / synthesize。
- Inputs / Dependencies: `03` 第 3.2、3.7、4.2、5.2(A)(D)、6.1 节；依赖 `TASK-21`、`TASK-22`。
- Files to Modify: `.claude/settings.json`、`.claude/skills/paper-ingest.md`、`.claude/skills/paper-status.md`、`.claude/agents/ingest-operator.md`
- Implementation Notes: 1-3 篇由 skill 直接处理，4+ 篇再委托 subagent；批量确认交给 hook，不交给后端。
- Acceptance Criteria: settings 只引用现有 tool；skill / agent allowedTools 对齐 `03`；批量 ingest 前存在确认钩子。
- Risks / Guardrails: 不要让 subagent 再调用 subagent；不要给 agent “全工具集”；不要提前接 compare / synthesize。
- Suggested Next Task: `TASK-24`

#### Task 24
- Task ID: `TASK-24`
- Title: 实现 retrieval 核心检索模块
- Objective: 为证据检索提供向量检索、全文检索、混合排序与元数据过滤。
- Scope: `vector_search.py`、`text_search.py`、`hybrid.py`、`filters.py` 与对应最小单测。
- Out of Scope: MCP server；Claude skill；引用图谱；reindex。
- Inputs / Dependencies: `01` 第 2.15 节；`02` `retrieve_evidence` 契约、`RetrievalHit`、`SectionType`；依赖 `TASK-08`、`TASK-09`、`TASK-17`、`TASK-19`。
- Files to Modify: `backend/retrieval/vector_search.py`、`backend/retrieval/text_search.py`、`backend/retrieval/hybrid.py`、`backend/retrieval/filters.py`、`tests/unit/test_vector_search.py`、`tests/unit/test_text_search.py`、`tests/unit/test_hybrid.py`、`tests/unit/test_filters.py`
- Implementation Notes: Phase 1 只做 FAISS + SQLite FTS5 + RRF；检索结果要补齐 paper 标题、作者、section、页码等冗余展示字段。
- Acceptance Criteria: 能返回稳定 top-k；混合排序可合并两路结果；过滤器可按 year / section_type 生效。
- Risks / Guardrails: 不要引入 citation graph；不要把 search provider 与 retrieval 混用；不要把 FTS 设计成新 schema 分叉。
- Suggested Next Task: `TASK-25`

#### Task 25
- Task ID: `TASK-25`
- Title: 开放 `retrieve_evidence` MCP tool
- Objective: 让 retrieval 能通过 MCP 被 Claude Code 调用。
- Scope: retrieval `tools.py`、`mcp_server.py`、`retrieve_evidence` handler、`reindex_paper` 保留占位或不注册、契约测试。
- Out of Scope: Claude 侧 skill；hook；compare / citation 工具。
- Inputs / Dependencies: `02` `retrieve_evidence` 契约；依赖 `TASK-24`。
- Files to Modify: `backend/retrieval/tools.py`、`backend/retrieval/mcp_server.py`、`tests/contract/test_retrieval_mcp_contract.py`
- Implementation Notes: 只开放 `retrieve_evidence`；`reindex_paper` 作为未来任务保留，不应抢跑实现。
- Acceptance Criteria: MCP server 可列出 `retrieve_evidence`；返回字段与 `RetrievalHit` 契约一致；契约测试覆盖必填字段。
- Risks / Guardrails: 不要在 retrieval server 注册 ingest tool；不要提前实现 `reindex_paper` 并改变当前任务范围。
- Suggested Next Task: `TASK-26`

#### Task 26
- Task ID: `TASK-26`
- Title: 接入 Claude Code 的证据检索与论文规则文件
- Objective: 让 Claude 侧具备 evidence-first 的论文行为规范与检索入口。
- Scope: `.claude/CLAUDE.md`、`.claude/rules/` 子文件、settings 注册 retrieval server、`paper-evidence.md`、`post-retrieve-cite` hook。
- Out of Scope: `paper-analyze.md`；Phase 2 output style/plugin packaging；memory 复杂策略实现。
- Inputs / Dependencies: `03` 第 1、2、3.3、5.2(B)、6 节；依赖 `TASK-12`、`TASK-25`。
- Files to Modify: `.claude/CLAUDE.md`、`.claude/rules/paper-routing.md`、`.claude/rules/paper-output-format.md`、`.claude/rules/paper-error-handling.md`、`.claude/settings.json`、`.claude/skills/paper-evidence.md`
- Implementation Notes: `CLAUDE.md` 主文件保持轻量，优先用 `@include`；规则只在论文意图下激活。
- Acceptance Criteria: Claude 侧已注册 retrieval server；`paper-evidence` skill 工具集与 `03` 对齐；检索结果呈现被 hook 强制要求带引用。
- Risks / Guardrails: 不要把 CLAUDE.md 写成超长总章程；不要把 coding 能力覆盖掉；不要直接读写 `data/`。
- Suggested Next Task: `TASK-27`

#### Task 27
- Task ID: `TASK-27`
- Title: 实现 orchestrator 侧单篇分析 skill
- Objective: 在 Phase 1 不新建 Analysis MCP Server 的前提下提供单篇论文分析能力。
- Scope: `paper-analyze.md`、`post-analyze-evidence-check` hook、必要的 settings 扩展。
- Out of Scope: `backend/analysis/mcp_server.py`；`analyze_paper` 后端化；compare / synthesize；deep cross-paper analyst agent。
- Inputs / Dependencies: `01` 第 2.16 节；`03` 第 3.4、5.2(C) 节；依赖 `TASK-25`、`TASK-26`。
- Files to Modify: `.claude/skills/paper-analyze.md`、`.claude/settings.json`
- Implementation Notes: skill 应先确认 paper 已 `ready`，再通过 `retrieve_evidence` 拉取 chunk 并由 orchestrator 完成结构化分析。
- Acceptance Criteria: skill 说明与 `03` 一致；未注册不存在的 analysis MCP tool；分析输出结构包含 summary / contributions / methodology / key findings / limitations。
- Risks / Guardrails: 最大风险是偷建后端分析服务或新增 tool 契约；本任务明确禁止。
- Suggested Next Task: `TASK-28`

#### Task 28
- Task ID: `TASK-28`
- Title: 完成契约、集成、质量与冒烟收尾
- Objective: 用测试与脚本把 MVP 链路收口到“可验收”状态。
- Scope: 完善 contract / integration / quality tests，补充 `tests/integration/test_mcp_stdio.py`、`tests/quality/test_retrieval_relevance.py`、`scripts/start_servers.sh`、`scripts/health_check.py`、必要 fixture 与 smoke 流程说明。
- Out of Scope: 新功能扩展；Phase 2/3 功能补丁；大规模 prompt 调优。
- Inputs / Dependencies: `04` 第 3、4、6 节；依赖 `TASK-21`、`TASK-25`、`TASK-27`。
- Files to Modify: `tests/integration/test_mcp_stdio.py`、`tests/quality/test_retrieval_relevance.py`、`tests/fixtures/**`、`scripts/start_servers.sh`、`scripts/health_check.py`
- Implementation Notes: 以 `04` 的 MVP 场景为最终验收用例；脚本只做启动与健康检查，不内嵌业务流程。
- Acceptance Criteria: 至少能验证 search → ingest → status → retrieve → analyze 的 MVP 主链；脚本可用于本地检查 server 可用性。
- Risks / Guardrails: 不要为了让测试通过而修改契约；不要把质量基线写成宽松到失去意义的测试。
- Suggested Next Task: `None - MVP backlog complete`

## D. Recommended Execution Order

### D1. By Group

| 顺序 | Group | 包含 Task | 说明 |
|------|-------|-----------|------|
| 1 | `G1` | `TASK-01` ~ `TASK-06` | 先稳定地基，再进入存储和业务链路 |
| 2 | `G2` | `TASK-07` ~ `TASK-12` | 先把存储层和最短 search slice 跑通 |
| 3 | `G3` | `TASK-13` ~ `TASK-23` | 这是 ingest 主体工作量最大的工作流组 |
| 4 | `G4` | `TASK-24` ~ `TASK-27` | 在 ingest ready 后接 retrieval 和 Claude 壳层 |
| 5 | `G5` | `TASK-28` | 最后做测试、冒烟、收尾 |

### D2. By Session Pack

推荐减少会话数时，直接按下面顺序开会话：

1. `SP-01`
2. `SP-02`
3. `SP-03`
4. `SP-04`
5. `SP-05`
6. `SP-06`
7. `SP-07`
8. `SP-08`
9. `SP-09`
10. `SP-10`
11. `SP-11`
12. `SP-12`
13. `SP-13`
14. `SP-14`

相比“28 个 task 开 28 个会话”，按 `Session Pack` 执行后，推荐会话数可压缩到 14 个左右，同时仍保留高风险任务的独立边界。

### D3. Do Not Merge List

以下 task 不建议与其它 task 合并：

- `TASK-01`
- `TASK-06`
- `TASK-20`
- `TASK-28`

原因：
- 它们分别承担骨架校验、状态机边界、核心 pipeline、最终收尾验收。
- 一旦和其它 task 混做，最容易导致越界实现、验收失焦、回滚困难。

执行纪律补充：
- 在 `TASK-21` 完成前，不应开始 `TASK-23`。
- 在 `TASK-25` 完成前，不应开始 `TASK-26` 与 `TASK-27`。
- `TASK-27` 完成后仍不得抢跑 Phase 2 的 Analysis MCP Server、compare、synthesize。
- 即使在同一个 `Session Pack` 中，也不得跳过前序 task 的验收直接进入后序 task。

## E. Handoff Template

```text
以 00_master_index.md 作为导航，以 01_architecture_and_boundaries.md、02_schema_and_tool_contracts.md、03_claude_code_adaptation.md 作为设计约束与验收依据，只执行 05_execution_backlog.md 中的 TASK-XX。

执行要求：
1. 只完成当前 TASK-XX 的 Scope，严格遵守 Out of Scope。
2. 若 TASK-XX 与 01-03.md 冲突，以 01-03.md 为准，并仅报告最小修正建议，不得自行扩展架构或重写契约。
3. 不得擅自修改 schema、tool 契约、主 prompt 边界、hook 触发逻辑、Claude Code src/ 核心源码。
4. 不得直接读写 data/pdfs/、data/db/、data/index/；论文数据操作必须通过 MCP tool 或 backend 存储层完成。
5. Phase 1 不得创建独立 Analysis MCP Server；单篇分析保持在 orchestrator skill 侧。

完成后请输出：
- 修改文件列表
- 实现说明
- 与 01-03.md 的约束符合性检查
- 验收结果（逐条对应 Acceptance Criteria）
- 未解决问题与最小后续建议
```
