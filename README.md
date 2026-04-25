# ☀️ Python for Solar Physics

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Contributions](https://img.shields.io/badge/Contributions-Welcome-orange.svg)]()

> A comprehensive collection of Python scripts and tools for multi-wavelength solar data analysis, designed to support scientific research on solar flares, radio bursts, CMEs, and coronal heating.

---

## 📌 Overview

This repository provides a set of modular, well-documented Python scripts for processing and visualizing observations from multiple solar instruments:

- **SDO/AIA** — EUV imaging (multiple wavelengths)
- **SDO/HMI** — Photospheric magnetic field
- **GOES** — Soft X-ray (SXR) flux
- **ASO-S/HXI** — Hard X-ray imaging
- **CSO / DSRT** — Solar radio spectrograms and imaging
- **SOHO/LASCO** — Coronagraph (CME tracking)
- **Hessi / RHESSI (HXR)** — Hard X-ray spectroscopy

The scripts are designed to work together, sharing utilities via `utils_solar.py` and supporting multi-wavelength co-alignment, overlay plotting, and difference imaging.

---

## 📂 Repository Structure

### 🛰️ EUV & Magnetic Field

| Script | Description |
|--------|-------------|
| [`AIA.py`](AIA.py) | Core AIA FITS processing: single-band, multi-band 2×3 composites, ROI extraction, parallel processing |
| [`aia_multipanel.py`](aia_multipanel.py) | Read and plot AIA images in 6-panel multi-wavelength layout |
| [`AIA_difference_base.py`](AIA_difference_base.py) | Base-difference imaging for AIA (pre-flare reference subtraction) |
| [`AIA_difference_running.py`](AIA_difference_running.py) | Running difference imaging for dynamic event tracking |
| [`AIA_Flux_data.py`](AIA_Flux_data.py) | Extract AIA light curves and flux data from FITS sequences |
| [`AIA_Flux_data_plot.py`](AIA_Flux_data_plot.py) | Visualize AIA flux / light curves with customizable styling |
| [`AIA_time_distance.py`](AIA_time_distance.py) | Create time-distance diagrams from AIA map sequences |
| [`AIA_rename.py`](AIA_rename.py) | Batch rename FITS files with custom prefixes |
| [`AIA_select_files.py`](AIA_select_files.py) | Filter and copy AIA FITS files by target time |
| [`HMI.py`](HMI.py) | HMI magnetogram processing, alignment, and submap extraction |

### 📡 Radio Data

| Script | Description |
|--------|-------------|
| [`CSO_PLOT.py`](CSO_PLOT.py) | Comprehensive CSO spectrogram plotting: memory-mapped I/O, parallel channels (LL/RR), customizable downsampling |
| [`plot_cso_spectrogram.py`](plot_cso_spectrogram.py) | CSO spectrogram class with rebinning and time-frequency visualization |
| [`csoSpectraGUIV09.py`](csoSpectraGUIV09.py) | CSO spectra GUI tool |
| [`RS_plot.py`](RS_plot.py) | Radio spectrogram processing: single-band & multi-band composite imaging, ellipse Gaussian fitting |
| [`AIA_RS.py`](AIA_RS.py) | Radio source + AIA + HMI overlay: configurable multi-instrument composite plots with polarization overlays |
| [`HXI_SXR.py`](HXI_SXR.py) | HXI + SXR time series comparison |

### 🌡️ Thermodynamics & High-Energy

| Script | Description |
|--------|-------------|
| [`DEM.py`](DEM.py) | Differential Emission Measure (DEM) inversion from AIA data |
| [`DEM_RS.py`](DEM_RS.py) | DEM analysis with radio source intensity gradient overlay |
| [`HXI.py`](HXI.py) | ASO-S/HXI hard X-ray FITS data reading and mapping |
| [`HXR.py`](HXR.py) | Hard X-ray (RHESSI / HESSI) light curve plotting |
| [`SXR.py`](SXR.py) | GOES soft X-ray flux data (NetCDF format) processing |
| [`from SXR to HXR.py`](from%20SXR%20to%20HXR.py) | **Neupert effect analysis**: SXR temporal derivative vs HXR comparison |
| [`AIA_HXI.py`](AIA_HXI.py) | AIA + HXI overlay visualization |
| [`AIA_SXR_HXR_plot.py`](AIA_SXR_HXR_plot.py) | 3-panel figure: AIA image + GOES SXR flux + HXR light curve |

### 👑 Coronagraph & CME

| Script | Description |
|--------|-------------|
| [`LASCO_data.py`](LASCO_data.py) | Download SOHO/LASCO data from Helioviewer (hvpy) |
| [`LOSCO_plot.py`](LOSCO_plot.py) | Basic LASCO image plotting with sunpy |
| [`LASCO_difference_plot.py`](LASCO_difference_plot.py) | LASCO running difference imaging for CME tracking |

### 🔧 Shared Utilities

| Script | Description |
|--------|-------------|
| [`utils_solar.py`](utils_solar.py) | Shared toolkit: time parsing, file sorting, memory management, configuration, coordinate transformations |
| [`M_V.py`](M_V.py) | Video generation from image sequences (supports FFmpeg, imageio, OpenCV) |

### 🧪 Test & Experimental

| Script | Description |
|--------|-------------|
| `01.py` | Misc/experimental |
| `test_AIA_RS_0.py` | AIA + RS pipeline tests |
| `test_AIA_RS_1.py` | AIA + RS pipeline tests |
| `test_AIA_RS_3.py` | AIA + RS pipeline tests |
| `test_CSO.py` | CSO data processing test |
| `test_header.py` | FITS header parsing test |
| `test_sun_contour.py` | Solar limb contour detection test |
| `test_time.py` | Time parsing utilities test |
| `test.py` | General test script |

### 📄 Paper Reader (Subproject)

| Directory | Description |
|-----------|-------------|
| [`paper_reader_ollama/`](paper_reader_ollama/) | AI-powered paper reader using [crewAI](https://crewai.com) + Ollama. Multi-agent system for automated literature analysis. See its [own README](paper_reader_ollama/README.md) for details. |

> **Note:** The `solar_toolkit/` package is a minimal scaffold (`__init__.py` only); the core functionality lives in the standalone scripts listed above.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- 4GB+ RAM (8GB+ recommended for large FITS datasets)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YUCONG-28/python-for-solar-physics.git
cd python-for-solar-physics

# 2. Create a virtual environment (recommended)
python -m venv venv

# Activate it:
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install numpy scipy astropy sunpy matplotlib pandas reproject scikit-image pyyaml tqdm

# 4. Install optional dependencies for full functionality
pip install seaborn plotly opencv-python dask fitsio drms
```

You can also install the package in development mode:

```bash
pip install -e .
```

### Verification

```python
import numpy as np
import astropy
import sunpy
import matplotlib.pyplot as plt

print(f"NumPy:     {np.__version__}")
print(f"AstroPy:   {astropy.__version__}")
print(f"SunPy:     {sunpy.__version__}")
print("✅ All core dependencies loaded successfully!")
```

---

## 💡 Usage Examples

### Multi-wavelength AIA Composite

```python
# Run the AIA multi-band processor
python AIA.py --data_dir /path/to/aia/data --output_dir ./output
```

### Radio Spectrogram Visualization

```python
# Plot CSO spectrogram with polarization channels
python CSO_PLOT.py --input /path/to/cso.fits --mode total
```

### Neupert Effect Analysis

```python
# Compare SXR derivative with HXR emission
python "from SXR to HXR.py"
```

### AIA + HXI Overlay

```python
# Overlay HXI contours on AIA EUV image
python AIA_HXI.py
```

---

## 🤝 Contributing

Contributions are welcome! If you have ideas for improvements, new instruments, or bug fixes:

1. Fork the repository
2. Create a feature branch
3. Submit a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## ⭐ Support

If you find this project useful for your research, please consider giving it a ⭐ on GitHub!

---

## 📚 Citation

If you use this toolkit in your research, please cite it as:

```bibtex
@software{solar_physics_python_2025,
  author = {Solar Physics Research Team (Severus, Lee, Ninghao)},
  title = {Python for Solar Physics: Multi-wavelength Data Processing Toolkit},
  year = {2025},
  url = {https://github.com/YUCONG-28/python-for-solar-physics}
}
```
