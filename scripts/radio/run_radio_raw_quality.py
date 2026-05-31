"""Entrypoint for raw radio FITS quality diagnostics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.radio.configs import load_radio_output_config, load_radio_user_config
    from scripts.radio.core.radio_raw_quality import analyze_radio_raw_quality
else:
    from .configs import load_radio_output_config, load_radio_user_config
    from .core.radio_raw_quality import analyze_radio_raw_quality


DEFAULT_RAW_QUALITY_CONFIG = "radio_20250503_config"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan radio FITS directories and report raw-data quality issues."
    )
    parser.add_argument("--config", default=DEFAULT_RAW_QUALITY_CONFIG)
    parser.add_argument("--root")
    parser.add_argument("--output-dir")
    parser.add_argument("--start-idx", type=int)
    parser.add_argument("--end-idx", type=int)
    parser.add_argument("--freqs", help="Comma-separated frequencies in MHz.")
    parser.add_argument("--polarizations", help="Comma-separated polarizations.")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    root: str | Path | None = None,
    freqs: list[int | float] | None = None,
    polarizations: list[str] | tuple[str, ...] | None = None,
    output_dir: str | Path | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
):
    """Run raw radio quality diagnostics from config, CLI, or direct parameters."""

    args = _parse_args(argv) if _should_parse_args(root, freqs, output_dir) else None
    config_name = args.config if args is not None else DEFAULT_RAW_QUALITY_CONFIG
    user_config, _newkirk_config = load_radio_user_config(config_name)
    output_config = load_radio_output_config(config_name)
    data_cfg = user_config.get("data", {})

    resolved_root = root or (args.root if args is not None else None)
    resolved_root = resolved_root or data_cfg.get("multi_band_root")
    if not resolved_root:
        raise ValueError("Radio root is required; set --root or data.multi_band_root.")

    resolved_freqs = (
        freqs
        or (_parse_freqs(args.freqs) if args is not None else [])
        or list(data_cfg.get("multi_band_freqs", []))
    )
    if not resolved_freqs:
        raise ValueError("At least one frequency is required; set --freqs.")

    resolved_pols = (
        polarizations
        or (_parse_polarizations(args.polarizations) if args is not None else [])
        or _default_polarizations(data_cfg)
    )
    resolved_start = (
        start_idx
        if start_idx is not None
        else (
            args.start_idx if args is not None and args.start_idx is not None else None
        )
    )
    resolved_end = (
        end_idx
        if end_idx is not None
        else (args.end_idx if args is not None and args.end_idx is not None else None)
    )
    resolved_output = output_dir or (args.output_dir if args is not None else None)
    resolved_output = (
        resolved_output
        or output_config.get("output_dir")
        or user_config.get("output", {}).get("output_dir")
        or "outputs"
    )

    result = analyze_radio_raw_quality(
        resolved_root,
        freqs=[float(freq) for freq in resolved_freqs],
        polarizations=list(resolved_pols),
        output_dir=resolved_output,
        start_idx=int(
            resolved_start
            if resolved_start is not None
            else data_cfg.get("start_idx", 0)
        ),
        end_idx=(
            int(resolved_end)
            if resolved_end is not None
            else (
                int(data_cfg["end_idx"])
                if data_cfg.get("end_idx") is not None
                else None
            )
        ),
    )
    _print_summary(result)
    return result


def _should_parse_args(
    root: str | Path | None,
    freqs: list[int | float] | None,
    output_dir: str | Path | None,
) -> bool:
    return root is None or freqs is None or output_dir is None


def _parse_freqs(raw: str | None) -> list[float]:
    if not raw:
        return []
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def _parse_polarizations(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_polarizations(data_cfg: dict) -> list[str]:
    polarization = str(data_cfg.get("polarization", "RR") or "RR")
    if polarization == "RR+LL" or data_cfg.get("combine_polarizations", False):
        return ["RR", "LL"]
    return [polarization]


def _print_summary(result) -> None:
    bad_files = sum(1 for row in result.file_rows if row.quality_flag == "bad")
    bad_slots = sum(1 for row in result.slot_rows if row.quality_flag == "bad")
    print("[Radio Raw Quality] outputs:")
    print(f"  File diagnostics: {result.file_csv_path}")
    print(f"  Slot diagnostics: {result.slot_csv_path}")
    print(f"  Bad files: {bad_files}/{len(result.file_rows)}")
    print(f"  Bad slots: {bad_slots}/{len(result.slot_rows)}")


if __name__ == "__main__":
    main()
