"""Pure helpers for normalizing SDO/AIA and SDO/HMI FITS filenames."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AIA_UV_PREFIX = "aia.lev1_uv_24s"
AIA_EUV_PREFIX = "aia.lev1_euv_12s"
HMI_PREFIX = "hmi.M_45s"

AIA_UV_WAVELENGTHS = {"1600"}
AIA_EUV_WAVELENGTHS = {"94", "131", "171", "193", "211", "304", "335"}
KNOWN_PREFIXES = (AIA_UV_PREFIX, AIA_EUV_PREFIX, HMI_PREFIX)

AIA_IMAGE_PATTERN = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2}T\d{6}Z)\." r"(?P<wavelength>\d+)\.image_lev1\.fits$",
    re.IGNORECASE,
)
HMI_MAGNETOGRAM_PATTERN = re.compile(
    r"^\d{8}_\d{6}_TAI\.\d+\.magnetogram\.fits$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RenameDecision:
    """Describe the action selected for one FITS path."""

    action: str
    source: Path
    target: Path | None
    message: str


@dataclass
class RenameSummary:
    """Collect counts from a recursive rename operation."""

    renamed: int = 0
    planned: int = 0
    skipped: int = 0
    unrecognized: int = 0
    conflicts: int = 0


def strip_known_prefix(filename: str) -> tuple[str | None, str]:
    """Return an existing standard prefix and the remaining filename."""

    for prefix in KNOWN_PREFIXES:
        marker = f"{prefix}."
        if filename.startswith(marker):
            return prefix, filename[len(marker) :]
    return None, filename.lstrip(".")


def expected_prefix_for_payload(payload: str) -> str | None:
    """Infer the standard product prefix from an unprefixed filename."""

    match = AIA_IMAGE_PATTERN.match(payload)
    if match:
        wavelength = match.group("wavelength")
        if wavelength in AIA_UV_WAVELENGTHS:
            return AIA_UV_PREFIX
        if wavelength in AIA_EUV_WAVELENGTHS:
            return AIA_EUV_PREFIX
        return None
    return HMI_PREFIX if HMI_MAGNETOGRAM_PATTERN.match(payload) else None


def build_target_name(filename: str) -> tuple[str | None, str]:
    """Return a normalized name and an explanation when no rename is needed."""

    existing, payload = strip_known_prefix(filename)
    expected = expected_prefix_for_payload(payload)
    if expected is None:
        return None, "unrecognized AIA/HMI product filename"
    if existing == expected:
        return None, "already normalized"
    if existing is not None:
        return None, f"existing prefix {existing!r} conflicts with {expected!r}"
    return f"{expected}.{payload}", ""


def decide_rename(path: Path) -> RenameDecision:
    """Choose whether and how to rename one filesystem path."""

    if path.suffix.lower() != ".fits":
        return RenameDecision("skipped", path, None, "not a FITS file")
    target_name, reason = build_target_name(path.name)
    if target_name is None:
        action = "unrecognized" if reason.startswith("unrecognized") else "skipped"
        return RenameDecision(action, path, None, reason)
    target = path.with_name(target_name)
    if target.exists():
        return RenameDecision("conflict", path, target, "target already exists")
    return RenameDecision("rename", path, target, "pending")


def iter_fits_files(directory: Path) -> list[Path]:
    """Return recursively discovered FITS files in deterministic order."""

    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".fits"
    )


def rename_fits_files(directory: str | Path, dry_run: bool = False) -> RenameSummary:
    """Normalize filenames under an explicit directory without overwriting."""

    root = Path(directory).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    summary = RenameSummary()
    for source in iter_fits_files(root):
        decision = decide_rename(source)
        if decision.action == "rename":
            if dry_run:
                summary.planned += 1
            else:
                assert decision.target is not None
                source.rename(decision.target)
                summary.renamed += 1
        elif decision.action == "conflict":
            summary.conflicts += 1
        elif decision.action == "unrecognized":
            summary.unrecognized += 1
        else:
            summary.skipped += 1
    return summary


__all__ = [
    "AIA_EUV_PREFIX",
    "AIA_EUV_WAVELENGTHS",
    "AIA_IMAGE_PATTERN",
    "AIA_UV_PREFIX",
    "AIA_UV_WAVELENGTHS",
    "HMI_MAGNETOGRAM_PATTERN",
    "HMI_PREFIX",
    "KNOWN_PREFIXES",
    "RenameDecision",
    "RenameSummary",
    "build_target_name",
    "decide_rename",
    "expected_prefix_for_payload",
    "iter_fits_files",
    "rename_fits_files",
    "strip_known_prefix",
]
