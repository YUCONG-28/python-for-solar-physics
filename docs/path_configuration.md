# Path Configuration

Many scripts need local observation data. The repository keeps runnable defaults in the scripts, but users can override local paths without editing source files.

## Local Config File

Copy the example file:

```powershell
Copy-Item configs\paths.example.yaml configs\paths.local.yaml
```

Edit `configs/paths.local.yaml` for your machine. This file is ignored by Git.

## Environment Variable

You can also point to a config file anywhere:

```powershell
$env:SOLAR_PHYSICS_CONFIG="D:\my_project\solar_paths.yaml"
```

## Format

Configuration sections are keyed by script name:

```yaml
scripts:
  sdo_aia_euv_processor:
    data_path: D:\solar_data\AIA
    output_dir: D:\solar_output\AIA
  soho_lasco_running_difference:
    input_dir: D:\solar_data\LASCO
    output_dir: D:\solar_output\LASCO\difference
    show_plot: false
```

Missing config files or missing sections leave the script defaults unchanged.

For long batch jobs, scripts that support `show_plot` default to `false` so
figures are saved and closed without blocking the run with GUI windows.

## Module Templates

The repository also includes module-level example templates:

- `configs/aia.example.yaml`
- `configs/radio.example.yaml`
- `configs/cso.example.yaml`
- `configs/overlay.example.yaml`

These files do not replace `configs/paths.example.yaml` yet. They are planning
templates for future refactoring so path, frequency, colormap, threshold, and
output settings can eventually be centralized without changing the scientific
algorithms.

Do not put real local data paths or private observation paths in committed YAML
files. Use placeholders in examples and keep machine-specific values in
`configs/paths.local.yaml` or another file referenced by `SOLAR_PHYSICS_CONFIG`.
