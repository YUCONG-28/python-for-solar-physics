# Radio Source Map Refactor Report

Date: 2026-05-22

## Scope

Phase 3B reviews the radio source-map scripts and keeps the basic workflow
separate from the advanced Gaussian/spectrogram/drift-rate workflow. No files
were deleted, moved, or renamed. No real FITS plotting workflow was run.

## Main Code

Primary radio source-map workflow:

- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`

This remains the main code for:

- radio source map plotting;
- background-aware Gaussian fitting and overlays;
- fitted-center/FWHM/residual diagnostics;
- CSO spectrogram panels;
- manual/JSON drift-rate selection and overlay;
- drift-rate diagnostics.

No Gaussian fitting model, FWHM conversion, residual calculation, coordinate
orientation rule, or drift-rate formula was changed in this phase.

## Basic Code

Basic retained entry point:

- `scripts/radio/radio_source_map_plot.py`

This file should remain the simplest runnable radio source-map script. It keeps:

- `read_fits`;
- `calc_extent`;
- `TimeParser`;
- `main`;
- basic single-band plotting;
- basic multi-band plotting;
- RR/LL matching and optional RR+LL combination;
- color-range and simple layout controls.

It should not grow Gaussian fitting, drift-rate selection, browser/frontend
tools, background fitting, residual panels, or spectrogram-panel logic. Those
belong in `radio_source_map_plot_gaussian_overlay.py`.

## Comparison Summary

| Area | Basic script | Advanced script | Phase 3B decision |
| --- | --- | --- | --- |
| FITS reading | `read_fits` reads 2D image data from ImageHDU or primary HDU | Same basic pattern | Keep local in both for now; low risk but not worth changing without caller tests |
| Extent/origin | `calc_extent` uses legacy `[x_min, x_max, y_max, y_min]` with plotting calls using `origin="upper"` | Uses preserved FITS WCS edge extent plus selected origin, usually `origin="lower"` | Do not replace. Added TODO in basic script to compare against `solar_toolkit.coordinates` before migration |
| Time parsing | `TimeParser` supports multiple date formats and filename patterns | Similar parser exists in advanced script | Keep local for now. Added TODO in basic script; extract only after filename parity tests |
| Single-band plotting | Present | Present, plus Gaussian/background/spectrogram options | Keep basic version local |
| Multi-band plotting | Present | Present with extra layout, background, Gaussian and spectrogram integration | Keep basic version local |
| Gaussian fitting | Not present in basic script | Present and complex | Keep only in advanced script |
| Spectrogram panel | Not present in basic script | Present | Keep only in advanced script |
| Drift-rate selection | Not present in basic script | Present | Keep only in advanced script |
| Browser/frontend | Not present in basic script | Present for drift selection | Keep only in advanced script |

## Changes Made

Only two TODO notes were added to `scripts/radio/radio_source_map_plot.py`:

- `calc_extent`: documents why the legacy `origin="upper"` coordinate mapping
  was not replaced by the newer shared coordinate helpers yet.
- `TimeParser`: documents the duplicate parser and the need for filename-format
  parity tests before extraction.

No functional code path was changed.

## Duplicates Not Yet Merged

The following duplicate or near-duplicate areas remain intentionally untouched:

- `read_fits`
  - Simple and duplicated, but keeping it local avoids unintended import and
    dependency changes in the basic entry point.
- `calc_extent` / radio origin handling
  - High risk because the basic and advanced scripts currently use different
    display-origin conventions.
- `TimeParser`
  - Needs parameterized filename tests across both scripts before extraction.
- RR/LL matching helpers
  - Similar behavior exists in both scripts, but any change could alter which
    files are paired in real observations.
- color-range helpers
  - Similar but tied to different plotting modes and diagnostics.

## Delete Or Legacy Candidates

No deletion is recommended in this phase.

Recommended final keep set:

- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
- `scripts/radio/radio_source_map_plot.py`

Recommended legacy files:

- None for now. `radio_source_map_plot.py` is not legacy; it is the retained
  basic workflow.

Deletion candidates:

- None.

## Manual Review Before Future Extraction

Before replacing basic-script coordinate or time parsing logic, manually verify:

- radio source positions are not flipped vertically or horizontally;
- `CDELT1`/`CDELT2` sign handling matches expected FITS WCS orientation;
- `origin="upper"` vs `origin="lower"` changes do not move plotted sources;
- RR/LL file pairing is unchanged for real observing sequences;
- filename parsing matches 6-digit, 7-digit, millisecond, and no-millisecond
  historical file patterns.

## Algorithm Impact

This phase did not change scientific algorithms. It did not change Gaussian
fitting, drift-rate calculation, radio FITS coordinate direction handling, or
plotting computations. The only code edits are TODO documentation comments in
the basic radio source-map script.
