# 04：落地实施方案

> 本文档面向工程执行。所有设计决策引用前三阶段结论，不再重复论证。
>
> 关联文档：[00_master_index](00_master_index.md) · [01_architecture_and_boundaries](01_architecture_and_boundaries.md) · [02_schema_and_tool_contracts](02_schema_and_tool_contracts.md) · [03_claude_code_adaptation](03_claude_code_adaptation.md)

---

## 1. 代码级目录结构最终版

```
paper-workflow/                        # 项目根目录
│
├── .claude/                           # ── Claude Code 扩展层 ──
│   ├── CLAUDE.md                      # 论文路由规则 + evidence 纪律 + 输出格式
│   ├── CLAUDE.local.md                # 本地覆盖（gitignored）
│   ├── settings.json                  # MCP 注册 + 权限 + hooks
│   ├── settings.local.json            # 本地 API key 等（gitignored）
│   │
│   ├── skills/                        # 论文 skills（用户可 /skill-name 调用）
│   │   ├── paper-search.md            # MVP
│   │   ├── paper-ingest.md            # MVP
│   │   ├── paper-evidence.md          # MVP
│   │   ├── paper-analyze.md           # MVP
│   │   ├── paper-status.md            # MVP
│   │   ├── paper-compare.md           # Phase 2
│   │   └── paper-synthesize.md        # Phase 3
│   │
│   ├── agents/                        # 论文 subagents
│   │   ├── source-hunter.md           # MVP (广泛搜索)
│   │   ├── ingest-operator.md         # MVP (批量 ingest)
│   │   ├── evidence-miner.md          # MVP (深度检索)
│   │   ├── paper-analyst.md           # Phase 2 (deep 分析)
│   │   ├── compare-analyst.md         # Phase 2
│   │   └── synthesis-writer.md        # Phase 3
│   │
│   ├── rules/                         # CLAUDE.md @include 子文件
│   │   ├── paper-routing.md           # 路由规则 15 条
│   │   ├── paper-output-format.md     # 结构化输出约束
│   │   └── paper-error-handling.md    # 错误处理策略
│   │
│   └── memory/
│       └── MEMORY.md                  # 用户论文偏好记忆（auto-memory 管理）
│
├── backend/                           # ── Python 论文 Backend ──
│   ├── pyproject.toml                 # 项目依赖（uv 管理）
│   ├── __init__.py
│   │
│   ├── common/                        # 跨模块共享
│   │   ├── __init__.py
│   │   ├── config.py                  # 路径 + 模型 + 数据库连接配置
│   │   ├── models.py                  # Pydantic models: Paper, Chunk, Section, IngestJob, etc.
│   │   ├── db.py                      # SQLite 连接管理 + migration
│   │   ├── errors.py                  # ToolError 统一错误类 + 错误码常量
│   │   └── logging_config.py          # structlog JSON 日志配置
│   │
│   ├── ingest/                        # Ingest MCP Server
│   │   ├── __init__.py
│   │   ├── mcp_server.py              # MCP stdio server 入口 + tool 注册
│   │   ├── tools.py                   # tool handler 实现：ingest_paper, batch_ingest, get_ingest_status, fetch_pdf, search_papers
│   │   ├── downloader.py              # PDF 下载（requests + retry + hash 校验）
│   │   ├── parser.py                  # PyMuPDF 解析器
│   │   ├── structurer.py              # 元数据提取 + section 识别 + SectionType 分类
│   │   ├── chunker.py                 # chunk 切分（512 token / 128 overlap）
│   │   ├── embedder.py                # sentence-transformers embedding
│   │   ├── indexer.py                 # SQLite 写入 + FAISS 索引写入
│   │   ├── deduplicator.py            # DOI / title+author 模糊去重
│   │   ├── pipeline.py                # 状态机编排：discovered → ready
│   │   └── state_machine.py           # PaperStatus 枚举 + 转移校验
│   │
│   ├── retrieval/                     # Retrieval MCP Server
│   │   ├── __init__.py
│   │   ├── mcp_server.py              # MCP stdio server 入口
│   │   ├── tools.py                   # tool handler：retrieve_evidence, reindex_paper
│   │   ├── vector_search.py           # FAISS top-k 检索
│   │   ├── text_search.py             # SQLite FTS5 全文检索
│   │   ├── hybrid.py                  # RRF 混合排序
│   │   └── filters.py                 # 元数据过滤（year, author, section_type）
│   │
│   ├── analysis/                      # Analysis 模块（Phase 1 不单独做 MCP server）
│   │   ├── __init__.py
│   │   ├── mcp_server.py              # Phase 2 启用
│   │   ├── single_paper.py            # 单篇分析 prompt + LLM 调用
│   │   └── tools.py                   # analyze_paper tool handler
│   │
│   ├── search/                        # 外部学术搜索 API 封装
│   │   ├── __init__.py
│   │   ├── base.py                    # SearchProvider 抽象基类
│   │   ├── arxiv_provider.py          # arXiv API 封装
│   │   └── s2_provider.py             # Semantic Scholar API 封装
│   │
│   └── storage/                       # 存储层封装
│       ├── __init__.py
│       ├── sqlite_store.py            # SQLite 表创建 + CRUD + FTS5
│       ├── faiss_store.py             # FAISS 索引 create/add/search/save/load
│       └── file_store.py              # PDF 文件管理（路径规范 + hash 命名）
│
├── data/                              # ── 运行时数据（gitignored）──
│   ├── pdfs/                          # 原始 PDF（以 sha256 前 16 位命名）
│   ├── db/
│   │   └── papers.db                  # SQLite 主数据库
│   ├── index/
│   │   └── faiss.index                # FAISS 向量索引文件
│   ├── cache/                         # 解析中间缓存
│   └── logs/
│       ├── ingest/                    # ingest 日志（JSONL，按日分文件）
│       ├── retrieval/                 # 检索诊断日志
│       └── traces/                    # per-paper trace
│
├── configs/
│   └── default.yaml                   # 全局默认配置
│
├── tests/                             # ── 测试 ──
│   ├── conftest.py                    # pytest fixtures: tmp_db, tmp_index, sample_pdfs
│   ├── unit/
│   │   ├── test_downloader.py
│   │   ├── test_parser.py
│   │   ├── test_chunker.py
│   │   ├── test_embedder.py
│   │   ├── test_state_machine.py
│   │   ├── test_deduplicator.py
│   │   ├── test_vector_search.py
│   │   ├── test_text_search.py
│   │   ├── test_hybrid.py
│   │   └── test_filters.py
│   ├── contract/
│   │   ├── test_ingest_mcp_contract.py   # MCP tool 输入输出 schema 校验
│   │   └── test_retrieval_mcp_contract.py
│   ├── quality/
│   │   ├── test_parse_quality.py         # 解析质量基准测试
│   │   └── test_retrieval_relevance.py   # 检索相关性基准测试
│   ├── integration/
│   │   ├── test_ingest_e2e.py            # 下载 → 解析 → 入库 全流程
│   │   ├── test_retrieval_e2e.py         # 入库 → 检索 全流程
│   │   └── test_mcp_stdio.py            # MCP server 启动 + tool 调用
│   └── fixtures/
│       ├── sample_pdfs/                  # 3-5 个测试用 PDF
│       │   ├── attention_is_all_you_need.pdf
│       │   ├── bert.pdf
│       │   └── simple_2page.pdf
│       └── expected/                     # 预期解析结果
│           ├── attention_metadata.json
│           └── attention_sections.json
│
├── scripts/
│   ├── setup.sh                       # 一键环境初始化
│   ├── start_servers.sh               # 启动 MCP servers（开发用）
│   ├── seed_test_data.py              # 灌入测试论文
│   └── health_check.py                # backend 健康检查
│
└── .gitignore                         # data/, *.db, .claude/settings.local.json, etc.
```

### 关键职责说明

| 目录 | 核心职责 | 首要交付物 |
|------|---------|-----------|
| `.claude/skills/` | 用户入口，定义"做什么" | 5 个 markdown skill 文件 |
| `.claude/agents/` | 复杂任务执行者，定义"怎么做" | 3 个 markdown agent 文件 |
| `.claude/rules/` | 行为规范，定义"不能做什么" | 3 个规则子文件 |
| `backend/common/` | 全局数据模型 + 错误类 + 配置 | `models.py`, `errors.py` |
| `backend/ingest/` | ingest pipeline 全流程 | `mcp_server.py` + `pipeline.py` |
| `backend/retrieval/` | 检索全流程 | `mcp_server.py` + `hybrid.py` |
| `backend/search/` | 外部搜索 API 封装 | `arxiv_provider.py` |
| `backend/storage/` | 持久化封装 | `sqlite_store.py` + `faiss_store.py` |
| `tests/unit/` | 最小功能验证 | 每个模块对应一个测试文件 |
| `tests/contract/` | MCP 接口契约 | 输入输出 schema 校验 |

---

## 2. 模块改造清单

### 总则：不改 Claude Code src/ 任何文件

所有改造通过扩展机制完成。以下按执行顺序排列。

### 第一批（Day 1-5）：地基层

| 序号 | 模块 | 文件 | 做什么 | 工时估算 |
|------|------|------|--------|---------|
| 1 | `backend/common/models.py` | 新建 | Paper, Chunk, Section, IngestJob, RetrievalHit, ToolError 的 Pydantic model | 0.5d |
| 2 | `backend/common/errors.py` | 新建 | 错误码常量 + ToolError 工厂函数 | 0.5d |
| 3 | `backend/common/config.py` | 新建 | 路径、embedding 模型名、SQLite 路径等配置 | 0.5d |
| 4 | `backend/common/db.py` | 新建 | SQLite 建表（papers, chunks, sections, ingest_jobs, parse_metrics）+ migration | 0.5d |
| 5 | `backend/ingest/state_machine.py` | 新建 | PaperStatus enum + 转移校验函数 | 0.5d |
| 6 | `backend/storage/sqlite_store.py` | 新建 | Paper/Chunk/Section CRUD | 1d |
| 7 | `backend/storage/faiss_store.py` | 新建 | FAISS index create/add/search/save/load | 1d |
| 8 | `backend/storage/file_store.py` | 新建 | PDF 文件存储（hash 命名 + 路径管理） | 0.5d |

**合计约 5 天。这批完成后，存储层可用。**

### 第二批（Day 6-12）：核心 Pipeline

| 序号 | 模块 | 文件 | 做什么 | 工时估算 |
|------|------|------|--------|---------|
| 9 | `backend/ingest/downloader.py` | 新建 | PDF 下载（retry + hash 校验 + 大小限制） | 1d |
| 10 | `backend/ingest/parser.py` | 新建 | PyMuPDF 解析（文本提取 + 页码映射） | 1d |
| 11 | `backend/ingest/structurer.py` | 新建 | 元数据抽取 + section 识别 + SectionType 分类 | 1d |
| 12 | `backend/ingest/chunker.py` | 新建 | 512 token / 128 overlap 切分 | 0.5d |
| 13 | `backend/ingest/embedder.py` | 新建 | sentence-transformers batch embedding | 0.5d |
| 14 | `backend/ingest/indexer.py` | 新建 | 组合 sqlite_store + faiss_store 完成入库 | 0.5d |
| 15 | `backend/ingest/deduplicator.py` | 新建 | DOI / title 模糊匹配去重 | 0.5d |
| 16 | `backend/ingest/pipeline.py` | 新建 | 状态机编排：url → download → parse → chunk → embed → index → ready | 1d |
| 17 | `backend/search/arxiv_provider.py` | 新建 | arXiv API 搜索（arxiv Python 包） | 0.5d |
| 18 | `backend/search/s2_provider.py` | 新建 | Semantic Scholar API 搜索 | 0.5d |

**合计约 7 天。这批完成后，ingest pipeline 端到端可用。**

### 第三批（Day 13-17）：MCP Server + 检索

| 序号 | 模块 | 文件 | 做什么 | 工时估算 |
|------|------|------|--------|---------|
| 19 | `backend/ingest/mcp_server.py` | 新建 | MCP stdio server：注册 search_papers, ingest_paper, batch_ingest, get_ingest_status, fetch_pdf | 1.5d |
| 20 | `backend/ingest/tools.py` | 新建 | 各 tool handler 实现（调用 pipeline + 返回 JSON） | 1d |
| 21 | `backend/retrieval/vector_search.py` | 新建 | FAISS 检索封装 | 0.5d |
| 22 | `backend/retrieval/text_search.py` | 新建 | FTS5 检索封装 | 0.5d |
| 23 | `backend/retrieval/hybrid.py` | 新建 | RRF 混合排序 | 0.5d |
| 24 | `backend/retrieval/mcp_server.py` | 新建 | MCP stdio server：注册 retrieve_evidence, reindex_paper | 1d |

**合计约 5 天。这批完成后，两个 MCP server 均可独立启动和调用。**

### 第四批（Day 18-22）：Claude Code 侧接入

| 序号 | 模块 | 文件 | 做什么 | 工时估算 |
|------|------|------|--------|---------|
| 25 | `.claude/settings.json` | 新建 | 注册 paper-ingest + paper-retrieval MCP server + 权限白名单 | 0.5d |
| 26 | `.claude/CLAUDE.md` + `rules/` | 新建 | 路由规则 + evidence 纪律 + 输出格式 + 错误处理 | 1d |
| 27 | `.claude/skills/paper-search.md` | 新建 | 搜索 skill | 0.5d |
| 28 | `.claude/skills/paper-ingest.md` | 新建 | ingest skill | 0.5d |
| 29 | `.claude/skills/paper-evidence.md` | 新建 | 检索 skill | 0.5d |
| 30 | `.claude/skills/paper-analyze.md` | 新建 | 分析 skill（Phase 1：orchestrator 用 LLM 原生能力基于 chunks 分析） | 0.5d |
| 31 | `.claude/skills/paper-status.md` | 新建 | 状态查询 skill | 0.5d |
| 32 | `.claude/agents/ingest-operator.md` | 新建 | 批量 ingest subagent | 0.5d |
| 33 | hooks 配置 | settings.json | 添加 post-ingest-verify + post-retrieve-cite hooks | 0.5d |

**合计约 5 天。这批完成后，用户可通过 Claude Code 调用论文工作流。**

### 先不碰的模块

| 模块 | 理由 | 何时动 |
|------|------|--------|
| `backend/analysis/mcp_server.py` | Phase 1 分析由 orchestrator LLM 直接做 | Phase 2 |
| `.claude/agents/compare-analyst.md` | 依赖 compare_papers tool | Phase 2 |
| `.claude/agents/synthesis-writer.md` | 依赖 synthesize_topic tool | Phase 3 |
| `.claude/skills/paper-compare.md` | 依赖 compare_papers tool | Phase 2 |
| `.claude/skills/paper-synthesize.md` | 依赖 synthesize_topic tool | Phase 3 |
| `docker/` | 本地开发不需要 | Phase 2 |
| `plugin/manifest.json` | 稳定后再打包 | Phase 2 |
| Claude Code `src/` 任何文件 | **永远不动** | 永远不动 |

---

## 3. 最小可用实现步骤（MVP Sprint）

### Step 1: 搜论文

```
目标: 用户输入关键词 → 返回论文列表
```

| 维度 | 说明 |
|------|------|
| **输入** | 用户自然语言 query (e.g., "LLM agent papers 2024") |
| **输出** | 论文表格（title, authors, year, venue, citations, url） |
| **依赖** | `backend/search/arxiv_provider.py` + `backend/ingest/mcp_server.py`（仅 search_papers tool）+ `.claude/skills/paper-search.md` + `.claude/settings.json` |
| **验收** | 在 Claude Code 中输入 `/paper-search transformer attention`，返回 ≥10 条 arXiv 结果，表格格式正确 |

**实施顺序**：
1. 实现 `arxiv_provider.py`（纯函数，可独立测试）
2. 实现 `ingest/mcp_server.py` 的最小骨架（仅注册 `search_papers` tool）
3. 实现 `ingest/tools.py` 中 `handle_search_papers`
4. 写 `.claude/settings.json` 注册 MCP server
5. 写 `paper-search.md` skill
6. 手动测试：启动 Claude Code → `/paper-search` → 看结果

**单测**：`test_arxiv_provider.py`（mock HTTP response，验证解析逻辑）

---

### Step 2: 下载 PDF

```
目标: 给定 URL → 下载 PDF → 存储到 data/pdfs/ → 返回路径和 hash
```

| 维度 | 说明 |
|------|------|
| **输入** | PDF URL (e.g., `https://arxiv.org/pdf/2401.12345`) |
| **输出** | `{pdf_path, file_size_bytes, pdf_hash, already_exists}` |
| **依赖** | `backend/ingest/downloader.py` + `backend/storage/file_store.py` + MCP `fetch_pdf` tool |
| **验收** | 调用 `fetch_pdf` → PDF 文件出现在 `data/pdfs/` → hash 校验通过 → 重复下载返回 `already_exists=true` |

**实施顺序**：
1. 实现 `file_store.py`（hash 命名、路径管理）
2. 实现 `downloader.py`（requests + retry + 大小限制 + Content-Type 校验）
3. 在 `tools.py` 中添加 `handle_fetch_pdf`
4. 在 `mcp_server.py` 中注册 `fetch_pdf` tool
5. 单测 + 手动测试

**单测**：`test_downloader.py`（mock HTTP，验证 retry 逻辑、hash 校验、大小限制）

---

### Step 3: 解析入库

```
目标: PDF → 解析 → 结构化 → chunk → embedding → 写入 SQLite + FAISS → status=ready
```

| 维度 | 说明 |
|------|------|
| **输入** | PDF URL 或本地路径 |
| **输出** | `{job_id, paper_id, status}` + 可通过 `get_ingest_status` 查询进度 |
| **依赖** | Step 2 的所有模块 + `parser.py` + `structurer.py` + `chunker.py` + `embedder.py` + `indexer.py` + `pipeline.py` + `state_machine.py` + `sqlite_store.py` + `faiss_store.py` + `db.py` |
| **验收** | 调用 `ingest_paper(url="https://arxiv.org/pdf/1706.03762")` → 状态从 queued 流转到 ready → `get_ingest_status` 返回 chunk_count > 0 → SQLite 中有 paper + chunks 记录 → FAISS 索引有对应向量 |

**实施顺序**：
1. 实现 `db.py`（建表 DDL）
2. 实现 `sqlite_store.py`（Paper + Chunk CRUD）
3. 实现 `faiss_store.py`（create + add + save + load）
4. 实现 `state_machine.py`（状态枚举 + 转移校验）
5. 实现 `parser.py`（PyMuPDF 文本提取）
6. 实现 `structurer.py`（标题/作者/摘要提取 + section 分割）
7. 实现 `chunker.py`（512 token / 128 overlap）
8. 实现 `embedder.py`（sentence-transformers all-MiniLM-L6-v2）
9. 实现 `indexer.py`（组合 sqlite + faiss 写入）
10. 实现 `pipeline.py`（状态机编排，逐步 download → parse → chunk → embed → index）
11. 在 `tools.py` 中添加 `handle_ingest_paper` + `handle_get_ingest_status`
12. 在 `mcp_server.py` 中注册这两个 tool
13. 写 `paper-ingest.md` skill + `paper-status.md` skill
14. 端到端测试

**关键单测**：
- `test_parser.py`：用 fixture PDF 验证文本提取完整性
- `test_chunker.py`：验证 chunk 数量、overlap、token 计数
- `test_state_machine.py`：验证所有合法/非法转移
- `test_ingest_e2e.py`：集成测试，从 URL 到 ready

---

### Step 4: 简单检索

```
目标: 用户输入自然语言 query → 返回最相关的 chunks + 来源信息
```

| 维度 | 说明 |
|------|------|
| **输入** | 自然语言 query + 可选过滤条件 |
| **输出** | `RetrievalHit[]`（text, score, paper_title, authors, section_type, page） |
| **依赖** | Step 3 完成（库中有论文）+ `vector_search.py` + `text_search.py` + `hybrid.py` + retrieval MCP server |
| **验收** | ingest "Attention Is All You Need" 后，查询 "multi-head attention mechanism" → 返回相关 chunk，top score > 0.5，来源信息正确 |

**实施顺序**：
1. 实现 `vector_search.py`（FAISS search → chunk_id 列表 → 关联 Paper 元数据）
2. 实现 `text_search.py`（FTS5 MATCH query → chunk_id + rank）
3. 实现 `hybrid.py`（RRF 合并 vector + text 结果）
4. 实现 `filters.py`（year / section_type 过滤）
5. 实现 `retrieval/tools.py`（`handle_retrieve_evidence`）
6. 实现 `retrieval/mcp_server.py`
7. 在 `.claude/settings.json` 中注册 paper-retrieval MCP server
8. 写 `paper-evidence.md` skill
9. 写 `post-retrieve-cite` hook
10. 端到端测试

**关键单测**：
- `test_vector_search.py`：验证 top-k 返回正确数量、分数递减
- `test_hybrid.py`：验证 RRF 排序逻辑
- `test_retrieval_relevance.py`：用已知 query-chunk 对验证检索命中

---

### Step 5: 单篇分析

```
目标: 给定 paper_id → 返回结构化分析（summary, contributions, methodology, findings, limitations）
```

| 维度 | 说明 |
|------|------|
| **输入** | paper_id + 可选 focus + depth |
| **输出** | AnalysisResult 结构 |
| **依赖** | Step 4 完成 + `paper-analyze.md` skill |
| **验收** | 对已入库论文调用 `/paper-analyze`，返回有 summary + contributions + methodology + key_findings，每项非空 |

**Phase 1 实施方式（不建独立 Analysis MCP Server）**：

paper-analyze skill 的 prompt 直接指导 orchestrator：
1. 调 `retrieve_evidence(paper_id=X, top_k=30)` 获取论文全部 chunk
2. 用 LLM 自身能力对 chunk 进行结构化分析
3. 按 AnalysisResult 格式输出

**实施顺序**：
1. 写 `paper-analyze.md` skill（prompt 中包含分析指引 + 输出格式约束）
2. 写 `post-analyze-evidence-check` hook
3. 测试：ingest 一篇论文 → `/paper-analyze` → 检查输出结构完整性

---

### MVP 里程碑验收

全部 5 步完成后，执行以下端到端验收场景：

```
场景: "搜索 transformer 论文，下载前 3 篇，入库，查询 attention mechanism，分析第一篇"

验收步骤：
1. /paper-search "transformer attention" → 表格显示 ≥10 篇
2. 选择前 3 篇 → /paper-ingest → 3 篇入库成功
3. /paper-status → 显示 3 papers ready
4. /paper-evidence "what are the main types of attention mechanisms" → 返回 ≥5 条 evidence + 来源
5. /paper-analyze [paper_id of first paper] → 返回完整 AnalysisResult
```

---

## 4. 测试方案

### 4.1 测试分层

```
                    ┌─────────────────────┐
                    │ E2E Workflow Tests   │  ← 1-2 个场景，跑全流程
                    │ (最慢，最少)          │
                    ├─────────────────────┤
                    │ Integration Tests    │  ← MCP server 启停 + tool 调用
                    │ (中等)               │
                    ├─────────────────────┤
                    │ Contract Tests       │  ← MCP tool 输入输出 schema 校验
                    │ (快，关键)            │
                    ├─────────────────────┤
                    │ Quality Benchmarks   │  ← 解析质量 + 检索相关性
                    │ (离线跑)             │
                    ├─────────────────────┤
                    │ Unit Tests           │  ← 每个模块独立测试
                    │ (最快，最多)          │
                    └─────────────────────┘
```

### 4.2 单元测试

| 模块 | 测试文件 | 重点测什么 | 优先级 |
|------|---------|-----------|--------|
| downloader | `test_downloader.py` | retry 逻辑、超时处理、Content-Type 校验、大小限制 | P0 |
| parser | `test_parser.py` | 用 fixture PDF 验证文本提取完整性、页码映射 | P0 |
| chunker | `test_chunker.py` | chunk 数量、token 计数、overlap 正确性、边界处理 | P0 |
| state_machine | `test_state_machine.py` | 所有合法转移通过、所有非法转移抛异常 | P0 |
| embedder | `test_embedder.py` | 向量维度正确、batch 处理、空文本处理 | P1 |
| deduplicator | `test_deduplicator.py` | DOI 精确匹配、title 模糊匹配（阈值验证） | P1 |
| vector_search | `test_vector_search.py` | top-k 数量、分数递减、空索引处理 | P0 |
| text_search | `test_text_search.py` | FTS5 query 正确、中文/特殊字符处理 | P1 |
| hybrid | `test_hybrid.py` | RRF 公式正确、去重、两路结果合并 | P0 |
| filters | `test_filters.py` | year 过滤、section_type 过滤、组合过滤 | P1 |
| sqlite_store | `test_sqlite_store.py` | CRUD 正确性、FTS5 索引建立 | P1 |
| faiss_store | `test_faiss_store.py` | create/add/search/save/load 往返正确 | P1 |

**最先写的 3 个单测**：`test_state_machine.py`、`test_parser.py`、`test_chunker.py`——这三个出错会导致整个 pipeline 不可用。

### 4.3 契约测试

```python
# tests/contract/test_ingest_mcp_contract.py

import jsonschema

def test_ingest_paper_output_schema(ingest_mcp_client):
    """ingest_paper 返回值必须包含 job_id, status 字段"""
    result = ingest_mcp_client.call("ingest_paper", {
        "url": "https://arxiv.org/pdf/1706.03762"
    })
    assert "job_id" in result
    assert result["status"] in ["queued", "skipped"]
    if result["status"] == "skipped":
        assert "paper_id" in result

def test_tool_error_format(ingest_mcp_client):
    """所有错误必须返回 ToolError 格式"""
    result = ingest_mcp_client.call("ingest_paper", {
        "url": "not-a-valid-url"
    })
    assert result["error"] == True
    assert "error_code" in result
    assert "error_message" in result
    assert "retryable" in result

def test_retrieve_evidence_output_schema(retrieval_mcp_client):
    """retrieve_evidence 返回的 hits 必须包含必填字段"""
    result = retrieval_mcp_client.call("retrieve_evidence", {
        "query": "attention mechanism"
    })
    for hit in result["hits"]:
        assert "chunk_id" in hit
        assert "paper_id" in hit
        assert "text" in hit
        assert "score" in hit
        assert 0.0 <= hit["score"] <= 1.0
        assert "paper_title" in hit
```

**最先写的契约测试**：`test_tool_error_format`——确保所有 error 走 ToolError 格式。

### 4.4 解析质量测试

```python
# tests/quality/test_parse_quality.py

QUALITY_BENCHMARKS = [
    {
        "pdf": "fixtures/sample_pdfs/attention_is_all_you_need.pdf",
        "expected_title": "Attention Is All You Need",
        "expected_author_count": 8,
        "min_section_count": 5,
        "min_char_count": 30000,
        "must_have_sections": ["abstract", "introduction", "conclusion"],
    },
]

@pytest.mark.parametrize("bench", QUALITY_BENCHMARKS)
def test_parse_quality(bench):
    result = parse_pdf(bench["pdf"])
    assert bench["expected_title"].lower() in result.title.lower()
    assert len(result.authors) >= bench["expected_author_count"]
    assert len(result.sections) >= bench["min_section_count"]
    assert result.char_count >= bench["min_char_count"]
    section_types = {s.section_type for s in result.sections}
    for required in bench["must_have_sections"]:
        assert required in section_types, f"Missing section type: {required}"
```

### 4.5 状态机测试

```python
# tests/unit/test_state_machine.py

VALID_TRANSITIONS = [
    ("discovered", "queued"),
    ("queued", "downloading"),
    ("downloading", "downloaded"),
    ("downloading", "failed"),
    ("downloaded", "parsing"),
    ("parsing", "parsed"),
    ("parsing", "failed"),
    ("parsed", "chunked"),
    ("chunked", "embedding"),
    ("embedding", "indexed"),
    ("indexed", "ready"),
    ("failed", "queued"),        # retry
    ("ready", "archived"),
    ("ready", "queued"),         # force re-ingest
]

INVALID_TRANSITIONS = [
    ("discovered", "ready"),     # 不能跳过
    ("downloading", "ready"),
    ("parsing", "indexed"),
    ("ready", "downloading"),    # 不能倒退（除了 ready→queued）
    ("archived", "ready"),       # 必须经过 queued
]

@pytest.mark.parametrize("from_state,to_state", VALID_TRANSITIONS)
def test_valid_transition(from_state, to_state):
    assert is_valid_transition(from_state, to_state) == True

@pytest.mark.parametrize("from_state,to_state", INVALID_TRANSITIONS)
def test_invalid_transition(from_state, to_state):
    with pytest.raises(InvalidTransitionError):
        transition(from_state, to_state)
```

### 4.6 检索相关性测试

```python
# tests/quality/test_retrieval_relevance.py

RELEVANCE_CASES = [
    {
        "setup_papers": ["attention_is_all_you_need.pdf"],
        "query": "multi-head attention mechanism",
        "must_hit_section_types": ["methodology"],
        "min_top_score": 0.4,
        "min_hits": 3,
    },
    {
        "setup_papers": ["attention_is_all_you_need.pdf"],
        "query": "training hyperparameters",
        "must_hit_section_types": ["experiments"],
        "min_top_score": 0.3,
        "min_hits": 1,
    },
]

@pytest.mark.parametrize("case", RELEVANCE_CASES)
def test_retrieval_relevance(seeded_index, case):
    hits = retrieve_evidence(query=case["query"], top_k=10)
    assert len(hits) >= case["min_hits"]
    assert hits[0].score >= case["min_top_score"]
    hit_section_types = {h.section_type for h in hits if h.section_type}
    for required in case["must_hit_section_types"]:
        assert required in hit_section_types
```

### 4.7 端到端工作流测试

```python
# tests/integration/test_ingest_e2e.py

def test_full_ingest_pipeline(tmp_data_dir):
    """从 URL 到 ready 的完整 ingest 流程"""
    pdf_path = "tests/fixtures/sample_pdfs/attention_is_all_you_need.pdf"

    job = ingest_from_local(pdf_path, data_dir=tmp_data_dir)

    paper = get_paper(job.paper_id)
    assert paper.status == "ready"
    assert paper.chunk_count > 0
    assert paper.title != ""

    chunks = get_chunks(job.paper_id)
    assert len(chunks) > 0
    assert all(c.text != "" for c in chunks)

    hits = retrieve_evidence("attention mechanism", paper_ids=[job.paper_id])
    assert len(hits) > 0

# tests/integration/test_mcp_stdio.py

def test_mcp_server_lifecycle():
    """MCP server 可以启动、处理请求、正常关闭"""
    proc = start_mcp_server("backend.ingest.mcp_server")
    try:
        tools = mcp_list_tools(proc)
        assert "search_papers" in [t["name"] for t in tools]
        assert "ingest_paper" in [t["name"] for t in tools]

        result = mcp_call_tool(proc, "search_papers", {"query": "test", "max_results": 1})
        assert "results" in result
    finally:
        proc.terminate()
        proc.wait(timeout=5)
```

### 4.8 测试优先级总结

| 优先级 | 测试 | 目的 | 何时写 |
|--------|------|------|--------|
| **P0** | `test_state_machine.py` | pipeline 骨架正确性 | Day 1（与代码同步） |
| **P0** | `test_parser.py` | 解析器基本功能 | Day 7（parser 完成时） |
| **P0** | `test_chunker.py` | chunk 切分正确性 | Day 8 |
| **P0** | `test_tool_error_format` (contract) | 错误格式统一 | Day 14（MCP server 完成时） |
| **P0** | `test_ingest_e2e.py` | 全流程正确性 | Day 16 |
| **P1** | `test_parse_quality.py` | 解析质量基线 | Day 10 |
| **P1** | `test_retrieval_relevance.py` | 检索质量基线 | Day 17 |
| **P1** | `test_mcp_stdio.py` | MCP 通信正确性 | Day 15 |
| **P2** | `test_hybrid.py` | 混合排序逻辑 | Day 16 |
| **P2** | 其他单元测试 | 模块级正确性 | 随模块开发 |

---

## 5. 实施风险与避坑

### Risk 1: 把 CLAUDE.md 写太重

**症状**：CLAUDE.md 超过 500 行，每次 query 消耗大量 prompt token；规则之间冲突；agent 无法同时遵守所有规则。

**规避**：
- CLAUDE.md 主文件 < 30 行（只放 `@include` 指令）
- 每个 `@include` 子文件 < 80 行
- 总规则数不超过 20 条
- 每次加规则前问自己：这条规则是否可以通过 hook 替代？如果可以，用 hook 而非规则
- 定期用 `/paper-search` + `/paper-evidence` 做冒烟测试，看 agent 是否还能正常路由

### Risk 2: 过早做复杂多 agent

**症状**：Phase 1 就搞 coordinator mode + 多 agent 并行；subagent 之间互相调用形成环；调试时无法追踪哪个 agent 出了错。

**规避**：
- Phase 1 只允许 **skill → 直接 MCP tool** 和 **skill → 单个 subagent → MCP tool** 两种调用链
- 不允许 subagent 调 subagent
- 不使用 coordinator mode（Phase 3 再考虑）
- 每个 subagent 的 `allowedTools` 严格限定，不给"全套工具"

### Risk 3: Schema 漂移

**症状**：Python backend 的 `models.py` 和 MCP tool 的实际返回 JSON 不一致；orchestrator 的 skill prompt 里描述的字段名和 tool 实际返回的不同。

**规避**：
- `models.py` 是唯一的 schema 真相源
- MCP tool 的返回值必须由 Pydantic model `.model_dump()` 生成（不手写 dict）
- 契约测试 `test_*_mcp_contract.py` 在 CI 中每次都跑
- 改 schema 时，**先改 models.py → 再改 tool handler → 再改 skill prompt → 最后跑契约测试**

### Risk 4: Ingest 和 Analysis 耦合

**症状**：analysis 模块直接 import ingest 模块的内部函数；改 parser 导致 analysis 挂了。

**规避**：
- `backend/analysis/` 只通过 `backend/storage/` 和 `backend/common/models.py` 访问论文数据
- 不允许 analysis import ingest
- 不允许 retrieval import ingest
- 依赖方向严格单向：`ingest → storage`，`retrieval → storage`，`analysis → storage`

```
            ┌─────────┐
   ingest ──┤         │
            │ storage │
 retrieval ──┤         │
            │  + db   │
  analysis ──┤         │
            └─────────┘
  三个模块互不 import，只通过 storage 层共享数据
```

### Risk 5: 日志和 trace 缺失

**症状**：ingest 失败后无法定位原因；检索效果差但不知道 query 和 score 分布。

**规避**：
- **Day 1 就配好 structlog**。不用 print，不用 logging.info 裸调用
- 每个 pipeline stage 的入口和出口都记一条 JSON log
- `pipeline.py` 中每次状态转移都写入 `paper_traces` 表
- 检索每次调用都写入 `data/logs/retrieval/` JSONL
- 先写日志基础设施（`logging_config.py`），再写业务代码

### Risk 6: Tool 契约不稳定

**症状**：频繁修改 MCP tool 的输入/输出 schema；skill prompt 跟不上 tool 变化；用户已经习惯的命令突然行为变了。

**规避**：
- Phase 1 确定的 P0 tool（`ingest_paper`, `retrieve_evidence`, `get_ingest_status`, `search_papers`）的输入输出一旦定稿，**不做 breaking change**
- 新增字段可以随时加（向后兼容），但不能删字段或改字段类型
- 如果必须 breaking change，版本号递增 + 在 CHANGELOG 里标明
- 契约测试是防线

### Risk 7: 权限边界不清

**症状**：agent 绕过 MCP tool 直接 `cat data/db/papers.db`；agent 在 `data/pdfs/` 里创建临时文件；agent 修改 `backend/` 代码。

**规避**：
- CLAUDE.md 中明确写入禁止规则（已设计在 03 §1）
- code review 时检查 agent 对话日志中是否有直接文件操作

### Risk 8: MCP Server 冷启动延迟

**症状**：用户第一次调论文 tool 时等 3-5 秒（Python 进程启动 + 模型加载）。

**规避**：
- `embedder.py` 延迟加载模型（只在第一次 embed 时加载，不在 server 启动时加载）
- MCP server 启动时只做最小初始化（SQLite 连接 + FAISS index load，通常 <500ms）
- sentence-transformers 模型下载应在 `setup.sh` 中预完成，而非运行时下载
- 如果延迟仍不可接受，考虑 MCP server 常驻模式

---

## 6. 执行排期建议

### 立刻做（Day 1-2）

| # | 任务 | 产出 | 依赖 |
|---|------|------|------|
| 1 | 初始化项目结构 | `pyproject.toml` + 目录骨架 + `.gitignore` | 无 |
| 2 | `backend/common/models.py` | Paper, Chunk, IngestJob, RetrievalHit, ToolError 的 Pydantic model | 无 |
| 3 | `backend/common/errors.py` | 错误码常量 + ToolError 构造 | models.py |
| 4 | `backend/ingest/state_machine.py` | PaperStatus enum + 转移函数 | models.py |
| 5 | `tests/unit/test_state_machine.py` | 状态机全路径测试 | state_machine.py |
| 6 | `backend/common/db.py` | SQLite 建表 | models.py |
| 7 | `backend/common/config.py` | 路径 + 模型名 + 日志配置 | 无 |
| 8 | `backend/common/logging_config.py` | structlog JSON 配置 | 无 |

### 本周做（Day 3-5）

| # | 任务 | 产出 | 依赖 |
|---|------|------|------|
| 9 | `backend/storage/` 三个文件 | SQLite CRUD + FAISS 封装 + 文件存储 | db.py |
| 10 | `backend/ingest/downloader.py` + 单测 | PDF 下载器 | file_store.py |
| 11 | `backend/ingest/parser.py` + 单测 | PyMuPDF 解析器 | 无 |
| 12 | `backend/ingest/structurer.py` | 元数据 + section 提取 | parser.py |
| 13 | `backend/ingest/chunker.py` + 单测 | chunk 切分 | 无 |
| 14 | `backend/ingest/embedder.py` | embedding（先不测，等集成测试） | 无 |
| 15 | `scripts/setup.sh` | Python venv + 依赖 + 模型预下载 | pyproject.toml |

### 下周做（Day 6-10）

| # | 任务 | 产出 | 依赖 |
|---|------|------|------|
| 16 | `backend/ingest/pipeline.py` | 完整 ingest pipeline | 所有 ingest 子模块 |
| 17 | `backend/search/arxiv_provider.py` | arXiv 搜索 | 无 |
| 18 | `backend/ingest/mcp_server.py` + `tools.py` | Ingest MCP server（search + ingest + status + fetch） | pipeline + search |
| 19 | `backend/retrieval/` 全部 | 向量+全文+混合检索 | storage |
| 20 | `backend/retrieval/mcp_server.py` | Retrieval MCP server | retrieval 模块 |
| 21 | `tests/contract/` | MCP 契约测试 | MCP servers |
| 22 | `tests/integration/test_ingest_e2e.py` | ingest 端到端测试 | pipeline |

### 第三周做（Day 11-15）

| # | 任务 | 产出 | 依赖 |
|---|------|------|------|
| 23 | `.claude/settings.json` | MCP 注册 + 权限 + hooks | MCP servers 可用 |
| 24 | `.claude/CLAUDE.md` + `rules/` | 路由规则 + 纪律约束 | 无 |
| 25 | `.claude/skills/` 5 个 skill | 用户入口 | settings.json |
| 26 | `.claude/agents/ingest-operator.md` | 批量 ingest subagent | skills |
| 27 | 端到端冒烟测试 | 手动跑完整场景 | 全部以上 |
| 28 | Bug fix + prompt 调优 | 修复实际使用发现的问题 | 冒烟测试 |

### 第一版先不做

| 任务 | 理由 |
|------|------|
| Analysis MCP Server（独立 Python 服务） | Phase 1 用 LLM 原生能力做分析，不需要独立 backend |
| GROBID 集成 | Phase 2，先用 PyMuPDF |
| 引用图谱 | Phase 2，依赖 GROBID 的 reference 解析 |
| compare_papers / synthesize_topic tool | Phase 2/3 |
| Docker 化 | Phase 2 |
| Plugin 打包 | Phase 2，等组件稳定 |
| source-hunter / evidence-miner subagent | MVP 后根据实际使用决定是否需要 |
| Semantic Scholar API 搜索 | MVP 用 arXiv 够了 |
| Web UI | Phase 3+，独立项目 |
| 多用户 / 团队协作 | 远期 |

### 后续版本规划

| 版本 | 任务 |
|------|------|
| v0.2 | GROBID 解析、引用图谱、Analysis MCP Server、compare_papers、Plugin 打包 |
| v0.3 | synthesize_topic、综述生成、coordinator mode 多 agent 协作 |
| v0.4 | Docker Compose 部署、HTTP transport、远程 MCP server |
| v1.0 | Marketplace 发布、文档完善、性能优化 |
