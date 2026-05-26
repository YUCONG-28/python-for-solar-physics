# Radio Migration Notes

## Current Compatibility Layer

- `run_radio_burst_pipeline.py` is the preferred full pipeline entrypoint. It
  now imports scientific helpers from `core/` and still uses the archived
  source-map script for the full radio plotting workflow and shared config
  migration helpers.
- `run_radio_source_map.py` is intentionally a thin wrapper around
  `legacy.radio_source_map_plot_gaussian_overlay.main()`.
- `run_aia_radio_hmi_overlay.py` loads AIA/HMI/radio overlay config and calls
  `legacy.sdo_aia_radio_hmi_overlay.main(user_config=...)`.

## Remaining Legacy Dependencies

- `core.radio_gaussian_fit` still imports array aliases, diagnostics fields,
  coordinate conversion helpers, and output-subdirectory logic from
  `legacy.radio_source_map_plot_gaussian_overlay`.
- `core.radio_spectrogram` still imports datetime/index parsing helpers from
  `legacy.radio_source_map_plot_gaussian_overlay`.
- `core.radio_drift_rate` still imports datetime parsing, drift output path
  resolution, and diagnostics field definitions from
  `legacy.radio_source_map_plot_gaussian_overlay`.
- The AIA/HMI/radio overlay script still contains its own Gaussian fitting code;
  it should later reuse `core.radio_gaussian_fit`.

## Safe Next Steps

1. Move low-risk utility helpers from
   `legacy.radio_source_map_plot_gaussian_overlay` into a small
   `core.radio_io` module: datetime parsing, output path resolution, config path
   normalization, and diagnostics-field constants.
2. Update `core.radio_gaussian_fit`, `core.radio_spectrogram`, and
   `core.radio_drift_rate` to depend on `core.radio_io` instead of legacy.
3. Extract the plotting orchestration from
   `legacy.radio_source_map_plot_gaussian_overlay.main()` into smaller functions
   that can be called by `run_radio_source_map.py`.
4. Continue moving AIA/HMI/radio defaults from
   `legacy.sdo_aia_radio_hmi_overlay.Config` into event config files as new
   event-specific settings are needed.
5. Only after repeated runs match current outputs, consider removing or
   deprecating legacy code in a separate review.
