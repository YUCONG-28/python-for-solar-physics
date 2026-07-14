"""Persist same-page drift endpoint selections without launching another UI."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["build_parser", "main", "run"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate explicit two-point drift lines and save compatible JSON and "
            "diagnostic CSV products."
        )
    )
    parser.add_argument(
        "--drift-lines-json",
        required=True,
        help="JSON array of explicit drift-line endpoint objects.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output folder managed by the calling workspace.",
    )
    return parser


def run(
    drift_lines_json: str | Sequence[Mapping[str, Any]] | Mapping[str, Any],
    output_dir: str | Path = ".",
) -> tuple[Path, Path]:
    """Validate selected lines through the canonical drift calculator and save them."""

    from solar_toolkit.radio.drift_rate import calculate_drift_rate_from_line

    raw_lines = _parse_lines(drift_lines_json)
    if not raw_lines:
        raise ValueError("At least one explicit drift line is required")
    normalized_lines: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_lines, start=1):
        line = dict(raw)
        line.setdefault("label", f"drift_{index:03d}")
        line.setdefault("mode", "manual")
        line.setdefault("color", "white")
        line.setdefault("note", "")
        result = calculate_drift_rate_from_line(line)
        normalized_lines.append(
            {
                "label": result.label,
                "mode": result.mode,
                "t_start": result.t_start.isoformat(timespec="milliseconds"),
                "f_start_mhz": float(result.f_start_mhz),
                "t_end": result.t_end.isoformat(timespec="milliseconds"),
                "f_end_mhz": float(result.f_end_mhz),
                "color": result.color,
                "note": str(line.get("note", "")),
            }
        )
        row = asdict(result)
        row["t_start"] = result.t_start.isoformat(timespec="milliseconds")
        row["t_end"] = result.t_end.isoformat(timespec="milliseconds")
        diagnostics.append(row)

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "drift_rate_selection.json"
    csv_path = output / "drift_rate_diagnostics.csv"
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "radio-workspace-same-page-selection",
        "lines": normalized_lines,
    }
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(diagnostics[0]))
        writer.writeheader()
        writer.writerows(diagnostics)
    return json_path, csv_path


def _parse_lines(
    value: str | Sequence[Mapping[str, Any]] | Mapping[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid drift-line JSON: {exc.msg}") from exc
    else:
        payload = value
    if isinstance(payload, Mapping):
        payload = payload.get("lines")
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise TypeError("Drift-line JSON must be an array or an object with lines")
    lines: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise TypeError("Every drift line must be a JSON object")
        lines.append(dict(item))
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    json_path, csv_path = run(args.drift_lines_json, args.output_dir)
    print(f"Drift selection: {json_path}")
    print(f"Drift diagnostics: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
