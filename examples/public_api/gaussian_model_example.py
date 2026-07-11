"""Evaluate the public Gaussian model without external data."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from solar_toolkit.modeling.gaussian import elliptical_gaussian_2d

REQUIRES_LOCAL_DATA = False


def build_gaussian_image(size: int = 9) -> NDArray[np.float64]:
    """Return a deterministic rotated Gaussian image on a square grid."""

    if size < 3:
        raise ValueError("size must be at least 3")
    axis = np.linspace(-2.0, 2.0, size)
    x_grid, y_grid = np.meshgrid(axis, axis)
    image = elliptical_gaussian_2d(
        (x_grid, y_grid),
        1.0,
        0.0,
        0.0,
        0.8,
        1.2,
        np.deg2rad(20.0),
    )
    return np.asarray(image, dtype=np.float64)


def build_parser() -> argparse.ArgumentParser:
    """Build the no-data example parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=9)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Print array diagnostics and return a status code."""

    args = build_parser().parse_args(argv)
    image = build_gaussian_image(args.size)
    print(f"shape={image.shape} peak={image.max():.6f} sum={image.sum():.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
