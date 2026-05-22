# README Display Assets

This directory is reserved for small, curated assets used by `README.md` and
project documentation.

## `docs/assets/images/`

Use this folder for compressed example figures:

- AIA single-band or mosaic previews
- AIA base/running difference examples
- AIA/radio/HMI overlay examples
- CSO dynamic spectrogram examples
- Radio Gaussian fitting diagnostic examples

Recommended image size:

- Prefer widths around 1200-1800 px for README figures.
- Prefer each image under 500 KB.
- Special cases should stay under 2 MB to avoid pre-commit large-file checks.

## `docs/assets/videos/`

Use this folder for short README demonstration videos only:

- Short MP4 clips
- Short GIF previews when MP4 is not practical

Do not upload full science batch outputs, long time-series videos, or raw
processing products.

## Data Policy

- Do not place real raw observation data here.
- Do not place FITS, JP2, NetCDF, NPY/NPZ, HDF5, or local path configs here.
- Example figures must be compressed, desensitized if needed, and have a clear
  source or generation note in documentation.

The current root-level files `HXR.png`, `SXR.png`, `SXR to HXR.png`, and
`SXR to HXR enhance.png` need manual review before any future move into
`docs/assets/images/`. This cleanup phase intentionally leaves them in place.
