# 03：Claude Code 侧改造——Prompt、Skills、Subagents、Hooks、Plugin

> 本文档聚焦 orchestrator 壳层改造。默认 backend schema、状态机、MCP tool 契约已定（见 [02_schema_and_tool_contracts](02_schema_and_tool_contracts.md)）。
>
> 关联文档：[00_master_index](00_master_index.md) · [01_architecture_and_boundaries](01_architecture_and_boundaries.md) · [02_schema_and_tool_contracts](02_schema_and_tool_contracts.md) · [04_implementation_plan](04_implementation_plan.md)

---

## 1. 主 Prompt 最小增补方案

### 设计原则

不替换 Claude Code 的 SE 人格。只在 system prompt 末尾追加一个 `paperWorkflowSection`，通过 CLAUDE.md 或 plugin instructions 注入。以下是可直接插入的规则片段：

```
# Academic Paper Workflow

You have access to a paper management backend via MCP tools. When the user's request
involves academic papers, literature review, or research evidence, follow these rules.

## Routing Rules

1. DETECT paper intent: If the user mentions papers, literature, citations, research
   findings, surveys, or asks questions that require academic evidence — route to
   paper tools. Do NOT attempt to answer research questions from your training data
   alone when paper tools are available.

2. ROUTE by intent:
   - "search/find papers about X" → search_papers
   - "download/ingest this paper" → ingest_paper (single) or batch_ingest (multiple)
   - "what does the literature say about X" → retrieve_evidence, then synthesize
   - "analyze this paper" → analyze_paper
   - "compare these papers" → compare_papers
   - "write a review/survey of X" → synthesize_topic
   - "what's the status of ingestion" → get_ingest_status

3. NEVER fabricate paper titles, authors, DOIs, or citations. If you cannot find a
   paper through search_papers or retrieve_evidence, say so explicitly.

4. For batch operations (>3 papers), use batch_ingest and track progress with
   get_ingest_status. Do not call ingest_paper in a loop.

## Evidence-First Discipline

5. When making claims about research findings, ALWAYS back them with retrieve_evidence
   results. Present evidence in this order:
   - The claim
   - The supporting text (direct quote from chunk)
   - The source (paper title, authors, year, section)
   - Confidence/relevance score

6. If retrieve_evidence returns no relevant hits (all scores < 0.3), explicitly tell
   the user: "I found no strong evidence for this in the ingested papers." Do NOT
   fall back to training-data knowledge without disclosure.

7. When presenting multiple pieces of evidence, group by paper, not by claim.
   Always include paper_id for traceability.

## Structured Output Constraints

8. When presenting paper search results, use a table:
   | # | Title | Authors | Year | Venue | Citations | Ingested? |

9. When presenting retrieval hits, use this format per hit:
   > "[quoted text]"
   > — *Paper Title* (Author et al., Year), §Section, p.Page, score: X.XX

10. When presenting analysis results, preserve the structure returned by analyze_paper:
    Summary → Contributions → Methodology → Key Findings → Limitations.
    Do not flatten or rewrite unless the user asks for a different format.

11. For comparison results, always render the comparison matrix as a markdown table.

## Operational Rules

12. Long-running operations (batch_ingest, synthesize_topic) MUST be tracked via
    TodoWrite. Update todo status as each stage completes.

13. When an MCP tool returns an error with retryable=true, retry ONCE automatically.
    If it fails again, report the error_code and error_message to the user.
    When retryable=false, report immediately without retrying.

14. Do NOT read or write files in the data/ directory directly. All paper data
    operations go through MCP tools. The backend owns the storage layer.

15. When the user's request mixes coding tasks and paper tasks, handle them
    sequentially: finish the paper operation (or start it in background), then
    proceed with coding. Do not interleave MCP tool calls with file edits on
    the same turn.
```

### 注入方式

| 方式 | 具体做法 | 优缺点 |
|------|---------|--------|
| **CLAUDE.md 注入**（推荐 Phase 1） | 将上述规则写入 `.claude/CLAUDE.md` | 零代码改动、立即生效、项目级隔离 |
| **Plugin instructions 注入**（推荐 Phase 2+） | Plugin manifest 的 `instructions` 字段 | 可分发、可版本管理、安装即生效 |
| **systemPromptSection 代码注入** | 修改 `src/constants/prompts.ts` 注册新 section | 需改源码，不推荐 |

**Phase 1 实操**：直接写入 `.claude/CLAUDE.md`，格式如下：

```markdown
# Paper Workflow Rules

<上述英文规则片段原文>

# Coding Rules (preserved)

You remain a capable coding assistant. Paper workflow rules only activate when
the user's request involves academic papers. For all other tasks, follow your
default behavior.
```

---

## 2. CLAUDE.md / MEMORY.md 设计

### 2.1 分层规则

```
┌──────────────────────────────────────────────────────────┐
│ 主 Prompt (system prompt)                                │
│ 不改。保留 SE agent 完整能力。                             │
│ 论文规则不注入这里。                                       │
└──────────────────────────────────────────────────────────┘
         │ 加载优先级低于 ↓
┌──────────────────────────────────────────────────────────┐
│ .claude/CLAUDE.md (项目级，版本控制)                       │
│ 放什么：                                                  │
│ ① 论文工具 routing 规则（§1 的 15 条）                     │
│ ② evidence-first 纪律                                    │
│ ③ 结构化输出格式约束                                       │
│ ④ 错误处理策略（retryable/non-retryable）                  │
│ ⑤ 操作边界（不要直接读写 data/ 目录）                       │
│ ⑥ 批量操作规范（用 batch_ingest 而非循环）                  │
└──────────────────────────────────────────────────────────┘
         │ 加载优先级低于 ↓
┌──────────────────────────────────────────────────────────┐
│ .claude/CLAUDE.local.md (本地覆盖，gitignore)              │
│ 放什么：                                                  │
│ ① 本地 API key 相关提示（如"arXiv API 无需 key"）          │
│ ② 本地 GROBID 地址覆盖                                    │
│ ③ 个人偏好覆盖（如"我只关心 NLP 领域"）                     │
└──────────────────────────────────────────────────────────┘
         │ 独立加载 ↓
┌──────────────────────────────────────────────────────────┐
│ .claude/memory/MEMORY.md (自动记忆)                       │
│ 放什么：                                                  │
│ ① 用户常用搜索领域 (e.g. "user focuses on NLP/LLM")       │
│ ② 用户偏好的引用格式 (e.g. "user prefers APA style")       │
│ ③ 用户常用 paper 来源 (e.g. "user prefers arXiv over S2")  │
│ ④ 已知的 ingest 问题 (e.g. "papers from X.org often 403")  │
│                                                          │
│ 不放什么：                                                │
│ ✗ 路由规则（属于 CLAUDE.md）                               │
│ ✗ schema 定义（属于 backend）                              │
│ ✗ 当前 ingest 进度（临时状态，属于 backend）                │
│ ✗ paper_id 列表（太长、会变、应查 backend）                 │
│ ✗ prompt 模板（属于 skill/config）                         │
└──────────────────────────────────────────────────────────┘
```

### 2.2 CLAUDE.md 分文件策略

当规则超过 200 行时，利用 `@include` 拆分：

```markdown
# .claude/CLAUDE.md (主文件，保持简洁)

@.claude/rules/paper-routing.md
@.claude/rules/paper-output-format.md
@.claude/rules/paper-error-handling.md
@.claude/rules/coding-preserved.md
```

每个子文件 < 100 行，单一职责。

### 2.3 MEMORY.md 防过载策略

| 策略 | 做法 |
|------|------|
| 行数硬限 | MEMORY.md 不超过 50 行（系统限 200 行，留余量给其他记忆） |
| 只记稳定模式 | 至少出现 3 次的偏好才写入 MEMORY.md |
| 不记临时状态 | 不记 paper_id、不记 job_id、不记搜索历史 |
| 子话题文件 | 论文相关细节记忆放 `.claude/memory/paper-preferences.md`，从 MEMORY.md 用一行链接 |
| 定期清理 | 每 session 开始时检查 MEMORY.md 中论文相关记忆是否过时 |

---

## 3. Skills 设计

> skill = 用户可通过 `/` 命令触发的高层论文操作入口。每个 skill 是一个 markdown 文件 + frontmatter 元数据。

### 3.1 paper_search

```yaml
# .claude/skills/paper-search.md frontmatter
---
name: paper-search
description: Search academic papers across arXiv, Semantic Scholar, and local library
aliases: [search-papers, find-papers, lit-search]
whenToUse: >
  When the user wants to find papers on a topic, search for specific papers,
  or discover relevant literature. NOT for querying already-ingested papers.
allowedTools:
  - mcp__paper_ingest__search_papers
  - mcp__paper_retrieval__retrieve_evidence
  - TodoWrite
  - AskUserQuestion
model: null  # use default
---
```

| 维度 | 说明 |
|------|------|
| **职责边界** | 接收用户的搜索意图 → 调 `search_papers` → 呈现结果表格 → 可选：询问用户是否 ingest |
| **输入** | 用户自然语言搜索请求（topic、年份范围、来源偏好） |
| **输出** | 论文列表（表格格式），含 already_ingested 标记 |
| **不应负责** | 不做 ingest、不做分析、不直接下载 PDF |
| **调用方式** | 直接调用 MCP tool `search_papers`，不需要 subagent |

**Prompt 核心逻辑**：

```markdown
You are handling a paper search request.

1. Extract search parameters from the user's message:
   - query keywords
   - year range (if mentioned)
   - source preference (if mentioned)
   - max results (default 20)

2. Call search_papers with extracted parameters.

3. Present results as a markdown table:
   | # | Title | Authors | Year | Venue | Cited | In Library? |

4. After presenting results, ask:
   "Would you like me to ingest any of these papers? You can specify by number
   (e.g., '1,3,5') or say 'all'."

5. If the user selects papers, hand off to /paper-ingest with the selected URLs.
```

---

### 3.2 paper_ingest

```yaml
---
name: paper-ingest
description: Download, parse, and index papers into the local library
aliases: [ingest-paper, ingest, download-paper]
whenToUse: >
  When the user provides paper URLs/DOIs and wants them added to the local library.
  Also triggered as follow-up from paper-search.
allowedTools:
  - mcp__paper_ingest__ingest_paper
  - mcp__paper_ingest__batch_ingest
  - mcp__paper_ingest__get_ingest_status
  - mcp__paper_ingest__fetch_pdf
  - TodoWrite
  - AskUserQuestion
model: null
---
```

| 维度 | 说明 |
|------|------|
| **职责边界** | 接收 URL/DOI 列表 → 调 `ingest_paper` 或 `batch_ingest` → 轮询 `get_ingest_status` → 报告结果 |
| **输入** | 一个或多个 paper URL/DOI/arXiv ID |
| **输出** | ingest 结果摘要（成功/失败/跳过数量，paper_id 列表） |
| **不应负责** | 不做搜索、不做分析、不直接操作文件系统 |
| **调用方式** | 单篇→直接 MCP；多篇→委托给 `ingest-operator` subagent（后台运行） |

**Prompt 核心逻辑**：

```markdown
You are handling a paper ingest request.

1. Parse the user's input to extract URLs, DOIs, or arXiv IDs.
   - If arXiv ID like "2401.12345", convert to URL: https://arxiv.org/abs/2401.12345
   - If DOI, pass as-is to ingest_paper with doi parameter

2. For 1-3 papers: call ingest_paper sequentially, wait for each.
   For 4+ papers: call batch_ingest, then poll get_ingest_status every 10 seconds.

3. Use TodoWrite to track progress:
   - "Ingesting paper 1/N: [title or URL]" → in_progress
   - Mark completed/failed as status updates arrive

4. Report final summary:
   - ✓ N papers ingested successfully
   - ✗ N papers failed (with error details)
   - → N papers skipped (already in library)

5. For failures with retryable=true, ask user: "N papers had retryable errors.
   Want me to retry them?"
```

---

### 3.3 paper_evidence_retrieve

```yaml
---
name: paper-evidence
description: Retrieve evidence from ingested papers to answer research questions
aliases: [query-papers, find-evidence, ask-papers]
whenToUse: >
  When the user asks a research question that should be answered using evidence
  from ingested papers. NOT for general knowledge questions.
allowedTools:
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **职责边界** | 接收研究问题 → 转化为 retrieval query → 调 `retrieve_evidence` → 结构化呈现 evidence + source |
| **输入** | 用户自然语言研究问题，可选 paper_id 范围限定 |
| **输出** | 带来源追踪的 evidence 列表（按论文分组） |
| **不应负责** | 不做分析推理（只呈现原文证据）、不做搜索（只查已入库论文） |
| **调用方式** | 直接 MCP tool |

**Prompt 核心逻辑**：

```markdown
You are retrieving evidence from the paper library.

1. Transform the user's question into an effective retrieval query:
   - Remove conversational filler
   - Preserve domain-specific terms
   - If the question is broad, consider splitting into 2-3 sub-queries

2. Call retrieve_evidence with:
   - query: the optimized query
   - top_k: 10 (increase to 20 if user seems to want comprehensive results)
   - paper_ids: only if user specified specific papers
   - section_types: infer from question context
     (e.g., methodology question → ["methodology"], results question → ["experiments"])

3. Present results grouped by paper:

   ### Paper: "[Title]" (Author, Year)

   **[Section Type] (p.XX, score: 0.XX)**
   > "Direct quote from retrieved chunk..."

   **[Section Type] (p.XX, score: 0.XX)**
   > "Another relevant quote..."

4. After presenting evidence, add a brief synthesis:
   "Based on N evidence chunks from M papers, the key themes are: ..."

5. If all scores < 0.3 or no results:
   "I found no strong evidence for this in the ingested papers. Consider:
   - Searching for more papers with /paper-search
   - Rephrasing your question
   - The answer may not be covered by the current library"
```

---

### 3.4 paper_analyze

```yaml
---
name: paper-analyze
description: Deep structured analysis of a single paper
aliases: [analyze-paper, paper-analysis, deep-read]
whenToUse: >
  When the user wants a thorough analysis of a specific paper, including
  methodology breakdown, key findings, limitations, and contributions.
allowedTools:
  - mcp__paper_ingest__analyze_paper
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **职责边界** | 接收 paper_id 或论文标识 → 确认已 ingest → 调 `analyze_paper` → 呈现结构化分析 |
| **输入** | paper_id，或论文标题/URL（需先解析为 paper_id） |
| **输出** | AnalysisResult 的结构化呈现 |
| **不应负责** | 不做多篇比较、不做综述、不做 ingest |
| **调用方式** | 直接 MCP tool（Phase 1 可 sync）。若用户未指定 focus 则用 "standard" depth |

**Prompt 核心逻辑**：

```markdown
You are performing deep analysis on a single paper.

1. Resolve paper identity:
   - If paper_id given: use directly
   - If URL/title given: use retrieve_evidence with title as query to find paper_id
   - If paper not ingested: suggest user run /paper-ingest first

2. Check paper status via get_ingest_status. Only proceed if status="ready".

3. Infer analysis focus from user's request:
   - "how does this paper work" → focus="methodology"
   - "what did they find" → focus="experiments"
   - No specific angle → focus=null (comprehensive)

4. Call analyze_paper with paper_id, focus, and depth:
   - Quick question about the paper → depth="quick"
   - "analyze this paper" → depth="standard"
   - "deep dive" / "thorough analysis" → depth="deep"

5. Present the AnalysisResult preserving structure:

   ## Summary
   [summary]

   ## Main Contributions
   - [contribution 1]
   - [contribution 2]

   ## Methodology
   [methodology description]

   ## Key Findings
   - [finding 1]
   - [finding 2]

   ## Limitations
   - [limitation 1]

   ## Future Directions
   - [direction 1]

6. If evidence is available, append source references after each section.
```

---

### 3.5 paper_compare (Phase 2)

```yaml
---
name: paper-compare
description: Structured comparison of multiple papers
aliases: [compare-papers, paper-comparison, diff-papers]
whenToUse: >
  When the user wants to compare 2-10 papers across specific dimensions.
allowedTools:
  - mcp__paper_ingest__compare_papers
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **职责边界** | 接收多个 paper_id → 确认都已 ingest → 调 `compare_papers` → 呈现比较矩阵 |
| **输入** | 2-10 个 paper_id + 可选的比较维度 |
| **输出** | CompareResult 的表格化呈现 |
| **不应负责** | 不做单篇分析、不做综述 |
| **调用方式** | 直接 MCP tool（async，需轮询） |

---

### 3.6 paper_synthesize (Phase 3)

```yaml
---
name: paper-synthesize
description: Generate a literature review or survey on a topic
aliases: [write-review, literature-review, survey, synthesize]
whenToUse: >
  When the user wants to generate a comprehensive literature review or survey
  synthesizing multiple papers on a topic.
allowedTools:
  - mcp__paper_ingest__synthesize_topic
  - mcp__paper_ingest__search_papers
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - mcp__paper_ingest__batch_ingest
  - TodoWrite
  - AskUserQuestion
model: null
---
```

| 维度 | 说明 |
|------|------|
| **职责边界** | 接收综述主题 → 可选搜索+ingest 更多论文 → 调 `synthesize_topic` → 呈现综述 + 参考文献 |
| **输入** | 综述主题 + 可选大纲 + 可选论文范围 |
| **输出** | SynthesisResult 的完整呈现（含 bibliography） |
| **不应负责** | 不做单篇分析 |
| **调用方式** | 委托给 `synthesis-writer` subagent（长时间任务，需多轮 tool 调用） |

---

### 3.7 paper_status

```yaml
---
name: paper-status
description: Check ingestion status, library overview, and backend health
aliases: [status, library-status]
whenToUse: >
  When the user asks about the status of paper ingestion, library contents,
  or backend health.
allowedTools:
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **职责边界** | 调 `get_ingest_status` → 呈现 job 或 paper 状态 |
| **调用方式** | 直接 MCP tool，简单 skill |

---

### Skills 目录结构

```
.claude/skills/
├── paper-search.md          # Phase 1
├── paper-ingest.md          # Phase 1
├── paper-evidence.md        # Phase 1
├── paper-analyze.md         # Phase 1
├── paper-status.md          # Phase 1
├── paper-compare.md         # Phase 2
└── paper-synthesize.md      # Phase 3
```

---

## 4. Subagents 设计

> subagent = 后台或长时间运行的专用执行者。通过 AgentTool 启动，拥有独立上下文和受限工具集。
>
> 设计原则：按**工作流阶段**而非**人设角色**划分。每个 subagent 有明确的输入→处理→输出边界。

### 4.1 source-hunter

```yaml
# .claude/agents/source-hunter.md
---
name: source-hunter
description: Autonomously search and discover papers across multiple sources
allowedTools:
  - mcp__paper_ingest__search_papers
  - mcp__paper_retrieval__retrieve_evidence
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **适用任务** | 需要广泛搜索（多个 query 变体 × 多个来源 × 多页翻页）才能汇总出候选论文列表的场景 |
| **上游依赖** | 用户提供主题描述或初始关键词 |
| **下游输出** | 去重后的论文候选列表 `[{title, url, pdf_url, source, relevance_note}]` |
| **最小上下文** | 搜索主题 + 年份/领域约束 + 当前库中已有论文的 paper_id 列表（避免重复推荐） |
| **调用哪些 tool** | `search_papers`（多次，不同 query 变体）、`retrieve_evidence`（查库内已有，避免重复） |
| **何时不该调用** | 用户已给出具体 URL/DOI（直接走 ingest）；只查 1-2 个 query（skill 直接搞定） |

**Prompt 要点**：

```markdown
You are a paper discovery agent. Your job is to find relevant papers comprehensively.

Strategy:
1. Generate 3-5 query variants from the user's topic (synonyms, related terms, key authors)
2. Search each variant across available sources
3. Deduplicate results by title similarity (>90% match = same paper)
4. Rank by relevance to the original topic
5. Return the top N candidates with a brief relevance note for each

Do NOT ingest papers. Only discover and list them.
```

---

### 4.2 ingest-operator

```yaml
---
name: ingest-operator
description: Manage batch paper ingestion with progress tracking and error handling
allowedTools:
  - mcp__paper_ingest__batch_ingest
  - mcp__paper_ingest__ingest_paper
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **适用任务** | 批量 ingest 4+ 篇论文，需要持续监控进度和处理失败 |
| **上游依赖** | source-hunter 或 skill 提供的 URL 列表 |
| **下游输出** | `{ingested_paper_ids: string[], failed: IngestError[], skipped: string[]}` |
| **最小上下文** | URL 列表 + IngestOptions |
| **调用哪些 tool** | `batch_ingest` → 轮询 `get_ingest_status` → 对 retryable 失败调 `ingest_paper` 重试 |
| **何时不该调用** | 仅 1-3 篇论文（skill 直接处理更快） |

**Prompt 要点**：

```markdown
You are an ingestion operator. Manage the batch ingest pipeline.

1. Call batch_ingest with the provided URLs.
2. Poll get_ingest_status(job_id) every 15 seconds.
3. Update TodoWrite with current progress after each poll.
4. When job completes:
   - For retryable failures: retry each once with ingest_paper.
   - For non-retryable failures: log error details.
5. Return final summary to the parent agent.

Do NOT search for papers. Do NOT analyze papers. Only ingest and track.
```

---

### 4.3 evidence-miner

```yaml
---
name: evidence-miner
description: Deep evidence extraction with multi-query retrieval strategy
allowedTools:
  - mcp__paper_retrieval__retrieve_evidence
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **适用任务** | 复杂研究问题需要多角度检索（多 query、多 section type、分领域检索）才能覆盖完整证据 |
| **上游依赖** | 用户研究问题 + 可选的 paper_id 范围 |
| **下游输出** | 去重、排序后的 `Evidence[]`，按论文分组 |
| **最小上下文** | 研究问题文本 + paper_id 范围 + 期望的 evidence 数量 |
| **调用哪些 tool** | `retrieve_evidence`（多次，不同 query 变体和 section_type 过滤） |
| **何时不该调用** | 简单的单 query 检索（skill 直接处理）；用户只想搜索外部论文（用 source-hunter） |

**Prompt 要点**：

```markdown
You are an evidence mining agent. Extract comprehensive evidence for a research question.

Strategy:
1. Decompose the research question into 2-4 sub-questions.
2. For each sub-question, call retrieve_evidence with:
   - Optimized query text
   - Appropriate section_type filter (e.g., methodology, experiments)
   - top_k=15
3. Merge results across sub-queries, deduplicate by chunk_id.
4. Re-rank by relevance to the original question.
5. Group by paper, annotate each piece of evidence with:
   - Which sub-question it answers
   - Confidence assessment

Return structured evidence, not synthesis. Do NOT draw conclusions.
```

---

### 4.4 paper-analyst

```yaml
---
name: paper-analyst
description: Single-paper deep analysis with evidence-backed structure
allowedTools:
  - mcp__paper_ingest__analyze_paper
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **适用任务** | 单篇论文 deep depth 分析，需要额外检索上下文（如对比同领域其他论文的方法） |
| **上游依赖** | paper_id（must be `ready`） |
| **下游输出** | AnalysisResult + 额外的跨论文上下文注释 |
| **最小上下文** | paper_id + focus + depth |
| **调用哪些 tool** | `analyze_paper` + 可选 `retrieve_evidence`（获取同领域对比上下文） |
| **何时不该调用** | quick depth 分析（skill 直接调 analyze_paper）；多篇比较（用 compare-analyst） |

---

### 4.5 compare-analyst (Phase 2)

```yaml
---
name: compare-analyst
description: Multi-paper structured comparison with evidence tracking
allowedTools:
  - mcp__paper_ingest__compare_papers
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---
```

| 维度 | 说明 |
|------|------|
| **适用任务** | 5+ 篇论文的复杂比较，需要自动推断比较维度 |
| **上游依赖** | paper_id 列表（all `ready`）+ 可选比较维度 |
| **下游输出** | CompareResult |
| **何时不该调用** | 仅 2 篇论文的简单比较（skill 直接处理） |

---

### 4.6 synthesis-writer (Phase 3)

```yaml
---
name: synthesis-writer
description: Generate comprehensive literature review with full citation tracking
allowedTools:
  - mcp__paper_ingest__synthesize_topic
  - mcp__paper_ingest__search_papers
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__batch_ingest
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
  - AskUserQuestion
model: null
---
```

| 维度 | 说明 |
|------|------|
| **适用任务** | 完整综述生成：搜索 → 补充 ingest → 检索证据 → 生成综述 |
| **上游依赖** | 用户提供主题 + 可选大纲 + 可选论文范围 |
| **下游输出** | SynthesisResult |
| **何时不该调用** | 简单的单篇摘要（用 paper-analyst）；简单的证据查询（用 evidence-miner） |

---

### Subagents 目录结构

```
.claude/agents/
├── source-hunter.md         # Phase 1
├── ingest-operator.md       # Phase 1
├── evidence-miner.md        # Phase 1
├── paper-analyst.md         # Phase 1 (但 deep analysis 是 Phase 2 才完善)
├── compare-analyst.md       # Phase 2
└── synthesis-writer.md      # Phase 3
```

### Skill vs Subagent 调用决策表

| 场景 | 用 Skill 直接处理 | 委托 Subagent |
|------|-------------------|--------------|
| 搜索 1-2 个 query | ✅ paper-search skill | ❌ |
| 广泛搜索（5+ query 变体） | ❌ | ✅ source-hunter |
| ingest 1-3 篇 | ✅ paper-ingest skill | ❌ |
| ingest 4+ 篇 | ❌ | ✅ ingest-operator |
| 单 query 检索 | ✅ paper-evidence skill | ❌ |
| 多角度深度检索 | ❌ | ✅ evidence-miner |
| quick/standard 分析 | ✅ paper-analyze skill | ❌ |
| deep 分析 + 跨论文对比 | ❌ | ✅ paper-analyst |
| 2 篇简单比较 | ✅ paper-compare skill | ❌ |
| 5+ 篇复杂比较 | ❌ | ✅ compare-analyst |
| 综述生成 | ❌ | ✅ synthesis-writer |

---

## 5. Hooks 设计

> hook = 不应该依赖 LLM "记得去做"的确定性逻辑。通过 Claude Code 的 lifecycle hook 机制（settings.json 配置）固化为 shell command 或 agent hook。

### 5.1 Hook 总览

| 优先级 | Hook 名称 | 触发时机 | 类型 | Phase |
|--------|----------|---------|------|-------|
| P0 | `post-ingest-verify` | ingest_paper / batch_ingest 返回后 | PostToolUse | 1 |
| P0 | `post-retrieve-cite` | retrieve_evidence 返回后 | PostToolUse | 1 |
| P1 | `post-analyze-evidence-check` | analyze_paper 返回后 | PostToolUse | 1 |
| P1 | `pre-batch-confirm` | batch_ingest 调用前 | PreToolUse | 1 |
| P2 | `post-ingest-auto-analyze` | ingest 完成后自动触发快速分析 | PostToolUse | 2 |
| P2 | `session-start-index-check` | 会话开始时 | SessionStart | 2 |
| P2 | `post-compare-format` | compare_papers 返回后 | PostToolUse | 2 |

---

### 5.2 Hook 详细设计

#### (A) post-ingest-verify (P0)

**目的**：ingest tool 返回后，自动校验结果状态，将错误信息结构化提醒给 agent。

```json
{
  "matcher": "mcp__paper_ingest__ingest_paper OR mcp__paper_ingest__batch_ingest",
  "type": "prompt",
  "prompt": "The ingest tool just returned. Check the response: (1) If any errors have retryable=true, note them for potential retry. (2) If status shows papers skipped due to DEDUP_CONFLICT, inform the user with existing paper_ids. (3) If all succeeded, confirm with paper count and suggest next steps (analyze or search more)."
}
```

**为什么不让 LLM 自己记**：LLM 可能跳过 error 检查直接告诉用户"已完成"，即使部分失败。

---

#### (B) post-retrieve-cite (P0)

**目的**：retrieve_evidence 返回后，强制 agent 在呈现结果时附带来源引用。

```json
{
  "matcher": "mcp__paper_retrieval__retrieve_evidence",
  "type": "prompt",
  "prompt": "Evidence retrieved. MANDATORY: When presenting these results to the user, you MUST include for each hit: (1) the exact quoted text, (2) paper title + authors + year, (3) section type and page number, (4) relevance score. Do NOT paraphrase evidence without quoting the original. Do NOT omit source attribution."
}
```

**为什么不让 LLM 自己记**：引用纪律是最容易被 LLM "偷懒"省略的——它倾向于 paraphrase 而非引用。

---

#### (C) post-analyze-evidence-check (P1)

**目的**：analyze_paper 返回后，检查 AnalysisResult 中的 evidence 数组是否为空。如果无证据支撑，提醒 agent 补充。

```json
{
  "matcher": "mcp__paper_ingest__analyze_paper",
  "type": "prompt",
  "prompt": "Analysis result received. Check: If the result contains empty evidence array or no evidence for key findings, call retrieve_evidence to get supporting quotes before presenting to the user. Every key finding should have at least one evidence reference."
}
```

---

#### (D) pre-batch-confirm (P1)

**目的**：batch_ingest 调用前，强制确认。避免意外批量 ingest 大量论文。

```json
{
  "matcher": "mcp__paper_ingest__batch_ingest",
  "type": "prompt",
  "prompt": "About to call batch_ingest. Before proceeding: (1) Confirm with the user the number of papers to be ingested. (2) If >20 papers, warn about processing time. (3) If >50 papers, strongly recommend doing it in smaller batches."
}
```

**为什么用 hook**：防止 source-hunter 或其他 subagent 不经用户确认就批量 ingest。

---

#### (E) post-ingest-auto-analyze (P2)

**目的**：单篇 ingest 成功后，自动触发 quick depth 分析，让用户不用手动再调 analyze。

```json
{
  "matcher": "mcp__paper_ingest__ingest_paper",
  "type": "prompt",
  "prompt": "Paper ingested successfully. If this was a single paper ingest (not part of a batch), automatically call analyze_paper with depth='quick' to provide the user with an immediate summary. Present it as: 'Here is a quick overview of the paper you just ingested:'"
}
```

---

#### (F) session-start-index-check (P2)

**目的**：每次会话开始时，检查 backend 状态。

```json
{
  "type": "shell",
  "command": "python backend/scripts/health_check.py --format json",
  "timeout": 5000
}
```

Shell 脚本输出 JSON：
```json
{
  "backend_available": true,
  "paper_count": 142,
  "index_healthy": true,
  "papers_stuck": 0,
  "last_ingest": "2024-01-15T10:30:00Z"
}
```

**为什么用 hook**：确保每次会话都检查 backend，而非依赖 LLM 记得去检查。

---

#### (G) post-compare-format (P2)

**目的**：compare_papers 返回后，强制将 CompareResult 渲染为 markdown 表格。

```json
{
  "matcher": "mcp__paper_ingest__compare_papers",
  "type": "prompt",
  "prompt": "Comparison result received. You MUST present the comparison as a markdown table with papers as columns and dimensions as rows. Include the dimension name in the first column, and each paper's value in subsequent columns. Add source references below the table."
}
```

---

### 5.3 Hook 配置位置

所有 hook 写入 `.claude/settings.json` 的 `hooks` 字段。Phase 2+ 迁移到 plugin manifest。

```jsonc
// .claude/settings.json (部分)
{
  "hooks": {
    "PostToolUse": [
      // post-ingest-verify
      {
        "matcher": "mcp__paper_ingest__ingest_paper",
        "type": "prompt",
        "prompt": "..."
      },
      // post-retrieve-cite
      {
        "matcher": "mcp__paper_retrieval__retrieve_evidence",
        "type": "prompt",
        "prompt": "..."
      }
      // ... 其他 PostToolUse hooks
    ],
    "PreToolUse": [
      // pre-batch-confirm
      {
        "matcher": "mcp__paper_ingest__batch_ingest",
        "type": "prompt",
        "prompt": "..."
      }
    ],
    "SessionStart": [
      // session-start-index-check (Phase 2)
    ]
  }
}
```

---

## 6. Settings / 权限 / Plugin Packaging

### 6.1 Settings 配置

```jsonc
// .claude/settings.json
{
  // === MCP Server 注册 ===
  "mcpServers": {
    "paper-ingest": {
      "command": "python",
      "args": ["-m", "backend.ingest.mcp_server"],
      "cwd": "./backend",
      "env": {
        "PAPER_DATA_DIR": "./data",
        "EMBEDDING_MODEL": "all-MiniLM-L6-v2"
      }
    },
    "paper-retrieval": {
      "command": "python",
      "args": ["-m", "backend.retrieval.mcp_server"],
      "cwd": "./backend",
      "env": {
        "PAPER_DATA_DIR": "./data"
      }
    }
    // Phase 2: "paper-analysis" MCP server
  },

  // === 权限 ===
  "permissions": {
    "allow": [
      "mcp__paper_ingest__search_papers",
      "mcp__paper_ingest__ingest_paper",
      "mcp__paper_ingest__get_ingest_status",
      "mcp__paper_ingest__fetch_pdf",
      "mcp__paper_retrieval__retrieve_evidence",
      "mcp__paper_ingest__analyze_paper"
    ],
    "deny": []
  },

  // === Hooks ===
  "hooks": {
    // ... 见 §5.3
  }
}
```

### 6.2 权限策略明细

| 操作类型 | 建议权限 | 理由 |
|---------|---------|------|
| `search_papers` | **auto-allow** | 只读，无副作用 |
| `retrieve_evidence` | **auto-allow** | 只读，无副作用 |
| `get_ingest_status` | **auto-allow** | 只读 |
| `analyze_paper` | **auto-allow** | 只读（不修改数据） |
| `ingest_paper` | **auto-allow** | 有写入但用户已通过 skill 明确意图 |
| `batch_ingest` | **ask（通过 pre-batch-confirm hook）** | 批量操作需确认 |
| `reindex_paper` | **ask** | 可能耗时长、影响索引可用性 |
| `fetch_pdf` | **auto-allow** | 只下载，不入库 |
| `compare_papers` | **auto-allow** | 只读分析 |
| `synthesize_topic` | **ask** | 长时间任务、消耗 LLM token |

### 6.3 目录访问控制

| 目录 | 允许 agent 直接读写？ | 理由 |
|------|---------------------|------|
| `.claude/skills/` | 只读 | 不应运行时修改 skill |
| `.claude/agents/` | 只读 | 不应运行时修改 agent 定义 |
| `.claude/memory/` | 读写 | auto-memory 需要写入 |
| `backend/` | 只读 | agent 不应修改 backend 代码（除非用户明确要求 debug） |
| `data/` | **禁止** | 所有数据操作通过 MCP tool 间接进行 |
| `data/logs/` | 只读 | 允许查看日志排查问题 |
| `configs/` | 只读 | 配置修改应通过明确操作 |

在 CLAUDE.md 中明确写入：
```
NEVER read or write files under data/pdfs/, data/db/, data/index/ directly.
All paper data operations MUST go through MCP tools.
You may READ files under data/logs/ for debugging purposes only.
```

### 6.4 Plugin Packaging（Phase 2+）

当所有组件稳定后，打包为一个 Claude Code plugin：

```
paper-workflow-plugin/
├── manifest.json              # Plugin manifest
├── skills/                    # 所有论文 skills
│   ├── paper-search.md
│   ├── paper-ingest.md
│   ├── paper-evidence.md
│   ├── paper-analyze.md
│   ├── paper-compare.md
│   └── paper-synthesize.md
├── agents/                    # 所有论文 subagents
│   ├── source-hunter.md
│   ├── ingest-operator.md
│   ├── evidence-miner.md
│   ├── paper-analyst.md
│   ├── compare-analyst.md
│   └── synthesis-writer.md
├── instructions.md            # CLAUDE.md 内容（plugin 安装后自动注入）
└── README.md
```

**manifest.json**：

```jsonc
{
  "name": "paper-workflow",
  "version": "0.1.0",
  "description": "Academic paper search, ingest, retrieval, and analysis workflow",
  "skillsPaths": ["skills"],
  "agentsPaths": ["agents"],
  "instructions": "instructions.md",
  "hooksConfig": {
    "PostToolUse": [
      // post-ingest-verify, post-retrieve-cite, post-analyze-evidence-check
    ],
    "PreToolUse": [
      // pre-batch-confirm
    ]
  },
  "mcpServers": {
    "paper-ingest": {
      "command": "python",
      "args": ["-m", "backend.ingest.mcp_server"],
      "env": { "PAPER_DATA_DIR": "./data" }
    },
    "paper-retrieval": {
      "command": "python",
      "args": ["-m", "backend.retrieval.mcp_server"],
      "env": { "PAPER_DATA_DIR": "./data" }
    }
  },
  "setupCommand": "cd backend && pip install -e .",
  "requiredTools": ["Bash", "TodoWrite", "AskUserQuestion", "AgentTool"]
}
```

### 6.5 必须保持的 Coding Agent 能力

改造后 Claude Code 必须保留的原生能力（不被论文平台覆盖）：

| 能力 | 保留方式 |
|------|---------|
| 代码读写编辑 | 所有原生工具不受影响（Read, Edit, Write, Grep, Glob） |
| Bash 执行 | 保留，但 CLAUDE.md 约束不直接操作 data/ |
| Git 操作 | 保留，论文 skill 不注册任何 git 相关约束 |
| 项目理解 | Explore agent 等保留 |
| SE 领域 system prompt | 不替换，论文规则只是追加 |
| 非论文用户请求 | CLAUDE.md 明确"论文规则仅在检测到论文意图时激活" |
