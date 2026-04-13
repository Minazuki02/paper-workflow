---
name: paper-search
description: Search academic papers through the configured paper search provider
aliases:
  - search-papers
  - find-papers
  - lit-search
whenToUse: >
  When the user wants to find papers on a topic, look up a specific paper,
  or discover candidate literature from external search.
allowedTools:
  - mcp__paper_ingest__search_papers
model: null
---

You are handling a paper search request.

1. Extract the search parameters from the user's message:
   - query keywords
   - optional year range
   - optional source preference
   - optional max results (default 20)

2. Call `mcp__paper_ingest__search_papers` with the extracted parameters.

3. Present the results as a markdown table:
   | # | Title | Authors | Year | Source | In Library? |

4. Keep the scope limited to search:
   - do not ingest papers
   - do not download PDFs
   - do not analyze papers

5. If the search returns no results, say that no matching papers were found from the configured source.
