#!/usr/bin/env python3
"""Pre-final validation hook for world-cup-predictor run folders."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_FILES = ["source-ledger.md", "facts.json", "decision-matrix.md", "handoff.md"]
FINAL_DISCLAIMER = "# 仅供娱乐参考"
SELECTED_STATUSES = ("stable selected", "high selected")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def read_text(path: Path, result: ValidationResult) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        result.errors.append(f"missing required file: {path.name}")
    except UnicodeDecodeError:
        result.errors.append(f"file is not utf-8 text: {path.name}")
    return ""


def load_facts(path: Path, result: ValidationResult) -> dict[str, Any]:
    text = read_text(path, result)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        result.errors.append(f"facts.json is invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        result.errors.append("facts.json must contain an object")
        return {}
    return payload


def final_line(path: Path, result: ValidationResult) -> str:
    if not path:
        return ""
    text = read_text(path, result)
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def validate_required_files(run_dir: Path, result: ValidationResult) -> None:
    for name in REQUIRED_FILES:
        if not (run_dir / name).is_file():
            result.errors.append(f"missing required file: {name}")


def validate_source_ledger(run_dir: Path, result: ValidationResult) -> None:
    ledger = read_text(run_dir / "source-ledger.md", result)
    if "Sporttery" not in ledger and "sporttery" not in ledger:
        result.errors.append("source-ledger.md must include Sporttery as primary multiplier source")
    if "Polymarket" in ledger and "auxiliary" not in ledger.lower():
        result.warnings.append("Polymarket appears in source ledger; label it auxiliary/context only")


def validate_facts(facts: dict[str, Any], result: ValidationResult) -> None:
    if not facts.get("scope") and not facts.get("match"):
        result.errors.append("facts.json must include scope or match identity")
    if not facts.get("fixtures") and not facts.get("match"):
        result.errors.append("facts.json must include fixtures or match details")
    if not facts.get("sporttery_odds"):
        result.errors.append("facts.json must include sporttery_odds")
    if "historical_context" not in facts:
        result.warnings.append("facts.json has no historical_context; final conclusion may be under-supported")
    if "data_gaps" not in facts:
        result.errors.append("facts.json must include data_gaps, even when empty")


def selected_lines(matrix: str) -> list[str]:
    rows = []
    for line in matrix.splitlines():
        lowered = line.lower()
        if any(status in lowered for status in SELECTED_STATUSES):
            rows.append(line)
    return rows


def validate_decision_matrix(run_dir: Path, result: ValidationResult) -> None:
    matrix = read_text(run_dir / "decision-matrix.md", result)
    rows = selected_lines(matrix)
    if not rows:
        result.errors.append("decision-matrix.md must include at least one selected reference")
        return
    for row in rows:
        if "Polymarket" in row or "Covers" in row or "Kalshi" in row:
            result.errors.append("selected rows must not use Polymarket/Covers/Kalshi as final multiplier source")
        if "Sporttery" not in row and not any(code in row for code in [" had ", " hhad ", " crs ", " ttg ", " hafu "]):
            result.errors.append(f"selected row is missing Sporttery pool evidence: {row}")
        if "n/a" in row.lower():
            result.errors.append(f"selected row cannot use n/a multiplier: {row}")


def validate_handoff(run_dir: Path, result: ValidationResult) -> None:
    handoff = read_text(run_dir / "handoff.md", result)
    for heading in ["## Verified", "## Missing Or Conflicting", "## Decisions"]:
        if heading not in handoff:
            result.errors.append(f"handoff.md missing heading: {heading}")


def validate(run_dir: Path | str, final_answer: Path | str | None = None) -> ValidationResult:
    root = Path(run_dir)
    result = ValidationResult()
    validate_required_files(root, result)
    facts = load_facts(root / "facts.json", result)
    validate_source_ledger(root, result)
    validate_facts(facts, result)
    validate_decision_matrix(root, result)
    validate_handoff(root, result)
    if final_answer:
        line = final_line(Path(final_answer), result)
        if line != FINAL_DISCLAIMER:
            result.errors.append(f"final line must be exactly {FINAL_DISCLAIMER!r}")
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate world-cup-predictor run files before final output.")
    parser.add_argument("run_dir", help="Run folder, for example work/world-cup-predictor/YYYYMMDD-HHMM")
    parser.add_argument("--final-answer", help="Optional markdown draft to check final disclaimer line.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = validate(args.run_dir, args.final_answer)
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if result.ok:
        print("pre-final validation ok")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
