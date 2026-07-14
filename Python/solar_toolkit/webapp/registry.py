"""Workflow registry for the local web workbench."""

from __future__ import annotations

import importlib.util
import shlex
from dataclasses import dataclass, field
from pathlib import Path
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
        "placeholder": "D:/path/to/local/data",
        "help": "One path per line. Each path must stay inside an allowed root.",
    },
]


@dataclass(frozen=True)
class FeatureModule:
    """A registered workflow that can be launched by the local web app."""

    id: str
    title: str
    category: str
    description: str
    script_path: Path
    status: str
    risk_level: str
    input_schema: list[dict[str, Any]] = field(default_factory=list)
    launch_mode: str = "job"
    command_path: Path | None = None
    command_module: str | None = None
    available: bool = True
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.command_path is None:
            object.__setattr__(self, "command_path", self.script_path)

    def build_command(
        self,
        payload: dict[str, Any] | None,
        *,
        context: JobContext,
    ) -> list[str]:
        """Build a subprocess argument list after validating local paths."""

        from .runner import normalize_arguments, validate_payload_paths

        if not self.available:
            reason = self.unavailable_reason or "workflow command is unavailable"
            raise RuntimeError(f"Workflow {self.id!r} is unavailable: {reason}")
        payload = payload or {}
        validate_payload_paths(payload, context=context)
        args = normalize_arguments(payload.get("arguments", ""))
        if self.command_module:
            return [
                str(context.python_executable),
                "-m",
                self.command_module,
                *args,
            ]
        script = (context.repo_root / self.command_path).resolve()
        return [
            str(context.python_executable),
            script.as_posix(),
            *args,
        ]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "script_path": self.script_path.as_posix(),
            "command_path": self.command_path.as_posix(),
            "command_module": self.command_module,
            "status": self.status,
            "risk_level": self.risk_level,
            "launch_mode": self.launch_mode,
            "input_schema": self.input_schema,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True)
class ArchivedReference:
    """A read-only script reference kept visible but not runnable."""

    title: str
    path: Path
    description: str
    read_only: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "path": self.path.as_posix(),
            "description": self.description,
            "read_only": self.read_only,
        }


@dataclass
class WorkflowRegistry:
    """Container for runnable modules and read-only legacy references."""

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
            "modules": [module.to_public_dict() for module in self.runnable_modules()],
            "archived_references": [
                reference.to_public_dict() for reference in self.archived_references
            ],
        }


def default_registry(repo_root: str | Path | None = None) -> WorkflowRegistry:
    """Return the built-in workflow registry."""

    resolved_root = (
        Path(repo_root).resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[2]
    )
    modules = {}
    for spec in MODULE_SPECS:
        command_module = spec.get("command_module")
        command_path = Path(spec.get("command_path", spec["script_path"]))
        available = (
            importlib.util.find_spec(command_module) is not None
            if command_module
            else (resolved_root / command_path).is_file()
        )
        modules[spec["id"]] = FeatureModule(
            id=spec["id"],
            title=spec["title"],
            category=spec["category"],
            description=spec["description"],
            script_path=Path(spec["script_path"]),
            command_path=command_path,
            command_module=command_module,
            status=spec["status"],
            risk_level=spec["risk_level"],
            launch_mode=spec.get("launch_mode", "job"),
            input_schema=[dict(item) for item in COMMON_INPUT_SCHEMA],
            available=available,
            unavailable_reason=(
                None
                if available
                else (
                    f"Installed workflow module {command_module!r} is unavailable."
                    if command_module
                    else "This source-repository recipe is not included in the installed package."
                )
            ),
        )
    return WorkflowRegistry(
        modules=modules,
        archived_references=[
            ArchivedReference(
                title="Historical AIA Base Difference",
                path=Path("legacy/scripts/aia_hmi/sdo_aia_base_difference.py"),
                description="Archived historical base-difference workflow.",
            ),
            ArchivedReference(
                title="Historical AIA Running Difference",
                path=Path("legacy/scripts/aia_hmi/sdo_aia_running_difference.py"),
                description="Archived historical running-difference workflow.",
            ),
        ],
    )


def split_cli_arguments(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Split CLI arguments for tests and callers that need registry-only parsing."""

    if raw is None:
        return []
    if isinstance(raw, str):
        return shlex.split(raw, posix=False)
    return [str(item) for item in raw if str(item).strip()]


MODULE_SPECS = [
    {
        "id": "aia-euv-processor",
        "title": "AIA EUV Processor",
        "category": "AIA and HMI",
        "status": "main",
        "risk_level": "standard",
        "script_path": "scripts/aia_hmi/run_aia_euv_processor.py",
        "command_module": "solar_toolkit.aia.cli",
        "description": "Main SDO/AIA EUV image, mosaic, and difference workflow.",
    },
    {
        "id": "aia-jsoc-download",
        "title": "AIA JSOC Download",
        "category": "Data Download",
        "status": "main",
        "risk_level": "advanced",
        "script_path": "scripts/aia_hmi/sdo_aia_jsoc_download_20250124.py",
        "command_module": "solar_toolkit.net.jsoc",
        "description": "Download selected SDO/AIA JSOC level-1 FITS files.",
    },
    {
        "id": "stereo-euvi-download",
        "title": "STEREO-A EUVI Download",
        "category": "Data Download",
        "status": "main",
        "risk_level": "advanced",
        "script_path": "scripts/data_download/stereo_a_euvi_download_20250124.py",
        "description": "Download STEREO-A SECCHI/EUVI files for the event window.",
    },
    {
        "id": "goes-suvi-download",
        "title": "GOES SUVI Download",
        "category": "Data Download",
        "status": "main",
        "risk_level": "advanced",
        "script_path": "scripts/data_download/goes_suvi_download_20250124.py",
        "description": "Download GOES-16/18 SUVI L2 composite FITS files.",
    },
    {
        "id": "aia-hmi-fits-rename",
        "title": "AIA/HMI FITS Rename",
        "category": "AIA and HMI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/aia_hmi/sdo_aia_hmi_fits_rename.py",
        "description": "Normalize SDO/AIA and SDO/HMI FITS filenames.",
    },
    {
        "id": "aia-lightcurve-extraction",
        "title": "AIA Light Curve Extraction",
        "category": "AIA and HMI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/aia_hmi/sdo_aia_lightcurve_extraction.py",
        "command_module": "solar_toolkit.aia.lightcurve_extraction",
        "description": "Extract AIA light-curve tables from local FITS sequences.",
    },
    {
        "id": "aia-lightcurve-plot",
        "title": "AIA Light Curve Plot",
        "category": "AIA and HMI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/aia_hmi/sdo_aia_lightcurve_plot.py",
        "command_module": "solar_toolkit.aia.lightcurve_plot",
        "description": "Plot one or more AIA light-curve CSV products.",
    },
    {
        "id": "hmi-magnetogram-plot",
        "title": "HMI Magnetogram Plot",
        "category": "AIA and HMI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/aia_hmi/sdo_hmi_magnetogram_plot.py",
        "description": "Plot SDO/HMI magnetograms in a selected ROI.",
    },
    {
        "id": "solo-eui-soar-query",
        "title": "Solar Orbiter EUI SOAR Query",
        "category": "Data Download",
        "status": "utility",
        "risk_level": "advanced",
        "script_path": "scripts/data_download/solo_eui_soar_query_download.py",
        "description": "Query SOAR metadata and optionally download EUI files.",
    },
    {
        "id": "stereo-euvi-manifest",
        "title": "STEREO-A EUVI Manifest",
        "category": "STEREO and SUVI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/stereo_suvi/stereo_euvi_manifest_by_wavelength.py",
        "command_module": "solar_toolkit.data.stereo_manifest",
        "description": "Build a wavelength manifest for STEREO-A/EUVI data.",
    },
    {
        "id": "stereo-euvi-overview",
        "title": "STEREO-A EUVI Overview",
        "category": "STEREO and SUVI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/stereo_suvi/stereo_euvi_0448_overview_plot.py",
        "command_module": "solar_toolkit.visualization.stereo_euvi_overview",
        "description": "Plot STEREO-A/EUVI context images near 04:48 UT.",
    },
    {
        "id": "stereo-euvi-roi-movie",
        "title": "STEREO-A EUVI ROI Movie",
        "category": "STEREO and SUVI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/stereo_suvi/stereo_euvi_roi_movie.py",
        "command_module": "solar_toolkit.visualization.stereo_euvi_roi_movie",
        "description": "Generate fixed-ROI EUVI frame sequences and movies.",
    },
    {
        "id": "goes-suvi-quadrant",
        "title": "GOES SUVI Quadrant Plot",
        "category": "STEREO and SUVI",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/stereo_suvi/goes_suvi_0448_quadrant_plot.py",
        "command_module": "solar_toolkit.visualization.suvi_quadrant",
        "description": "Plot GOES SUVI lower-right quadrant context products.",
    },
    {
        "id": "image-sequence-video",
        "title": "Image Sequence to Video",
        "category": "Tools and Media",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/tools/image_sequence_to_video.py",
        "command_module": "solar_toolkit.visualization.video_cli",
        "description": "Convert an ordered image sequence to MP4.",
    },
    {
        "id": "image-sequence-viewer",
        "title": "Image Sequence Viewer",
        "category": "Tools and Media",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/tools/run_image_web_viewer.py",
        "command_module": "solar_toolkit.visualization.image_web_viewer.cli",
        "description": "Launch the local multi-folder image sequence viewer.",
    },
    {
        "id": "solar-workbench",
        "title": "Solar Physics Workbench",
        "category": "Tools and Media",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/tools/run_solar_webapp.py",
        "command_module": "solar_toolkit.webapp.cli",
        "description": "Launch the unified local English web GUI.",
    },
    {
        "id": "lasco-data-download",
        "title": "LASCO Data Download",
        "category": "LASCO and CME",
        "status": "utility",
        "risk_level": "advanced",
        "script_path": "scripts/lasco_cme/soho_lasco_data_download.py",
        "description": "Download SOHO/LASCO C2 JP2 files through Helioviewer.",
    },
    {
        "id": "lasco-image-plot",
        "title": "LASCO Image Plot",
        "category": "LASCO and CME",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/lasco_cme/soho_lasco_image_plot.py",
        "description": "Plot basic SOHO/LASCO images.",
    },
    {
        "id": "lasco-running-difference",
        "title": "LASCO Running Difference",
        "category": "LASCO and CME",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/lasco_cme/soho_lasco_running_difference.py",
        "description": "Generate LASCO running-difference CME images.",
    },
    {
        "id": "radio-burst-pipeline",
        "title": "Radio Burst Pipeline",
        "category": "Radio Analysis",
        "status": "main",
        "risk_level": "standard",
        "script_path": "scripts/radio/run_radio_burst_pipeline.py",
        "command_module": "solar_toolkit.radio.pipeline_cli",
        "description": "Run source maps, Gaussian diagnostics, drift, and height products.",
    },
    {
        "id": "radio-source-map",
        "title": "Radio Source Map",
        "category": "Radio Analysis",
        "status": "main",
        "risk_level": "standard",
        "script_path": "scripts/radio/run_radio_source_map.py",
        "command_module": "solar_toolkit.radio.source_map_cli",
        "description": "Create quick radio source maps with Gaussian overlays.",
    },
    {
        "id": "radio-center-extraction",
        "title": "Radio Center Extraction",
        "category": "Radio Analysis",
        "status": "main",
        "risk_level": "standard",
        "script_path": "scripts/radio/extract_radio_centers.py",
        "command_module": "solar_toolkit.radio.centers",
        "description": "Extract threshold or contour radio-source centers.",
    },
    {
        "id": "radio-source-trajectory-app",
        "title": "Radio Source Trajectory App",
        "category": "Radio Analysis",
        "status": "main",
        "risk_level": "standard",
        "script_path": "scripts/radio/run_radio_source_app.py",
        "command_path": "scripts/radio/run_radio_source_app_managed.py",
        "command_module": "solar_toolkit.radio.source_app_launcher",
        "launch_mode": "interactive",
        "description": "Launch the managed Streamlit trajectory playback app.",
    },
    {
        "id": "radio-roi-lightcurve-app",
        "title": "Radio ROI Light Curve App",
        "category": "Radio Analysis",
        "status": "main",
        "risk_level": "standard",
        "script_path": "scripts/radio/run_radio_roi_lightcurve_app.py",
        "command_module": "solar_toolkit.radio.roi_lightcurve_launcher",
        "launch_mode": "interactive",
        "description": "Launch the managed Streamlit app for user-selected radio FITS ROI light curves.",
    },
    {
        "id": "rrll-percentile-preview-comparison",
        "title": "RR/LL Percentile Preview Comparison",
        "category": "Radio Analysis",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/radio/run_rrll_percentile_preview_comparison.py",
        "command_module": "solar_toolkit.radio.rrll_percentile_preview_comparison",
        "description": "Compare fixed per-band percentile ranges for RR/LL source-map previews.",
    },
    {
        "id": "radio-trajectory-html-export",
        "title": "Radio Trajectory HTML Export",
        "category": "Radio Analysis",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/radio/export_radio_source_trajectory.py",
        "command_module": "solar_toolkit.radio.trajectory_cli",
        "description": "Export a selected radio-source trajectory frame to HTML.",
    },
    {
        "id": "aia-radio-hmi-overlay",
        "title": "AIA/Radio/HMI Overlay",
        "category": "Radio Analysis",
        "status": "main",
        "risk_level": "standard",
        "script_path": "scripts/radio/run_aia_radio_hmi_overlay.py",
        "command_module": "solar_toolkit.radio.overlay_cli",
        "description": "Overlay radio and optional HMI contours on AIA context images.",
    },
    {
        "id": "cso-spectrogram-legacy",
        "title": "CSO Dynamic Spectra Legacy Workflow",
        "category": "Advanced",
        "status": "main",
        "risk_level": "advanced",
        "script_path": "scripts/radio/legacy/cso_radio_spectrogram_plot.py",
        "command_module": "solar_toolkit.radio.cso_workflow",
        "description": "Compatibility CSO dynamic spectra workflow.",
    },
    {
        "id": "radio-raw-quality",
        "title": "Radio Raw Quality Diagnostics",
        "category": "Radio Analysis",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/radio/run_radio_raw_quality.py",
        "command_module": "solar_toolkit.radio.raw_quality_cli",
        "description": "Run raw radio FITS artifact and quality diagnostics.",
    },
    {
        "id": "aia-time-distance",
        "title": "AIA Time-Distance Diagram",
        "category": "Advanced",
        "status": "deprecated",
        "risk_level": "deprecated",
        "script_path": "scripts/aia_hmi/sdo_aia_time_distance_diagram.py",
        "description": "Deprecated demonstration of AIA time-distance analysis.",
    },
    {
        "id": "aia-hmi-overlay-deprecated",
        "title": "AIA/HMI Overlay",
        "category": "Advanced",
        "status": "deprecated",
        "risk_level": "deprecated",
        "script_path": "scripts/aia_hmi/sdo_aia_hmi_overlay.py",
        "command_module": "solar_toolkit.hmi.overlay_cli",
        "description": "Deprecated AIA/HMI magnetic contour overlay workflow.",
    },
    {
        "id": "aia-euv-processor-compat",
        "title": "AIA EUV Processor Compatibility Entry",
        "category": "Advanced",
        "status": "deprecated",
        "risk_level": "deprecated",
        "script_path": "scripts/aia_hmi/sdo_aia_euv_processor.py",
        "description": "Historical compatibility entrypoint for the AIA processor.",
    },
    {
        "id": "goes-sxr-lightcurve",
        "title": "GOES SXR Light Curve",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/goes_sxr_lightcurve_plot.py",
        "command_module": "solar_toolkit.xray_dem._goes_lightcurve",
        "description": "Plot GOES soft X-ray light curves.",
    },
    {
        "id": "hessi-hxr-lightcurve",
        "title": "HESSI HXR Light Curve",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/hessi_hxr_lightcurve_plot.py",
        "command_module": "solar_toolkit.xray_dem.hxi_lightcurve",
        "description": "Plot HXR light curves from FITS event files.",
    },
    {
        "id": "asos-hxi-image",
        "title": "ASO-S/HXI Image Plot",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/asos_hxi_image_plot.py",
        "command_module": "solar_toolkit.xray_dem.hxi_image",
        "description": "Plot ASO-S/HXI hard X-ray image maps.",
    },
    {
        "id": "asos-hxi-goes-comparison",
        "title": "ASO-S/HXI and GOES Comparison",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/asos_hxi_goes_sxr_comparison.py",
        "command_module": "solar_toolkit.xray_dem.hxi_sxr_comparison",
        "description": "Compare HXI count-rate evolution with GOES SXR context.",
    },
    {
        "id": "aia-asos-hxi-overlay",
        "title": "AIA and ASO-S/HXI Overlay",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/sdo_aia_asos_hxi_overlay.py",
        "command_module": "solar_toolkit.xray_dem.aia_hxi_overlay",
        "description": "Overlay ASO-S/HXI contours on SDO/AIA images.",
    },
    {
        "id": "flare-aia-sxr-hxr-summary",
        "title": "Flare AIA/SXR/HXR Summary",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/flare_aia_sxr_hxr_summary_plot.py",
        "command_module": "solar_toolkit.xray_dem._flare_summary",
        "description": "Build a three-panel flare diagnostic summary figure.",
    },
    {
        "id": "neupert-sxr-hxr-comparison",
        "title": "Neupert SXR/HXR Comparison",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/neupert_sxr_derivative_hxr_comparison.py",
        "command_module": "solar_toolkit.xray_dem._neupert_comparison",
        "description": "Compare smoothed SXR derivatives with HXR-style timing.",
    },
    {
        "id": "neupert-timing-error",
        "title": "Neupert Timing Error Analysis",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/neupert_timing_error_analysis.py",
        "command_module": "solar_toolkit.xray_dem._neupert_timing",
        "description": "Explore smoothing, timing, and derivative behavior.",
    },
    {
        "id": "aia-dem-inversion",
        "title": "AIA DEM Inversion",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/sdo_aia_dem_inversion.py",
        "command_module": "solar_toolkit.xray_dem.aia_dem_inversion",
        "description": "Visualize DEM and brightness-temperature products.",
    },
    {
        "id": "dem-radio-overlay",
        "title": "DEM and Radio Source Overlay",
        "category": "X-ray and DEM",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "scripts/xray_dem/dem_radio_source_overlay.py",
        "command_module": "solar_toolkit.xray_dem.dem_radio_source_overlay",
        "description": "Compare DEM/Tb structure with radio source morphology.",
    },
    {
        "id": "example-time-matching",
        "title": "Example: Time Matching",
        "category": "Examples",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "examples/public_api/time_matching_example.py",
        "description": "Match sample observation filenames by timestamp.",
    },
    {
        "id": "example-gaussian-model",
        "title": "Example: Gaussian Model",
        "category": "Examples",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "examples/public_api/gaussian_model_example.py",
        "description": "Evaluate the public Gaussian model without observation data.",
    },
    {
        "id": "example-solar-limb-contour",
        "title": "Example: Solar Limb Contour",
        "category": "Examples",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "examples/aia_hmi/solar_limb_contour_example.py",
        "description": "Run the small AIA/HMI-style solar limb contour example.",
    },
    {
        "id": "example-fits-header-metadata",
        "title": "Example: FITS Header Metadata",
        "category": "Examples",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "examples/radio/fits_header_metadata_example.py",
        "description": "Inspect FITS header metadata with the example script.",
    },
    {
        "id": "example-gaussian-newkirk-quicklook",
        "title": "Example: Gaussian Newkirk Quicklook",
        "category": "Examples",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "examples/gaussian_newkirk_quicklook/quicklook_gaussian_newkirk.py",
        "description": "Generate Gaussian and Newkirk quicklooks from local diagnostics.",
    },
    {
        "id": "example-aia-radio-hmi-overlay",
        "title": "Example: AIA Radio HMI Overlay",
        "category": "Examples",
        "status": "utility",
        "risk_level": "standard",
        "script_path": "examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py",
        "description": "Run the AIA, radio, and HMI overlay demonstration.",
    },
]
