# Documentation Assets

This directory is reserved for reviewed, non-observational assets used by
project documentation. Research observations, derived figures, diagnostic
plots, and data tables must remain outside Git even when they are compressed.

## `docs/assets/images/`

This folder is intentionally empty. Before adding an image, confirm that it is
not an observation, a derived science product, or a visualization of private
research data, and add its exact path to the repository data-policy allowlist.

## `docs/assets/videos/`

This folder is intentionally empty. Do not add recordings of research data or
local workflows. Any future non-sensitive demonstration must be reviewed and
explicitly allowlisted before it is tracked.

## Data Policy

- Do not place real raw observation data here.
- Do not place generated figures, tables, videos, or interactive exports here.
- Do not place FITS, JP2, NetCDF, NPY/NPZ, HDF5, local path configs, or
  credential material here.
- Keep local research products in ignored output directories.
- Treat the repository data-policy allowlist as an explicit review boundary,
  not as a general exemption for this directory.
