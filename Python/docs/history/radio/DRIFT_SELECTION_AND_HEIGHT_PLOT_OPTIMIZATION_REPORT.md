# Drift Selection and Height Plot Optimization Report

## New Drift-Selection Products

Added `scripts/radio/core/radio_drift_products.py` to preserve drift-rate selections as reproducible science artifacts after the manual or saved drift selections are finalized.

The product layer writes:

- `drift_selection/spectrogram_drift_rate_selection_preview_raw.png`
- `drift_selection/spectrogram_drift_rate_selection_preview_annotated.png`
- `drift_selection/spectrogram_drift_rate_selection_points.csv`
- `drift_selection/spectrogram_drift_rate_selection_metadata.json`
- `drift_selection/cutouts/drift_001_zoom.png`, `drift_002_zoom.png`, ...

The CSV stores one row per selected drift line with label, mode, endpoints, duration, bandwidth, drift rate, absolute drift rate, color, quality flag, and warning.

The metadata JSON stores the source file, annotated PNG path, time/frequency bounds, frequency-axis order, figure pixel size, axes bounding box, cutout names, and a full selections list with endpoint and drift-rate fields.

## Workflow Integration

`run_radio_burst_pipeline.py` now loads `DRIFT_SELECTION_PRODUCT_CONFIG` and saves the drift-selection products from either newly finalized drift selections or an existing drift-rate diagnostics CSV. This allows annotated previews and cutouts to be regenerated without forcing another interactive selection session.

Existing drift-rate diagnostics CSV behavior is preserved.

## Height-Time Plot Correction

`plot_gaussian_vs_newkirk_height_time(...)` no longer connects raw multi-frequency Gaussian or Newkirk table rows. Raw Gaussian projected heights are shown as scatter points, and raw Newkirk heights are shown as scatter points grouped by model/source type.

Connected lines are only drawn for rows with a non-empty `drift_label`, where the points represent an ordered drift-ridge sample. Empty or invalid inputs return a skipped status and do not save a misleading blank plot.

## Height-Frequency Plot Improvements

`plot_gaussian_vs_newkirk_height_frequency(...)` now shows raw Gaussian projected heights as small semi-transparent points, adds median plus IQR error bars at each frequency, plots clean Newkirk model curves, reverses the frequency axis by default, and highlights the model with the lowest median absolute height residual when possible.

Model labels use the format `2× Newkirk, s=2`.

## Residual Plot Improvements

`plot_height_residual_vs_frequency(...)` now keeps the zero-residual reference line, plots semi-transparent residual points, marks outliers with `abs(height_residual_rsun) > 0.5`, and overlays per-frequency median plus IQR summaries for each model.

It also writes:

- `gaussian_newkirk_height_residual_summary.csv`

with columns:

- `newkirk_multiplier`
- `harmonic`
- `frequency_mhz`
- `n`
- `median_residual_rsun`
- `iqr_residual_rsun`
- `mean_abs_residual_rsun`
- `outlier_count`

## Source-Type and Drift-Label Propagation

`build_gaussian_newkirk_height_table(...)` can now receive drift selections through config. If a Gaussian source time/frequency lies within the configured drift-line tolerances, the row receives `drift_label` and, when the selection carries a reliable source type, `source_type`.

Unmatched or ambiguous rows remain `source_type="unknown"` and do not receive a forced classification.

## Remaining Caveats

- Newkirk remains a 1D frequency-to-height density model, not a physical 2D reconstruction.
- Gaussian projected heights are plane-of-sky projected distances and can underestimate true radial height.
- Radio-wave scattering and refraction are not modeled here.
- Harmonic choice and Newkirk multiplier remain model assumptions.
- Drift-line source typing depends on the accuracy of manual or automatic drift selections.
- Gaussian fitting uncertainty and quality thresholds are inherited from the existing fitting workflow.
