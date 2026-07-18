# Public workflow index

Version 0.3.0 has no library console entry points. Library users import
`solar_toolkit` modules and pass paths and configuration explicitly.

Application source and its canonical Miniforge launcher are tracked in
[`../../Apps`](../../Apps/README.md). Use `Apps/run.ps1` for frontends,
workflows, administration, and tools. Private configuration, state, paths, and
outputs remain in the ignored `Local` runtime partition.
