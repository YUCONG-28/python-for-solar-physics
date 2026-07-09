# Script Index

This index describes the public runnable scripts, compatibility entrypoints, and
selected examples that users are expected to run directly. It intentionally does
not list every internal `core/` module or event-specific config module. Most
workflows expect local observation data and should be configured through
`configs/paths.local.yaml` or the `SOLAR_PHYSICS_CONFIG` environment variable.
The bilingual `README.md` links to the main workflows listed here.
For a beginner-safe path that starts with no-data checks, see
`docs/quickstart.md`.

Status labels:

- `main`: recommended public entry point.
- `utility`: useful support script or helper workflow.
- `archived`: kept in `legacy/` for review; do not treat as the current entry
  point.
- `deprecated`: not recommended for new work, but kept because it may preserve
  historical parameters or optional behavior.

## Main Workflows

| Status | Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- | --- |
| main | `scripts/aia_hmi/run_aia_euv_processor.py` | Main SDO/AIA EUV processor for single-band PNGs, multi-band mosaics, test previews, and optional base/running difference images. | AIA FITS files in wavelength folders; ROI, wavelength, scaling, and mosaic settings. | AIA PNG images, mosaics, and optional difference products. |
| main | `scripts/radio/run_radio_burst_pipeline.py` | Full radio burst workflow with source maps, Gaussian diagnostics, CSO spectrogram/drift support, Newkirk height comparison, Gaussian-Newkirk height residuals, and drift-speed diagnostics. | Radio source FITS files, optional CSO spectrogram FITS, Gaussian/drift/Newkirk settings. | Radio source maps, fitted centers, FWHM overlays, diagnostics CSV, Newkirk height tables, height-residual plots, and optional drift-rate JSON/preview products. |
| main | `scripts/radio/run_radio_source_map.py` | Quick radio source map workflow with Gaussian overlay through the compatibility source-map workflow. | Radio source FITS files, Gaussian settings. | Radio source maps, fitted centers, FWHM overlays, and diagnostics CSV. |
| main | `scripts/radio/extract_radio_centers.py` | Extract threshold/contour radio-source centers, such as 95% intensity regions, from a radio FITS folder. | Radio FITS files, threshold mode, centroid mode, optional LCP/RCP pairing. | CSV or XLSX center table with `obs_time`, `freq_mhz`, `polarization`, center coordinates, method, and quality flag. |
| main | `scripts/radio/run_radio_source_app.py` | Streamlit frontend for radio-source trajectory playback with optional AIA FITS background. | Center CSV/XLSX table, optional AIA FITS folder, playback and filtering controls. | Interactive browser view; no batch FITS extraction is run inside the app. |
| utility | `scripts/radio/export_radio_source_trajectory.py` | Export a selected radio-source trajectory frame to a static Plotly HTML file. | Center CSV/XLSX table, frame time or frame index, optional AIA FITS folder. | Standalone HTML trajectory figure. |
| main | `scripts/radio/run_aia_radio_hmi_overlay.py` | Overlay radio source contours and optional HMI contours on AIA context images. | AIA FITS, radio source FITS, optional HMI FITS, matching and fit settings. | AIA-radio or AIA-radio-HMI diagnostic figures with contours and fitted source markers. |
| main | `scripts/radio/legacy/cso_radio_spectrogram_plot.py` | Deprecated compatibility CSO dynamic spectra workflow with memory-aware slicing and downsampling; no `run_*.py` wrapper exists yet. | CSO spectrogram FITS, time/frequency ranges, polarization settings. | LL/RR, total intensity, and polarization-ratio spectrum figures. |
| main | `scripts/aia_hmi/sdo_aia_jsoc_download_20250124.py` | Download selected SDO/AIA JSOC level-1 EUV FITS files for 2025-01-24 04:00-05:00 UTC. | JSOC/DRMS query, 211 A and 304 A channels by default. | FITS files and `manifest_urls.txt` under `~/data/aia/20250124_2/`. |
| main | `scripts/data_download/stereo_a_euvi_download_20250124.py` | Download STEREO-A SECCHI/EUVI files for the 2025-01-24 event window. | SunPy/Fido query to STEREO/EUVI archive. | EUVI FTS files and `selected_files.txt`. |
| main | `scripts/data_download/goes_suvi_download_20250124.py` | Download GOES-16/18 SUVI L2 composite FITS files for the event window. | NOAA GOES SUVI public data directory. | SUVI FITS files grouped by satellite, channel, and date. |

## Utility Scripts

| Status | Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- | --- |
| utility | `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` | Normalize SDO/AIA and SDO/HMI FITS filenames recursively. | Raw or partially named AIA/HMI FITS files. | Renamed FITS files; dry-run summary when requested. |
| utility | `scripts/aia_hmi/sdo_aia_lightcurve_extraction.py` | Extract AIA flux/light-curve data from a region of interest. | AIA FITS sequence and ROI settings. | CSV table with observation time and flux. |
| utility | `scripts/aia_hmi/sdo_aia_lightcurve_plot.py` | Plot one or more AIA light-curve CSV files. | CSV products from light-curve extraction. | Publication-style light-curve figures. |
| utility | `scripts/aia_hmi/sdo_hmi_magnetogram_plot.py` | Plot SDO/HMI magnetograms in a selected ROI. | HMI magnetogram FITS files. | HMI PNG context images. |
| utility | `scripts/data_download/solo_eui_soar_query_download.py` | Query Solar Orbiter/EUI metadata and optionally download selected files. | SOAR TAP service; optional `--download`. | Metadata JSON and optional EUI FITS files. |
| utility | `scripts/stereo_suvi/stereo_euvi_manifest_by_wavelength.py` | Create a wavelength manifest and by-wavelength symlink view for STEREO-A/EUVI data. | EUVI FTS files under `data/raw/stereo/euvi/20250124/`. | `manifest_by_wavelength.csv` and `by_wavelength/`. |
| utility | `scripts/stereo_suvi/stereo_euvi_0448_overview_plot.py` | Plot STEREO-A/EUVI context images nearest the 2025-01-24 04:48 UT event time. | EUVI manifest from the wavelength organizer. | Single-channel and 2x2 overview PNG products. |
| utility | `scripts/stereo_suvi/stereo_euvi_roi_movie.py` | Generate fixed-ROI EUVI frame sequences and MP4 movies for event evolution. | EUVI manifest and local EUVI FTS files. | ROI PNG frames, MP4 movies, and `movie_summary.csv`. |
| utility | `scripts/stereo_suvi/goes_suvi_0448_quadrant_plot.py` | Plot GOES-16/18 SUVI lower-right quadrant event context images. | Local SUVI L2 FITS files. | Single-channel and overview PNG products. |
| utility | `scripts/tools/gaussian_source_fitting.py` | Compatibility wrapper for shared Gaussian fitting helpers in `solar_toolkit.gaussian`. | 2D intensity array and coordinate axes. | Gaussian parameters, covariance, and fitted source center/shape. |
| utility | `scripts/tools/image_sequence_to_video.py` | Convert an ordered image sequence to MP4 with FFmpeg/imageio/OpenCV fallbacks. | PNG/JPG image sequence and video settings. | MP4 time-evolution video. |
| utility | `scripts/tools/run_image_web_viewer.py` | Launch the local Flask/Canvas image sequence viewer with synchronized multi-folder playback, ROI selection, and MP4 export. | One or more local image folders, optional allowed-root boundary, playback/export settings. | Interactive browser view plus optional composite and per-folder MP4 files in the selected output directory. |
| utility | `scripts/tools/run_solar_webapp.py` | Launch the unified local English web GUI for registered AIA/HMI, radio, data-download, LASCO/CME, X-ray/DEM, example, and media workflows. | Optional allowed-root boundary and workbench port. | Local browser dashboard with workflow forms, job status, and logs. |
| utility | `scripts/lasco_cme/soho_lasco_data_download.py` | Download SOHO/LASCO C2 JP2 files through Helioviewer. | Time range, cadence, data source, output folder. | Local LASCO JP2 files. |
| utility | `scripts/lasco_cme/soho_lasco_image_plot.py` | Plot basic SOHO/LASCO images. | LASCO JP2 files. | LASCO PNG context images. |
| utility | `scripts/lasco_cme/soho_lasco_running_difference.py` | Generate LASCO running-difference CME images. | Time-sorted LASCO JP2 sequence. | Running-difference CME PNG figures. |

## Shared Helpers

| Status | Module | Purpose | Used by |
| --- | --- | --- | --- |
| utility | `solar_toolkit/time/` | SunPy-style timestamp parsing, filename time extraction, nearest-time matching, and time-range filtering. | AIA/HMI/radio/X-ray/CME workflows that align observations by time. |
| utility | `solar_toolkit/io/` | Local file scanning, natural sorting, FITS data/header reading, and CSV manifest helpers. | Scripts and library modules that scan local observation folders. |
| utility | `solar_toolkit/data/` | Lightweight observation-file inventory records without network side effects. | Future local data manifests and reviewed examples. |
| utility | `solar_toolkit/map/` | SunPy Map/FITS-header helper layer for extent, observation time, ROI crop, and image normalization. | Plotting and overlay workflows that need common image geometry. |
| utility | `solar_toolkit/timeseries/` | Light-curve table time normalization, time clipping, smoothing, and finite-difference derivatives. | GOES/HXI/AIA light-curve and Neupert-style workflows. |
| utility | `solar_toolkit/aia/` | Public AIA library boundary for configuration, FITS selection, difference helpers, mosaic helpers, and the lazy EUV processor dispatcher. | AIA/HMI entrypoints and historical `scripts.aia_hmi.core.*` compatibility imports. |
| utility | `solar_toolkit/hmi/` | Public HMI-facing namespace for FITS renaming, magnetogram, and overlay facades. | HMI/AIA script workflows and future reusable HMI extraction. |
| utility | `solar_toolkit/radio/raw_quality.py` | Raw radio FITS artifact/quality diagnostics. | `scripts/radio/run_radio_raw_quality.py` and compatibility imports. |
| utility | `solar_toolkit/radio/centers.py` | Threshold/contour radio-source center extraction from FITS image planes. | `scripts/radio/extract_radio_centers.py` and trajectory frontend workflows. |
| utility | `solar_toolkit/radio/trajectory.py` | Normalize threshold-center and Gaussian diagnostics tables, filter series, select playback frames, and compute LCP-RCP separation rows. | `scripts/radio/run_radio_source_app.py`, `scripts/radio/export_radio_source_trajectory.py`, and future trajectory products. |
| utility | `solar_toolkit/radio/spectrogram.py` | Dynamic spectrogram cache and overlay helpers. | Radio pipeline and AIA/radio overlay workflows. |
| utility | `solar_toolkit/radio/drift_rate.py` | Manual drift-rate selection and overlay helpers. | Full radio burst pipeline. |
| utility | `solar_toolkit/radio/drift_products.py` | Persistent drift-selection preview/table/metadata products. | Drift-selection tests and full radio burst pipeline. |
| utility | `solar_toolkit/path_config.py` | Load local path configuration from `configs/paths.example.yaml`-style YAML files without committing personal paths. | README-recommended workflows that need local data roots. |
| utility | `solar_toolkit/gaussian.py` | Shared Gaussian fitting helpers used by compatibility and diagnostic code. | Gaussian fitting tests and `scripts/tools/gaussian_source_fitting.py`. |
| utility | `solar_toolkit/coordinates.py` | Coordinate and image extent helpers for radio/AIA consistency checks. | Radio coordinate tests and plotting workflows. |
| utility | `solar_toolkit/cso.py` | CSO spectrogram utility helpers. | CSO tests and radio spectrogram workflows. |
| utility | `solar_toolkit/xray_dem/` | Public namespace for future X-ray/HXI/DEM helper extraction. | `scripts/xray_dem/` workflows. |
| utility | `solar_toolkit/cme/` | Public namespace for future LASCO/CME helper extraction. | `scripts/lasco_cme/` workflows. |
| utility | `solar_toolkit/net/` | Public namespace for future archive query/download helper extraction. | `scripts/data_download/` workflows. |
| utility | `solar_toolkit/modeling/` | Shared science-model boundary for Gaussian and Newkirk helpers. | Reusable model imports. |
| utility | `solar_toolkit/aia/background.py` | Lightweight AIA FITS folder scanning, nearest-frame matching, and downsampled HPLN/HPLT background grids. | Radio-source trajectory frontend and HTML export. |
| utility | `solar_toolkit/visualization/radio_source_trajectory.py` | Plotly figure and HTML export helpers for radio-source trajectories with optional AIA backgrounds. | `scripts/radio/run_radio_source_app.py` and `scripts/radio/export_radio_source_trajectory.py`. |
| utility | `solar_toolkit/visualization/image_web_viewer/` | Flask app factory, folder scanner, Canvas frontend assets, and MP4 export helpers for local image sequence review. | `scripts/tools/run_image_web_viewer.py` and browser API routes under `/api/*`. |
| utility | `solar_toolkit/visualization/` | Shared plotting/media namespace for reusable visual helpers. | Scripts and tools that generate figures, videos, or interactive HTML. |

## Specialized Or Legacy-Risk Scripts

These files are still tracked and may be scientifically useful. They are not
recommended as first entry points for new users.

| Status | Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- | --- |
| deprecated | `scripts/aia_hmi/sdo_aia_time_distance_diagram.py` | Demonstrate AIA time-distance analysis along a coordinate path. | AIA map sequence, currently using a SunPy/Fido example query. | Time-distance diagnostic figure. |
| deprecated | `scripts/aia_hmi/sdo_aia_hmi_overlay.py` | Overlay HMI magnetic contours on AIA images. | AIA FITS, HMI FITS, time matching, contour levels. | AIA-HMI overlay PNG figures. |
| deprecated | `scripts/aia_hmi/sdo_aia_euv_processor.py` | Deprecated compatibility entrypoint for the historical AIA EUV processor command; new work should use `run_aia_euv_processor.py`. | Same as the recommended AIA EUV entrypoint. | Same as the recommended AIA EUV entrypoint. |
| utility | `scripts/xray_dem/goes_sxr_lightcurve_plot.py` | Plot GOES soft X-ray light curves. | GOES NetCDF products. | SXR time-series PNG figures. |
| utility | `scripts/xray_dem/hessi_hxr_lightcurve_plot.py` | Plot HXR light curves from FITS event files. | HESSI/RHESSI-style HXR FITS files. | HXR time-series figures. |
| utility | `scripts/xray_dem/asos_hxi_image_plot.py` | Plot ASO-S/HXI hard X-ray image maps. | HXI FITS image cube or map products. | HXI image figures. |
| utility | `scripts/xray_dem/asos_hxi_goes_sxr_comparison.py` | Compare HXI count-rate evolution with GOES SXR context. | HXI FITS and optional GOES SXR products. | Multi-energy HXR/SXR comparison plots. |
| utility | `scripts/xray_dem/sdo_aia_asos_hxi_overlay.py` | Overlay ASO-S/HXI contours on SDO/AIA images. | AIA FITS sequence and HXI FITS images. | AIA-HXI overlay figures. |
| utility | `scripts/xray_dem/flare_aia_sxr_hxr_summary_plot.py` | Combine AIA light curves, GOES SXR, and HXR/HXI diagnostics. | AIA CSV products, GOES NetCDF, HXR/HXI FITS. | Three-panel flare diagnostic figures. |
| utility | `scripts/xray_dem/neupert_sxr_derivative_hxr_comparison.py` | Compare smoothed SXR derivatives with HXR-style timing. | GOES SXR NetCDF and smoothing parameters. | Neupert-effect diagnostic figures. |
| utility | `scripts/xray_dem/neupert_timing_error_analysis.py` | Explore smoothing, timing, and derivative behavior for Neupert analysis. | GOES SXR NetCDF. | Parameter-check figures for timing/derivative interpretation. |
| utility | `scripts/xray_dem/sdo_aia_dem_inversion.py` | Visualize DEM/Tb products in AIA coordinates. | AIA FITS, DEM/Tb `.npy` array, grid metadata. | DEM/Tb context figures. |
| utility | `scripts/xray_dem/dem_radio_source_overlay.py` | Compare DEM/Tb structure with radio source morphology. | AIA FITS, DEM/Tb `.npy`, radio source FITS files. | DEM/Tb and radio-source overlay figures. |

## Archived Scripts

| Status | Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- | --- |
| archived | `legacy/scripts/aia_hmi/sdo_aia_base_difference.py` | Historical base-difference AIA workflow kept for parameter review. | Time-sorted AIA FITS sequence and selected reference frame. | Difference PNG images for event evolution analysis. |
| archived | `legacy/scripts/aia_hmi/sdo_aia_running_difference.py` | Historical running-difference AIA workflow kept for parameter review. | Time-sorted AIA FITS sequence. | Running-difference PNG images for transient structure tracking. |

## Examples

| Status | Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- | --- |
| utility | `examples/aia_hmi/solar_limb_contour_example.py` | Small AIA/HMI-style solar limb contour example. | Example or local AIA data. | Demonstration figure. |
| utility | `examples/radio/fits_header_metadata_example.py` | Inspect FITS header metadata. | FITS file. | Printed metadata. |
| utility | `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | AIA/radio/HMI overlay demonstration. | Local AIA, radio, and optional HMI data. | Overlay figure. |
