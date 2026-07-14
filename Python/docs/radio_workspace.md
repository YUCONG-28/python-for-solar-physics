# Modular Radio Workspace

The Radio Workspace is the integrated browser surface for the repository's
radio-analysis capabilities. Start the existing `solar-webapp` process and open
`/radio`; no second port, iframe, CDN, or external Streamlit service is needed.
All visible application text is English-only.

The workspace is intentionally selective. Enabling, expanding, pinning, moving,
or applying a preset to a module does **not** run an action, read FITS data,
create a worker, or silently execute an upstream module. Each action has its own
inputs, Preview, Run, Cancel, log, and result area.

## Start the Workspace

Install the application dependencies and launch the unified workbench:

```powershell
python -m pip install -e ".[app]"

solar-webapp `
  --allowed-roots "D:\radio_data;D:\analysis_outputs" `
  --radio-output-root D:\analysis_outputs `
  --open-browser
```

Then open `http://127.0.0.1:7870/radio`. On Windows, separate multiple
`--allowed-roots` with a semicolon; on other platforms, use the platform path
separator. The repository root is the default workspace output root when
`--radio-output-root` is omitted.

The sidebar's **File access roots** section shows all effective directories
available to the local file browser. Choose **Manage** to replace the editable
data-root list for the current server session by entering one absolute
directory per line. Protected output roots, including saved workspaces with
custom outputs, remain available and cannot be removed from this editor. This
does not read files or start an analysis action, and queued or running actions
continue with their already resolved inputs. Session changes affect only future
requests and are intentionally temporary: after the server restarts, the
startup `--allowed-roots` value becomes the editable default again. If **Select
Local Path** reports that a requested location is outside the allowed roots,
use **Manage file access** in that dialog; the requested directory is appended
to the editable list and, after a successful update, the browser continues at
that location.

The main area opens empty. Every analysis module, action, Parameters section,
and Advanced section stays disabled or collapsed until explicitly opened.
**Runs & Results** is always available through the result drawer. Workspaces
created before UI layout version 2 receive this empty-layout migration once;
their paths, event settings, runs, artifacts, advanced configuration, and
concurrency are retained. Later visits restore the user's version-2 layout.

The left sidebar is organized as **Core**, **Analysis**, **Context**, and
**Advanced**. Advanced and adjacent compatibility actions remain inside their
owning research module instead of appearing as duplicate workflow cards. Users
can enable, pin, collapse, and reorder modules; unused modules stay tucked in
the sidebar.

## Fused Module Inventory

The UI groups related historical workflows by research purpose instead of
registering several overlapping cards for the same science path.

| Module | Current actions and fused capabilities | Independent use |
| --- | --- | --- |
| **Data & Configuration** | Allowed-root file browsing; event configuration; shared path, frequency, polarization, time, and index filters; raw FITS quality diagnostics and tables. | Browse paths or inspect data quality without enabling later analysis. File browsing itself does not read FITS arrays. |
| **Imaging & Source Localization** | Source-map inspection; threshold/contour center extraction; LCP/RCP and optional L+R centers; shared single- or multi-source Gaussian fitting; fitted centers, FWHM, masks/backgrounds, diagnostics, and images. The 2025-01-24 RR/LL nine-band percentile comparison is under **Advanced** and requires an explicit radio root plus spectrogram FITS. | Run only a map, only center extraction, or only Gaussian diagnostics. Compatible existing radio files or artifacts can be selected directly. |
| **ROI & Light Curves** | Same-page Plotly box/lasso ROI selection; an allowed-root-validated candidate list and up to nine selected multi-frequency reference panels; persisted ROI JSON; `raw_sum`, `raw_mean`, and `raw_peak` extraction; selectable CSV/JSON/reference/overview/detail/normalized products. | Does not require Gaussian, drift, Newkirk, or center extraction. A saved ROI artifact can be reused. The preview's selected-file list controls only the reference grid; extraction continues to use its explicit folder, pattern, recursion, frequency, polarization, and time filters. |
| **Spectrogram & Drift** | CSO LL/RR, total-intensity, and polarization-ratio spectra; time/frequency slicing and rebinning; same-page two-point drift-line selection; drift-rate JSON and diagnostic tables. **CSO Legacy Mode** remains under **Advanced** and requires an explicit CSO FITS input. | Use an existing CSO input or the separately indexed spectrogram image and metadata artifacts. Selecting drift lines does not start the spectrum workflow. |
| **Physical Diagnostics** | Gaussian/Newkirk quicklook; source-center and height comparison; residual, drift-speed, frequency-priority, and physics diagnostic outputs. **Legacy Full Pipeline** is an advanced compatibility action. | Read an existing Gaussian or drift artifact/table without running source localization or spectrogram generation. |
| **Context & Overlays** | Time-matched AIA-radio-HMI overlays; radio contours, centers, and Gaussian markers; context images and animations. **Overlay Existing Centers and Fits** reads a center CSV, Gaussian CSV, or both, optionally adds one AIA FITS background, and writes a static PNG plus metadata JSON without fitting. The **Adjacent** DEM/radio action accepts an explicit AIA reference FITS, DEM/Tb NPY map, and radio FITS file or time-matched radio folder. | Use raw radio files or persisted Gaussian/center products; no source localization, trajectory, or physical-diagnostic run is required. |
| **Trajectory & Media** | Compatible center CSV/XLSX loading; frequency, polarization, and method filters; current/tail/all frames; overlay or faceted views; L/R comparison; AIA-backed standalone Plotly HTML; same-page playback; local Mediabunny MP4/WebM recording; reproducible MP4/GIF/WebM backend export. | Reads any compatible center table; source-center extraction is optional and is never auto-started. |
| **Runs & Results** | Queue and status, incremental logs, resolved configuration, provenance, reusable artifact index, and safe image/table/HTML/video preview or download. | Always accessible as the result drawer, regardless of which analysis modules are enabled. |

The former complete `solar-radio pipeline` remains available as **Physical
Diagnostics / Advanced / Legacy Full Pipeline**. It is a compatibility
orchestrator over the package-owned radio workflows, not a second set of
workspace cards.

## Selection and Execution Rules

- Module controls change visibility and layout only. A disabled or collapsed
  module does not load its data or create a task.
- **Preview** resolves and validates only that action. Native ROI, trajectory,
  and drift previews stay on the `/radio` page.
- **Run** starts only the action whose button was pressed.
- **Cancel** requests termination of that action's queued or running process.
- **Run Selected** includes only explicitly checked actions. Before submission,
  the review page shows action order, input source, and run output directory;
  the batch request must be explicitly confirmed. A consumer may plan an
  artifact transfer only from an earlier action in that same explicit
  selection, and only when the producer declares the artifact type and the
  consumer field declares a matching `artifact_types` value. This never
  selects or runs an upstream action implicitly.
- A missing input produces a validation message. The workspace may suggest an
  existing artifact or an upstream module, but it never runs an upstream action
  automatically.
- An input may be a path inside an allowed root or a workspace artifact. An
  artifact binding points to the original file and records its source run ID;
  it does not copy the product into the new request.

The layout presets are also selection-only:

| Preset | Enabled module layout |
| --- | --- |
| **Source Localization** | Data & Configuration, Imaging & Source Localization, Trajectory & Media |
| **ROI Study** | Data & Configuration, ROI & Light Curves |
| **Burst Physics** | Imaging & Source Localization, Spectrogram & Drift, Physical Diagnostics |
| **Multi-Instrument Context** | Imaging & Source Localization, Context & Overlays |
| **Full Analysis** | All primary modules |

Every preset also keeps Runs & Results accessible. Applying a preset never
starts Preview, Run, or Run Selected.

## Figure Studio

An explicit Plotly/image preview or completed image artifact can be added to
the full-screen **Figure Studio**. Adding a source never runs an action. Plotly
previews are rasterized locally and registered as immutable, validated preview
sources; persisted drafts contain only controlled preview or run/artifact IDs,
not arbitrary paths, URLs, or data URLs.

**Single** mode exports one panel. **Mosaic** mode supports free placement plus
vertical, horizontal, and grid templates. Layers can be moved, resized,
reordered, centered, fitted, filled, panned, zoomed, or non-destructively
cropped. One active draft is saved per workspace and immutable snapshots can be
kept before an export.

All time-aware Mosaic layers share one UTC timeline. A PNG uses one selected
UTC time. MP4/WebM animation uses an inclusive UTC start/end range, a scientific
sample interval, and an independent playback FPS. Discrete images use the
nearest real frame only inside their declared tolerance; no image interpolation
is performed. A spectrogram keeps its real coverage and receives a moving time
cursor rather than a repeated synthetic frame.

Every export requires a fresh preflight. The report lists source coverage,
matched source times and deltas, missing ranges, and a common valid interval.
Missing data blocks export. The recommended repair moves a PNG to the nearest
common time or trims an animation to the longest common continuous interval,
and is applied only after confirmation. Spectrogram shortages first offer an
explicit adjacent-input rebuild using the canonical spectrogram coverage rules;
segments separated by more than one second are not joined. Holding an image or
keeping an out-of-range spectrogram note is an explicit advanced fallback and
is recorded in the export manifest.

## Configuration and Provenance

Radio Workspace configuration is resolved from lowest to highest priority:

```text
package defaults
  -> event preset
  -> workspace shared paths
  -> workspace/request Advanced JSON
  -> current action form and artifact bindings
```

This corresponds to the user-facing rule: current action form, then module
Advanced JSON, then shared workspace paths, then event preset, then package
defaults. The manifest records every layer separately, the final resolved
configuration, declared output types, input paths or artifact bindings, and
`dependencies_auto_run: false`.

Workspace concurrency defaults to 1, can be set from 1 through 4, and is also
bounded by an application-wide hard limit of 4 active tasks. Queued and running
tasks found after a service restart become `interrupted`; they are not retried.

## Persistence Layout

Each workspace is persisted below its selected output root:

```text
<output-root>/radio_workbench/<workspace-id>/
  workspace.json
  runs/<run-id>/
    request.json
    resolved_config.json
    run.json
    run.log
    artifacts/
  figure_studio/
    draft.json
    sources/<preview-id>/
      source.json
      preview.png
    snapshots/<snapshot-id>.json
    exports/<export-id>/
      figure.json
      preflight.json
      manifest.json
      figure.png | figure.mp4 | figure.webm
      thumbnail.png
```

The versioned contracts are:

- `RadioModuleSpec`: module group, actions, accepted/produced artifact types,
  and default enabled/collapsed state.
- `RadioActionSpec`: field schema (including per-path `artifact_types` binding
  metadata), preview adapter, runner adapter, Advanced or Adjacent section, and
  accepted/produced artifacts.
- `RadioWorkspace`: event preset, shared paths, Advanced JSON, module layout,
  output root, and concurrency.
- `RadioRunManifest`: module/action, request, resolved configuration, status,
  normalized progress from 0 through 1, relative `log_path`, command/log state,
  provenance, input sources, and artifacts.
- `RadioArtifact`: semantic type, relative path, MIME type, source run,
  previewability, and downloadability.
- `RadioFigureDraft`, `RadioFigureLayer`, `RadioFigureTimeline`, and
  `RadioFigureTemporalBinding`: versioned canvas, controlled source, transform,
  crop, and UTC time definitions.
- `RadioFigurePreflight` and `RadioFigureExport`: source-bound preflight
  revision, coverage decisions, and immutable exported media metadata.

Only paths inside the current effective roots may be browsed or passed to an
action. Effective roots combine the editable user roots with protected default
output and saved-workspace output roots; protected roots remain available when
the editable list changes. Resolved paths and symlinks are checked before
access, artifacts must stay inside their own run directory, and HTML artifact
responses use a sandbox policy. Advanced RR/LL and CSO compatibility actions
use explicit allowed-root-validated inputs; they do not fall back to event paths
from an ignored local configuration.

## HTTP API

The versioned local API is mounted under `/api/radio`:

| Area | Routes |
| --- | --- |
| Health and local assets | `GET /health`, `GET /assets/plotly.js`, `GET /assets/<approved-name>` |
| Catalog and presets | `GET /modules`, `GET /presets` |
| Workspaces | `GET/POST /workspaces`, `GET/PATCH/DELETE /workspaces/<id>`, `PATCH /workspaces/<id>/layout` |
| File access roots | `GET /allowed-roots`, `PUT /allowed-roots` |
| Allowed-root browser | `GET /files?path=...` |
| Preview | `POST /workspaces/<id>/modules/<module>/actions/<action>/preview` |
| Runs | `GET/POST /workspaces/<id>/runs`, `POST /workspaces/<id>/runs/batch`, `GET /workspaces/<id>/runs/<run>[/status]`, `GET .../log`, `POST .../cancel` |
| Artifacts | `GET /workspaces/<id>/artifacts`, `GET /workspaces/<id>/runs/<run>/artifacts`, `GET .../artifacts/<artifact>` |
| Figure Studio | `GET/PUT /workspaces/<id>/figures/draft`, `POST .../figures/snapshots`, `POST .../figures/preflight`, `GET/POST .../figures/exports`, controlled preview-source and export preview/download/delete subresources |

Batch execution rejects requests without `confirmed: true` and validates all
selected actions before queueing any of them.

`PUT /allowed-roots` and Figure Studio persistence/upload/delete routes are
restricted to loopback requests and require the per-start token returned to the
local frontend in the `X-Radio-Root-Token` header. Root updates replace only the
editable user-root list for the current server session; protected output and
workspace roots are retained.

## Code Boundaries

The integrated path follows four layers:

1. **Domain computation** — canonical Gaussian, coordinate, matching,
   spectrogram, drift, Newkirk, ROI, and trajectory implementations under
   `solar_toolkit.radio`, `solar_toolkit.map`, `solar_toolkit.modeling`, and
   `solar_toolkit.visualization`.
2. **Module services and action adapters** — fused catalog and native previews
   under `solar_toolkit.webapp.radio_workspace`, plus
   `roi_selection_cli.py`, `drift_selection_cli.py`, and
   `trajectory_media_cli.py`, and `existing_fit_overlay_cli.py` for structured
   independent actions.
3. **Workflow orchestration** — `RadioRunManager` resolves only selected
   actions, configuration, queueing, cancellation, progress, and artifact
   passing. It contains no duplicate science algorithms.
4. **Presentation and compatibility** — `/radio`, the unified Flask server,
   local Plotly/Mediabunny assets, installed `solar-radio` commands, old
   Streamlit launchers, and `scripts.radio.*` aliases.

New package code must not import `scripts`. `source_map_workflow`,
`overlay_workflow`, `pipeline_workflow`, and `cso_workflow` retain their public
names and compatibility anchors while delegating reusable calculations to the
canonical package modules.

## Compatibility Entrypoints

The workspace is the recommended integrated browser entry, but it does not
remove the existing command surfaces:

- `solar-radio centers`, `pipeline`, `source-map`, `overlay`, `quicklook`,
  `raw-quality`, `roi-lightcurve`, and `trajectory` remain installed.
- `scripts/radio/run_radio_burst_pipeline.py`, source-map, center, overlay, ROI,
  trajectory, and legacy scripts remain thin compatibility entrypoints.
- The ROI and trajectory Streamlit applications continue to call the same
  package-owned services for 0.x compatibility.
- `scripts.radio.core.*`, old configuration modules, and maintained legacy
  workflow paths remain true module aliases or forwarding facades rather than
  copied scientific implementations.

The workspace's per-action provenance and tests establish execution structure;
they do not by themselves claim byte-for-byte parity for every real-data
artifact. See `docs/validation/astropy_sunpy_reorg_parity.md` for the existing
real-data validation boundary.
