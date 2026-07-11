# CSO Spectrogram Refactor Report

Date: 2026-05-22

## Scope

Phase 3D organizes CSO dynamic-spectrogram code around the main batch plotting
script, keeps one basic reusable reader/class script, and moves the duplicate
example into legacy. No real CSO FITS data was read. No GUI was started.

## Main Code

Formal main code:

- `scripts/radio/cso_radio_spectrogram_plot.py`

This remains the recommended production entry point for:

- memory-aware CSO dynamic spectrum plotting;
- LL/RR extraction;
- LL+RR total-intensity plotting;
- polarization ratio plotting;
- chunked/downsampled plotting for large files;
- configurable color limits, time/frequency ranges, and output.

No frequency-intensity processing, LL/RR/sum/ratio calculation, or plotting
algorithm in the main code was changed in this phase.

## Basic Code

Retained basic/reusable script:

- `scripts/radio/cso_spectrogram_class.py`

Reason:

- It is shorter and easier to read than the full production plotter.
- It contains the basic `spectrogram` container plus small helper functions for
  reading, indexing, slicing, and plotting.
- It is a better teaching/reuse layer than the historical example file.

Change made:

- `readcso_spectrofits()` now delegates to the shared minimal reader in
  `solar_toolkit.cso.read_cso_spectrogram()`, then wraps the returned shared
  objects back into the local `spectrogram` class for compatibility.

This unifies the most duplicated CSO FITS header/data-reading behavior while
leaving plotting, slicing, and rebin behavior unchanged.

## Optional GUI

Kept as optional GUI:

- `scripts/radio/cso_radio_spectra_gui.py`

Reason:

- It provides interactive PyQt/pyqtgraph workflows, file dialogs, dynamic
  spectrum exploration, type-II fitting utilities, flux plotting, and save
  interactions.
- These behaviors are not covered by the batch plotter or the basic class.
- The file is large and duplicated in places, but deleting or moving it would
  remove an interactive workflow that may still be useful.

This phase did not modify the GUI and did not start it.

## Legacy Example

Moved to:

- `examples/legacy/radio/cso_spectrogram_processing_example.py`

Reason:

- It duplicates the `spectrogram` class and `readcso_spectrofits()` reader.
- It also duplicates LL/RR/sum/ratio plotting logic already covered by
  `cso_radio_spectrogram_plot.py`.
- It remains available as historical reference but is no longer the primary
  example.

## Delete Or Legacy Candidates

No file was deleted in this phase.

Recommended legacy candidates:

- `examples/legacy/radio/cso_spectrogram_processing_example.py`

Optional GUI, not deletion candidate yet:

- `scripts/radio/cso_radio_spectra_gui.py`

Future deletion candidate requiring human confirmation:

- `examples/legacy/radio/cso_spectrogram_processing_example.py`

Deletion should wait until:

- README/docs no longer reference the old example path;
- any paper-reproduction notes using its exact plotting defaults are migrated;
- its LL/RR/sum/ratio behavior is confirmed covered by the main plotter;
- collaborators confirm they do not run it directly.

## Duplicates Not Yet Merged

Intentionally not merged in this phase:

- `scripts/radio/cso_radio_spectrogram_plot.py`
  - Keeps its `LazySpectrogram`, memmap, chunked rebinning, color scaling, and
    plotting logic.
- `scripts/radio/cso_radio_spectra_gui.py`
  - Keeps GUI-specific readers and interaction state.
- `scripts/radio/cso_spectrogram_class.py`
  - Keeps legacy slicing/rebin plotting helpers. Only its reader entry point is
    unified through `solar_toolkit.cso`.

## Scientific Risk Notes

Areas that must not be merged without parity tests:

- LL/RR identification and order;
- LL+RR sum behavior;
- polarization ratio `(R-L)/(R+L)` handling and clipping;
- chunked/memmap downsampling in the main plotter;
- GUI background subtraction or interactive scaling choices;
- exact time/frequency index slicing behavior.

## Algorithm Impact

This phase did not change CSO frequency-intensity processing algorithms. It did
not change LL/RR/sum/ratio formulas. It only unified the basic FITS-reading
entry point in `cso_spectrogram_class.py`, moved a duplicate example to legacy,
and documented the retention decision.
