# Paper Workflow

> 把 Claude Code 变成论文研究助手——零侵入安装，一键拆卸。

[![Release](https://img.shields.io/github/v/release/Minazuki02/paper-workflow?include_prereleases&label=release&color=blue)](https://github.com/Minazuki02/paper-workflow/releases)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange)]()
[![Python](https://img.shields.io/badge/python-≥3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-89_cases-brightgreen)]()
[![MCP](https://img.shields.io/badge/protocol-MCP-8A2BE2)](https://modelcontextprotocol.io)

<img width="720" alt="Paper Workflow" src="https://github.com/user-attachments/assets/7e2434d2-034c-4f5d-8b8c-ebd25f3162d3" />

---

## 它能做什么

```
你: /paper-search "LLM agent reasoning 2024"
CC: 从 arXiv + Semantic Scholar 搜索到 20 篇论文……

你: /paper-ingest 1,3,5
CC: 3 篇论文下载、解析、embedding、入库完成 ✓

你: multi-head attention 的主要变体有哪些？
CC: 基于已入库论文检索到 8 条证据：
    > "Multi-head attention allows the model to jointly attend..."
    > — Attention Is All You Need (Vaswani et al., 2017), §3.2, p.4, score: 0.87
```

每一条结论都有 PDF 原文引用——不是模型在猜，是在查。

---

## 为什么需要这个项目

- **证据驱动，不靠猜。** 提一个研究问题 → 返回精确引用，附带论文标题、页码、相关性分数。不是 LLM 幻觉。
- **零侵入 Claude Code。** 通过 CC 官方扩展机制（Skills + MCP + Rules）安装，不改一行 CC 源码，不影响编程体验。
- **完全可拆卸。** `install.sh` 写入 manifest，`uninstall.sh` 精确移除。启用/禁用秒级切换。

---

## 快速开始

### 已经安装了 Claude Code？

```bash
git clone https://github.com/Minazuki02/paper-workflow.git
cd paper-workflow
bash scripts/install.sh
```

安装后在**任意目录**启动 Claude Code 即可使用论文功能：

```bash
claude
# 试试: /paper-search "transformer attention"
```

随时切换模式，不影响已有数据：

```bash
bash scripts/paper-workflow.sh disable   # 关闭论文模式
bash scripts/paper-workflow.sh enable    # 重新开启
```

完全卸载：`bash scripts/uninstall.sh`

> **前置条件：** Python ≥ 3.11 · 已安装 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

### 只想先了解项目？

不需要 Claude Code 也能浏览代码和运行测试：

```bash
git clone https://github.com/Minazuki02/paper-workflow.git
cd paper-workflow
pip install -e backend[dev]
pytest tests/
```

查看 [架构设计 →](docs/01_architecture_and_boundaries.md)

---

## 工作原理

```
┌─────────────────────────────┐
│ Claude Code（不修改）         │
│  Skills · Agents · Rules    │
│         ↕ MCP (stdio)       │
├─────────────────────────────┤
│ Python Backend（本项目）      │
│  Ingest → Retrieve → Analyze│
│  SQLite + FAISS + PDF 存储   │
└─────────────────────────────┘
```

CC 保持 orchestrator 角色，Backend 通过 [MCP 协议](https://modelcontextprotocol.io) 完成所有重计算（PDF 解析、embedding、检索）。

**核心设计：**
- CC 不碰数据，Backend 不碰用户，MCP 桥接两侧。
- 注入到 `~/.claude/` 的每个文件都由 manifest 追踪——卸载时精确移除，零残留。
- 不改一行 CC 源码，所有能力通过官方扩展机制接入。

[完整架构文档 →](docs/01_architecture_and_boundaries.md)

---

## 当前状态 — v0.1.0-alpha

> 项目处于 **early alpha** 阶段。核心链路端到端可用，但仍有粗糙之处。

| 功能 | 状态 |
|------|------|
| 多源搜索（arXiv + Semantic Scholar） | ✅ 可用 |
| PDF 下载 + 解析（PyMuPDF） | ✅ 可用 |
| 分块 + embedding + FAISS 索引 | ✅ 可用 |
| 混合检索（向量 + FTS5 + RRF） | ✅ 可用 |
| 单篇论文分析 | ✅ 可用 |
| 5 个 Claude Code Skills | ✅ 可用 |
| 全局安装 / 卸载 / 模式切换 | ✅ 可用 |
| 多篇论文对比 | 🔜 开发中 |
| 自动生成文献综述 | 🔜 规划中 |
| GROBID 集成 | 🔜 规划中 |

### 已知限制

- PDF 解析对文本型 PDF（如 arXiv 论文）效果最佳。扫描件/图片 PDF 暂不支持。
- 首次调用论文工具有 ~2-3 秒冷启动延迟（Python 进程加载）。
- Embedding 模型（`all-MiniLM-L6-v2`）针对英文优化，非英文论文检索质量可能下降。
- 尚未在 Windows 上测试，主要支持 macOS 和 Linux。

---

## MCP 工具

### Ingest Server

| 工具 | 说明 |
|------|------|
| `search_papers` | 跨 arXiv + Semantic Scholar 搜索，自动去重 |
| `fetch_pdf` | 仅下载 PDF，不触发 ingest 流程 |
| `ingest_paper` | 完整流程：下载 → 解析 → 分块 → embedding → 入库 |
| `batch_ingest` | 批量 ingest（最多 100 篇） |
| `get_ingest_status` | 查询任务或论文处理状态 |

### Retrieval Server

| 工具 | 说明 |
|------|------|
| `retrieve_evidence` | 混合检索（向量 + 全文 + RRF 排序），支持元数据过滤 |

---

## 文档

| 文档 | 说明 |
|------|------|
| [架构设计](docs/01_architecture_and_boundaries.md) | 四层架构、数据流、扩展机制 |
| [Schema 与工具契约](docs/02_schema_and_tool_contracts.md) | 数据模型、状态机、MCP 工具接口 |
| [Claude Code 适配](docs/03_claude_code_adaptation.md) | Skills、Agents、Hooks、CLAUDE.md 设计 |
| [实施计划](docs/04_implementation_plan.md) | Sprint 分解、测试方案、风险应对 |
| [Fork 改造指南](docs/fork-guide.md) | 如何改造为专利/法律/金融等领域工具 |
| [配置说明](docs/configuration.md) | Embedding 模型、LLM 设置、环境变量 |
| [常见问题](docs/faq.md) | 安全性、适用场景、对比方案 |

---

## Contributing

欢迎 PR 和 Issue。如果你基于本项目做了其他领域的改造，欢迎在 Issue 中分享。

## License

[MIT](LICENSE)

---

<p align="center"><a href="README.md">English README</a></p>
