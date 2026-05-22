# Shared Utilities Refactor Report

Date: 2026-05-22

## Scope

Phase 2 extracted small, stable public utilities without deleting, moving, or
renaming files. No real FITS batch processing, plotting workflow, downloads, GUI
workflow, or video generation was run.

The background-corrected experimental overlay script was reviewed for
comparison only and was not modified:

- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`

## Extracted Shared Functions

### Gaussian Fitting

New module:

- `solar_toolkit/gaussian.py`

Extracted functions:

- `elliptical_gaussian_2d`
- `unravel_2d_index`
- `true_indices`
- `initial_guess_from_peak`
- `fit_elliptical_gaussian`

Compatibility layer updated:

- `scripts/tools/gaussian_source_fitting.py`

The compatibility script now re-exports the shared Gaussian helpers. The
extracted implementation preserves the legacy no-background rotated Gaussian
model, peak/FWHM initial guess rule, parameter bounds, and `curve_fit`
`maxfev=5000` setting.

### Radio Extent/Origin

Existing shared module retained:

- `solar_toolkit/coordinates.py`

Shared pure functions:

- `calculate_fits_extent_from_header`
- `infer_image_origin_from_header`
- `normalize_radio_extent`
- `validate_extent_orientation`

These functions use mock FITS headers and do not read files or plot figures.
They provide the common baseline for later replacement of duplicated
`calc_extent`, origin, `CRPIX`/`CRVAL`/`CDELT`, and orientation handling in radio
scripts.

### CSO Spectrogram Reading

New module:

- `solar_toolkit/cso.py`

Extracted functions/classes:

- `CSOSpectrogram`
- `cso_base_datetime`
- `normalize_cso_polarization`
- `cso_unit_from_header`
- `read_cso_spectrogram_hdul`
- `read_cso_spectrogram`
- `readcso_spectrofits` legacy alias

The shared CSO reader only normalizes the duplicated FITS-reading behavior:
header date lookup, time/frequency extraction, polarization label normalization,
unit lookup, 2D single-plane handling, and 3D polarization splitting. It does
not perform plotting, downsampling, GUI work, downloads, or interactive
selection.

## Tests Added Or Retained

- `tests/test_gaussian_fitting_utils.py`
  - Uses synthetic Gaussian arrays.
  - Verifies model peak value, index helpers, initial guess behavior, and a
    synthetic no-background fit.
- `tests/test_radio_coordinates.py`
  - Uses mock FITS headers.
  - Verifies preserved vs normalized extent orientation and origin inference.
- `tests/test_cso_utils.py`
  - Uses fake HDU-like objects.
  - Verifies 2D and 3D CSO spectrogram reading without real FITS files.

No test reads real FITS files or compares real science images.

## Duplicates Not Yet Merged

The following implementations were intentionally not merged in this phase:

- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
  - Background models, background subtraction for fitting, source masks, quality
    flags, FWHM conversion in arcsec, residual panels, diagnostics CSV, and
    drift/spectrogram integration remain script-local.
- `scripts/radio/sdo_aia_radio_hmi_overlay.py`
  - Its Gaussian reprojection workflow remains script-local until a parity test
    can compare fitted centers and projected source maps.
- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
  - Not modified. Its robust/background fitting and background subtraction are
    experimental and may change scientific results.
- `scripts/radio/cso_radio_spectrogram_plot.py`
  - Memory-mapped lazy reading, chunked downsampling, plotting, axis formatting,
    and polarization-ratio calculations remain script-local.
- `scripts/radio/cso_radio_spectra_gui.py`
  - GUI classes, type-II fitting tools, DSRT support, and interactive save logic
    remain untouched.
- `examples/radio/cso_spectrogram_processing_example.py`
  - Historical example logic remains unchanged for now.

## Scientific Result Change Risks

Risk areas that require manual science review before caller replacement:

- Gaussian background models: no-background, constant-background, plane-
  background, and local-background subtraction are not equivalent.
- Source masks and robust fitting thresholds can shift fitted center, FWHM, and
  residual diagnostics.
- Radio image origin/extent changes can flip or shift plotted source positions
  if an existing script relied on legacy matplotlib orientation behavior.
- CSO memory-mapped readers and chunked downsampling may not be byte-for-byte
  equivalent to eager array loading in all workflows.
- GUI behavior may depend on side effects, labels, or interactive state not
  captured by a pure reader function.

## Core Scripts Not Yet Connected

The following core scripts have not yet been refactored to call the new shared
utilities:

- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
- `scripts/radio/sdo_aia_radio_hmi_overlay.py`
- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
- `scripts/radio/cso_radio_spectrogram_plot.py`
- `scripts/radio/cso_spectrogram_class.py`
- `scripts/radio/cso_radio_spectra_gui.py`
- `examples/radio/cso_spectrogram_processing_example.py`

Only `scripts/tools/gaussian_source_fitting.py` was connected as a compatibility
re-export because it is already the simple utility entry point.

## Next Stage Recommendations

1. Add parity tests that compare old script-local Gaussian helpers with
   `solar_toolkit.gaussian` on synthetic arrays.
2. Replace the simple no-background Gaussian implementation in
   `scripts/radio/sdo_aia_radio_hmi_overlay.py` only after center/FWHM parity is
   confirmed.
3. Keep background-corrected Gaussian logic separate until the science owner
   reviews background subtraction and robust mask behavior.
4. Introduce radio extent/origin helpers into plotting scripts behind a
   compatibility flag or with screenshot/coordinate parity tests.
5. Use `solar_toolkit.cso.read_cso_spectrogram_hdul` first in non-GUI examples,
   then evaluate the batch plotter and GUI separately.

## Output Impact

This phase does not intentionally change any scientific output. The only script
behavior changed is that `scripts/tools/gaussian_source_fitting.py` now imports
the equivalent shared implementation instead of hosting its own duplicate copy.
