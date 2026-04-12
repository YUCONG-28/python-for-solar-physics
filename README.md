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

## 🚀 快速开始

### 前提条件

- Python 3.8 或更高版本
- Git（用于克隆仓库）
- 至少 4GB 可用内存（处理天文数据建议 8GB+）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/solar-physics-toolkit.git
cd solar-physics-toolkit

# 2. 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
# 基础安装（核心功能）：
pip install -r requirements.txt

# 或者安装为可编辑包（推荐用于开发）：
pip install -e .

# 4. 安装完整功能（包含所有可选依赖）：
pip install -e ".[full]"

# 5. 安装开发工具（可选）：
pip install -e ".[dev]"
```

### 验证安装

```python
# 创建一个简单的测试脚本 test_install.py
import sys
print(f"Python版本: {sys.version}")

try:
    import numpy as np
    import astropy
    import sunpy
    import matplotlib.pyplot as plt
    
    print("✅ 核心依赖加载成功!")
    print(f"NumPy版本: {np.__version__}")
    print(f"AstroPy版本: {astropy.__version__}")
    print(f"SunPy版本: {sunpy.__version__}")
    
    # 测试基本功能
    from astropy import units as u
    from sunpy.coordinates import frames
    
    print("✅ 天文单位系统测试通过!")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)
```

运行测试：
```bash
python test_install.py
```

### 快速示例

```python
# 示例：加载和显示AIA数据
from solar_toolkit.processors import AIAProcessor
import matplotlib.pyplot as plt

# 初始化处理器
processor = AIAProcessor(data_dir="path/to/aia/data")

# 加载特定波段的图像
aia_193 = processor.load_wavelength(193)

# 创建简单的可视化
fig, ax = plt.subplots(figsize=(8, 8))
aia_193.plot(ax=ax, title="AIA 193Å")
plt.savefig("aia_193_example.png", dpi=150, bbox_inches='tight')
plt.show()
```

### 获取测试数据

```bash
# 下载示例数据（需要安装sunpy）
python -c "import sunpy.data; sunpy.data.download_sample_data()"

# 或者使用内置的示例数据
from sunpy.data.sample import AIA_193_IMAGE
import sunpy.map
aia_map = sunpy.map.Map(AIA_193_IMAGE)
print(f"示例数据加载成功: {aia_map.date}")
```

---

## 📊 Example Outputs

> *(You can place your figures in `/figures` and display them here)*

```markdown
loading...
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
