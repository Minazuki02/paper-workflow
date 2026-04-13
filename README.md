# Paper Workflow

[![Python](https://img.shields.io/badge/Python-≥3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/Protocol-MCP_(stdio)-8A2BE2)](https://modelcontextprotocol.io)
[![FAISS](https://img.shields.io/badge/Vector_Search-FAISS-0467DF)](https://github.com/facebookresearch/faiss)
[![SQLite](https://img.shields.io/badge/Metadata-SQLite_+_FTS5-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![PyMuPDF](https://img.shields.io/badge/PDF_Parse-PyMuPDF-CC0000)](https://pymupdf.readthedocs.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**把 Claude Code 变成你的论文研究助手，零侵入，5 分钟上手。**

Claude Code 是目前最强的 AI 编程工具，但它不懂论文。
Paper Workflow 通过 CC 的原生扩展机制，让它学会搜论文、读论文、检索证据、结构化分析——
**不改一行 CC 源码，不影响你原有的编程体验。**

```
你: /paper-search "LLM agent reasoning 2024"
CC: 从 arXiv + Semantic Scholar 搜索到 20 篇论文……

你: /paper-ingest 1,3,5
CC: 3 篇论文下载、解析、embedding、入库完成 ✓

你: multi-head attention 的主要变体有哪些？
CC: 基于已入库论文检索到 8 条证据：
    > "Multi-head attention allows the model to jointly attend..."
    > — Attention Is All You Need (Vaswani et al., 2017), §3.2, p.4

你: /paper-analyze <paper-id>
CC: ## Summary
    本文提出了 Transformer 架构……
    ## Contributions
    - 首个完全基于注意力机制的序列转导模型……
```

---

## 为什么需要这个项目？

### Q: Claude Code 已经很强了，为什么还要装你这个？

CC 的强项是**写代码**。但当你做科研时，你需要的不是写代码——你需要：

- 搜 50 篇论文，不想一篇篇打开浏览器
- 把 PDF 里的内容变成可检索的知识库
- 问"XXX 领域的主流方法有哪些"，并要求每句话都有论文出处
- 对一篇论文做结构化拆解：方法、贡献、局限、未来方向

CC 原生做不到这些。Paper Workflow 让它做到了。

### Q: 这跟直接问 ChatGPT "帮我总结论文" 有什么区别？

| | ChatGPT / 直接问 LLM | Paper Workflow |
|---|---|---|
| 数据来源 | 训练数据（可能过时或幻觉） | 你亲手入库的 PDF 原文 |
| 可溯源 | ❌ 无法验证出处 | ✅ 每条证据附带论文标题、页码、原文引用 |
| 知识范围 | 固定，无法新增 | 持续 ingest 新论文，知识库不断增长 |
| 检索方式 | 无 | 向量检索 + 全文检索 + 混合排序 |
| 分析深度 | 泛泛而谈 | 结构化输出：方法论、贡献、局限、证据链 |

**一句话：LLM 在猜，Paper Workflow 在查。**

### Q: 为什么不做成独立产品，非要依赖 Claude Code？

因为 CC 已经解决了最难的部分：

- **自然语言理解** — 你不需要学命令语法，直接说话
- **多步推理** — CC 自动判断该搜论文还是查库还是做分析
- **工具编排** — 搜索 → 下载 → 入库 → 检索 → 分析，CC 自动串联
- **编程能力保留** — 分析完论文，下一句就能让它帮你写代码实现

我们不重复造轮子，只补上 CC 缺失的论文能力。

### Q: 安装后会影响我用 CC 写代码吗？

**完全不会。** 论文规则仅在检测到论文相关意图时激活。你正常写代码、debug、git 操作，跟没装一样。

### Q: 我能用在自己的场景吗？比如改成专利检索、法律文书分析？

**这正是本项目最大的价值之一。** 往下看"给想 fork 改造的开发者"章节。

---

## 架构

```
┌──────────────────────────────────┐
│  Claude Code（不修改）            │
│  自动加载 .claude/ 下的配置        │
│  ┌────────┐ ┌────────┐ ┌──────┐ │
│  │ Skills │ │ Agents │ │ Rules│ │
│  └────┬───┘ └────┬───┘ └──┬───┘ │
│       │     MCP Protocol  │     │
└───────┼──────────┼────────┼─────┘
        │          │        │
┌───────▼──────────▼────────▼─────┐
│  Python Backend（本项目）         │
│  ┌─────────┐ ┌──────────┐       │
│  │ Ingest  │ │ Retrieval│       │
│  │ Server  │ │ Server   │       │
│  └────┬────┘ └─────┬────┘       │
│       │             │            │
│  ┌────▼─────────────▼────┐      │
│  │ SQLite + FAISS + PDF  │      │
│  └───────────────────────┘      │
└─────────────────────────────────┘
```

**核心设计：CC 不碰数据，Backend 不碰用户。** 通过 MCP 协议桥接，两侧完全解耦。

### Built With

| 层 | 技术 | 用途 |
|---|---|---|
| **协议层** | [MCP](https://modelcontextprotocol.io) (stdio) | Claude Code ↔ Python Backend 的标准通信协议 |
| **PDF 解析** | [PyMuPDF](https://pymupdf.readthedocs.io) 1.24+ | 文本提取、页码映射、元数据抽取 |
| **向量检索** | [FAISS](https://github.com/facebookresearch/faiss) 1.8+ | 高性能相似度搜索（百万级向量 <100ms） |
| **元数据 + 全文检索** | [SQLite](https://sqlite.org) + FTS5 | 零依赖的结构化存储 + 全文搜索引擎 |
| **数据模型** | [Pydantic](https://docs.pydantic.dev) v2 | 强类型 schema 校验（Paper, Chunk, IngestJob 等） |
| **Embedding** | 可选：本地 [sentence-transformers](https://sbert.net) 或任意 OpenAI-compatible API | 文本向量化，支持自选模型 |
| **LLM** | 任意 OpenAI-compatible API | 论文分析（GLM、Qwen、GPT 等均可） |
| **学术搜索** | [arXiv API](https://arxiv.org/help/api) + [Semantic Scholar API](https://api.semanticscholar.org) | 双源搜索、自动去重 |
| **日志** | [structlog](https://www.structlog.org) | JSON 结构化日志 |
| **测试** | [pytest](https://pytest.org) | 140+ 测试用例 |

---

## 快速开始

### 前置条件

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 已安装
- Python >= 3.11
- 约 500MB 磁盘空间（embedding 模型，如使用本地模式）

### 安装

```bash
git clone https://github.com/Minazuki02/paper-workflow.git
cd paper-workflow

# 安装 Python 依赖
pip install -e ./backend

# （可选）安装本地 embedding 模型
pip install -e "./backend[local-embedding]"

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 embedding API 和 LLM API 配置

# 启动 Claude Code — 自动加载论文工作流
claude
```

### 支持的 embedding / LLM 配置

Paper Workflow 不绑定特定模型。通过 `.env` 配置即可切换：

| 方案 | embedding | LLM | 成本 |
|------|-----------|-----|------|
| 全本地 | sentence-transformers | — (用 CC 自带) | 免费 |
| API 模式 | OpenAI-compatible API | 任意 LLM API | 按量付费 |
| 混合 | 本地 embedding + 远程 LLM | 自选 | 低成本 |

---

## 功能一览

| 命令 | 功能 | 状态 |
|------|------|------|
| `/paper-search` | 从 arXiv + Semantic Scholar 搜索论文 | ✅ 可用 |
| `/paper-ingest` | 下载 PDF → 解析 → embedding → 入库 | ✅ 可用 |
| `/paper-evidence` | 从已入库论文中检索证据（向量 + 全文 + 混合排序） | ✅ 可用 |
| `/paper-analyze` | 单篇论文结构化分析（方法、贡献、发现、局限） | ✅ 可用 |
| `/paper-status` | 查看 ingest 状态和库概况 | ✅ 可用 |
| `/paper-compare` | 多篇论文对比 | 🔜 开发中 |
| `/paper-synthesize` | 自动生成文献综述 | 🔜 规划中 |

---

## 给想 fork 改造的开发者

本项目是 **Claude Code 扩展机制的完整参考实现**。如果你想基于 CC 构建自己领域的 AI 工作流，这里是你需要的一切。

### CC 的四种扩展机制

| 机制 | 文件格式 | 作用 | 本项目示例 |
|------|---------|------|-----------|
| **CLAUDE.md** | markdown | 注入系统级规则，CC 每次对话自动加载 | 论文路由规则、输出格式约束 |
| **Skills** | markdown + frontmatter | 用户通过 `/` 命令触发的操作 | `/paper-search`、`/paper-ingest` |
| **Agents** | markdown + frontmatter | 后台长任务执行者，有独立上下文和受限工具集 | 批量 ingest agent |
| **MCP Server** | 任意语言 | 通过标准协议暴露外部工具给 CC 调用 | Python ingest/retrieval 服务 |

### 改造路线

整个项目结构为改造而设计：

```
.claude/
├── CLAUDE.md        ← 改成你的领域规则
├── rules/           ← 改成你的路由逻辑
├── skills/          ← 改成你的用户命令
├── agents/          ← 改成你的任务执行者
└── settings.json    ← 注册你自己的 MCP Server

backend/             ← 换成你的领域后端
```

只要你的场景符合"搜索 → 入库 → 检索 → 分析"模式，fork 本项目改 3 样东西就能用：

1. **`backend/`** — 换掉 PDF 解析为你的数据源解析
2. **`.claude/skills/`** — 改掉 skill 名称和 prompt
3. **`.claude/rules/`** — 改掉路由规则

CC 的 MCP 协议、skill 加载、agent 调度这些重活，已经帮你搭好了。

### 适合改造的方向

- 专利检索与分析
- 法律文书 / 判例检索
- 技术文档知识库（内部 wiki → 可检索的 AI 助手）
- 财报 / 研报分析
- 医学文献循证分析

---

## 项目结构

```
paper-workflow/
├── .claude/                 # CC 扩展配置（纯 markdown，即改即生效）
│   ├── CLAUDE.md            # 论文路由规则入口
│   ├── rules/               # 路由、输出格式、错误处理规则
│   ├── skills/              # 用户命令定义
│   ├── agents/              # 子任务执行者定义
│   └── settings.json        # MCP Server 注册 + 权限
│
├── backend/                 # Python 论文处理后端
│   ├── ingest/              # Ingest MCP Server（下载/解析/入库）
│   ├── retrieval/           # Retrieval MCP Server（向量+全文检索）
│   ├── search/              # arXiv + Semantic Scholar 搜索
│   ├── storage/             # SQLite + FAISS + PDF 文件管理
│   ├── analysis/            # 论文分析
│   └── common/              # 数据模型 + 配置 + 错误码
│
├── tests/                   # 140+ 测试用例
├── docs/                    # 架构设计文档
└── scripts/                 # 环境初始化 + 健康检查脚本
```

## 组件可替换性

所有核心组件均可按需替换，不影响其他模块：

| 组件 | 当前选型 | 可替换为 |
|------|---------|---------|
| PDF 解析 | PyMuPDF | GROBID（高质量结构化解析） |
| 向量索引 | FAISS | Qdrant / Milvus / Chroma |
| 元数据存储 | SQLite + FTS5 | PostgreSQL |
| Embedding 模型 | 可配置 | 任意 OpenAI-compatible API 或本地模型 |
| LLM | 可配置 | 任意 OpenAI-compatible API |
| 搜索源 | arXiv + Semantic Scholar | PubMed / DBLP / Google Scholar |

## Contributing

欢迎 PR 和 Issue。如果你基于本项目做了其他领域的改造，欢迎在 Issue 中分享。

## License

MIT
