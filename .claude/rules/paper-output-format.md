# Paper Output Format

Use these output rules only for paper-related requests.

1. Evidence-first discipline.
   - When making claims about research findings, support them with `retrieve_evidence` output.
   - Present evidence grouped by paper, not by claim.
   - Keep `paper_id` visible whenever it is available from tool output.

2. Search results formatting.
   - Present paper search results as a markdown table with the key metadata needed for selection.

3. Retrieval evidence formatting.
   - Quote the retrieved text directly.
   - Include paper title, authors, year, section type, page number, and relevance score for each hit.
   - Do not paraphrase evidence in place of the quote.

4. Single-paper analysis formatting.
   - Preserve this section order:
     `Summary`
     `Contributions`
     `Methodology`
     `Key Findings`
     `Limitations`
   - Keep every section evidence-backed. If a section lacks evidence, say that the current library evidence is insufficient.

5. Empty or weak evidence handling.
   - If all retrieval scores are below `0.3`, explicitly say: `I found no strong evidence for this in the ingested papers.`
   - Do not silently fall back to unsupported general knowledge.
