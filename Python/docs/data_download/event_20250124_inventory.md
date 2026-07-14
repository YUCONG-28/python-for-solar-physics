# 2025-01-24 Event Data Acquisition Inventory

This page documents the event-specific helpers that were folded into the main
project layout from a temporary staging workspace.

## Download And Query Scripts

| Script | Purpose | Main outputs |
| --- | --- | --- |
| `scripts/aia_hmi/sdo_aia_jsoc_download_20250124.py` | Download selected SDO/AIA JSOC level-1 EUV records for 2025-01-24 04:00-05:00 UTC. | FITS files and `manifest_urls.txt` under `~/data/aia/20250124_2/`. |
| `scripts/data_download/stereo_a_euvi_download_20250124.py` | Query STEREO-A SECCHI/EUVI records with SunPy/Fido and download the matching FTS files. | `data/raw/stereo/euvi/20250124/selected_files.txt` and EUVI FTS files. |
| `scripts/data_download/goes_suvi_download_20250124.py` | Download GOES-16/18 SUVI L2 composite images for 094, 131, 171, 195, 284, and 304 A. | `data/raw/suvi/goes*/ci*/20250124/*.fits`. |
| `scripts/data_download/solo_eui_soar_query_download.py` | Query Solar Orbiter Archive EUI metadata and optionally download selected FITS files with `--download`. | `data/raw/solo/eui/20250124/soar_eui_20250124_0400_0500_metadata.json`. |

## Recommended Event Workflow

The 2025-01-24 event workflow is complete at the script level for data
acquisition, indexing, and context visualization:

1. Download or query AIA, STEREO-A/EUVI, GOES/SUVI, and optional Solar
   Orbiter/EUI data.
2. Build the STEREO-A/EUVI wavelength manifest.
3. Generate EUVI 04:48 UT overview images.
4. Generate EUVI ROI movie frames and MP4 products when needed.
5. Generate GOES/SUVI lower-right quadrant context plots.

The scripts intentionally write raw data under `data/raw/` and generated
products under `data/products/` by default; both are ignored by Git.

## Processing And Visualization Scripts

| Script | Purpose | Main outputs |
| --- | --- | --- |
| `scripts/stereo_suvi/stereo_euvi_manifest_by_wavelength.py` | Read EUVI FITS headers, create a wavelength manifest, and build a by-wavelength symlink view. | `manifest_by_wavelength.csv` and `by_wavelength/`. |
| `scripts/stereo_suvi/stereo_euvi_0448_overview_plot.py` | Plot EUVI 171/195/284/304 A images nearest 2025-01-24 04:48:45 UTC. | Single-channel PNGs, a 2x2 overview PNG, and `selected_euvi_044830_044900.txt`. |
| `scripts/stereo_suvi/stereo_euvi_roi_movie.py` | Create fixed-canvas EUVI ROI frame sequences and MP4 movies for the event region. | ROI frame PNGs, MP4 videos, and `movie_summary.csv`. |
| `scripts/stereo_suvi/goes_suvi_0448_quadrant_plot.py` | Plot GOES-16/18 SUVI lower-right quadrant images at 04:48 UTC. | Single-channel PNGs, an overview PNG, and `selected_files.txt`. |

## Environment Overrides

These scripts default to repository-relative `data/raw/` and `data/products/`
paths where practical. Override locations with:

- `STEREO_EUVI_DATA_DIR`
- `STEREO_EUVI_PRODUCT_DIR`
- `STEREO_EUVI_ROI_PRODUCT_DIR`
- `SUVI_DATA_ROOT`
- `SUVI_PRODUCT_DIR`

Raw FITS/FTS data, generated PNG/MP4 products, zip archives, and Python caches
are intentionally excluded from Git.

## Completeness Notes

- AIA JSOC download: present as an event-specific helper.
- STEREO-A/EUVI download: present.
- GOES/SUVI download: present.
- Solar Orbiter/EUI metadata query and optional download: present.
- EUVI manifest/index generation: present.
- EUVI overview plotting: present.
- EUVI ROI MP4 generation: present.
- GOES/SUVI quadrant plotting: present.
- Raw data and generated products: intentionally local-only and ignored.
