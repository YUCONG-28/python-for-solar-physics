# Solar Physics Data Visualization and Analysis Toolkit

A research-oriented Python toolkit for multi-wavelength solar event analysis. The
repository focuses on practical, script-based workflows for SDO/AIA, SDO/HMI,
radio source imaging, CSO dynamic spectra, GOES soft X-rays, HXR/HXI diagnostics,
DEM/Tb visualization, and SOHO/LASCO CME context.

The code is designed for flare, jet, CME, and radio-burst studies where local
observation data must be turned into publication-quality figures, overlay maps,
light curves, source-center diagnostics, and time-evolution products.

GitHub: <https://github.com/YUCONG-28/python-for-solar-physics>

## Features

- Publication-quality SDO/AIA visualization
- HMI magnetic field overlay
- Radio source contour overlay
- Multi-frequency radio imaging support
- Difference imaging for dynamic solar events
- Gaussian fitting and source-center tracking
- Flexible plotting layout for single-band and multi-panel figures
- Configurable colormap, contour levels, intensity scaling, and ROI selection
- CSO dynamic spectrogram plotting with memory-aware downsampling
- GOES SXR, HXR/HXI, DEM/Tb, and LASCO CME support for event context
- Local YAML path configuration without committing personal data paths

## Scientific Workflows

The toolkit supports these common analysis products:

- SDO/AIA single-band EUV/UV images, mosaics, base differences, and running
  differences.
- SDO/HMI magnetograms and magnetic-field contours over AIA images.
- Radio source maps from FITS images, including RR/LL polarization handling,
  multi-frequency contours, and Gaussian source fitting.
- AIA, radio source, and optional HMI overlays for source-region comparisons.
- CSO radio dynamic spectra with LL/RR, total intensity, and polarization ratio
  views.
- AIA light-curve extraction, CSV light-curve plotting, and time-distance
  diagrams.
- GOES SXR and HXR/HXI light curves, Neupert-effect comparisons, and combined
  flare diagnostic panels.
- DEM/Tb and radio-source overlay figures.
- SOHO/LASCO JP2 image plotting and running-difference CME products.
- Image-sequence to MP4 video generation for time-evolution products.

## Input Data

Typical inputs are local science data products, not stored in this repository:

- SDO/AIA FITS files, usually grouped by wavelength such as `94`, `131`, `171`,
  `193`, `211`, `304`, `335`, or `1600`.
- SDO/HMI magnetogram FITS files.
- CSO spectrogram FITS files.
- Radio source FITS images organized by frequency and polarization.
- GOES SXR NetCDF files.
- ASO-S/HXI or HESSI/RHESSI-style HXR FITS files.
- DEM or brightness-temperature arrays such as `.npy` products.
- SOHO/LASCO JP2 images.
- CSV tables produced by the light-curve extraction scripts.

## Output Products

Generated products are usually written beside local data or into configured
output folders:

- AIA PNG figures and multi-band mosaics
- AIA base/running difference maps
- AIA-HMI, AIA-HXI, AIA-radio, and AIA-radio-HMI overlay figures
- Radio source maps, contours, fitted centers, and multi-frequency panels
- CSO dynamic spectra and polarization diagnostics
- AIA/GOES/HXR light-curve and summary figures
- DEM/Tb diagnostic images and radio overlays
- LASCO CME running-difference images
- MP4 videos made from image sequences

Large generated images, videos, FITS files, local data tables, and cache files
are intentionally ignored by Git.

## Project Structure

```text
python-for-solar-physics/
├── solar_toolkit/              # Shared helpers and package metadata
├── scripts/                    # Runnable research workflows
│   ├── aia_hmi/                # SDO/AIA and SDO/HMI processing
│   ├── radio/                  # CSO spectra and radio-source imaging
│   ├── xray_dem/               # GOES, HXR/HXI, Neupert, DEM/Tb workflows
│   ├── lasco_cme/              # SOHO/LASCO download and CME plotting
│   └── tools/                  # General utilities
├── examples/                   # Local-data examples and historical workflows
├── configs/                    # Path configuration templates
├── docs/                       # Project and script documentation
├── tests/                      # Lightweight tests without observation data
├── outputs/                    # Notes for generated local products
├── pyproject.toml              # Package metadata and optional extras
├── requirements.txt            # Convenient pip dependency list
└── README.md
```

See `docs/project_structure.md` and `docs/script_index.md` for more detail.

## Installation

The project is developed with Miniforge/conda on Windows, but the core package
can be installed with any Python 3.10+ environment that supports SunPy and
AstroPy.

```powershell
conda create -n solarphysics_env python=3.11
conda activate solarphysics_env
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For a broader local analysis environment:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e ".[dev,full]"
```

GUI and legacy radio-spectrum tools may require extra packages such as `PyQt5`,
`pyqtgraph`, and a local or pip-installable `rebin` module:

```powershell
python -m pip install -e ".[gui]"
```

## Code Style

This project uses a consistent Python code style to keep the scientific pipeline
maintainable.

- Black is used as the main Python formatter.
- Ruff is used for linting, import sorting, and safe automatic fixes.
- Pylance is recommended for type analysis and code navigation in VSCode.
- autopep8, yapf, flake8, and pylint are not used as default tools in this
  project.

Before committing changes, run:

```bash
pre-commit run --all-files
```

## Local Path Configuration

Most science workflows need local FITS, JP2, NetCDF, CSV, or NumPy data. Avoid
hard-coding personal paths in source files by copying the example config:

```powershell
Copy-Item configs\paths.example.yaml configs\paths.local.yaml
```

Edit `configs/paths.local.yaml` for your machine. This file is ignored by Git.
You can also point to another config file:

```powershell
$env:SOLAR_PHYSICS_CONFIG="D:\my_project\solar_paths.yaml"
```

Missing config sections leave each script's built-in defaults unchanged.

## Quick Start

```powershell
# AIA single-band or mosaic processing
python scripts\aia_hmi\sdo_aia_euv_processor.py --mode single --waves 171 193 304

# AIA preview mode for checking ROI and intensity scaling
python scripts\aia_hmi\sdo_aia_euv_processor.py --mode test --test-wave 171 --test-index 0 --roi -700 -100 -100 400

# Normalize AIA/HMI FITS filenames without modifying files
python scripts\aia_hmi\sdo_aia_hmi_fits_rename.py D:\solar_data\SDO --dry-run

# CSO dynamic spectrum plotting
python scripts\radio\cso_radio_spectrogram_plot.py

# AIA, radio source, and HMI overlay workflow
python scripts\radio\sdo_aia_radio_hmi_overlay.py

# Neupert-effect SXR derivative comparison
python scripts\xray_dem\neupert_sxr_derivative_hxr_comparison.py

# Convert generated PNG sequence to MP4
python scripts\tools\image_sequence_to_video.py
```

## Verification

These checks are data-independent and should run before committing:

```powershell
python -m compileall -q solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; python -m pytest -q tests
python -c "from solar_toolkit import solar_analysis_utils; import solar_toolkit; print(solar_toolkit.__version__)"
```

Full science workflows still require the corresponding local observation data.

## Data Policy

Do not commit raw observation data, generated figures, videos, local path
configs, cache folders, Excel/CSV products, or machine-specific temporary files.
Keep reproducible code, configuration templates, documentation, and lightweight
tests in Git.

## Citation

Citation metadata is provided in `CITATION.cff`.

Li, Y. (2025). *Python for Solar Physics: Multi-wavelength Data Processing
Toolkit*. Shandong University.
<https://github.com/YUCONG-28/python-for-solar-physics>

## License

MIT License. See `LICENSE`.
