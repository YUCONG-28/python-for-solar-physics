# ☀️ Solar Physics Data Processing & Visualization Toolkit

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Contributions](https://img.shields.io/badge/Contributions-Welcome-orange.svg)]()

> A research-oriented toolkit for multi-wavelength solar data analysis, designed for efficient processing, precise co-alignment, and publication-quality visualization.

---

## 📌 Overview

This repository provides an integrated pipeline for processing and visualizing multi-instrument solar observations, including EUV, magnetic field, radio, and X-ray data.

It is specifically designed to support **scientific research workflows**, enabling:

* rapid data preprocessing
* accurate multi-wavelength alignment
* high-quality figure generation

The toolkit bridges the gap between raw observational data and physical interpretation, making it particularly suitable for studies of:

* solar flares
* radio bursts
* coronal heating
* CME dynamics

---

## ✨ Key Features

### 🛰️ EUV & Magnetic Field Analysis

* Visualization of **SDO/AIA** and **SDO/HMI** data with publication-quality rendering
* Precise co-alignment of EUV images with photospheric magnetic field maps
* Direct visualization of magnetic topology (loop footpoints, active region polarity)

---

### 📡 Radio Data Processing

* Imaging of radio sources from **Daocheng Solar Radio Telescope (DART)**
* Accurate overlay of radio source centroids and contours onto EUV images
* Dynamic spectrum visualization for **Chashan Solar Radio Telescope** data

---

### 🌡️ Thermodynamics & High-Energy Analysis

* Integrated **Differential Emission Measure (DEM)** inversion tools
* Support for **ASO-S / HXI** hard X-ray observations
* Built-in analysis of **GOES soft X-ray (SXR)** flux and its temporal derivative
* Direct comparison with HXR emission for studying the **Neupert effect**

---

### 👑 Coronagraph & CME Analysis

* Processing and visualization of **SOHO/LASCO** coronagraph data
* Suitable for tracking **Coronal Mass Ejections (CMEs)** and large-scale coronal structures

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/your-username/your-repo-name.git

# Enter the directory
cd your-repo-name

# Install dependencies
pip install -r requirements.txt
```

---

## 📊 Example Outputs

> *(You can place your figures in `/figures` and display them here)*

```markdown
![AIA + HMI Overlay](figures/aia_hmi_overlay.png)
![Radio + EUV Overlay](figures/radio_euv_overlay.png)
![GOES Neupert Effect](figures/goes_neupert.png)
```

---

## 🧠 Scientific Motivation

Multi-wavelength observations are essential for understanding the physical processes in the solar atmosphere. However, challenges such as:

* heterogeneous data formats
* coordinate misalignment
* complex preprocessing pipelines

often hinder efficient analysis.

This project aims to provide a **unified, reproducible, and extensible framework** that simplifies these processes and accelerates scientific discovery.

---

## 🛠️ Roadmap

* [ ] Automated DEM pipeline
* [ ] Machine learning integration for feature detection
* [ ] Interactive visualization (Jupyter / web-based)
* [ ] Expanded support for additional instruments

---

## 🤝 Contributing

Contributions are welcome!
If you have ideas for improvements, new instruments, or optimizations:

1. Fork the repository
2. Create a feature branch
3. Submit a Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

## ⭐ Support

If you find this project useful for your research, consider giving it a ⭐ on GitHub — it helps increase visibility and supports further development.
