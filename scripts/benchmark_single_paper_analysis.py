#!/usr/bin/env python3
"""Run a single-paper analysis benchmark using the configured backend LLM."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from backend.analysis.single_paper import SinglePaperAnalysisError, SinglePaperAnalyzer


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-id", required=True, help="Ready paper_id to analyze.")
    parser.add_argument("--focus", default=None, help="Optional analysis focus, such as methodology or experiments.")
    parser.add_argument("--user-query", default=None, help="Optional original user question to bias the analysis.")
    parser.add_argument("--json", action="store_true", help="Print the full result as JSON.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    analyzer = SinglePaperAnalyzer()

    try:
        response = analyzer.analyze(
            paper_id=args.paper_id,
            focus=args.focus,
            user_query=args.user_query,
        )
    except SinglePaperAnalysisError as exc:
        print(json.dumps({"ok": False, "error_code": exc.error_code, "error_message": str(exc)}, ensure_ascii=False))
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "result": response.result.model_dump(),
                    "metrics": asdict(response.metrics),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"[ok] paper_id={response.result.paper_id} model={response.result.model_used}")
    print(
        "metrics:",
        json.dumps(asdict(response.metrics), ensure_ascii=False),
    )
    print("summary:", response.result.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
