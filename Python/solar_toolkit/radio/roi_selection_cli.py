"""Normalize Plotly ROI selections into the package ``RadioRoi`` JSON schema."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = ["build_parser", "main", "run"]

_OUTPUT_NAME = "radio_roi_selection.json"


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone ROI-selection normalizer parser."""

    parser = argparse.ArgumentParser(
        description="Normalize a Plotly box/lasso selection into RadioRoi JSON."
    )
    parser.add_argument(
        "--roi-json-payload",
        required=True,
        help="Plotly selection or existing RadioRoi JSON object.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Workspace-managed output directory; default is the current directory.",
    )
    return parser


def run(
    roi_json_payload: str | Mapping[str, Any],
    output_dir: str | Path = ".",
) -> Path:
    """Normalize one selection and write ``radio_roi_selection.json``."""

    payload = _load_payload(roi_json_payload)

    # Lazy import keeps the CLI help path free of NumPy and the FITS stack.
    from solar_toolkit.radio.roi_lightcurve import RadioRoi, radio_roi_from_json

    if _is_radio_roi_payload(payload):
        roi = radio_roi_from_json(payload)
    else:
        selection = payload.get("selection", payload)
        if not isinstance(selection, Mapping):
            raise ValueError("Plotly 'selection' must be a JSON object.")
        label = str(payload.get("label", selection.get("label", "")))
        lasso = selection.get("lassoPoints")
        box = selection.get("range")
        if isinstance(lasso, Mapping):
            xs, ys = _xy_lists(lasso, name="lassoPoints", minimum=3)
            roi = RadioRoi.from_polygon(
                list(zip(xs, ys, strict=True)),
                label=label,
            )
        elif isinstance(box, Mapping):
            xs, ys = _xy_lists(box, name="range", minimum=2)
            roi = RadioRoi.from_box(
                xs[0],
                ys[0],
                xs[1],
                ys[1],
                label=label,
            )
        else:
            raise ValueError(
                "ROI payload must contain Plotly 'range', Plotly 'lassoPoints', "
                "or an existing RadioRoi JSON object."
            )

    workspace_dir = Path(output_dir).expanduser().resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    output_path = workspace_dir / _OUTPUT_NAME
    output_path.write_text(
        json.dumps(roi.to_json_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    """Run the ROI normalizer and print the generated JSON path."""

    args = build_parser().parse_args(argv)
    output_path = run(args.roi_json_payload, args.output_dir)
    print(f"Radio ROI selection: {output_path}")
    return 0


def _load_payload(source: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    if not isinstance(source, str):
        raise ValueError("roi_json_payload must be a JSON object or JSON text.")
    try:
        payload = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"roi_json_payload must be valid JSON: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})."
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("roi_json_payload must decode to a JSON object.")
    return payload


def _is_radio_roi_payload(payload: Mapping[str, Any]) -> bool:
    candidate = payload.get("roi", payload)
    return isinstance(candidate, Mapping) and any(
        key in candidate for key in ("vertices_arcsec", "bounds_arcsec", "kind")
    )


def _xy_lists(
    payload: Mapping[str, Any],
    *,
    name: str,
    minimum: int,
) -> tuple[list[float], list[float]]:
    xs = _finite_values(payload.get("x"), field=f"{name}.x")
    ys = _finite_values(payload.get("y"), field=f"{name}.y")
    if len(xs) != len(ys):
        raise ValueError(f"{name}.x and {name}.y must have the same length.")
    if len(xs) < minimum:
        raise ValueError(f"{name} requires at least {minimum} coordinate pairs.")
    return xs, ys


def _finite_values(source: Any, *, field: str) -> list[float]:
    if (
        not isinstance(source, Sequence)
        or isinstance(source, (str, bytes, bytearray))
        or not source
    ):
        raise ValueError(f"{field} must be a non-empty JSON array of numbers.")
    values: list[float] = []
    for index, raw in enumerate(source):
        if isinstance(raw, bool):
            raise ValueError(f"{field}[{index}] must be a finite number.")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field}[{index}] must be a finite number.") from exc
        if not math.isfinite(value):
            raise ValueError(f"{field}[{index}] must be a finite number.")
        values.append(value)
    return values


if __name__ == "__main__":
    raise SystemExit(main())
