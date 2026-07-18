# Synthetic examples

These examples are deterministic, import-safe, and require no observation
files. By default, every generated file is written below
`Local/outputs/examples/`, which is part of the ignored runtime tree. Both
examples reject output paths inside `Apps/`.

Initialize the private runtime through the public launcher first:

```powershell
.\Apps\run.ps1 admin init
```

The examples are developer entry points rather than public application
commands. Run them with the same Miniforge environment used by the launcher:

```powershell
& "<miniforge-root>\Scripts\conda.exe" run -n solarphysics_env_latest python .\Apps\examples\synthetic_radio_display.py
& "<miniforge-root>\Scripts\conda.exe" run -n solarphysics_env_latest python .\Apps\examples\synthetic_state_and_paths.py
```

## Spatial radio display

`synthetic_radio_display.py` creates a small two-source NumPy array, applies
`SpatialRadioDisplay`, and writes a PNG plus its schema-1 JSON sidecar. It
demonstrates the same colormap, invalid-value color, transform, percentile,
field-of-view, and cache-signature contract used by Source Map.

Choose a different non-`Apps` destination with `--output`:

```powershell
& "<miniforge-root>\Scripts\conda.exe" run -n solarphysics_env_latest python .\Apps\examples\synthetic_radio_display.py --output "<ignored-output-path>\synthetic_radio_display.png"
```

## State and recent paths

`synthetic_state_and_paths.py` creates an isolated example directory, saves
the latest UI fields with `StateStore`, records one synthetic directory with
`RecentPathMemory`, then constructs fresh readers to verify restart recovery.
It saves only the latest values: no history, timestamps, job identifiers,
logs, or scientific results.

Choose a different non-`Apps` destination with `--output-dir`:

```powershell
& "<miniforge-root>\Scripts\conda.exe" run -n solarphysics_env_latest python .\Apps\examples\synthetic_state_and_paths.py --output-dir "<ignored-output-directory>"
```

Each module exposes `main(argv=None) -> int`, so integration tests can import
it without creating files or opening a GUI.
