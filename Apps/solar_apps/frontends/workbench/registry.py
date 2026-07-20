"""Import-resolvable workflow registry for the Solar Physics Workbench."""

from __future__ import annotations

import importlib
import shlex
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runner import JobContext

__all__ = [
    "ArchivedReference",
    "FeatureModule",
    "WorkflowRegistry",
    "default_registry",
    "split_cli_arguments",
]

COMMON_INPUT_SCHEMA = [
    {
        "name": "arguments",
        "label": "CLI arguments",
        "type": "textarea",
        "placeholder": "--help",
        "help": "Additional command-line arguments passed as separate tokens.",
    },
    {
        "name": "paths",
        "label": "Local paths",
        "type": "textarea",
        "placeholder": "<allowed-root>/data",
        "help": "One path per line. Every path must stay inside an allowed root.",
    },
]


@dataclass(frozen=True)
class FeatureModule:
    """One active workflow addressed only by a stable importable module."""

    id: str
    title: str
    category: str
    description: str
    command_module: str
    status: str = "utility"
    risk_level: str = "standard"
    input_schema: list[dict[str, Any]] = field(default_factory=list)
    launch_mode: str = "job"

    def build_command(
        self,
        payload: dict[str, Any] | None,
        *,
        context: JobContext,
    ) -> list[str]:
        from .runner import normalize_arguments, validate_payload_paths

        payload = payload or {}
        validate_payload_paths(payload, context=context)
        return [
            str(context.python_executable),
            "-m",
            self.command_module,
            *normalize_arguments(payload.get("arguments", "")),
        ]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "workflow_id": self.id,
            "command_module": self.command_module,
            "status": self.status,
            "risk_level": self.risk_level,
            "launch_mode": self.launch_mode,
            "input_schema": self.input_schema,
            "available": True,
            "unavailable_reason": None,
        }


@dataclass(frozen=True)
class ArchivedReference:
    """A visible but deliberately non-executable historical recipe."""

    id: str
    title: str
    description: str
    reason: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "reason": self.reason,
            "read_only": True,
        }


@dataclass
class WorkflowRegistry:
    modules: dict[str, FeatureModule]
    archived_references: list[ArchivedReference] = field(default_factory=list)

    def get(self, module_id: str) -> FeatureModule:
        try:
            return self.modules[module_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workflow module: {module_id}") from exc

    def runnable_modules(self) -> list[FeatureModule]:
        return sorted(
            self.modules.values(),
            key=lambda item: (item.category.casefold(), item.title.casefold()),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "modules": [item.to_public_dict() for item in self.runnable_modules()],
            "archived_references": [
                item.to_public_dict() for item in self.archived_references
            ],
        }


def _spec(
    id: str,
    title: str,
    category: str,
    command_module: str,
    description: str,
    *,
    status: str = "utility",
    risk_level: str = "standard",
    launch_mode: str = "job",
) -> dict[str, str]:
    return locals()


MODULE_SPECS = (
    _spec(
        "aia-euv-processor",
        "AIA EUV Processor",
        "AIA and HMI",
        "solar_apps.workflows.aia.application",
        "Process AIA EUV images, mosaics, and differences.",
        status="main",
    ),
    _spec(
        "aia-jsoc-download",
        "AIA JSOC Download",
        "Data Download",
        "solar_apps.workflows.net.jsoc_cli",
        "Query and download selected JSOC data.",
        risk_level="advanced",
    ),
    _spec(
        "aia-hmi-fits-rename",
        "AIA/HMI FITS Rename",
        "AIA and HMI",
        "solar_apps.workflows.hmi.fits_rename_cli",
        "Normalize AIA and HMI FITS filenames.",
    ),
    _spec(
        "aia-lightcurve-extraction",
        "AIA Light Curve Extraction",
        "AIA and HMI",
        "solar_apps.workflows.aia.lightcurve_extraction",
        "Extract AIA light-curve tables.",
    ),
    _spec(
        "aia-lightcurve-plot",
        "AIA Light Curve Plot",
        "AIA and HMI",
        "solar_apps.workflows.aia.lightcurve_plot",
        "Plot AIA light-curve products.",
    ),
    _spec(
        "aia-hmi-overlay",
        "AIA/HMI Overlay",
        "AIA and HMI",
        "solar_apps.workflows.hmi.overlay_cli",
        "Overlay HMI contours on AIA context images.",
    ),
    _spec(
        "stereo-euvi-manifest",
        "STEREO-A EUVI Manifest",
        "STEREO and SUVI",
        "solar_apps.workflows.data.stereo_manifest_cli",
        "Build a wavelength manifest for EUVI observations.",
    ),
    _spec(
        "stereo-euvi-overview",
        "STEREO-A EUVI Overview",
        "STEREO and SUVI",
        "solar_apps.workflows.visualization.stereo_euvi_overview",
        "Plot EUVI context images.",
    ),
    _spec(
        "stereo-euvi-roi-movie",
        "STEREO-A EUVI ROI Movie",
        "STEREO and SUVI",
        "solar_apps.workflows.visualization.stereo_euvi_roi_movie",
        "Generate EUVI ROI sequences and movies.",
    ),
    _spec(
        "goes-suvi-quadrant",
        "GOES SUVI Quadrant Plot",
        "STEREO and SUVI",
        "solar_apps.workflows.visualization.suvi_quadrant",
        "Plot GOES SUVI quadrant context products.",
    ),
    _spec(
        "image-sequence-video",
        "Image Sequence to Video",
        "Tools and Media",
        "solar_apps.workflows.visualization.video_cli",
        "Convert an ordered image sequence to video.",
    ),
    _spec(
        "image-sequence-viewer",
        "Image Sequence Viewer",
        "Tools and Media",
        "solar_apps.frontends.image_viewer.cli",
        "Launch the image sequence viewer.",
        launch_mode="interactive",
    ),
    _spec(
        "radio-burst-pipeline",
        "Radio Burst Pipeline",
        "Radio Analysis",
        "solar_apps.workflows.radio.pipeline_cli",
        "Run source-map and radio diagnostics.",
        status="main",
    ),
    _spec(
        "radio-source-map",
        "Radio Source Map",
        "Radio Analysis",
        "solar_apps.workflows.radio.source_map_cli",
        "Create radio source maps with Gaussian overlays.",
        status="main",
    ),
    _spec(
        "radio-center-extraction",
        "Radio Center Extraction",
        "Radio Analysis",
        "solar_apps.workflows.radio.centers_application",
        "Extract radio-source centers.",
        status="main",
    ),
    _spec(
        "radio-source-trajectory-app",
        "Radio Source Trajectory App",
        "Radio Analysis",
        "solar_apps.frontends.radio.source_trajectory.source_app_launcher",
        "Launch trajectory playback.",
        status="main",
        launch_mode="interactive",
    ),
    _spec(
        "radio-roi-lightcurve-app",
        "Radio ROI Light Curve App",
        "Radio Analysis",
        "solar_apps.frontends.radio.roi_lightcurve.roi_lightcurve_launcher",
        "Launch ROI light-curve analysis.",
        status="main",
        launch_mode="interactive",
    ),
    _spec(
        "radio-dart-spectrogram-app",
        "DART Spectrogram App",
        "Radio Analysis",
        "solar_apps.frontends.radio.dart_spectrogram.dart_spectrogram_launcher",
        "Launch DART spectrogram analysis.",
        status="main",
        launch_mode="interactive",
    ),
    _spec(
        "radio-composite-figure-app",
        "Radio Composite Figure App",
        "Radio Analysis",
        "solar_apps.frontends.radio.composite_figure.composite_figure_launcher",
        "Launch the Source Map, ROI curve, and DART narrowband composite workflow.",
        status="main",
        launch_mode="interactive",
    ),
    _spec(
        "rrll-percentile-preview",
        "RR/LL Percentile Preview",
        "Radio Analysis",
        "solar_apps.workflows.radio.rrll_percentile_preview_comparison",
        "Compare fixed RR/LL display ranges.",
    ),
    _spec(
        "radio-trajectory-export",
        "Radio Trajectory HTML Export",
        "Radio Analysis",
        "solar_apps.workflows.radio.trajectory_cli",
        "Export radio-source trajectory HTML.",
    ),
    _spec(
        "radio-trajectory-media",
        "Radio Trajectory Media Export",
        "Radio Analysis",
        "solar_apps.workflows.radio.trajectory_media_cli",
        "Export radio-source trajectory media.",
    ),
    _spec(
        "aia-radio-hmi-overlay",
        "AIA/Radio/HMI Overlay",
        "Radio Analysis",
        "solar_apps.workflows.radio.overlay_cli",
        "Overlay radio and HMI contours on AIA.",
    ),
    _spec(
        "radio-existing-fit-overlay",
        "Existing Fit Overlay",
        "Radio Analysis",
        "solar_apps.workflows.radio.existing_fit_overlay_cli",
        "Overlay existing source fits.",
    ),
    _spec(
        "radio-raw-quality",
        "Radio Raw Quality Diagnostics",
        "Radio Analysis",
        "solar_apps.workflows.radio.raw_quality_cli",
        "Inspect raw radio FITS quality.",
    ),
    _spec(
        "radio-roi-selection",
        "Radio ROI Selection",
        "Radio Analysis",
        "solar_apps.workflows.radio.roi_selection_cli",
        "Prepare radio ROI selections.",
    ),
    _spec(
        "radio-physical-diagnostics",
        "Radio Physical Diagnostics",
        "Radio Analysis",
        "solar_apps.workflows.radio.physical_diagnostics_cli",
        "Run physical radio diagnostics.",
    ),
    _spec(
        "radio-quicklook",
        "Radio Quicklook",
        "Radio Analysis",
        "solar_apps.workflows.radio.quicklook",
        "Generate radio quicklooks.",
    ),
    _spec(
        "cso-spectrogram",
        "CSO Dynamic Spectra",
        "Radio Analysis",
        "solar_apps.workflows.radio.cso_workflow",
        "Run the maintained CSO spectrogram workflow.",
    ),
    _spec(
        "hessi-hxr-lightcurve",
        "HXR Light Curve",
        "X-ray and DEM",
        "solar_apps.workflows.xray_dem.hxi_lightcurve",
        "Plot HXR light curves.",
    ),
    _spec(
        "asos-hxi-image",
        "ASO-S/HXI Image",
        "X-ray and DEM",
        "solar_apps.workflows.xray_dem.hxi_image",
        "Plot HXI image maps.",
    ),
    _spec(
        "asos-hxi-goes-comparison",
        "ASO-S/HXI and GOES",
        "X-ray and DEM",
        "solar_apps.workflows.xray_dem.hxi_sxr_comparison",
        "Compare HXI and GOES evolution.",
    ),
    _spec(
        "aia-asos-hxi-overlay",
        "AIA and ASO-S/HXI Overlay",
        "X-ray and DEM",
        "solar_apps.workflows.xray_dem.aia_hxi_overlay",
        "Overlay HXI contours on AIA.",
    ),
    _spec(
        "aia-dem-inversion",
        "AIA DEM Inversion",
        "X-ray and DEM",
        "solar_apps.workflows.xray_dem.aia_dem_inversion",
        "Visualize DEM products.",
    ),
    _spec(
        "dem-radio-overlay",
        "DEM and Radio Source Overlay",
        "X-ray and DEM",
        "solar_apps.workflows.xray_dem.dem_radio_source_overlay",
        "Compare DEM and radio morphology.",
    ),
)

ARCHIVED_SPECS = (
    ArchivedReference(
        "historical-aia-difference",
        "Historical AIA Difference Recipes",
        "Earlier base/running-difference scripts.",
        "Historical source is intentionally excluded from the Apps package.",
    ),
    ArchivedReference(
        "historical-download-recipes",
        "Historical Download Recipes",
        "Event-specific LASCO, SUVI, STEREO, and SOAR scripts.",
        "Replace with maintained workflow modules before activation.",
    ),
    ArchivedReference(
        "historical-examples",
        "Historical Standalone Examples",
        "Direct source-tree example scripts.",
        "Examples are read-only references and are not subprocess targets.",
    ),
)


def default_registry(_repo_root: object = None) -> WorkflowRegistry:
    """Build a registry whose active entries are all import-resolvable."""

    modules: dict[str, FeatureModule] = {}
    archived = list(ARCHIVED_SPECS)
    for spec in MODULE_SPECS:
        command_module = spec["command_module"]
        try:
            imported = importlib.import_module(command_module)
        except Exception as exc:  # unavailable optional dependency stays archived
            archived.append(
                ArchivedReference(
                    spec["id"],
                    spec["title"],
                    spec["description"],
                    f"Installed module {command_module!r} is unavailable: "
                    f"{type(exc).__name__}.",
                )
            )
            continue
        if not callable(getattr(imported, "main", None)):
            archived.append(
                ArchivedReference(
                    spec["id"],
                    spec["title"],
                    spec["description"],
                    f"Installed module {command_module!r} has no callable main.",
                )
            )
            continue
        modules[spec["id"]] = FeatureModule(
            id=spec["id"],
            title=spec["title"],
            category=spec["category"],
            description=spec["description"],
            command_module=command_module,
            status=spec["status"],
            risk_level=spec["risk_level"],
            launch_mode=spec["launch_mode"],
            input_schema=[dict(item) for item in COMMON_INPUT_SCHEMA],
        )
    return WorkflowRegistry(modules, archived)


def split_cli_arguments(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return shlex.split(raw, posix=False)
    return [str(item) for item in raw if str(item).strip()]
