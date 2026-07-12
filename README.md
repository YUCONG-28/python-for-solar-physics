# Solar Radio and SDO/AIA-HMI Analysis Toolkit

[![CI](https://github.com/YUCONG-28/python-for-solar-physics/actions/workflows/ci.yml/badge.svg)](https://github.com/YUCONG-28/python-for-solar-physics/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Citation](https://img.shields.io/badge/citation-CITATION.cff-lightgrey)

A research-oriented Python toolkit for multi-wavelength solar event analysis,
with script-based workflows for SDO/AIA, SDO/HMI, radio source imaging, CSO
dynamic spectra, Gaussian source diagnostics, and multi-instrument context
figures.

GitHub: <https://github.com/YUCONG-28/python-for-solar-physics>

## Abstract

This repository supports the local analysis of solar flares, jets, CMEs, and
radio bursts using multi-instrument observations. It provides reproducible
script workflows for turning FITS, FTS, JP2, NetCDF, CSV, and NumPy products
into publication-oriented figures, diagnostic tables, source-center
measurements, and time-evolution products.

The current codebase is organized as a research toolkit rather than a turnkey
data portal. Raw observations and large generated products are intentionally
kept outside Git; users are expected to configure local data paths before
running full science workflows.

New users should start with `docs/quickstart.md`. It lists data-independent
checks, first import examples, and safe `--help` commands before any local
observation archive is required.

## Scientific Scope

- **SDO/AIA and SDO/HMI context imaging**: EUV visualization, mosaics,
  base/running-difference products, HMI magnetogram plotting, and magnetic
  contour overlays.
- **Solar radio diagnostics**: CSO dynamic spectrogram plotting, radio source
  image overlays, Gaussian source fitting, FWHM visualization, source-center
  diagnostics, and drift-rate products.
- **Height and density-model analysis**: Newkirk density-model extrapolation,
  drift-speed tables, Gaussian-Newkirk height residuals, and
  height/time/frequency diagnostic plots.
- **Multi-instrument event context**: STEREO-A/EUVI, GOES/SUVI, Solar
  Orbiter/EUI, SOHO/LASCO, GOES SXR, HXR/HXI, and DEM/Tb helper workflows for
  event-scale interpretation.

## Key Capabilities

**Observation processing**

- Process SDO/AIA single-band images, multi-band mosaics, preview products, and
  difference images.
- Normalize AIA/HMI FITS filenames and manage local path configuration without
  committing machine-specific paths.
- Generate context images and movies from STEREO-A/EUVI, GOES/SUVI, and LASCO
  products.
- Review local image sequences from one or more folders in a browser, compare
  frames side by side with synchronized playback/ROI selection, and save
  MP4/GIF/WebM recordings or sequence exports.

**Radio analysis**

- Plot CSO dynamic spectra with memory-aware slicing and downsampling.
- Build radio source maps and AIA/radio/HMI overlays.
- Fit two-dimensional Gaussian source models, export fitted centers, and
  generate FWHM and quality-diagnostic products.
- Extract threshold/contour radio-source centers such as 95% intensity regions,
  then review multi-frequency trajectories in a Streamlit playback frontend or
  export a static Plotly HTML view.
- Support manual drift-rate selections, saved JSON selections, Newkirk height
  comparison, and drift-speed diagnostics.

**Reproducibility and maintenance**

- Keep reusable, data-independent helpers in `solar_toolkit/`. The public
  package layer now follows an Astropy/SunPy-style boundary with
  `solar_toolkit.time`, `solar_toolkit.io`, `solar_toolkit.data`,
  `solar_toolkit.map`, `solar_toolkit.timeseries`, `solar_toolkit.aia`,
  `solar_toolkit.hmi`, `solar_toolkit.radio`, `solar_toolkit.xray_dem`,
  `solar_toolkit.cme`, `solar_toolkit.net`, `solar_toolkit.modeling`, and
  `solar_toolkit.visualization`.
- The root API uses explicit `__all__`, `__getattr__`, and `__dir__`: public
  namespaces such as `solar_toolkit.radio` load on first access, so importing
  `solar_toolkit` does not execute workflows or eagerly import every science
  dependency.
- The `solar_toolkit.radio` namespace is the recommended library API for
  reusable radio coordinates, Gaussian fitting, Newkirk, spectrogram, drift,
  raw-quality, quicklook, and diagnostic helpers.
- Keep all maintained implementations under `solar_toolkit/`; `scripts/`
  contains only thin commands, launchers, and compatibility aliases grouped by
  instrument. Historical `scripts.radio.core.*`, `scripts.aia_hmi.core.*`, and
  `scripts/radio/legacy/` imports remain deprecated compatibility paths, but
  resolve to the same package-owned implementations.
- The root aliases `solar_toolkit.gaussian`, `solar_toolkit.coordinates`, and
  `solar_toolkit.cso` are deprecated from `0.2.0`; new code should use
  `solar_toolkit.modeling.gaussian`, `solar_toolkit.map.coordinates`, and
  `solar_toolkit.radio.cso`. Compatibility remains through 0.x and is not
  considered for removal before `1.0.0` plus real-data equivalence review.
- Keep data-independent tests in `tests/`; full scientific products require
  local observations and explicit path configuration.

## Example Research Products

Curated README figures live under `docs/assets/images/`. Full-resolution
science outputs remain local and are not tracked by Git.

![2025-01-24 multi-band radio Gaussian centers over a CSO dynamic spectrum](docs/assets/images/20250124-radio-gaussian-spectrogram-overlay.jpg)

**Figure 1.** Multi-band DART/DSRT radio-source Gaussian centers aligned with a
CSO dynamic spectrum near 2025-01-24 04:48:37 UT.

![2025-01-24 SDO/AIA six-band context with DART/DSRT radio-source contours and CSO spectrum](docs/assets/images/20250124-aia-radio-spectrogram-sixband.jpg)

**Figure 2.** SDO/AIA six-band EUV context with DART/DSRT radio-source contours
and the matching CSO dynamic spectrum.

Data provenance:

- **SDO**: AIA extreme-ultraviolet images and HMI magnetic context are from the
  NASA Solar Dynamics Observatory mission. Instrument and data references:
  [SDO/NASA](https://sdo.gsfc.nasa.gov/),
  [AIA/LMSAL](https://aia.lmsal.com/),
  [HMI/Stanford](https://hmi.stanford.edu/), and
  [JSOC](https://jsoc.stanford.edu/).
- **DART / DSRT (Daocheng)**: radio-source spatial data are attributed to the
  DAocheng Radio Telescope / Daocheng Solar Radio Telescope system in Daocheng,
  Sichuan. Public sources use both DART and DSRT naming. References:
  [NSSC DART note](https://www.nssc.ac.cn/xwdt2015/kydt2015/202603/t20260327_8178611.html)
  and
  [Gov.cn DSRT completion report](https://english.www.gov.cn/news/202309/28/content_WS6514cd8ec6d0868f4e8dfcfc.html).
- **CSO / CBSm**: dynamic-spectrum data are attributed to the Chashan
  Observatory broadband solar radio spectrometer, associated with Shandong
  University LEAD/ISS and supported by the Chinese Meridian Project Phase II.
  Reference: [CESRA CBSm data release](https://cesra.net/?p=3773).

## Installation

The package metadata targets Python 3.10+ and is developed primarily with
Miniforge/conda. A typical public installation is:

```powershell
git clone https://github.com/YUCONG-28/python-for-solar-physics.git
cd python-for-solar-physics

conda create -n solarphysics_env python=3.11
conda activate solarphysics_env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev,full]"
```

Optional GUI workflows may also need:

```powershell
python -m pip install -e ".[gui]"
```

Optional radio-source trajectory frontend workflows use:

```powershell
python -m pip install -e ".[app]"
```

Core dependencies include NumPy, SciPy, AstroPy, SunPy, Matplotlib, Reproject,
Scikit-image, PyYAML, Pandas, and tqdm. Optional workflows may require DRMS,
Requests, OpenCV, ImageIO, PyQt5, pyqtgraph, Helioviewer-related packages, or
archive-specific libraries. The `app` extra adds Streamlit, Plotly, OpenPyXL,
and Flask for interactive trajectory playback, Excel table support, and the
local image-sequence web viewer.

## Minimal Usage

Full science workflows require local observation data and event-specific path
configuration. The main public command-line entrypoints are:

```powershell
# Installed, package-owned command surfaces
solar-aia --help
solar-radio --help
solar-image-viewer --help
solar-webapp --help

# Package-owned Radio workflows
solar-radio source-map --config radio_20250124_config --output-dir outputs\radio-map
solar-radio pipeline --config radio_20250124_config --output-dir outputs\radio-pipeline
solar-radio overlay --config radio_20250124_config --overlay-section aia_multi_wave_gaussian_spectrogram
```

`solar-radio` exposes `centers`, `pipeline`, `source-map`, `overlay`,
`quicklook`, `raw-quality`, `roi-lightcurve`, and `trajectory`. All eight
subcommands, including the default event configurations, are included in the
installed wheel. The following source-checkout scripts are equivalent
compatibility surfaces:

```powershell
# SDO/AIA single-band, mosaic, preview, and difference products
python scripts/aia_hmi/run_aia_euv_processor.py --mode single --waves 171 193 304

# Full radio burst workflow: maps, Gaussian diagnostics, drift, and Newkirk products
python scripts/radio/run_radio_burst_pipeline.py --config radio_20250124_config

# Quick radio source maps with Gaussian overlays
python scripts/radio/run_radio_source_map.py

# Extract threshold/contour radio-source centers to a table
python scripts/radio/extract_radio_centers.py --radio-dir D:\path\to\radio_fits --out outputs\radio_centers.csv --threshold 0.95 --threshold-mode bg_peak --make-sum

# Launch the Streamlit radio-source trajectory frontend
streamlit run scripts/radio/run_radio_source_app.py

# Launch the managed radio ROI light-curve frontend
solar-radio roi-lightcurve --radio-dir D:\path\to\radio_fits --output-dir outputs\radio-roi

# Export one selected trajectory frame to static Plotly HTML
python scripts/radio/export_radio_source_trajectory.py --centers outputs\radio_centers.csv --out outputs\radio_source_trajectory.html

# Launch the local multi-folder image sequence viewer with video export
python scripts/tools/run_image_web_viewer.py --allowed-roots D:\path\to\images --open-browser

# AIA/radio/HMI context overlays
python scripts/radio/run_aia_radio_hmi_overlay.py
```

The current public script inventory, including utility and legacy-risk
workflows, is maintained in `docs/script_index.md`.

Reusable radio helpers can also be imported directly from the installable
package layer:

```python
from solar_toolkit.radio import centers, gaussian, newkirk, quicklook, trajectory
```

The `gaussian` object above is the radio-domain aggregation surface. Import the
instrument-independent model from `solar_toolkit.modeling.gaussian`.

## Configuration and Data Policy

Copy `configs/paths.example.yaml` to `configs/paths.local.yaml` and adapt it to
your local observation archive. `configs/paths.local.yaml` is ignored by Git.
Alternatively, set `SOLAR_PHYSICS_CONFIG` to point to an external YAML file.
Radio event configuration is validated by `solar_toolkit.radio.config`.
Precedence is CLI arguments, explicit config file/object/mapping, path-only
environment configuration, then defaults; scientific ROI, threshold, Gaussian,
and Newkirk assumptions are not inferred from environment variables.

## Documentation Map

- `docs/quickstart.md`: beginner path for environment setup, safe checks,
  first imports, path configuration, and recommended entrypoints.
- `docs/README.md`: documentation index that separates current guidance from
  historical audit reports.
- `CONTRIBUTING.md`: development environment, checks, and contribution notes.

## Citation

Citation metadata is provided in `CITATION.cff`.

Li, Y. (2025). *Python for Solar Physics: Multi-wavelength Data Processing
Toolkit*. Shandong University.
<https://github.com/YUCONG-28/python-for-solar-physics>

## License

MIT License. See `LICENSE`.
