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
```

Missing config files or missing sections leave the script defaults unchanged.
