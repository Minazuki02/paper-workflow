# 06 Session Prompts

## Usage

本文件为 `05_execution_backlog.md` 中 `Session Pack` 的直接执行模版。

使用规则：
- 一个新会话只复制一个 `SP-XX` prompt。
- 不要手动扩展到下一个 `Session Pack`。
- 如果执行模型在包内某个 task 未通过验收，应停在当前 task，不继续后续 task。
- 若 `01-03.md` 与本文件冲突，以 `01-03.md` 和 `05_execution_backlog.md` 为准。

---

## SP-01

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-01`，其包含的任务是：
- `TASK-01`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-01` 内的任务，也就是：
- `TASK-01: 初始化目录骨架与基础工程文件`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-01`。
```

---

## SP-02

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-02`，其包含的任务是：
- `TASK-02`
- `TASK-03`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-02` 内的任务，也就是：
- `TASK-02: 定义 P0 共享数据模型`
- `TASK-03: 建立统一错误码与 ToolError 工厂`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-02`。
```

---

## SP-03

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-03`，其包含的任务是：
- `TASK-04`
- `TASK-05`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-03` 内的任务，也就是：
- `TASK-04: 建立配置与结构化日志基础设施`
- `TASK-05: 实现 SQLite 初始化与最小 migration 框架`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-03`。
```

---

## SP-04

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-04`，其包含的任务是：
- `TASK-06`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-04` 内的任务，也就是：
- `TASK-06: 实现 PaperStatus 状态机并补齐单元测试`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-04`。
```

---

## SP-05

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-05`，其包含的任务是：
- `TASK-07`
- `TASK-08`
- `TASK-09`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-05` 内的任务，也就是：
- `TASK-07: 实现 PDF 文件存储层`
- `TASK-08: 实现 SQLite 元数据存储层`
- `TASK-09: 实现 FAISS 索引存储层`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-05`。
```

---

## SP-06

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-06`，其包含的任务是：
- `TASK-10`
- `TASK-11`
- `TASK-12`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-06` 内的任务，也就是：
- `TASK-10: 实现 arXiv 搜索 provider`
- `TASK-11: 建立 ingest MCP server 最小骨架并开放 search_papers`
- `TASK-12: 接入 Claude Code 的搜索入口`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-06`。
```

---

## SP-07

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-07`，其包含的任务是：
- `TASK-13`
- `TASK-14`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-07` 内的任务，也就是：
- `TASK-13: 实现 PDF 下载器与 fetch_pdf tool`
- `TASK-14: 实现 PDF 解析器骨架`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-07`。
```

---

## SP-08

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-08`，其包含的任务是：
- `TASK-15`
- `TASK-16`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-08` 内的任务，也就是：
- `TASK-15: 实现元数据抽取与章节结构化`
- `TASK-16: 实现 chunk 切分器`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-08`。
```

---

## SP-09

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-09`，其包含的任务是：
- `TASK-17`
- `TASK-18`
- `TASK-19`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-09` 内的任务，也就是：
- `TASK-17: 实现 embedding 生成器`
- `TASK-18: 实现去重器`
- `TASK-19: 实现索引写入器`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-09`。
```

---

## SP-10

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-10`，其包含的任务是：
- `TASK-20`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-10` 内的任务，也就是：
- `TASK-20: 实现单篇 ingest pipeline`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-10`。
```

---

## SP-11

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-11`，其包含的任务是：
- `TASK-21`
- `TASK-22`
- `TASK-23`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-11` 内的任务，也就是：
- `TASK-21: 开放 ingest_paper 与 get_ingest_status`
- `TASK-22: 实现 batch_ingest 后端入口`
- `TASK-23: 接入 Claude Code 的 ingest 入口与批量操作 agent`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-11`。
```

---

## SP-12

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-12`，其包含的任务是：
- `TASK-24`
- `TASK-25`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-12` 内的任务，也就是：
- `TASK-24: 实现 retrieval 核心检索模块`
- `TASK-25: 开放 retrieve_evidence MCP tool`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-12`。
```

---

## SP-13

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-13`，其包含的任务是：
- `TASK-26`
- `TASK-27`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-13` 内的任务，也就是：
- `TASK-26: 接入 Claude Code 的证据检索与论文规则文件`
- `TASK-27: 实现 orchestrator 侧单篇分析 skill`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-13`。
```

---

## SP-14

```text
请严格按以下约束执行：

你现在只允许执行 `05_execution_backlog.md` 中的 `SP-14`，其包含的任务是：
- `TASK-28`

不要执行任何不属于该 `Session Pack` 的 task，也不要顺手推进 `Suggested Next Task` 或下一个 `Session Pack`。

约束优先级：
1. `01_architecture_and_boundaries.md`
2. `02_schema_and_tool_contracts.md`
3. `03_claude_code_adaptation.md`
4. `05_execution_backlog.md`
5. `04_implementation_plan.md` 仅作为补充来源
6. `00_master_index.md` 仅作导航

本次唯一目标：
只完成 `SP-14` 内的任务，也就是：
- `TASK-28: 完成契约、集成、质量与冒烟收尾`

执行要求：
- 只做本次 `Session Pack` 中各 task 的 Scope
- 严格遵守每个 task 的 Out of Scope
- 必须按 task 顺序执行，不允许跳过前置 task
- 每完成一个 task，先对照该 task 的 `Acceptance Criteria` 做一次局部验收，再继续下一个 task
- 如果当前 task 未通过验收，不得继续包内后续 task
- 不得擅自扩展架构
- 不得修改 schema / tool 契约 / 状态机定义 / hook 触发逻辑 / 主 prompt 边界
- 不得修改 Claude Code `src/` 下任何文件
- 不得提前创建或实现 Phase 2 / Phase 3 内容
- 不得创建超出当前 task 范围的实现文件
- 不得把 orchestrator 变成 PDF 解析、embedding、检索、存储执行者
- 不得直接读写 `data/pdfs/`、`data/db/`、`data/index/`

冲突处理规则：
- 如果 `Session Pack` 中任何 task 与 `01-03.md` 或 `05_execution_backlog.md` 冲突，以 `01-03.md` 为准
- 遇到冲突时立即停止在当前 task
- 不要自行重构
- 不要扩展解释为更大改造
- 只报告“最小修正建议”
- 不得继续推进包内后续 task

开始前先阅读：
- `01_architecture_and_boundaries.md`
- `02_schema_and_tool_contracts.md`
- `03_claude_code_adaptation.md`
- `05_execution_backlog.md`

完成后请按以下格式输出：

1. 本次执行的 Session Pack
2. 修改文件列表
3. 按 task 列出的完成情况
4. 每个 task 对照 `Acceptance Criteria` 的逐条验收结果
5. 对照 `01-03.md` 的约束符合性检查
6. 未完成项 / 风险
7. 如果中途停止，说明停止在哪个 task、为什么停止

现在开始，仅执行 `SP-14`。
```
