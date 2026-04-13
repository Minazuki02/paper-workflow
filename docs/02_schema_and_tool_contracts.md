# 02：Schema 定义、状态机、MCP Tool 接口契约、可观测性

> 本文档定义全部 15 个数据 schema、Paper 状态机与失败恢复策略、10 个 MCP tool 接口契约、统一错误码体系、以及可观测性/日志设计。
>
> 关联文档：[00_master_index](00_master_index.md) · [01_architecture_and_boundaries](01_architecture_and_boundaries.md) · [03_claude_code_adaptation](03_claude_code_adaptation.md) · [04_implementation_plan](04_implementation_plan.md)

---

> 标注约定：
> - `[B]` = 仅 backend 内部使用
> - `[O]` = orchestrator / agent 可见（通过 MCP tool 返回）
> - `[B+O]` = 两侧都用
> - `req` = 必填, `opt` = 选填
> - Phase 标注表示该 schema 在哪个阶段引入

---

## 1. Schema 设计

### 1.1 Paper

核心实体。一篇论文在系统中的全局表示。

```typescript
interface Paper {
  // === 标识 ===
  paper_id:       string    // req [B+O] UUID v4，系统内唯一标识
  doi:            string | null  // opt [B+O] DOI，用于去重和外部引用
  arxiv_id:       string | null  // opt [B+O] arXiv ID (e.g. "2401.12345v2")
  semantic_scholar_id: string | null  // opt [B] S2 corpus ID

  // === 元数据 ===
  title:          string    // req [B+O] 论文标题
  authors:        Author[]  // req [B+O] 作者列表
  abstract:       string    // opt [B+O] 摘要全文
  year:           number | null  // opt [B+O] 发表年份
  venue:          string | null  // opt [B+O] 会议/期刊名称
  keywords:       string[]  // opt [B+O] 关键词
  url:            string | null  // opt [B+O] 原始 URL（landing page）
  pdf_url:        string | null  // opt [B] 直接 PDF 下载链接

  // === 状态 ===
  status:         PaperStatus   // req [B+O] 当前处理状态（见状态机）
  ingested_at:    string | null // opt [B+O] ISO 8601 入库完成时间
  updated_at:     string        // req [B]   最后更新时间

  // === 存储 ===
  pdf_path:       string | null // opt [B] 本地 PDF 文件路径（相对于 data/pdfs/）
  pdf_hash:       string | null // opt [B] PDF 文件 SHA-256，用于去重和校验

  // === 统计 ===
  chunk_count:    number    // opt [B+O] 已切分 chunk 数量
  section_count:  number    // opt [B+O] 已识别 section 数量
  citation_count: number    // opt [B+O] 引用条目数量（该论文引了多少别的论文）
}

interface Author {
  name:           string    // req [B+O]
  affiliation:    string | null  // opt [B+O]
  email:          string | null  // opt [B]
}
```

---

### 1.2 PaperSource

记录论文的发现来源，支持溯源和去重。

```typescript
interface PaperSource {
  source_id:      string    // req [B] UUID
  paper_id:       string    // req [B] FK → Paper
  source_type:    "arxiv" | "semantic_scholar" | "pubmed" | "manual_url" | "local_file" | "citation_crawl"
                            // req [B+O] 来源类型
  source_query:   string | null  // opt [B] 触发发现的搜索 query
  source_url:     string    // req [B] 来源 URL
  discovered_at:  string    // req [B] 发现时间 ISO 8601
  confidence:     number    // opt [B] 来源可信度 0.0-1.0（可调整：视是否需要而定）
}
```

---

### 1.3 IngestJob

批量/单篇 ingest 的任务追踪实体。

```typescript
interface IngestJob {
  job_id:         string    // req [B+O] UUID
  job_type:       "single" | "batch"  // req [B+O]
  status:         JobStatus // req [B+O] "pending"|"running"|"completed"|"partial"|"failed"|"cancelled"
  created_at:     string    // req [B+O] ISO 8601
  started_at:     string | null  // opt [B+O]
  completed_at:   string | null  // opt [B+O]

  // === 输入 ===
  paper_urls:     string[]  // req [B] 待处理 URL 列表
  total_count:    number    // req [B+O] 总论文数

  // === 进度 ===
  succeeded:      number    // req [B+O] 成功数
  failed:         number    // req [B+O] 失败数
  skipped:        number    // req [B+O] 跳过数（如已存在/去重）
  in_progress:    number    // req [B+O] 进行中

  // === 结果 ===
  paper_ids:      string[]  // opt [B+O] 成功入库的 paper_id 列表
  errors:         IngestError[]  // opt [B+O] 错误详情

  // === 配置 ===
  options:        IngestOptions  // opt [B] 本次 ingest 的配置覆盖
}

interface IngestError {
  url:            string    // [B+O] 失败的 URL
  stage:          PaperStatus  // [B+O] 失败发生在哪个阶段
  error_code:     string    // [B+O] 错误码（见 §3 错误码设计）
  error_message:  string    // [B+O] 人类可读错误信息
  retryable:      boolean   // [B+O] 是否可重试
}

interface IngestOptions {
  skip_existing:  boolean   // 默认 true，遇到已有论文跳过
  force_reparse:  boolean   // 默认 false，强制重新解析
  max_retries:    number    // 默认 3
  parser:         "pymupdf" | "grobid"  // 默认 "pymupdf"，Phase 2 支持 grobid
}
```

---

### 1.4 ParseResult

PDF 解析的中间产物。backend 内部使用为主，部分字段可暴露给 orchestrator 做质量判断。

```typescript
interface ParseResult {
  parse_id:       string    // req [B] UUID
  paper_id:       string    // req [B] FK → Paper
  parser_used:    "pymupdf" | "grobid"  // req [B+O]
  parsed_at:      string    // req [B]

  // === 质量指标 ===
  page_count:     number    // req [B+O] PDF 总页数
  char_count:     number    // req [B] 提取总字符数
  confidence:     number    // opt [B+O] 解析置信度 0.0-1.0（推测：可基于提取完整性估算）
  has_ocr:        boolean   // opt [B+O] 是否经过 OCR
  encoding_issues: boolean  // opt [B] 是否存在编码问题

  // === 结构化输出 ===
  raw_text:       string    // req [B] 全文纯文本（不含格式）
  sections:       Section[] // opt [B] 抽取的 section 列表
  figures:        Figure[]  // opt [B] 抽取的图表列表（Phase 2）
  tables:         Table[]   // opt [B] 抽取的表格列表（Phase 2）
  references_raw: string[]  // opt [B] 原始参考文献文本列表
}
```

---

### 1.5 Section

论文的结构化章节。

```typescript
interface Section {
  section_id:     string    // req [B] UUID
  paper_id:       string    // req [B] FK → Paper
  heading:        string    // req [B+O] 章节标题 (e.g. "3. Methodology")
  section_type:   SectionType  // req [B+O] 语义类型
  level:          number    // req [B] 层级深度 (1=顶级, 2=子章节, ...)
  order_index:    number    // req [B] 在论文中的顺序位置
  text:           string    // req [B] 章节全文
  char_count:     number    // req [B] 字符数
  parent_id:      string | null  // opt [B] 父章节 section_id
}

type SectionType =
  | "abstract"
  | "introduction"
  | "related_work"
  | "methodology"    // 也包括 "methods", "approach"
  | "experiments"    // 也包括 "evaluation", "results"
  | "discussion"
  | "conclusion"
  | "appendix"
  | "references"     // 参考文献区域
  | "other"          // 无法识别
```

---

### 1.6 Chunk

检索的最小单元。chunk 切分策略由 backend 控制。

```typescript
interface Chunk {
  chunk_id:       string    // req [B+O] UUID
  paper_id:       string    // req [B+O] FK → Paper
  section_id:     string | null  // opt [B] FK → Section（可能跨 section 的 chunk 为 null）

  // === 内容 ===
  text:           string    // req [B+O] chunk 文本
  char_count:     number    // req [B] 字符数
  token_count:    number    // opt [B] token 数（推测：按 embedding 模型 tokenizer 计算）

  // === 定位 ===
  order_index:    number    // req [B] 在论文中的顺序
  page_start:     number | null  // opt [B+O] 起始页码
  page_end:       number | null  // opt [B+O] 结束页码

  // === 向量 ===
  embedding:      number[] | null  // opt [B] 向量表示（不通过 MCP 传输，太大）
  embedding_model: string   // req [B] 使用的 embedding 模型名称

  // === 上下文元数据 ===
  section_type:   SectionType | null  // opt [B+O] 来源 section 的语义类型（冗余，加速过滤检索）
  heading:        string | null       // opt [B+O] 来源 section 标题（冗余，方便展示）
}
```

**重要设计决策**：`embedding` 字段不通过 MCP tool 返回给 orchestrator（向量维度 384-1536，序列化开销大且 agent 无法直接使用）。检索完全在 backend 内部完成。

---

### 1.7 Figure (Phase 2)

```typescript
interface Figure {
  figure_id:      string    // req [B] UUID
  paper_id:       string    // req [B] FK → Paper
  figure_number:  string    // req [B+O] 原始编号 (e.g. "Figure 3", "Fig. 2a")
  caption:        string    // req [B+O] 图注文本
  image_path:     string | null  // opt [B] 截图文件路径（相对于 data/parsed/）
  page:           number    // opt [B+O] 所在页码
  section_id:     string | null  // opt [B] 所属章节
  mentioned_in:   string[]  // opt [B] 引用该图的 chunk_id 列表
}
```

---

### 1.8 Table (Phase 2)

```typescript
interface Table {
  table_id:       string    // req [B] UUID
  paper_id:       string    // req [B] FK → Paper
  table_number:   string    // req [B+O] 原始编号 (e.g. "Table 1")
  caption:        string    // req [B+O] 表注
  headers:        string[]  // opt [B+O] 表头列名
  rows:           string[][] // opt [B+O] 表格内容（二维字符串数组）
  raw_text:       string    // opt [B] 表格的纯文本表示
  page:           number    // opt [B+O] 所在页码
  section_id:     string | null  // opt [B]
}
```

---

### 1.9 Citation / Reference

论文间的引用关系。

```typescript
// 论文中的单条参考文献
interface Reference {
  reference_id:   string    // req [B] UUID
  paper_id:       string    // req [B] FK → Paper（引用方）
  order_index:    number    // req [B] 参考文献列表中的位置 (e.g. [1], [2])

  // === 被引论文信息（可能不在库中）===
  cited_paper_id: string | null  // opt [B+O] FK → Paper（如果被引论文已入库）
  cited_title:    string    // req [B+O] 被引论文标题
  cited_authors:  string    // opt [B+O] 被引作者字符串
  cited_year:     number | null  // opt [B+O]
  cited_venue:    string | null  // opt [B+O]
  cited_doi:      string | null  // opt [B] 被引 DOI
  raw_text:       string    // req [B] 原始参考文献文本

  // === 引用上下文 ===
  citing_contexts: CitingContext[]  // opt [B+O] 正文中引用该文献的上下文
}

interface CitingContext {
  chunk_id:       string    // [B+O] 出现引用的 chunk
  text_snippet:   string    // [B+O] 引用处的上下文文本（前后约 200 字符）
  citation_intent: CitationIntent | null  // [B+O] 引用意图（推测：可调整，Phase 2+ 可由 LLM 分类）
}

type CitationIntent =
  | "background"      // 背景引用
  | "method_use"      // 使用了被引论文的方法
  | "comparison"      // 与被引论文进行比较
  | "extension"       // 在被引论文基础上扩展
  | "criticism"       // 批评或指出局限
  | "other"
```

---

### 1.10 RetrievalHit

检索结果的标准化表示。不持久化——仅作为 MCP tool 返回值的运行时结构。

```typescript
interface RetrievalHit {
  // === 命中目标 ===
  chunk_id:       string    // req [O] 命中的 chunk
  paper_id:       string    // req [O] 所属论文
  text:           string    // req [O] chunk 文本

  // === 排序信息 ===
  score:          number    // req [O] 综合相关性分数 0.0-1.0
  vector_score:   number | null  // opt [O] 向量检索分数（如果参与）
  text_score:     number | null  // opt [O] 全文检索分数（如果参与）

  // === 上下文 ===
  paper_title:    string    // req [O] 论文标题（冗余，方便展示）
  authors:        string    // req [O] 作者列表字符串
  year:           number | null  // opt [O]
  section_type:   SectionType | null  // opt [O]
  heading:        string | null       // opt [O] 所属章节标题
  page_start:     number | null       // opt [O]

  // === 高亮 ===
  highlights:     string[] | null  // opt [O] 关键词匹配高亮片段（全文检索时）
}
```

---

### 1.11 Evidence

从论文中抽取的证据项。用于支撑分析结论。

```typescript
interface Evidence {
  evidence_id:    string    // req [O] UUID
  claim:          string    // req [O] 证据所支撑的论断 (e.g. "Attention is more efficient than RNN")
  text:           string    // req [O] 证据原文
  chunk_id:       string    // req [O] 来源 chunk
  paper_id:       string    // req [O] 来源论文
  paper_title:    string    // req [O] 论文标题（冗余）
  section_type:   SectionType | null  // opt [O]
  confidence:     number    // req [O] 证据强度 0.0-1.0（LLM 判断）
  evidence_type:  "quantitative" | "qualitative" | "methodological" | "theoretical"
                            // req [O] 证据类型
  page:           number | null  // opt [O]
}
```

---

### 1.12 AnalysisTask

分析任务的追踪实体。

```typescript
interface AnalysisTask {
  task_id:        string    // req [B+O] UUID
  task_type:      "single_paper" | "comparison" | "evidence_extraction" | "synthesis" | "trend"
                            // req [B+O]
  status:         JobStatus // req [B+O] 同 IngestJob 的 JobStatus
  created_at:     string    // req [B+O]
  completed_at:   string | null  // opt [B+O]

  // === 输入 ===
  paper_ids:      string[]  // req [B+O] 分析对象论文列表
  focus:          string | null  // opt [B+O] 分析聚焦方向 (e.g. "methodology", "performance")
  user_query:     string | null  // opt [B+O] 用户原始提问

  // === 输出 ===
  result_id:      string | null  // opt [B+O] 指向具体 result 实体
  error:          string | null  // opt [B+O] 错误信息
}
```

---

### 1.13 AnalysisResult

单篇论文深度分析的结果。

```typescript
interface AnalysisResult {
  result_id:      string    // req [O] UUID
  task_id:        string    // req [O] FK → AnalysisTask
  paper_id:       string    // req [O] 分析的论文

  // === 结构化分析 ===
  summary:        string    // req [O] 一段式核心摘要（200-500 字）
  contributions:  string[]  // req [O] 主要贡献列表
  methodology:    string    // req [O] 方法论描述
  key_findings:   string[]  // req [O] 关键发现列表
  limitations:    string[]  // opt [O] 局限性列表
  future_work:    string[]  // opt [O] 未来方向

  // === 证据链 ===
  evidence:       Evidence[]  // opt [O] 支撑各结论的证据

  // === 元信息 ===
  model_used:     string    // req [B+O] 生成分析的 LLM 模型
  generated_at:   string    // req [B+O] ISO 8601
  token_cost:     number | null  // opt [B] LLM token 消耗
}
```

---

### 1.14 CompareResult (Phase 2)

多篇论文比较的结果。

```typescript
interface CompareResult {
  result_id:      string    // req [O] UUID
  task_id:        string    // req [O] FK → AnalysisTask
  paper_ids:      string[]  // req [O] 参与比较的论文
  focus:          string    // req [O] 比较维度

  // === 比较矩阵 ===
  dimensions:     CompareDimension[]  // req [O] 比较维度列表
  summary:        string    // req [O] 比较总结
  recommendation: string | null  // opt [O] 推荐/结论

  // === 来源 ===
  evidence:       Evidence[]  // opt [O]
  model_used:     string    // req [B+O]
  generated_at:   string    // req [B+O]
}

interface CompareDimension {
  dimension:      string    // req [O] 比较维度名 (e.g. "Model Architecture", "Dataset Used")
  entries:        CompareEntry[]  // req [O]
}

interface CompareEntry {
  paper_id:       string    // req [O]
  paper_title:    string    // req [O]
  value:          string    // req [O] 该论文在此维度的值/描述
  evidence_id:    string | null  // opt [O] 支撑证据
}
```

---

### 1.15 SynthesisResult (Phase 3)

综述/综合分析的结果。

```typescript
interface SynthesisResult {
  result_id:      string    // req [O] UUID
  task_id:        string    // req [O] FK → AnalysisTask
  topic:          string    // req [O] 综述主题
  paper_ids:      string[]  // req [O] 纳入综述的论文

  // === 综述内容 ===
  outline:        SynthesisSection[]  // req [O] 综述大纲 + 内容
  abstract:       string    // req [O] 综述摘要
  word_count:     number    // req [O] 总字数

  // === 来源追踪 ===
  citation_map:   Record<string, string[]>  // req [O] paragraph_id → [evidence_id] 映射
  bibliography:   BibEntry[]  // req [O] 参考文献列表

  // === 元信息 ===
  model_used:     string    // req [B+O]
  generated_at:   string    // req [B+O]
}

interface SynthesisSection {
  section_id:     string    // req [O]
  heading:        string    // req [O]
  content:        string    // req [O] 该节正文（markdown）
  subsections:    SynthesisSection[]  // opt [O] 子节
}

interface BibEntry {
  ref_key:        string    // req [O] 引用键 (e.g. "[1]", "[Smith2024]")
  paper_id:       string    // req [O] FK → Paper
  formatted:      string    // req [O] 格式化后的参考文献条目
}
```

---

### Schema 引入阶段总结

| Schema | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| Paper | ✅ 完整 | 追加 citation_count | — |
| PaperSource | ✅ 基础 | 追加 citation_crawl | — |
| IngestJob | ✅ 完整 | 追加 retry 相关 | — |
| ParseResult | ✅ 基础（无 figure/table） | 追加 figure/table | — |
| Section | ✅ 完整 | — | — |
| Chunk | ✅ 完整 | — | — |
| Figure | — | ✅ | — |
| Table | — | ✅ | — |
| Citation/Reference | — | ✅ | — |
| RetrievalHit | ✅ 完整 | 追加 highlights | — |
| Evidence | ✅ 基础 | 追加 evidence_type | — |
| AnalysisTask | ✅ 完整 | — | — |
| AnalysisResult | ✅ 完整 | — | — |
| CompareResult | — | ✅ | — |
| SynthesisResult | — | — | ✅ |

---

## 2. 状态机与失败恢复

### 2.1 Paper 状态机

```
                          ┌──────────────────────────────────┐
                          │          失败可重试               │
                          │  ┌─────────────────────────┐     │
                          │  │                         │     │
 ┌──────────┐    ┌────────▼──┴─┐    ┌──────────┐    ┌─┴─────▼───┐
 │discovered├───►│  queued     ├───►│downloading├───►│downloaded │
 └──────────┘    └─────────────┘    └─────┬─────┘    └─────┬─────┘
                                          │                │
                                          │ fail           │
                                          ▼                ▼
                                    ┌──────────┐    ┌──────────┐
                                    │  failed  │    │ parsing  │
                                    │(terminal)│    └─────┬────┘
                                    └──────────┘          │
                                          ▲               ▼
                                          │         ┌──────────┐
                                          │ fail    │  parsed  │
                                          ├─────────┴─────┬────┘
                                          │               │
                                          │               ▼
                                          │         ┌──────────┐
                                          │ fail    │ chunked  │
                                          ├─────────┴─────┬────┘
                                          │               │
                                          │               ▼
                                          │         ┌──────────┐
                                          │ fail    │ embedding│
                                          ├─────────┴─────┬────┘
                                          │               │
                                          │               ▼
                                          │         ┌──────────┐
                                          │ fail    │ indexed  │
                                          ├─────────┴─────┬────┘
                                          │               │
                                          │               ▼
                                          │         ┌──────────┐
                                          └─────────┤  ready   │
                                                    └─────┬────┘
                                                          │ 用户手动
                                                          ▼
                                                    ┌──────────┐
                                                    │ archived │
                                                    └──────────┘

      retrying 不是独立状态，而是 failed → queued 的转移动作（附带 retry_count++）
```

### 2.2 状态定义

```typescript
type PaperStatus =
  | "discovered"   // 通过搜索/引用爬取发现，尚未启动 ingest
  | "queued"       // 已加入 ingest 队列，等待处理
  | "downloading"  // 正在下载 PDF
  | "downloaded"   // PDF 下载完成，校验通过
  | "parsing"      // 正在解析 PDF（PyMuPDF 或 GROBID）
  | "parsed"       // 解析完成，结构化数据已产出
  | "chunked"      // chunk 切分完成
  | "embedding"    // 正在计算 embedding
  | "indexed"      // embedding 已写入向量索引，元数据已写入 SQLite
  | "ready"        // 全流程完成，可供检索和分析
  | "failed"       // 处理失败（附带 error_code + error_stage + retry_count）
  | "archived"     // 用户手动归档，从检索中移除但数据保留
```

### 2.3 合法状态转移表

| 当前状态 → | 合法目标状态 | 触发条件 |
|-----------|-------------|---------|
| `discovered` | `queued` | 用户或 batch_ingest 发起 ingest |
| `queued` | `downloading` | worker 取到任务 |
| `downloading` | `downloaded` | PDF 下载完成且 hash 校验通过 |
| `downloading` | `failed` | 下载超时 / 404 / 网络错误（超出重试上限） |
| `downloaded` | `parsing` | 解析 worker 开始处理 |
| `parsing` | `parsed` | 解析完成 |
| `parsing` | `failed` | 解析异常（加密 PDF / 损坏 / 无文本） |
| `parsed` | `chunked` | chunk 切分完成 |
| `chunked` | `embedding` | 开始计算 embedding |
| `embedding` | `indexed` | embedding 写入向量索引完成 |
| `indexed` | `ready` | 元数据校验通过，全部就绪 |
| 任何 `failed` | `queued` | 重试（retry_count < max_retries） |
| `ready` | `archived` | 用户手动归档 |
| `archived` | `queued` | 用户手动恢复 → 重新 ingest |
| `ready` | `queued` | 用户请求重新 ingest（force_reparse=true） |

**禁止的转移**：不允许跳过中间状态（如 `downloading` → `ready`），必须逐步流转以保证每一步的产物完整。

### 2.4 失败分类与恢复策略

| 失败场景 | 发生阶段 | 错误码 | 可自动重试 | 重试策略 | 人工介入条件 |
|---------|---------|--------|----------|---------|-------------|
| 网络超时 | downloading | `DOWNLOAD_TIMEOUT` | ✅ | 指数退避，3次，base=5s | 连续 3 次超时 |
| HTTP 404 | downloading | `DOWNLOAD_NOT_FOUND` | ❌ | — | 通知用户 URL 无效 |
| HTTP 403/429 | downloading | `DOWNLOAD_RATE_LIMITED` | ✅ | 指数退避，5次，base=30s | 连续 5 次被限 |
| PDF 损坏/无法打开 | parsing | `PARSE_CORRUPT_PDF` | ❌ | — | 通知用户 |
| PDF 加密 | parsing | `PARSE_ENCRYPTED` | ❌ | — | 通知用户需解密 |
| PDF 纯扫描件无文本 | parsing | `PARSE_NO_TEXT` | ❌ fallback | 尝试 OCR（Phase 2），否则标记失败 | 通知用户 |
| GROBID 服务不可用 | parsing | `PARSE_GROBID_UNAVAILABLE` | ✅ fallback | fallback 到 PyMuPDF | GROBID 持续不可用 |
| embedding 模型 OOM | embedding | `EMBED_OOM` | ✅ | 减小 batch size 重试 | 持续 OOM |
| embedding 模型不可用 | embedding | `EMBED_MODEL_UNAVAILABLE` | ✅ | 等待 + 重试，3次 | 模型配置错误 |
| FAISS 索引写入失败 | indexed | `INDEX_WRITE_FAILED` | ✅ | 重试 3 次 | 磁盘空间不足 |
| SQLite 写入失败 | indexed | `DB_WRITE_FAILED` | ✅ | 重试 3 次 | 数据库锁定或损坏 |
| 去重冲突 | queued | `DEDUP_CONFLICT` | ❌ skip | 跳过并标记 skipped | — |

### 2.5 Retry Policy

```typescript
interface RetryPolicy {
  max_retries:        3        // 默认最大重试次数
  base_delay_sec:     5        // 基础延迟（秒）
  max_delay_sec:      300      // 最大延迟 5 分钟
  backoff_factor:     2        // 指数退避因子
  jitter:             true     // 添加随机抖动避免雪崩
  retry_on:           string[] // 可重试的错误码白名单
}

// 阶段级 retry policy 覆盖
const STAGE_RETRY_POLICIES: Record<string, Partial<RetryPolicy>> = {
  downloading: { max_retries: 5, base_delay_sec: 10 },  // 网络操作多给几次
  parsing:     { max_retries: 2, base_delay_sec: 3 },   // 解析失败大概率是固有问题
  embedding:   { max_retries: 3, base_delay_sec: 5 },
  indexing:    { max_retries: 3, base_delay_sec: 2 },
}
```

### 2.6 Fallback 策略

| 场景 | 主路径 | Fallback 路径 | 触发条件 |
|------|--------|-------------|---------|
| PDF 解析 | GROBID (Phase 2) | PyMuPDF | GROBID 不可用或解析失败 |
| 元数据提取 | PDF 解析结果 | 外部 API 查询（Semantic Scholar / CrossRef） | 标题/作者缺失 |
| embedding 模型 | 首选模型 (e.g. `all-MiniLM-L6-v2`) | 备选模型 (e.g. `paraphrase-MiniLM-L3-v2`) | 首选模型不可用（推测：可调整） |
| PDF 下载源 | 原始 URL | arXiv 镜像 / Semantic Scholar PDF | 原始 URL 不可达 |

---

## 3. MCP / 外部 Tool 接口设计

> 所有 tool 通过 MCP protocol 暴露。输入输出均为 JSON。
> 约定：异步 tool 返回 `job_id`，caller 通过 `get_ingest_status` 轮询。

---

### 3.1 search_papers

**功能**：在外部学术搜索引擎中搜索论文（不查本地库）。

```yaml
tool: search_papers
sync: true
batchable: false

input:
  query:          string    # req - 搜索关键词
  source:         "arxiv" | "semantic_scholar" | "all"  # opt, default "all"
  year_from:      number | null    # opt - 起始年份
  year_to:        number | null    # opt - 截止年份
  max_results:    number           # opt, default 20, max 100
  sort_by:        "relevance" | "date" | "citations"  # opt, default "relevance"

output:
  results:        SearchResult[]
  total_found:    number           # 总命中数（可能远大于返回数）
  source_used:    string           # 实际使用的搜索源

SearchResult:
  title:          string
  authors:        string
  year:           number | null
  abstract:       string           # 摘要（可能截断）
  url:            string           # landing page URL
  pdf_url:        string | null    # PDF 直链（如果有）
  doi:            string | null
  citation_count: number | null
  source:         string           # 来自哪个搜索引擎
  already_ingested: boolean        # 是否已在本地库中

errors:
  SEARCH_RATE_LIMITED:    "搜索 API 限流，请稍后重试"
  SEARCH_API_ERROR:       "搜索 API 返回错误"
  SEARCH_TIMEOUT:         "搜索超时"
  SEARCH_INVALID_QUERY:   "搜索词无效"
```

---

### 3.2 fetch_pdf

**功能**：下载单个 PDF 到本地，但不触发 ingest pipeline。用于预览或手动操作。

```yaml
tool: fetch_pdf
sync: true (但可能耗时几十秒)
batchable: false

input:
  url:            string    # req - PDF URL
  filename:       string | null  # opt - 指定文件名，默认自动命名

output:
  success:        boolean
  pdf_path:       string           # 本地存储路径
  file_size_bytes: number
  pdf_hash:       string           # SHA-256
  already_exists: boolean          # 是否已有相同 hash 的文件

errors:
  DOWNLOAD_TIMEOUT:       "下载超时（默认 120s）"
  DOWNLOAD_NOT_FOUND:     "URL 返回 404"
  DOWNLOAD_RATE_LIMITED:  "下载被限流"
  DOWNLOAD_INVALID_URL:   "URL 格式无效"
  DOWNLOAD_NOT_PDF:       "下载内容不是 PDF 格式"
  DOWNLOAD_TOO_LARGE:     "PDF 超过大小限制（默认 100MB）"
```

---

### 3.3 ingest_paper

**功能**：完整 ingest 单篇论文（下载 → 解析 → chunk → embedding → 入库）。

```yaml
tool: ingest_paper
sync: false (返回 job_id，通过 get_ingest_status 轮询)
batchable: false (单篇用此接口；批量用 batch_ingest)

input:
  url:            string    # req - PDF URL 或 arXiv URL
  doi:            string | null  # opt - 如已知 DOI 可辅助去重
  skip_if_exists: boolean         # opt, default true
  parser:         "pymupdf" | "grobid"  # opt, default "pymupdf"

output:
  job_id:         string           # ingest job ID
  paper_id:       string | null    # 如果 skip_if_exists=true 且已存在，直接返回
  status:         "queued" | "skipped"
  message:        string

errors:
  INGEST_INVALID_URL:     "URL 格式无效或不可达"
  INGEST_DEDUP_CONFLICT:  "论文已存在（返回已有 paper_id）"
  INGEST_QUEUE_FULL:      "ingest 队列已满，请稍后"
```

---

### 3.4 batch_ingest

**功能**：批量 ingest 多篇论文。

```yaml
tool: batch_ingest
sync: false (返回 job_id)
batchable: N/A (自身就是批量接口)

input:
  urls:           string[]         # req - URL 列表，max 100
  options:        IngestOptions    # opt - 见 §1.3 IngestOptions

output:
  job_id:         string           # batch job ID
  total_count:    number
  queued_count:   number           # 实际入队数（去除已存在的）
  skipped_count:  number           # 跳过数
  skipped_urls:   SkipInfo[]       # 跳过详情

SkipInfo:
  url:            string
  reason:         "already_exists" | "invalid_url" | "duplicate_in_batch"
  existing_paper_id: string | null

errors:
  INGEST_BATCH_TOO_LARGE: "批量数超过上限（100）"
  INGEST_QUEUE_FULL:      "队列已满"
```

---

### 3.5 retrieve_evidence

**功能**：从已入库论文中检索与 query 相关的 chunk，返回结构化 RetrievalHit。

```yaml
tool: retrieve_evidence
sync: true
batchable: false

input:
  query:          string    # req - 自然语言检索 query
  top_k:          number    # opt, default 10, max 50
  paper_ids:      string[] | null  # opt - 限定在这些论文中检索；null = 全库
  section_types:  SectionType[] | null  # opt - 限定 section 类型
  year_from:      number | null
  year_to:        number | null
  search_mode:    "hybrid" | "vector" | "text"  # opt, default "hybrid"
  min_score:      number    # opt, default 0.3

output:
  hits:           RetrievalHit[]    # 见 §1.10
  total_candidates: number          # 初筛候选数
  search_mode_used: string
  query_embedding_ms: number        # query embedding 耗时（ms）
  search_ms:      number            # 检索耗时（ms）

errors:
  RETRIEVE_EMPTY_INDEX:   "向量索引为空，请先 ingest 论文"
  RETRIEVE_INVALID_PAPER: "指定的 paper_id 不存在"
  RETRIEVE_QUERY_TOO_LONG: "query 超长（>2000 字符）"
  RETRIEVE_MODEL_ERROR:   "embedding 模型错误"
```

---

### 3.6 analyze_paper

**功能**：对单篇论文进行深度结构化分析。

```yaml
tool: analyze_paper
sync: false (Phase 1 可做 sync，因为分析时间可控；Phase 2 转 async)
batchable: false

input:
  paper_id:       string    # req
  focus:          string | null    # opt - 分析聚焦方向 (e.g. "methodology", "experiments")
  depth:          "quick" | "standard" | "deep"  # opt, default "standard"
                  # quick: 仅摘要+贡献，~15s
                  # standard: 完整分析，~30-60s
                  # deep: 含证据链+局限性+未来方向，~60-120s

output:
  # depth=quick 或 sync 模式
  task_id:        string
  result:         AnalysisResult | null  # sync 模式直接返回；async 模式为 null
  status:         "completed" | "queued"

errors:
  ANALYZE_PAPER_NOT_FOUND:  "paper_id 不存在"
  ANALYZE_PAPER_NOT_READY:  "论文尚未完成 ingest（status != ready）"
  ANALYZE_LLM_ERROR:        "LLM 调用失败"
  ANALYZE_CONTEXT_TOO_LONG: "论文内容超出 LLM 上下文窗口"
```

---

### 3.7 compare_papers (Phase 2)

**功能**：多篇论文结构化比较。

```yaml
tool: compare_papers
sync: false
batchable: false

input:
  paper_ids:      string[]  # req, min 2, max 10
  dimensions:     string[] | null  # opt - 指定比较维度；null = 自动识别
                  # e.g. ["model architecture", "dataset", "performance metrics"]
  focus:          string | null    # opt - 比较聚焦方向

output:
  task_id:        string
  result:         CompareResult | null
  status:         "completed" | "queued"

errors:
  COMPARE_TOO_FEW_PAPERS:  "至少需要 2 篇论文"
  COMPARE_TOO_MANY_PAPERS: "最多支持 10 篇论文"
  COMPARE_PAPER_NOT_READY: "部分论文尚未完成 ingest"
  COMPARE_LLM_ERROR:       "LLM 调用失败"
```

---

### 3.8 synthesize_topic (Phase 3)

**功能**：围绕一个主题，基于多篇论文生成综述。

```yaml
tool: synthesize_topic
sync: false (长时间任务)
batchable: false

input:
  topic:          string    # req - 综述主题
  paper_ids:      string[] | null  # opt - 指定论文；null = 自动检索相关论文
  max_papers:     number    # opt, default 20
  outline:        string[] | null  # opt - 用户自定义大纲节标题
  target_words:   number    # opt, default 3000
  style:          "academic" | "survey" | "blog"  # opt, default "academic"

output:
  task_id:        string
  status:         "queued"

errors:
  SYNTH_TOPIC_TOO_BROAD:   "主题过于宽泛，建议缩窄"
  SYNTH_NOT_ENOUGH_PAPERS: "相关论文不足（<3 篇）"
  SYNTH_LLM_ERROR:         "LLM 调用失败"
```

---

### 3.9 get_ingest_status

**功能**：查询 ingest job 或单篇论文的处理状态。

```yaml
tool: get_ingest_status
sync: true
batchable: false

input:
  # 二选一
  job_id:         string | null    # 查 ingest job 整体状态
  paper_id:       string | null    # 查单篇论文状态

output:
  # 当查 job
  job:            IngestJob | null       # 见 §1.3
  # 当查 paper
  paper:          Paper | null           # 见 §1.1（仅返回状态相关字段子集）
  current_stage:  PaperStatus
  progress:       string                 # 人类可读进度描述
  errors:         IngestError[]          # 当前未解决的错误
  retry_count:    number
  estimated_remaining_sec: number | null # 预估剩余时间（推测：粗略估算）

errors:
  STATUS_NOT_FOUND:  "job_id 或 paper_id 不存在"
```

---

### 3.10 reindex_paper

**功能**：对已入库论文重新生成 embedding 并更新索引。用于 embedding 模型升级或索引损坏恢复。

```yaml
tool: reindex_paper
sync: false
batchable: true (支持 paper_ids 列表)

input:
  paper_ids:      string[]  # req - 要重建索引的论文列表；传 ["*"] 表示全库重建
  embedding_model: string | null  # opt - 指定新模型；null = 使用当前默认模型
  force:          boolean   # opt, default false - true 时即使 embedding 没变也重建

output:
  job_id:         string
  papers_affected: number

errors:
  REINDEX_PAPER_NOT_FOUND: "paper_id 不存在"
  REINDEX_PAPER_NOT_READY: "论文状态不是 ready/indexed"
  REINDEX_MODEL_ERROR:     "指定的 embedding 模型不可用"
  REINDEX_IN_PROGRESS:     "该论文正在被其他 reindex job 处理"
```

---

### 错误码体系总结

```
错误码命名规范: {DOMAIN}_{SPECIFIC_ERROR}

域 (DOMAIN):
  SEARCH_     搜索相关
  DOWNLOAD_   PDF 下载相关
  INGEST_     ingest pipeline 相关
  PARSE_      PDF 解析相关
  EMBED_      embedding 相关
  INDEX_      索引相关
  RETRIEVE_   检索相关
  ANALYZE_    分析相关
  COMPARE_    比较相关
  SYNTH_      综述相关
  STATUS_     状态查询相关
  REINDEX_    重建索引相关
  DB_         数据库相关
  SYSTEM_     系统级错误

通用错误码（适用所有 tool）:
  SYSTEM_INTERNAL_ERROR:   "内部错误"
  SYSTEM_NOT_INITIALIZED:  "backend 未初始化"
  SYSTEM_DISK_FULL:        "磁盘空间不足"
```

每个 MCP tool 的错误返回统一格式：

```typescript
interface ToolError {
  error:          true
  error_code:     string    // 上述错误码之一
  error_message:  string    // 人类可读描述，可直接呈现给用户
  retryable:      boolean   // 是否建议重试
  details:        Record<string, any> | null  // 附加调试信息
}
```

---

## 4. 可观测性 / 日志设计

### 4.1 日志分层

```
┌─────────────────────────────────────────────────────────┐
│  Orchestrator 层 (Claude Code)                          │
│  ─ skill/subagent 调用日志                               │
│  ─ MCP tool 调用日志（request/response/latency）         │
│  ─ 用户会话上下文                                        │
│  → 看什么: 用户意图是否被正确理解和路由                     │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│  MCP 通信层                                              │
│  ─ tool call trace (tool_name, input_hash, duration_ms)  │
│  ─ 序列化/反序列化错误                                    │
│  → 看什么: 通信是否正常、延迟是否异常                       │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│  Backend 层 (Python)                                     │
│  ─ ingest pipeline 逐阶段日志                             │
│  ─ 检索诊断日志                                          │
│  ─ 分析 LLM 调用日志                                     │
│  ─ 存储操作日志                                          │
│  → 看什么: 处理是否正确、性能瓶颈在哪里                     │
└─────────────────────────────────────────────────────────┘
```

### 4.2 日志类型明细

#### (A) Ingest Job Logs

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | ISO 8601 | 事件时间 |
| `job_id` | string | ingest job ID |
| `paper_id` | string | 当前处理的论文 |
| `stage` | PaperStatus | 当前阶段 |
| `event` | `"stage_start"` \| `"stage_end"` \| `"stage_error"` \| `"retry"` \| `"skip"` | 事件类型 |
| `duration_ms` | number | 阶段耗时 |
| `details` | object | 阶段特定数据（如文件大小、chunk 数等） |
| `error` | ToolError \| null | 错误信息 |

**格式**：JSON Lines（每行一条），写入 `data/logs/ingest/{date}.jsonl`

**排查什么**：某篇论文卡在哪个阶段；批量 ingest 的整体吞吐量；哪些 URL 频繁失败；解析器选择是否合适

---

#### (B) Per-Paper Trace

每篇论文的完整生命周期 trace，用于问题复盘。

```typescript
interface TraceEvent {
  timestamp:      string
  stage:          PaperStatus
  event:          string        // e.g. "download_start", "parse_complete", "chunk_split"
  duration_ms:    number | null
  metadata:       Record<string, any>  // 阶段特定元数据
  // 示例 metadata:
  // download: { url, file_size_bytes, http_status }
  // parse:    { parser, page_count, char_count, confidence }
  // chunk:    { chunk_count, avg_chunk_size, strategy }
  // embed:    { model, dimension, batch_size }
  // index:    { vector_index_size, db_rows_written }
}
```

**格式**：JSON，存入 SQLite `paper_traces` 表（或独立 JSON 文件 `data/logs/traces/{paper_id}.json`）

**排查什么**：单篇论文处理异常的根因；各阶段耗时分布；重试次数和原因

---

#### (C) Parse Quality Metrics

| 指标 | 类型 | 说明 |
|------|------|------|
| `paper_id` | string | |
| `parser_used` | string | 使用的解析器 |
| `page_count` | number | PDF 页数 |
| `extracted_char_count` | number | 提取字符数 |
| `chars_per_page` | number | 每页平均字符数（过低可能是扫描件） |
| `section_count` | number | 识别的 section 数 |
| `has_abstract` | boolean | 是否成功提取摘要 |
| `has_references` | boolean | 是否成功提取参考文献 |
| `reference_count` | number | 参考文献数量 |
| `figure_count` | number | 图表数量 |
| `table_count` | number | 表格数量 |
| `encoding_issues` | boolean | 是否有编码问题 |
| `confidence` | number | 整体置信度 |

**格式**：SQLite 表 `parse_metrics`

**排查什么**：解析质量整体趋势；哪些论文解析质量差需要重处理；是否该切换解析器；chars_per_page < 100 → 疑似扫描件

---

#### (D) Retrieval Diagnostics

| 字段 | 类型 | 说明 |
|------|------|------|
| `query_id` | string | 检索请求 ID |
| `timestamp` | string | |
| `query_text` | string | 原始 query |
| `search_mode` | string | 使用的检索模式 |
| `query_embedding_ms` | number | query embedding 耗时 |
| `vector_search_ms` | number | 向量检索耗时 |
| `text_search_ms` | number | 全文检索耗时 |
| `rerank_ms` | number | 重排序耗时 |
| `total_ms` | number | 总耗时 |
| `candidates_count` | number | 初筛候选数 |
| `returned_count` | number | 最终返回数 |
| `top_score` | number | 最高分 |
| `avg_score` | number | 平均分 |
| `score_distribution` | number[] | 分数分布直方图 (5 bins) |
| `paper_diversity` | number | 返回结果覆盖了多少不同论文 |
| `filter_applied` | object | 使用的过滤条件 |

**格式**：JSON Lines，`data/logs/retrieval/{date}.jsonl`

**排查什么**：检索延迟是否达标（target: <500ms）；检索质量是否合理；结果多样性是否足够；向量 vs 全文 vs 混合哪个效果好

---

#### (E) Analysis Provenance

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 分析任务 ID |
| `result_id` | string | 结果 ID |
| `paper_ids` | string[] | 输入论文 |
| `model_used` | string | LLM 模型 |
| `prompt_template_version` | string | prompt 模板版本 |
| `input_token_count` | number | 输入 token 数 |
| `output_token_count` | number | 输出 token 数 |
| `llm_latency_ms` | number | LLM 调用延迟 |
| `chunk_ids_used` | string[] | 实际送入 LLM 的 chunk 列表 |
| `temperature` | number | 采样温度 |

**格式**：SQLite 表 `analysis_provenance`

**排查什么**：分析结果是否可复现；LLM 成本核算；输入是否合理

---

#### (F) Error Summaries

```typescript
interface ErrorSummary {
  time_window:    string    // e.g. "2024-01-15T10:00:00Z/PT1H" (过去 1 小时)
  total_errors:   number
  by_code:        Record<string, number>   // error_code → count
  by_stage:       Record<string, number>   // stage → count
  top_failing_urls: Array<{url: string, count: number, last_error: string}>
  retry_success_rate: number               // 重试成功率
  papers_stuck:   number                   // 卡在非终态超过 30 分钟的论文数
}
```

**格式**：按小时聚合，存 SQLite 表 `error_summaries`

**排查什么**：系统整体健康度；是否有批量失败；是否需要人工干预

---

#### (G) Cache/Index Versioning

```typescript
interface IndexVersion {
  version_id:     string    // UUID
  created_at:     string
  embedding_model: string   // 模型名 + 版本
  embedding_dim:  number    // 向量维度
  paper_count:    number    // 索引中的论文数
  chunk_count:    number    // 索引中的 chunk 数
  index_size_bytes: number  // 索引文件大小
  index_path:     string    // 索引文件路径
  is_active:      boolean   // 是否为当前使用的索引
}
```

**格式**：SQLite 表 `index_versions`

**排查什么**：当前索引是用什么模型建的；索引是否需要重建；索引大小增长趋势

---

### 4.3 Orchestrator 层日志要点

Claude Code orchestrator 不需要自建日志系统（它有自己的 cost-tracker 和 analytics），但在 CLAUDE.md 中应指导 agent：

1. **MCP tool 调用日志**：每次调用论文 MCP tool 时，在 TodoWrite 中记录调用状态
2. **失败处理日志**：tool 返回错误时，向用户展示 `error_message`，并记录 `error_code` 到对话中
3. **进度追踪**：长时间任务（batch_ingest、synthesize_topic）应使用 TodoWrite 更新进度

orchestrator 不写文件日志。它的"日志"就是对话历史本身。

### 4.4 日志保留策略

| 日志类型 | 保留期限 | 理由 |
|---------|---------|------|
| Ingest job logs | 30 天 | 排查近期问题 |
| Per-paper traces | 永久（随论文存在） | 论文级审计 |
| Parse quality metrics | 永久 | 质量趋势分析 |
| Retrieval diagnostics | 7 天 | 量大且只用于短期优化 |
| Analysis provenance | 永久（随结果存在） | 可复现性 |
| Error summaries | 90 天 | 趋势分析 |
| Index versions | 永久 | 版本管理 |

---

## 5. 数据契约层面的建议

### 5.1 必须先稳定的 Schema（Phase 1 Day 1 固定）

| 优先级 | Schema | 理由 |
|--------|--------|------|
| P0 | **Paper** (核心字段) | 所有模块依赖 paper_id + status，改一个全改 |
| P0 | **Chunk** | 检索的基本单元，embedding 维度一旦确定不易更改 |
| P0 | **PaperStatus 枚举** | 状态机是 ingest pipeline 的骨架 |
| P0 | **IngestJob** | batch_ingest 的进度追踪依赖 |
| P0 | **RetrievalHit** | orchestrator 展示检索结果的数据契约 |
| P1 | **ToolError 格式** | 所有 MCP tool 的统一错误返回格式 |
| P1 | **IngestOptions** | ingest 行为配置，影响 tool 接口签名 |

### 5.2 最容易设计错的字段

| 字段/决策 | 风险点 | 建议 |
|----------|--------|------|
| `paper_id` 生成策略 | 用 DOI？用 hash？用 UUID？ | **用 UUID v4**。DOI 不总有，hash 依赖内容，UUID 最稳定。DOI/arxiv_id 作为辅助去重字段 |
| `embedding` 维度 | 模型切换后维度变化，旧向量失效 | **index_versions 表记录模型+维度**，切换模型时必须 reindex 而非混用 |
| `SectionType` 枚举 | 过细则分类困难，过粗则无法过滤 | Phase 1 用上述 10 种，不要超过 15 种。允许 `"other"` 兜底 |
| `confidence` 类字段 | 含义模糊，不同场景不可比 | **每个 confidence 字段必须注释计算方式**，不要跨场景比较 |
| `chunk` 切分策略参数 | 切分窗口大小影响检索效果，改了需要全量重建 | Phase 1 固定 512 token / 128 token overlap，记录在 IndexVersion 中，不要频繁调整 |
| `author` 字段结构 | 姓名格式不统一（"Smith, J." vs "John Smith"） | 存原始格式 + 标准化格式两个字段（可调整：Phase 1 只存 name 字符串，Phase 2 再加标准化） |
| `SearchResult.already_ingested` | 需要实时查库，可能拖慢搜索 | 允许延迟判断：先返回搜索结果，`already_ingested` 可以是异步填充或近似值 |

### 5.3 必须尽早固定的 Tool 契约

| 优先级 | Tool | 理由 |
|--------|------|------|
| P0 | `ingest_paper` | skills 和 subagents 的 prompt 都依赖这个接口签名 |
| P0 | `retrieve_evidence` | 检索是最高频操作，接口稳定才能优化 prompt |
| P0 | `get_ingest_status` | 进度追踪 + 失败恢复都依赖 |
| P0 | `search_papers` | 用户第一个接触的 tool |
| P1 | `batch_ingest` | 基本可复用 ingest_paper 的输出结构 |
| P1 | `analyze_paper` | Phase 1 可以先在 orchestrator 层做分析，不急于固定 backend 接口 |
| P2 | `compare_papers` | Phase 2 才需要 |
| P2 | `synthesize_topic` | Phase 3 才需要 |

### 5.4 可以晚一点再细化的细节

| 细节 | 可延迟到 | 理由 |
|------|---------|------|
| Figure / Table schema 字段 | Phase 2 | Phase 1 不做图表抽取 |
| Citation / Reference 完整结构 | Phase 2 | Phase 1 不做引用图谱 |
| CompareResult 的 dimensions 结构 | Phase 2 | 需要真实使用后才知道什么维度有用 |
| SynthesisResult 全部字段 | Phase 3 | 综述生成是最后实现的功能 |
| Analysis provenance 的完整字段 | Phase 2 | Phase 1 分析在 orchestrator 层做，不经过 backend |
| Retrieval diagnostics 的 score_distribution 格式 | Phase 2 | Phase 1 先记录基本指标即可 |
| CitationIntent 分类体系 | Phase 2 | 需要数据验证分类是否合理 |
| retry policy 的精确参数 | 运行期调优 | 初始值可以粗糙，跑起来后根据日志调整 |

### 5.5 关键设计原则总结

1. **MCP tool 的输出永远不包含 embedding 向量**——向量太大且 agent 无法使用
2. **所有 ID 用 UUID v4**——不要用自增 ID（跨库不唯一）、不要用 DOI（不总存在）
3. **所有时间用 ISO 8601 UTC**——不要用 unix timestamp
4. **ToolError 是唯一的错误返回格式**——所有 tool 失败都走这个结构
5. **状态机转移必须逐步**——不允许跳过中间状态
6. **backend 自管状态，orchestrator 只查不写**——保持职责分离
7. **日志在 backend 层写文件/SQLite，orchestrator 层只通过对话呈现**——不要在两个进程中写同一份日志
