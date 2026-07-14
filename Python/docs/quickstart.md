# Public library quickstart

Install from the unified repository root:

```powershell
D:\miniforge3\envs\solarphysics_env_latest\python.exe -m pip install -e .\Python
```

Current commands default to `solarphysics_env_latest`. The retained
`solarphysics_env` environment is the formal backup; select its interpreter
explicitly only when a compatibility fallback is required.

The public package is import-only: it installs no console scripts and discovers
no event or workstation paths. Supply paths and configuration objects directly.

```python
from solar_toolkit.radio.config import RadioEventConfig

config = RadioEventConfig.from_mapping(
    {"user": {"data": {"multi_band_freqs": [149.0, 164.0]}}}
)
```

Local CLIs and GUI workflows are documented in `../Local/README.md`; they are
not part of the public repository index or wheel.
