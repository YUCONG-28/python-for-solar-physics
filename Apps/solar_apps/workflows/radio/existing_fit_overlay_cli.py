"""CLI adapter for static overlays from existing radio-source tables."""

from __future__ import annotations

import argparse
import json

from solar_toolkit.radio.existing_fit_overlay import (
    ExistingFitOverlayRequest,
    render_existing_fit_overlay,
)

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Overlay existing center and/or Gaussian CSV products without "
            "running source localization."
        )
    )
    parser.add_argument("--center-csv", help="Existing threshold/contour center CSV.")
    parser.add_argument("--gaussian-csv", help="Existing Gaussian diagnostics CSV.")
    parser.add_argument("--aia-fits", help="Optional AIA FITS background.")
    parser.add_argument("--output-dir", default="existing_fit_overlay")
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--marker-size", type=int, default=10)
    parser.add_argument("--theme", choices=("auto", "light", "dark"), default="light")
    parser.add_argument(
        "--markers-only",
        action="store_true",
        help="Draw source markers without connecting time-series lines.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = render_existing_fit_overlay(
        ExistingFitOverlayRequest(
            center_csv=args.center_csv,
            gaussian_csv=args.gaussian_csv,
            aia_fits=args.aia_fits,
            output_dir=args.output_dir,
            width=args.width,
            height=args.height,
            marker_size=args.marker_size,
            theme=args.theme,
            draw_lines=not args.markers_only,
        )
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
