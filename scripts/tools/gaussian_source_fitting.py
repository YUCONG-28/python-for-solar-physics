#!/usr/bin/env python3
"""Compatibility import for shared rotated 2D Gaussian fitting helpers."""

from solar_toolkit.modeling.gaussian import (
    IntArray,
    _true_indices,
    _unravel_2d_index,
    elliptical_gaussian_2d,
    fit_elliptical_gaussian,
    initial_guess_from_peak,
    true_indices,
    unravel_2d_index,
)

__all__ = [
    "IntArray",
    "elliptical_gaussian_2d",
    "fit_elliptical_gaussian",
    "initial_guess_from_peak",
    "true_indices",
    "unravel_2d_index",
    "_true_indices",
    "_unravel_2d_index",
]
