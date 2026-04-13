# Paper Error Handling

Use these rules for paper tool calls.

1. Retry policy.
   - If a paper MCP tool returns `retryable=true`, retry at most once automatically when the same tool call is still appropriate.
   - If the retry fails again, report the returned `error_code` and `error_message`.
   - If `retryable=false`, report the error immediately without retrying.

2. Retrieval failure handling.
   - If retrieval returns no relevant hits or only weak hits, tell the user that the current ingested library does not provide strong evidence.
   - Suggest the next valid action only when it stays inside the paper workflow boundary, such as searching for more papers or ingesting missing papers.

3. Boundary protection.
   - Do not compensate for tool failures by reading backend storage directly.
   - Do not invent missing citations, quotes, or metadata to make the answer look complete.

4. User-facing transparency.
   - Surface the reason for failure in plain language.
   - Preserve structured backend fields like `error_code`, `error_message`, and `retryable` when relevant.
