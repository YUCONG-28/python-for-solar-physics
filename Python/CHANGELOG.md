# Changelog

## Unreleased

- Updated contributor and architecture documentation for `solarphysics_env`
  setup, standalone `pre-commit` usage, verification environment variables, and
  public-surface documentation sync rules.

## 0.2.0

- Reorganized standalone workflows under `scripts/` by scientific task and
  moved reusable implementations into `solar_toolkit/`.
- Added package-owned commands: `solar-aia`, `solar-radio`,
  `solar-image-viewer`, and `solar-webapp`.
- Expanded `solar-radio` into eight package-owned subcommands: `centers`,
  `pipeline`, `source-map`, `overlay`, `quicklook`, `raw-quality`,
  `roi-lightcurve`, and `trajectory`.
- Added the integrated `/radio` workspace in the local webapp for explicit
  Preview, Run, and Cancel actions over selected radio modules.
- Added path-only local configuration support through `solar_toolkit.path_config`,
  `configs/paths.example.yaml`, and ignored `configs/paths.local.yaml`.
- Split data-independent tests into `tests/` and local-data examples into
  `examples/`.
- Added GitHub Actions lightweight CI, citation metadata, contribution guidance,
  pre-commit/Gitleaks checks, and architecture documentation.
