"""Shared pure helpers for rotated 2D Gaussian source fitting."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import curve_fit

IntArray = NDArray[np.intp]


def elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta):
    """Evaluate a rotated elliptical 2D Gaussian model."""

    x, y = xy
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    x_rot = (x - x0) * cos_t + (y - y0) * sin_t
    y_rot = -(x - x0) * sin_t + (y - y0) * cos_t
    exponent = (x_rot**2) / (2 * sigma_x**2) + (y_rot**2) / (2 * sigma_y**2)
    return A * np.exp(-exponent)


def unravel_2d_index(
    flat_index: int | np.integer, shape: tuple[int, ...]
) -> tuple[int, int]:
    """Return integer 2D coordinates for a flattened index."""

    coords = np.asarray(np.unravel_index(int(flat_index), shape), dtype=np.intp)
    return int(coords[0]), int(coords[1])


def true_indices(mask: np.ndarray) -> IntArray:
    """Return one-dimensional indices where ``mask`` is true."""

    mask_bool = np.asarray(mask, dtype=np.bool_)
    return np.asarray(np.nonzero(mask_bool)[0], dtype=np.intp)


def initial_guess_from_peak(data, x, y):
    """Build the legacy peak/FWHM initial guess for Gaussian fitting."""

    max_y, max_x = unravel_2d_index(int(np.argmax(data)), data.shape)
    init_x0 = x[max_x]
    init_y0 = y[max_y]
    init_A = np.max(data)

    half_max = init_A / 2.0
    row_max = data[max_y, :]
    indices = true_indices(row_max >= half_max)
    if len(indices) > 1:
        init_sigma_x = (x[indices[-1]] - x[indices[0]]) / 2.355
    else:
        init_sigma_x = (x[-1] - x[0]) / 10.0

    col_max = data[:, max_x]
    indices_y = true_indices(col_max >= half_max)
    if len(indices_y) > 1:
        init_sigma_y = (y[indices_y[-1]] - y[indices_y[0]]) / 2.355
    else:
        init_sigma_y = (y[-1] - y[0]) / 10.0

    return (init_A, init_x0, init_y0, init_sigma_x, init_sigma_y, 0.0)


def fit_elliptical_gaussian(data, x, y, initial_guess=None):
    """Fit the legacy rotated 2D Gaussian model to image data.

    This function preserves the model, initial-guess rule, bounds, and
    ``curve_fit`` settings used by the legacy script-level implementation.
    """

    X, Y = np.meshgrid(x, y)
    x_flat = X.ravel()
    y_flat = Y.ravel()
    data_flat = data.ravel()

    if initial_guess is None:
        initial_guess = initial_guess_from_peak(data, x, y)

    bounds = (
        [0, -np.inf, -np.inf, 1e-3, 1e-3, -np.pi / 2],
        [np.inf, np.inf, np.inf, np.inf, np.inf, np.pi / 2],
    )

    popt, pcov = curve_fit(
        elliptical_gaussian_2d,
        (x_flat, y_flat),
        data_flat,
        p0=initial_guess,
        bounds=bounds,
        maxfev=5000,
    )
    return popt, pcov


# Backward-compatible private names used by older scripts/tests.
_unravel_2d_index = unravel_2d_index
_true_indices = true_indices
