"""Analytic Gaussian models used by radio-source fitting."""

from __future__ import annotations

from solar_toolkit.modeling.gaussian import elliptical_gaussian_2d

__all__ = [
    "elliptical_gaussian_2d",
    "elliptical_gaussian_2d_with_constant_bg",
    "elliptical_gaussian_2d_with_plane_bg",
    "gaussian_only_from_popt",
]


def elliptical_gaussian_2d_with_constant_bg(xy, A, x0, y0, sigma_x, sigma_y, theta, b0):
    return elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta) + b0


def elliptical_gaussian_2d_with_plane_bg(
    xy, A, x0, y0, sigma_x, sigma_y, theta, b0, bx, by
):
    x, y = xy
    return (
        elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta)
        + b0
        + bx * x
        + by * y
    )


def gaussian_only_from_popt(xy, popt, background_model):
    return elliptical_gaussian_2d(xy, *popt[:6])
