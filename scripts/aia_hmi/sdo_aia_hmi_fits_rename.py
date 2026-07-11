"""Compatibility CLI for :mod:`solar_toolkit.hmi.fits_rename`.

The reusable filename classification and rename implementation lives in the
installed ``solar_toolkit`` package. This historical script keeps its editable
path and dry-run defaults so existing direct-run workflows continue to work.
"""

from __future__ import annotations

from solar_toolkit.hmi.fits_rename import (
    AIA_EUV_PREFIX,
    AIA_EUV_WAVELENGTHS,
    AIA_IMAGE_PATTERN,
    AIA_UV_PREFIX,
    AIA_UV_WAVELENGTHS,
    HMI_MAGNETOGRAM_PATTERN,
    HMI_PREFIX,
    KNOWN_PREFIXES,
    RenameDecision,
    RenameSummary,
    build_target_name,
    decide_rename,
    expected_prefix_for_payload,
    iter_fits_files,
    parse_args,
    print_summary,
    rename_fits_files,
    strip_known_prefix,
)
from solar_toolkit.hmi.fits_rename import main as _package_main

# Historical direct-run configuration. Keep these names local so existing
# workflows and tests can override them without mutating the public package.
TARGET_FOLDER = r"<PROJECT_ROOT>\2026\20260326\SDO"
DRY_RUN = True


def main(argv: list[str] | None = None) -> int:
    """Run the package CLI with this script's compatibility defaults."""
    return _package_main(
        argv,
        target_folder=TARGET_FOLDER,
        default_dry_run=DRY_RUN,
        rename_func=rename_fits_files,
    )


__all__ = [
    "AIA_EUV_PREFIX",
    "AIA_EUV_WAVELENGTHS",
    "AIA_IMAGE_PATTERN",
    "AIA_UV_PREFIX",
    "AIA_UV_WAVELENGTHS",
    "DRY_RUN",
    "HMI_MAGNETOGRAM_PATTERN",
    "HMI_PREFIX",
    "KNOWN_PREFIXES",
    "RenameDecision",
    "RenameSummary",
    "TARGET_FOLDER",
    "build_target_name",
    "decide_rename",
    "expected_prefix_for_payload",
    "iter_fits_files",
    "main",
    "parse_args",
    "print_summary",
    "rename_fits_files",
    "strip_known_prefix",
]


if __name__ == "__main__":
    raise SystemExit(main())
