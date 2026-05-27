# Newkirk Height Comparison Revision Report

Date: 2026-05-27

## Why The Previous Spatial Projection Is Limited

The Newkirk model is a one-dimensional radial electron-density model. It maps
electron density to heliocentric radius, but it does not specify longitude,
latitude, line-of-sight depth, or a unique `x/y` location on an AIA image. Any
plane-of-sky position requires an extra geometric assumption. The earlier
Gaussian-anchored plane-of-sky projection is therefore useful only as an
illustrative schematic, not as a physical 2D reconstruction.

## Why Height Comparison Is More Rigorous

The revised diagnostic compares quantities that both methods can support more
directly:

- Gaussian radio fitting gives a projected distance from Sun center.
- Newkirk inversion gives a radial height from radio frequency.

Comparing projected Gaussian height with Newkirk-derived height avoids treating
the Newkirk model as a source of true image-plane positions. The main
scientific products are now height tables, height-frequency plots,
height-time plots, and Gaussian-Newkirk height residuals.

## Gaussian Projected Height

The Gaussian projected height is computed from the fitted radio source center:

```text
rho = sqrt(x_arcsec^2 + y_arcsec^2) / solar_radius_arcsec
height = rho - 1
```

Rows inside the disk have negative projected height and are flagged with
`inside_disk_projected_distance_only`, because the projected distance is not a
true radial height.

## Newkirk Height

The Newkirk height is computed from the observed radio frequency:

```text
f = s f_p
n_e = (1000 f_MHz / (8.98 s))^2
n_e(r) = M * 4.2e4 * 10^(4.32 / r)
height = r - 1
```

Here `s` is the harmonic and `M` is the Newkirk multiplier. The configured model
set compares `1x`, `2x`, and `4x` Newkirk with `s=1` and `s=2`.

## Generated Plots

When `NEWKIRK_HEIGHT_COMPARISON_CONFIG["enable"]` is true, the pipeline writes:

- `gaussian_newkirk_height_comparison_table.csv`
- `gaussian_vs_newkirk_height_frequency.png`
- `gaussian_vs_newkirk_height_time.png`
- `gaussian_newkirk_height_residual_vs_frequency.png`

The optional old projection schematic remains available only when
`NEWKIRK_SPATIAL_CONFIG["enable"]` is explicitly set to true.

## Remaining Caveats

- Plane-of-sky projection: Gaussian projected height is a lower-limit style
  projected distance, not a full 3D height.
- Scattering/refraction: radio source centroids may be shifted by coronal
  propagation effects.
- Harmonic ambiguity: `s=1` and `s=2` can imply meaningfully different heights.
- Newkirk multiplier uncertainty: `1x`, `2x`, and `4x` represent different
  density assumptions.
- Gaussian fitting uncertainty: center quality, source mask, and FWHM diagnostics
  still control how trustworthy the projected Gaussian height is.
