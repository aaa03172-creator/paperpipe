from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List

import fitz
from openai import OpenAI

from src.ingest.parser_backends import (
    TABLE_FAIL_BUDGET_EXCEEDED,
    TABLE_FAIL_CELL_COVERAGE_LOW,
    TABLE_FAIL_CELL_OVERLAP_HIGH,
    TABLE_FAIL_LOW_ACCURACY,
    TABLE_FAIL_NO_TABLE_FOUND,
    TableExtractionDiagnostics,
    TableExtractionResult,
)
from src.schemas.agent_artifacts import TableData

logger = logging.getLogger(__name__)


class CloudTableFallbackExtractor:
    """
    Optional Pass3 cloud table extractor.
    It is strictly best-effort and returns explicit failure taxonomy on miss.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 30,
        preflight_callback: Callable[[str, int], bool] | None = None,
    ):
        self.model = str(model or "gpt-4o-mini")
        self.api_key = str(api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self.base_url = str(base_url).strip() if base_url else None
        self.timeout_seconds = int(timeout_seconds)
        self.preflight_callback = preflight_callback
        self.client = self._create_client()

    def _create_client(self) -> OpenAI | None:
        if not self.api_key:
            return None
        try:
            kwargs: Dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout_seconds}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            return OpenAI(**kwargs)
        except Exception as exc:
            logger.warning("Cloud table fallback client init failed: %s", exc)
            return None

    def is_available(self) -> bool:
        return self.client is not None

    def extract_tables(self, pdf_path: Path, page_budget: int) -> TableExtractionResult:
        failures: set[str] = set()
        budget = int(page_budget)
        if budget <= 0:
            failures.add(TABLE_FAIL_BUDGET_EXCEEDED)
            return TableExtractionResult(
                tables=[],
                diagnostics=TableExtractionDiagnostics(
                    table_extraction_pass="pass3",
                    table_failure_taxonomy=sorted(failures),
                    fallback_used=False,
                    fallback_pages=[],
                ),
            )

        selected_pages = self._select_candidate_pages(pdf_path, budget)
        if not selected_pages:
            failures.add(TABLE_FAIL_NO_TABLE_FOUND)
            return TableExtractionResult(
                tables=[],
                diagnostics=TableExtractionDiagnostics(
                    table_extraction_pass="pass3",
                    table_failure_taxonomy=sorted(failures),
                    fallback_used=False,
                    fallback_pages=[],
                ),
            )

        if self.client is None:
            failures.add(TABLE_FAIL_LOW_ACCURACY)
            failures.add("NO_API")
            return TableExtractionResult(
                tables=[],
                diagnostics=TableExtractionDiagnostics(
                    table_extraction_pass="pass3",
                    table_failure_taxonomy=sorted(failures),
                    fallback_used=False,
                    fallback_pages=selected_pages,
                ),
            )

        collected: List[TableData] = []
        table_idx = 1
        for page in selected_pages:
            page_text = self._extract_page_text(pdf_path, page)
            if not page_text:
                continue
            if self.preflight_callback is not None and not self.preflight_callback(page_text, page):
                failures.add("PRIVACY_PREFLIGHT_BLOCKED")
                continue
            page_tables = self._extract_page_tables_with_llm(page_text, page)
            if page_tables is None:
                failures.add(TABLE_FAIL_LOW_ACCURACY)
                continue
            for table_rows in page_tables:
                normalized = self._normalize_table_rows(table_rows)
                valid, quality_failures = self._evaluate_table_quality(normalized)
                if not valid:
                    for code in quality_failures:
                        failures.add(code)
                    failures.add(TABLE_FAIL_LOW_ACCURACY)
                    continue
                collected.append(
                    TableData(
                        table_id=f"CF{table_idx}",
                        caption=f"Cloud fallback table (page {page})",
                        data=normalized,
                        source_page=page,
                        source_ref=f"{pdf_path}#page={page - 1}",
                        extraction_method=f"cloud_table_fallback.{self.model}",
                        confidence=0.4,
                        provenance_note="LLM-reconstructed fallback table from page text; cell bbox provenance is unavailable.",
                    )
                )
                table_idx += 1

        if not collected:
            failures.add(TABLE_FAIL_NO_TABLE_FOUND)

        return TableExtractionResult(
            tables=collected,
            diagnostics=TableExtractionDiagnostics(
                table_extraction_pass="pass3",
                table_failure_taxonomy=sorted(failures),
                fallback_used=bool(collected),
                fallback_pages=selected_pages,
            ),
        )

    @staticmethod
    def _extract_page_text(pdf_path: Path, page_number: int) -> str:
        try:
            doc = fitz.open(pdf_path)
        except Exception:
            return ""
        try:
            idx = int(page_number) - 1
            if idx < 0 or idx >= len(doc):
                return ""
            return (doc[idx].get_text("text") or "").strip()
        finally:
            doc.close()

    @staticmethod
    def _select_candidate_pages(pdf_path: Path, page_budget: int) -> List[int]:
        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            logger.warning("Cloud fallback could not open PDF %s: %s", pdf_path, exc)
            return []

        scored: List[tuple[int, int]] = []
        try:
            for idx, page in enumerate(doc):
                text = (page.get_text("text") or "").strip()
                if not text:
                    continue
                lowered = text.lower()
                num_like = len(re.findall(r"\b\d+(?:\.\d+)?\b", lowered))
                pipe_count = lowered.count("|")
                tab_count = lowered.count("\t")
                table_keyword = 2 if "table" in lowered else 0
                score = min(num_like, 10) + min(pipe_count + tab_count, 10) + table_keyword
                if score > 0:
                    scored.append((idx + 1, score))
        finally:
            doc.close()

        if not scored:
            return []

        scored.sort(key=lambda item: (-item[1], item[0]))
        top = [page for page, _ in scored[: max(1, int(page_budget))]]
        return sorted(set(top))

    def _extract_page_tables_with_llm(self, page_text: str, page_number: int) -> List[Any] | None:
        if self.client is None:
            return None

        prompt = (
            "Extract machine-readable tables from this PDF page text. "
            "Return strict JSON object with key 'tables'. Each table must contain 'data' "
            "as 2D array of strings including header row. Skip narrative text."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You extract tables only. Output valid JSON only.",
                    },
                    {
                        "role": "user",
                        "content": f"{prompt}\n\nPage: {page_number}\n\nText:\n{page_text}",
                    },
                ],
            )
        except Exception as exc:
            logger.warning("Cloud table fallback request failed on page %s: %s", page_number, exc)
            return None

        content = ""
        try:
            content = response.choices[0].message.content or ""
            payload = json.loads(content)
        except Exception as exc:
            logger.warning("Cloud table fallback JSON parse failed on page %s: %s", page_number, exc)
            return None

        raw_tables = payload.get("tables", []) if isinstance(payload, dict) else []
        if not isinstance(raw_tables, list):
            return []
        return raw_tables

    @staticmethod
    def _normalize_table_rows(rows: Any) -> List[List[str]]:
        if not isinstance(rows, list):
            return []
        normalized: List[List[str]] = []
        for row in rows:
            if isinstance(row, list):
                normalized.append([str(cell or "").strip() for cell in row])
            elif isinstance(row, dict):
                normalized.append([str(v or "").strip() for v in row.values()])
        return [r for r in normalized if any(cell for cell in r)]

    def _evaluate_table_quality(self, rows: List[List[str]]) -> tuple[bool, List[str]]:
        failures: List[str] = []
        if len(rows) < 2:
            return False, failures

        max_cols = max((len(row) for row in rows), default=0)
        if max_cols <= 1:
            return False, failures

        total_cells = max_cols * len(rows)
        non_empty = 0
        for row in rows:
            padded = row + [""] * max(0, max_cols - len(row))
            non_empty += sum(1 for cell in padded if str(cell or "").strip())
        coverage = (non_empty / total_cells) if total_cells > 0 else 0.0
        if coverage < 0.35:
            failures.append(TABLE_FAIL_CELL_COVERAGE_LOW)

        overlap_ratio = CloudTableFallbackExtractor._estimate_overlap_ratio(rows, max_cols)
        if overlap_ratio >= 0.5:
            failures.append(TABLE_FAIL_CELL_OVERLAP_HIGH)

        return len(failures) == 0, failures

    @staticmethod
    def _estimate_overlap_ratio(rows: List[List[str]], max_cols: int) -> float:
        # Heuristic overlap proxy: repeated identical rows imply collapsed/overlapped cells.
        canonical: List[tuple[str, ...]] = []
        for row in rows:
            padded = row + [""] * max(0, max_cols - len(row))
            canonical.append(tuple(str(cell or "").strip().lower() for cell in padded))
        if not canonical:
            return 0.0
        unique_count = len(set(canonical))
        return 1.0 - (unique_count / len(canonical))
