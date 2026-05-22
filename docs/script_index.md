# Script Index

This index describes the main runnable scripts. Most workflows expect local
observation data and should be configured through `configs/paths.local.yaml` or
the `SOLAR_PHYSICS_CONFIG` environment variable.

## Core Workflows

These are the recommended public entry points for new users and README examples.

| Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- |
| `scripts/aia_hmi/sdo_aia_euv_processor.py` | Main SDO/AIA EUV processor for single-band PNGs, multi-band mosaics, test previews, and optional base/running difference images. | AIA FITS files in wavelength folders; ROI, wavelength, scaling, and mosaic settings. | AIA PNG images in `plot/`, multi-band mosaics in `multi_band/`, optional difference products. |
| `scripts/radio/radio_source_map_plot_gaussian_overlay.py` | Advanced radio source map workflow with RR/LL handling, multi-band panels, Gaussian fitting, CSO spectrogram panels, and manual drift-rate overlays. | Radio source FITS files, optional CSO spectrogram FITS, Gaussian/drift settings. | Radio source maps, fitted centers, FWHM overlays, diagnostics CSV, optional drift-rate JSON/preview products. |
| `scripts/radio/sdo_aia_radio_hmi_overlay.py` | Overlay radio source contours and optional HMI contours on AIA context images. | AIA FITS, radio source FITS, optional HMI FITS, matching and fit settings. | AIA-radio or AIA-radio-HMI diagnostic figures with contours and fitted source markers. |
| `scripts/radio/cso_radio_spectrogram_plot.py` | Plot CSO dynamic spectra with memory-aware slicing and downsampling. | CSO spectrogram FITS, time/frequency ranges, polarization settings. | LL/RR, total intensity, and polarization-ratio spectrum figures. |
| `scripts/tools/gaussian_source_fitting.py` | Fit rotated 2D Gaussian models to source maps. | 2D intensity array and coordinate axes. | Gaussian parameters, covariance, and fitted source center/shape. |

## Utility Scripts

These scripts are useful supporting tools and can remain part of the normal
workflow, but they are not the main README entry points.

| Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- |
| `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` | Normalize SDO/AIA and SDO/HMI FITS filenames recursively. | Raw or partially named AIA/HMI FITS files. | Renamed FITS files; dry-run summary when requested. |
| `scripts/aia_hmi/sdo_aia_lightcurve_extraction.py` | Extract AIA flux/light-curve data from a region of interest. | AIA FITS sequence and ROI settings. | CSV table with observation time and flux. |
| `scripts/aia_hmi/sdo_aia_lightcurve_plot.py` | Plot one or more AIA light-curve CSV files. | CSV products from light-curve extraction. | Publication-style light-curve figures. |
| `scripts/aia_hmi/sdo_aia_time_file_selector.py` | Select AIA files closest to a target time. | AIA FITS folders, target time, and tolerance. | Copied matching files organized for follow-up workflows. |
| `scripts/aia_hmi/sdo_hmi_magnetogram_plot.py` | Plot SDO/HMI magnetograms in a selected ROI. | HMI magnetogram FITS files. | HMI PNG context images. |
| `scripts/tools/image_sequence_to_video.py` | Convert an ordered image sequence to MP4 with FFmpeg/imageio/OpenCV fallbacks. | PNG/JPG image sequence and video settings. | MP4 time-evolution video. |

## Legacy or Experimental Scripts

Keep these files for now. They may contain useful historical parameters or
specialized workflows, but future cleanup should compare them against the core
workflows before merging or deprecating them.

| Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- |
| `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | Build synchronized multi-wavelength AIA overview panels. | AIA FITS files across multiple wavelengths. | Multi-panel AIA figures with common ROI and labels. |
| `scripts/aia_hmi/sdo_aia_base_difference.py` | Generate base-difference AIA images relative to a reference frame. | Time-sorted AIA FITS sequence and selected reference frame. | Difference PNG images for event evolution analysis. |
| `scripts/aia_hmi/sdo_aia_running_difference.py` | Generate running-difference AIA images from adjacent frames. | Time-sorted AIA FITS sequence. | Running-difference PNG images for transient structure tracking. |
| `scripts/aia_hmi/sdo_aia_time_distance_diagram.py` | Demonstrate AIA time-distance analysis along a coordinate path. | AIA map sequence, currently using a SunPy/Fido example query. | Time-distance diagnostic figure. |
| `scripts/aia_hmi/sdo_aia_hmi_overlay.py` | Overlay HMI magnetic contours on AIA images. | AIA FITS, HMI FITS, time matching, contour levels. | AIA-HMI overlay PNG figures. |
| `scripts/radio/radio_source_map_plot.py` | Plot single-band or multi-band radio source FITS maps. | Radio FITS images organized by frequency and polarization. | Radio source maps, multi-frequency panels, contours, and optional polarization products. |
| `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` | Experimental background-corrected AIA/radio/HMI overlay workflow. | AIA FITS, radio source FITS, optional HMI FITS, background settings. | Overlay figures and optional fit diagnostics. |
| `scripts/radio/cso_spectrogram_class.py` | Provide a reusable CSO spectrogram reader and plotting helper. | CSO FITS files and plotting ranges. | Dynamic spectrum plots from class/helper functions. |
| `scripts/xray_dem/goes_sxr_lightcurve_plot.py` | Plot GOES soft X-ray light curves. | GOES NetCDF products. | SXR time-series PNG figures. |
| `scripts/xray_dem/hessi_hxr_lightcurve_plot.py` | Plot HXR light curves from FITS event files. | HESSI/RHESSI-style HXR FITS files. | HXR time-series figures. |
| `scripts/xray_dem/asos_hxi_image_plot.py` | Plot ASO-S/HXI hard X-ray image maps. | HXI FITS image cube or map products. | HXI image figures. |
| `scripts/xray_dem/asos_hxi_goes_sxr_comparison.py` | Compare HXI count-rate evolution with GOES SXR context. | HXI FITS and optional GOES SXR products. | Multi-energy HXR/SXR comparison plots. |
| `scripts/xray_dem/sdo_aia_asos_hxi_overlay.py` | Overlay ASO-S/HXI contours on SDO/AIA images. | AIA FITS sequence and HXI FITS images. | AIA-HXI overlay figures. |
| `scripts/xray_dem/flare_aia_sxr_hxr_summary_plot.py` | Combine AIA light curves, GOES SXR, and HXR/HXI diagnostics. | AIA CSV products, GOES NetCDF, HXR/HXI FITS. | Three-panel flare diagnostic figures. |
| `scripts/xray_dem/neupert_sxr_derivative_hxr_comparison.py` | Compare smoothed SXR derivatives with HXR-style timing. | GOES SXR NetCDF and smoothing parameters. | Neupert-effect diagnostic figures. |
| `scripts/xray_dem/neupert_timing_error_analysis.py` | Explore smoothing, timing, and derivative behavior for Neupert analysis. | GOES SXR NetCDF. | Parameter-check figures for timing/derivative interpretation. |
| `scripts/xray_dem/sdo_aia_dem_inversion.py` | Visualize DEM/Tb products in AIA coordinates. | AIA FITS, DEM/Tb `.npy` array, grid metadata. | DEM/Tb context figures. |
| `scripts/xray_dem/dem_radio_source_overlay.py` | Compare DEM/Tb structure with radio source morphology. | AIA FITS, DEM/Tb `.npy`, radio source FITS files. | DEM/Tb and radio-source overlay figures. |

## Examples

| Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- |
| `examples/aia_hmi/solar_limb_contour_example.py` | Small AIA/HMI-style solar limb contour example. | Example or local AIA data. | Demonstration figure. |
| `examples/radio/cso_spectrogram_processing_example.py` | Historical CSO spectrogram processing example. | CSO FITS files. | Demonstration spectrum plot. |
| `examples/radio/fits_header_metadata_example.py` | Inspect FITS header metadata. | FITS file. | Printed metadata. |
| `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | AIA/radio/HMI overlay demonstration. | Local AIA, radio, and optional HMI data. | Overlay figure. |
| `examples/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py` | Extended AIA/radio/HMI overlay example. | Local AIA, radio, and optional HMI data. | Overlay figure and diagnostics. |
| `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py` | Historical single-file AIA/radio overlay variant. | Local AIA and radio FITS. | Optional overlay figure. |
| `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py` | Historical single-file AIA/radio overlay variant. | Local AIA and radio FITS. | Optional overlay figure. |

## Optional GUI/Download Scripts

| Script | Purpose | Main inputs | Main outputs |
| --- | --- | --- | --- |
| `scripts/radio/cso_radio_spectra_gui.py` | Interactive CSO radio-spectrum GUI and type-II fitting utilities. | CSO or DSRT-style spectrogram files; PyQt5/pyqtgraph. | Interactive plots, selected spectra, and optional saved products. |
| `scripts/lasco_cme/soho_lasco_data_download.py` | Download SOHO/LASCO C2 JP2 files through Helioviewer. | Time range, cadence, data source, output folder. | Local LASCO JP2 files. |
| `scripts/lasco_cme/soho_lasco_image_plot.py` | Plot basic SOHO/LASCO images. | LASCO JP2 files. | LASCO PNG context images. |
| `scripts/lasco_cme/soho_lasco_running_difference.py` | Generate LASCO running-difference CME images. | Time-sorted LASCO JP2 sequence. | Running-difference CME PNG figures. |
