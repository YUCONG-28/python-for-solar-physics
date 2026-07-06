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
- Reusable raw-quality, spectrogram, drift-rate, and drift-product helpers now
  live in `solar_toolkit.radio` and are re-exported through historical
  `scripts.radio.core.*` wrappers.

## Remaining Legacy Dependencies

- `core.radio_gaussian_fit` still imports array aliases, diagnostics fields,
  coordinate conversion helpers, and output-subdirectory logic from
  `legacy.radio_source_map_plot_gaussian_overlay`.
- `solar_toolkit.radio.gaussian` is still a large compatibility-oriented module,
  with smaller facade modules for model, background, mask, fit, diagnostics,
  and I/O imports.
- The AIA/HMI/radio overlay script still contains its own Gaussian fitting code;
  it should later reuse `core.radio_gaussian_fit`.

## Safe Next Steps

1. Continue reducing `solar_toolkit.radio.gaussian` by moving real
   implementations behind the facade modules once focused tests cover each
   extraction.
2. Extract the plotting orchestration from
   `legacy.radio_source_map_plot_gaussian_overlay.main()` into smaller functions
   that can be called by `run_radio_source_map.py`.
3. Continue moving AIA/HMI/radio defaults from
   `legacy.sdo_aia_radio_hmi_overlay.Config` into event config files as new
   event-specific settings are needed.
4. Only after repeated runs match current outputs, consider removing or
   deprecating legacy code in a separate review.
