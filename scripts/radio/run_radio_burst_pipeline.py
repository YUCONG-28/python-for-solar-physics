"""Gaussian + spectrogram + drift-rate + Newkirk extrapolation pipeline."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ in {None, ""}:  # direct ``python scripts/radio/...`` execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if __package__ in {None, ""}:
    from scripts.radio.configs import (
        DEFAULT_CONFIG_NAME,
        load_aia_radio_hmi_user_config,
        load_drift_selection_product_config,
        load_newkirk_height_comparison_config,
        load_newkirk_spatial_config,
        load_radio_diagnostic_presentation_config,
        load_radio_user_config,
    )
else:
    from .configs import (
        DEFAULT_CONFIG_NAME,
        load_aia_radio_hmi_user_config,
        load_drift_selection_product_config,
        load_newkirk_height_comparison_config,
        load_newkirk_spatial_config,
        load_radio_diagnostic_presentation_config,
        load_radio_user_config,
    )


DEFAULT_NEWKIRK_CONFIG = {
    "enabled": True,
    "multipliers": [1, 2, 4],
    "harmonics": [1, 2],
    "solar_radius_arcsec": 959.63,
    "los_sign": 1,
}


def _parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--config", default=DEFAULT_CONFIG_NAME)
    args, _unknown = parser.parse_known_args()
    return args


def main(config_name: str | None = None):
    from scripts.radio.legacy import radio_source_map_plot_gaussian_overlay as legacy

    args = _parse_args() if config_name is None else None
    selected_config = config_name or args.config
    user_config, newkirk_cfg = load_radio_user_config(selected_config)
    _aia_config = load_aia_radio_hmi_user_config(selected_config)
    newkirk_height_cfg = load_newkirk_height_comparison_config(selected_config)
    newkirk_spatial_cfg = load_newkirk_spatial_config(selected_config)
    drift_product_cfg = load_drift_selection_product_config(selected_config)
    presentation_cfg = load_radio_diagnostic_presentation_config(selected_config)
    if not newkirk_cfg:
        newkirk_cfg = dict(DEFAULT_NEWKIRK_CONFIG)

    cfg = legacy.build_config(user_config, legacy.DEFAULT_CONFIG)
    cfg = legacy._migrate_config(cfg)
    cfg["enable_gaussian_overlay"] = True
    cfg["save_gaussian_diagnostics"] = True
    if user_config.get("drift_rate", {}).get("enabled", False):
        cfg["enable_spectrogram_panel"] = True
        cfg["enable_drift_rate_overlay"] = True

    legacy.CONFIG = cfg
    legacy.main()

    output_dir = Path(cfg.get("output_dir") or os.getcwd())
    analysis_dir = output_dir / legacy._plot_output_subdir(cfg)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    gaussian_csv = analysis_dir / cfg.get(
        "gaussian_diagnostics_csv", "radio_gaussian_fit_diagnostics.csv"
    )
    if not gaussian_csv.exists():
        raise FileNotFoundError(f"Gaussian diagnostics CSV not found: {gaussian_csv}")

    gaussian_df = pd.read_csv(gaussian_csv)
    valid_df = _valid_gaussian_centers(gaussian_df)
    valid_csv = analysis_dir / "radio_gaussian_valid_centers.csv"
    valid_df.to_csv(valid_csv, index=False)

    if newkirk_cfg.get("enabled", True):
        newkirk_df = _build_gaussian_newkirk_table(valid_df, newkirk_cfg)
        newkirk_csv = analysis_dir / newkirk_cfg.get(
            "output_csv", "radio_gaussian_newkirk_extrapolated.csv"
        )
        newkirk_df.to_csv(newkirk_csv, index=False)
    else:
        newkirk_df = pd.DataFrame()
        newkirk_csv = None

    drift_df = _load_or_create_drift_diagnostics(cfg, drift_product_cfg)
    if newkirk_cfg.get("enabled", True) and not drift_df.empty:
        drift_speed_df = _build_drift_newkirk_table(drift_df, newkirk_cfg)
    else:
        drift_speed_df = pd.DataFrame()
    drift_speed_csv = analysis_dir / newkirk_cfg.get(
        "drift_speed_csv", "radio_drift_newkirk_speed.csv"
    )
    drift_speed_df.to_csv(drift_speed_csv, index=False)

    _plot_gaussian_center_trajectory(
        valid_df, analysis_dir / "gaussian_center_trajectory.png"
    )
    _plot_gaussian_newkirk_height_time(
        newkirk_df, analysis_dir / "gaussian_newkirk_height_time.png"
    )
    _plot_gaussian_newkirk_height_time(
        newkirk_df,
        analysis_dir / "gaussian_newkirk_geometry_valid_height_time.png",
        geometry_valid_only=True,
    )
    _plot_drift_speed_comparison(
        drift_speed_df, analysis_dir / "drift_newkirk_speed_comparison.png"
    )
    if newkirk_height_cfg.get("enable", True):
        _run_newkirk_height_comparison(
            gaussian_df,
            analysis_dir,
            newkirk_height_cfg,
            newkirk_cfg,
            drift_df,
            presentation_cfg,
            cfg,
        )
    if newkirk_spatial_cfg.get("enable", False):
        _run_newkirk_spatial_product(
            gaussian_df,
            analysis_dir,
            newkirk_spatial_cfg,
            newkirk_cfg,
        )

    print("[Pipeline] outputs:")
    print(f"  Gaussian diagnostics: {gaussian_csv}")
    print(f"  Valid Gaussian centers: {valid_csv}")
    if newkirk_csv is not None:
        print(f"  Gaussian Newkirk extrapolation: {newkirk_csv}")
    print(f"  Drift Newkirk speeds: {drift_speed_csv}")


def _run_newkirk_height_comparison(
    gaussian_df: pd.DataFrame,
    analysis_dir: Path,
    height_cfg: dict,
    newkirk_cfg: dict,
    drift_df: pd.DataFrame | None = None,
    presentation_cfg: dict | None = None,
    pipeline_cfg: dict | None = None,
) -> None:
    from scripts.radio.core.radio_height_comparison import (
        build_gaussian_newkirk_height_summary_table,
        build_gaussian_newkirk_height_table,
    )
    from scripts.radio.core.radio_height_plots import (
        plot_gaussian_vs_newkirk_height_frequency,
        plot_gaussian_vs_newkirk_height_time,
        plot_height_residual_vs_frequency,
    )
    from scripts.radio.core.radio_io import summarize_invalid_reasons

    cfg = dict(height_cfg or {})
    presentation = dict(presentation_cfg or {})
    for key in (
        "comparison_frequency_mhz",
        "drift_source_type_map",
        "drift_time_tolerance_s",
        "drift_frequency_tolerance_mhz",
        "max_adaptive_frequency_tolerance_mhz",
        "min_adaptive_frequency_tolerance_mhz",
        "reference_newkirk_assumption",
    ):
        if key in presentation and key not in cfg:
            cfg[key] = presentation[key]
    if cfg.get("solar_radius_arcsec") is None:
        cfg["solar_radius_arcsec"] = float(
            newkirk_cfg.get("solar_radius_arcsec", 959.63)
        )
    if drift_df is not None and not drift_df.empty:
        cfg["drift_selections"] = drift_df.to_dict("records")

    print("[Newkirk Height] enabled")
    height_df = build_gaussian_newkirk_height_table(gaussian_df, cfg)
    raw_table_path = analysis_dir / cfg.get(
        "raw_output_table_name", "gaussian_newkirk_height_rows.csv"
    )
    height_df.to_csv(raw_table_path, index=False)
    print(f"[Newkirk Height] raw comparison rows saved: {raw_table_path}")
    height_summary_df = build_gaussian_newkirk_height_summary_table(height_df, cfg)
    table_path = analysis_dir / cfg.get(
        "output_table_name", "gaussian_newkirk_height_comparison_table.csv"
    )
    height_summary_df.to_csv(table_path, index=False)
    print(f"[HeightComparison] summary table saved: {table_path}")

    skipped_rows = (
        int((~height_df["height_valid"].map(_truthy)).sum())
        if not height_df.empty
        else 0
    )
    skipped_reasons = summarize_invalid_reasons(
        height_df, "height_valid", "height_invalid_reason"
    )
    print(f"[Newkirk Height] invalid height rows: {skipped_rows}")
    print(f"[Newkirk Height] invalid height reasons: {skipped_reasons}")

    if cfg.get("plot_height_frequency", True):
        path = analysis_dir / cfg.get(
            "height_frequency_plot_name", "gaussian_vs_newkirk_height_frequency.png"
        )
        result = plot_gaussian_vs_newkirk_height_frequency(height_df, path, cfg)
        if result.get("status") == "saved":
            print(f"[Newkirk Height] frequency plot saved: {path}")
        else:
            print(
                f"[Newkirk Height] frequency plot skipped: {result.get('reason', 'unknown')}"
            )
    if cfg.get("plot_height_time", True):
        path = analysis_dir / cfg.get(
            "height_time_plot_name", "gaussian_vs_newkirk_height_time.png"
        )
        result = plot_gaussian_vs_newkirk_height_time(height_df, path, cfg)
        if result.get("status") == "saved":
            print(f"[Newkirk Height] time plot saved: {path}")
        else:
            print(
                f"[Newkirk Height] time plot skipped: {result.get('reason', 'unknown')}"
            )
    if cfg.get("plot_residual_frequency", True):
        path = analysis_dir / cfg.get(
            "height_residual_plot_name",
            "gaussian_newkirk_height_residual_vs_frequency.png",
        )
        result = plot_height_residual_vs_frequency(height_df, path, cfg)
        if result.get("status") == "saved":
            print(f"[Newkirk Height] residual plot saved: {path}")
            if result.get("summary_csv"):
                print(
                    f"[Newkirk Height] residual summary saved: {result['summary_csv']}"
                )
        else:
            print(
                f"[Newkirk Height] residual plot skipped: {result.get('reason', 'unknown')}"
            )
    if presentation.get("enable", True):
        _run_frequency_priority_diagnostics(
            height_df,
            gaussian_df,
            drift_df if drift_df is not None else pd.DataFrame(),
            analysis_dir,
            presentation,
            pipeline_cfg or {},
        )


def _run_frequency_priority_diagnostics(
    height_df: pd.DataFrame,
    gaussian_df: pd.DataFrame,
    drift_df: pd.DataFrame,
    analysis_dir: Path,
    presentation_cfg: dict,
    pipeline_cfg: dict,
) -> None:
    from scripts.radio.core.radio_frequency_priority_diagnostics import (
        build_frequency_priority_summary,
        build_selected_band_newkirk_height_speed_table,
        plot_drift_frequency_band_matching,
        plot_event_gaussian_newkirk_height_comparison,
        plot_event_newkirk_speed_frequency,
        plot_frequency_priority_summary,
        plot_gaussian_center_by_frequency_facets,
        plot_gaussian_center_trajectory_by_frequency,
        plot_height_time_by_frequency_facets,
        save_frequency_priority_summary_csv,
        save_newkirk_physical_consistency_report,
        write_frequency_priority_dashboard,
    )
    from scripts.radio.core.radio_height_comparison import (
        build_gaussian_newkirk_height_summary_table,
    )

    cfg = dict(presentation_cfg or {})
    print("[Frequency Priority] enabled")
    summary = build_frequency_priority_summary(height_df, gaussian_df, drift_df, cfg)
    csv_path = analysis_dir / cfg.get(
        "summary_csv_name", "radio_newkirk_frequency_priority_summary.csv"
    )
    save_frequency_priority_summary_csv(summary, csv_path)
    print(f"[Frequency Priority] summary CSV saved: {csv_path}")
    selected_band_path = analysis_dir / cfg.get(
        "selected_band_newkirk_table_name",
        "event_selected_band_newkirk_table.csv",
    )
    selected_band_table = build_selected_band_newkirk_height_speed_table(drift_df, cfg)
    selected_band_table.to_csv(selected_band_path, index=False)
    print(
        f"[Frequency Priority] selected-band Newkirk table saved: {selected_band_path}"
    )
    height_summary_table = build_gaussian_newkirk_height_summary_table(height_df, cfg)
    report_path = analysis_dir / cfg.get(
        "physical_consistency_report_name",
        "newkirk_physical_consistency_report.md",
    )
    report_result = save_newkirk_physical_consistency_report(
        selected_band_table, height_summary_table, report_path, cfg
    )
    print(f"[PhysicalCheck] report saved: {report_result['path']}")

    if cfg.get("enable_event_height_comparison", True):
        path = analysis_dir / cfg.get(
            "event_height_comparison_name",
            "event_gaussian_newkirk_height_comparison.png",
        )
        result = plot_event_gaussian_newkirk_height_comparison(height_df, path, cfg)
        if result.get("status") == "saved":
            print(f"[Frequency Priority] event height comparison saved: {path}")
        else:
            print(
                "[Frequency Priority] event height comparison skipped: "
                f"{result.get('reason', 'unknown')}"
            )

    if cfg.get("enable_event_speed_frequency", True):
        path = analysis_dir / cfg.get(
            "event_speed_frequency_name",
            "event_newkirk_speed_frequency_scatter.png",
        )
        result = plot_event_newkirk_speed_frequency(selected_band_table, path, cfg)
        if result.get("status") == "saved":
            print(f"[Frequency Priority] event speed-frequency plot saved: {path}")
        else:
            print(
                "[Frequency Priority] event speed-frequency plot skipped: "
                f"{result.get('reason', 'unknown')}"
            )

    debug_outputs = []
    if cfg.get("enable_static_summary", True):
        debug_outputs.append(
            (
                "summary panel",
                analysis_dir
                / cfg.get(
                    "summary_panel_name",
                    "radio_newkirk_frequency_priority_summary.png",
                ),
                lambda path: plot_frequency_priority_summary(
                    height_df, gaussian_df, drift_df, path, cfg
                ),
            )
        )
    if cfg.get("enable_debug_center_facets", False):
        debug_outputs.append(
            (
                "center facets",
                analysis_dir
                / cfg.get(
                    "center_facets_name", "gaussian_center_by_frequency_facets.png"
                ),
                lambda path: plot_gaussian_center_by_frequency_facets(
                    gaussian_df, path, cfg
                ),
            )
        )
    if cfg.get("enable_debug_height_time_facets", False):
        debug_outputs.append(
            (
                "height-time facets",
                analysis_dir
                / cfg.get(
                    "height_time_facets_name",
                    "height_time_by_frequency_facets.png",
                ),
                lambda path: plot_height_time_by_frequency_facets(height_df, path, cfg),
            )
        )
    for label, path, func in debug_outputs:
        result = func(path)
        if result.get("status") == "saved":
            print(f"[Frequency Priority] {label} saved: {path}")
        else:
            print(
                f"[Frequency Priority] {label} skipped: "
                f"{result.get('reason', 'unknown')}"
            )
    if cfg.get("enable_debug_drift_band_matching", False):
        _run_drift_band_matching_plot(
            drift_df,
            analysis_dir,
            cfg,
            pipeline_cfg,
            plot_drift_frequency_band_matching,
        )
    if cfg.get("enable_debug_trajectory_by_frequency", False):
        trajectory_result = plot_gaussian_center_trajectory_by_frequency(
            gaussian_df, analysis_dir, cfg
        )
        if trajectory_result.get("status") == "saved":
            print(
                "[Frequency Priority] time-colored trajectories saved: "
                f"{len(trajectory_result.get('paths', []))} files"
            )
        else:
            print(
                "[Frequency Priority] time-colored trajectories skipped: "
                f"{trajectory_result.get('reason', 'unknown')}"
            )

    if cfg.get("enable_html_dashboard", True):
        path = analysis_dir / cfg.get(
            "dashboard_name", "radio_newkirk_frequency_priority_dashboard.html"
        )
        result = write_frequency_priority_dashboard(
            height_df, gaussian_df, drift_df, path, cfg
        )
        if result.get("status") == "saved":
            print(f"[Frequency Priority] dashboard saved: {path}")


def _run_drift_band_matching_plot(
    drift_df: pd.DataFrame,
    analysis_dir: Path,
    cfg: dict,
    pipeline_cfg: dict,
    plot_func,
) -> None:
    if drift_df.empty:
        print("[Frequency Priority] drift band matching skipped: no_drift_rows")
        return
    try:
        from scripts.radio.core.radio_spectrogram import build_spectrogram_cache

        cache = build_spectrogram_cache(pipeline_cfg)
    except Exception as exc:
        print(f"[Frequency Priority] drift band matching skipped: {exc}")
        return
    if cache is None:
        print(
            "[Frequency Priority] drift band matching skipped: missing_spectrogram_cache"
        )
        return
    path = analysis_dir / cfg.get(
        "drift_band_matching_name", "drift_frequency_band_matching.png"
    )
    result = plot_func(
        cache.data, cache.time_datetimes, cache.freq, drift_df, path, cfg
    )
    if result.get("status") == "saved":
        print(f"[Frequency Priority] drift band matching saved: {path}")
    else:
        print(
            "[Frequency Priority] drift band matching skipped: "
            f"{result.get('reason', 'unknown')}"
        )


def _run_newkirk_spatial_product(
    gaussian_df: pd.DataFrame,
    analysis_dir: Path,
    spatial_cfg: dict,
    newkirk_cfg: dict,
) -> None:
    from scripts.radio.core.radio_aia171_spatial_plot import (
        plot_aia171_typeIII_spike_newkirk_distribution,
    )
    from scripts.radio.core.radio_io import summarize_invalid_reasons
    from scripts.radio.core.radio_newkirk_spatial import build_newkirk_spatial_dataframe

    cfg = dict(spatial_cfg or {})
    if cfg.get("solar_radius_arcsec") is None:
        cfg["solar_radius_arcsec"] = float(
            newkirk_cfg.get("solar_radius_arcsec", 959.63)
        )
    cfg.setdefault("harmonic", (newkirk_cfg.get("harmonics") or [1])[0])
    cfg.setdefault("newkirk_multiplier", (newkirk_cfg.get("multipliers") or [1])[0])

    print("[Newkirk Spatial] enabled as illustrative projection only")
    spatial_df = build_newkirk_spatial_dataframe(gaussian_df, cfg)
    csv_path = analysis_dir / cfg.get(
        "comparison_csv_name", "gaussian_newkirk_comparison_table.csv"
    )
    spatial_df.to_csv(csv_path, index=False)
    print(f"[Newkirk Spatial] comparison table saved: {csv_path}")

    skipped_rows = (
        int((~spatial_df["geometry_valid"].map(_truthy)).sum())
        if not spatial_df.empty
        else 0
    )
    skipped_reasons = summarize_invalid_reasons(
        spatial_df, "geometry_valid", "geometry_reason"
    )
    print(f"[Newkirk Spatial] skipped rows: {skipped_rows}")
    print(f"[Newkirk Spatial] skipped reasons: {skipped_reasons}")

    output_path = analysis_dir / cfg.get(
        "output_name", "aia171_typeIII_spike_newkirk_projection_schematic.png"
    )
    aia171_path = cfg.get("aia171_path")
    if not aia171_path:
        print("[Newkirk Spatial] AIA 171 plot skipped: missing_aia171_path")
        return
    result = plot_aia171_typeIII_spike_newkirk_distribution(
        aia171_path,
        spatial_df,
        output_path,
        cfg,
    )
    if result.get("status") == "saved":
        print(f"[Newkirk Spatial] spatial plot saved: {output_path}")
    else:
        print(
            "[Newkirk Spatial] AIA 171 plot skipped: "
            f"{result.get('reason', 'unknown')}"
        )


def _valid_gaussian_centers(df: pd.DataFrame) -> pd.DataFrame:
    required = {"quality_flag", "overlay_valid", "trajectory_valid"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"Gaussian diagnostics missing required columns: {sorted(missing)}"
        )
    mask = (
        df["quality_flag"].astype(str).str.lower().eq("ok")
        & df["overlay_valid"].map(_truthy)
        & df["trajectory_valid"].map(_truthy)
    )
    return df.loc[mask].copy().reset_index(drop=True)


def _build_gaussian_newkirk_table(
    valid_df: pd.DataFrame, newkirk_cfg: dict
) -> pd.DataFrame:
    from scripts.radio.core.radio_newkirk_extrapolation import (
        attach_newkirk_height_to_gaussian,
    )

    frames = []
    for multiplier in newkirk_cfg.get("multipliers", [1]):
        for harmonic in newkirk_cfg.get("harmonics", [1]):
            frames.append(
                attach_newkirk_height_to_gaussian(
                    valid_df,
                    multiplier=multiplier,
                    harmonic=harmonic,
                    solar_radius_arcsec=float(
                        newkirk_cfg.get("solar_radius_arcsec", 959.63)
                    ),
                    los_sign=float(newkirk_cfg.get("los_sign", 1)),
                )
            )
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _load_or_create_drift_diagnostics(
    cfg: dict, product_cfg: dict | None = None
) -> pd.DataFrame:
    from scripts.radio.core.radio_drift_rate import (
        get_or_load_drift_rate_results,
        save_drift_rate_diagnostics_once,
    )
    from scripts.radio.core.radio_spectrogram import build_spectrogram_cache
    from scripts.radio.legacy import radio_source_map_plot_gaussian_overlay as legacy

    csv_path = Path(legacy._drift_output_path(cfg, "drift_rate_diagnostics_csv"))
    if csv_path.exists():
        drift_df = pd.read_csv(csv_path)
        _save_drift_selection_products_from_cache(
            cfg, product_cfg, drift_df, csv_path.parent
        )
        return drift_df
    if not cfg.get("enable_drift_rate_overlay", False):
        return pd.DataFrame()
    cache = build_spectrogram_cache(cfg)
    if cache is None:
        return pd.DataFrame()
    results = get_or_load_drift_rate_results(cache, cfg)
    save_drift_rate_diagnostics_once(results, cfg, cache.source_file)
    drift_df = pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame()
    _save_drift_selection_products(cache, product_cfg, drift_df, csv_path.parent)
    return drift_df


def _save_drift_selection_products_from_cache(
    cfg: dict,
    product_cfg: dict | None,
    drift_df: pd.DataFrame,
    analysis_dir: Path,
) -> None:
    if not product_cfg or not product_cfg.get("enable", True) or drift_df.empty:
        return
    try:
        from scripts.radio.core.radio_spectrogram import build_spectrogram_cache

        cache = build_spectrogram_cache(cfg)
    except Exception as exc:
        print(f"[Drift selection products] skipped: {exc}")
        return
    if cache is None:
        print("[Drift selection products] skipped: missing_spectrogram_cache")
        return
    _save_drift_selection_products(cache, product_cfg, drift_df, analysis_dir)


def _save_drift_selection_products(
    cache,
    product_cfg: dict | None,
    drift_df: pd.DataFrame,
    analysis_dir: Path,
) -> None:
    if not product_cfg or not product_cfg.get("enable", True) or drift_df.empty:
        return
    from scripts.radio.core.radio_drift_products import save_drift_selection_artifacts

    out_dir = Path(analysis_dir) / product_cfg.get("output_subdir", "drift_selection")
    preview_cfg = dict(product_cfg)
    preview_cfg.update(
        {
            "cmap": cache.cmap,
            "vmin": cache.vmin,
            "vmax": cache.vmax,
            "colorbar_label": cache.cbar_label,
        }
    )
    try:
        result = save_drift_selection_artifacts(
            cache.data,
            cache.time_datetimes,
            cache.freq,
            drift_df,
            out_dir,
            source_file=cache.source_file,
            config=preview_cfg,
        )
    except Exception as exc:
        print(f"[Drift selection products] skipped: {exc}")
        return
    if result.get("status") == "saved":
        print(f"[Drift selection products] saved: {out_dir}")
    else:
        print(f"[Drift selection products] skipped: {result.get('reason', 'unknown')}")


def _build_drift_newkirk_table(
    drift_df: pd.DataFrame, newkirk_cfg: dict
) -> pd.DataFrame:
    from scripts.radio.core.radio_newkirk_extrapolation import (
        extrapolate_drift_line_with_newkirk,
    )

    rows = []
    ok_df = drift_df
    if "quality_flag" in ok_df.columns:
        ok_df = ok_df[ok_df["quality_flag"].astype(str).str.lower().eq("ok")]
    for _, row in ok_df.iterrows():
        for multiplier in newkirk_cfg.get("multipliers", [1]):
            for harmonic in newkirk_cfg.get("harmonics", [1]):
                rows.append(
                    extrapolate_drift_line_with_newkirk(
                        row.to_dict(), multiplier=multiplier, harmonic=harmonic
                    )
                )
    return pd.DataFrame(rows)


def parse_radio_time_value(value):
    digits = "".join(re.findall(r"\d", str(value)))
    if len(digits) < 14:
        return pd.NaT

    base = digits[:14]
    suffix = digits[14:]
    if suffix:
        if len(suffix) <= 3:
            microsecond = suffix.zfill(3) + "000"
        else:
            microsecond = suffix[:6].ljust(6, "0")
    else:
        microsecond = "000000"

    return pd.to_datetime(base + microsecond, format="%Y%m%d%H%M%S%f", errors="coerce")


def _plot_gaussian_center_trajectory(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6), dpi=180)
    if not df.empty:
        freqs = pd.to_numeric(df.get("freq"), errors="coerce")
        sc = ax.scatter(
            pd.to_numeric(df["center_x_arcsec"], errors="coerce"),
            pd.to_numeric(df["center_y_arcsec"], errors="coerce"),
            c=freqs,
            cmap="viridis",
            s=28,
            edgecolors="black",
            linewidths=0.3,
        )
        fig.colorbar(sc, ax=ax, label="Frequency (MHz)")
    ax.set_xlabel("x (arcsec)")
    ax.set_ylabel("y (arcsec)")
    ax.set_title("Gaussian center trajectory")
    ax.grid(True, linestyle=":", alpha=0.35)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_gaussian_center_trajectory_time_colored(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6), dpi=180)
    if not df.empty:
        data = df.copy()
        data["time_dt"] = data["time"].map(parse_radio_time_value)
        data["freq_num"] = pd.to_numeric(data.get("freq"), errors="coerce")
        data["center_x_num"] = pd.to_numeric(data["center_x_arcsec"], errors="coerce")
        data["center_y_num"] = pd.to_numeric(data["center_y_arcsec"], errors="coerce")
        data = data.dropna(
            subset=["time_dt", "freq_num", "center_x_num", "center_y_num"]
        ).sort_values("time_dt")
        if not data.empty:
            time_nums = mdates.date2num(data["time_dt"])
            ax.plot(
                data["center_x_num"],
                data["center_y_num"],
                color="0.55",
                linewidth=1.0,
                alpha=0.75,
                zorder=1,
            )
            sc = ax.scatter(
                data["center_x_num"],
                data["center_y_num"],
                c=time_nums,
                cmap="plasma",
                s=34,
                edgecolors="black",
                linewidths=0.3,
                zorder=2,
            )
            for _, row in data.iterrows():
                ax.annotate(
                    f"{row['freq_num']:.0f}",
                    (row["center_x_num"], row["center_y_num"]),
                    xytext=(3, 3),
                    textcoords="offset points",
                    fontsize=6,
                    color="black",
                )
            if len(data) >= 2:
                start = data.iloc[-2]
                end = data.iloc[-1]
                ax.annotate(
                    "",
                    xy=(end["center_x_num"], end["center_y_num"]),
                    xytext=(start["center_x_num"], start["center_y_num"]),
                    arrowprops=dict(arrowstyle="->", color="black", linewidth=1.2),
                )
            cbar = fig.colorbar(sc, ax=ax, label="Time (UT)")
            cbar.ax.yaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.set_xlabel("x (arcsec)")
    ax.set_ylabel("y (arcsec)")
    ax.set_title("Gaussian center trajectory colored by time")
    ax.grid(True, linestyle=":", alpha=0.35)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_gaussian_newkirk_height_time(
    df: pd.DataFrame, path: Path, geometry_valid_only: bool = False
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5), dpi=180)
    if not df.empty:
        data = df.copy()
        data["time_dt"] = data["time"].map(parse_radio_time_value)
        data["newkirk_height_rsun_num"] = pd.to_numeric(
            data["newkirk_height_rsun"], errors="coerce"
        )
        if geometry_valid_only and "newkirk_geometry_valid" in data.columns:
            data = data[data["newkirk_geometry_valid"].map(_truthy)]
        data = data[
            data["time_dt"].notna() & np.isfinite(data["newkirk_height_rsun_num"])
        ]
        for (multiplier, harmonic), group in data.groupby(
            ["newkirk_multiplier", "newkirk_harmonic"]
        ):
            group = group.sort_values("time_dt")
            ax.plot(
                group["time_dt"],
                group["newkirk_height_rsun_num"],
                marker="o",
                linewidth=1.2,
                markersize=3,
                label=f"{multiplier:g}x H{harmonic:g}",
            )
        if not data.empty:
            ax.legend(fontsize=8, ncol=2)
            ax.set_xlim(data["time_dt"].min(), data["time_dt"].max())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.set_xlabel("Time (UT)")
    ax.set_ylabel("Newkirk height (Rsun above photosphere)")
    title = "Gaussian Newkirk height evolution"
    if geometry_valid_only:
        title += " (geometry valid only)"
    ax.set_title(title)
    ax.grid(True, linestyle=":", alpha=0.35)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_drift_speed_comparison(df: pd.DataFrame, path: Path) -> None:
    from scripts.radio.core.radio_frequency_priority_diagnostics import (
        format_newkirk_case_label,
    )

    fig, ax = plt.subplots(figsize=(10, 6.4), dpi=180)
    if not df.empty:
        data = df.copy()
        data["newkirk_case"] = (
            data["newkirk_multiplier"].map(lambda v: f"{float(v):g}x")
            + "H"
            + data["newkirk_harmonic"].map(lambda v: f"{float(v):g}")
        )
        case_labels = {
            row["newkirk_case"]: format_newkirk_case_label(
                row["newkirk_multiplier"], row["newkirk_harmonic"], compact=True
            )
            for _, row in data.drop_duplicates(subset=["newkirk_case"]).iterrows()
        }
        drift_rates = (
            data.assign(
                drift_rate_num=pd.to_numeric(
                    data.get("drift_rate_mhz_s"), errors="coerce"
                )
            )
            .drop_duplicates(subset=["label"])
            .set_index("label")["drift_rate_num"]
            .to_dict()
        )
        speed_col = (
            "newkirk_speed_km_s"
            if "newkirk_speed_km_s" in data.columns
            else "speed_km_s"
        )
        data["speed_km_s_num"] = pd.to_numeric(data[speed_col], errors="coerce")
        if "newkirk_speed_c" in data.columns:
            data["speed_c_num"] = pd.to_numeric(
                data["newkirk_speed_c"], errors="coerce"
            )
        else:
            data["speed_c_num"] = data["speed_km_s_num"] / 299792.458
        heatmap = data.pivot_table(
            index="label",
            columns="newkirk_case",
            values="speed_km_s_num",
            aggfunc="mean",
        )
        heatmap_c = data.pivot_table(
            index="label",
            columns="newkirk_case",
            values="speed_c_num",
            aggfunc="mean",
        )
        desired_cols = ["1xH1", "1xH2", "2xH1", "2xH2", "4xH1", "4xH2"]
        existing_cols = [col for col in desired_cols if col in heatmap.columns]
        extra_cols = [col for col in heatmap.columns if col not in existing_cols]
        heatmap = heatmap.reindex(columns=existing_cols + extra_cols)
        heatmap_c = heatmap_c.reindex(index=heatmap.index, columns=heatmap.columns)
        values = heatmap.to_numpy(dtype=float)
        c_values = heatmap_c.to_numpy(dtype=float)
        if values.size:
            finite_mean = np.nanmean(values) if np.isfinite(values).any() else np.nan
            im = ax.imshow(values, aspect="auto", cmap="viridis")
            ax.set_xticks(np.arange(len(heatmap.columns)))
            ax.set_xticklabels(
                [case_labels.get(col, col) for col in heatmap.columns],
                rotation=40,
                ha="right",
                fontsize=8,
            )
            ax.set_yticks(np.arange(len(heatmap.index)))
            ax.set_yticklabels(
                [
                    (
                        f"{label}\n{drift_rates[label]:.2f} MHz/s"
                        if label in drift_rates and np.isfinite(drift_rates[label])
                        else label
                    )
                    for label in heatmap.index
                ]
            )
            for y_idx in range(values.shape[0]):
                for x_idx in range(values.shape[1]):
                    value = values[y_idx, x_idx]
                    c_value = c_values[y_idx, x_idx] if c_values.size else np.nan
                    if np.isfinite(value):
                        ax.text(
                            x_idx,
                            y_idx,
                            (
                                f"{value:.0f}\n{c_value:.2f}c"
                                if np.isfinite(c_value)
                                else f"{value:.0f}"
                            ),
                            ha="center",
                            va="center",
                            color="white" if value > finite_mean else "black",
                            fontsize=7,
                        )
            fig.colorbar(im, ax=ax, label="Newkirk-inferred exciter speed (km/s)")
    ax.set_xlabel("Density / emission assumption")
    ax.set_ylabel("Drift label")
    ax.set_title("Drift-rate-derived Newkirk exciter speed comparison")
    fig.text(
        0.5,
        0.02,
        "Note: 1xH2 and 4xH1 are degenerate because the inferred height depends on N*s^2.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.subplots_adjust(bottom=0.30)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _prepare_newkirk_spatial_dataframe(
    df: pd.DataFrame, solar_radius_arcsec: float = 959.63
) -> pd.DataFrame:
    data = pd.DataFrame(df).copy()
    if data.empty:
        return data

    data["time_dt"] = data["time"].map(parse_radio_time_value)
    data["freq_num"] = pd.to_numeric(data.get("freq"), errors="coerce")
    data["center_x_arcsec_num"] = pd.to_numeric(
        data["center_x_arcsec"], errors="coerce"
    )
    data["center_y_arcsec_num"] = pd.to_numeric(
        data["center_y_arcsec"], errors="coerce"
    )
    data["newkirk_r_rsun_num"] = pd.to_numeric(data["newkirk_r_rsun"], errors="coerce")
    data["newkirk_height_rsun_num"] = pd.to_numeric(
        data["newkirk_height_rsun"], errors="coerce"
    )
    data["newkirk_z_rsun_num"] = pd.to_numeric(data["newkirk_z_rsun"], errors="coerce")
    data["newkirk_multiplier_num"] = pd.to_numeric(
        data["newkirk_multiplier"], errors="coerce"
    )
    data["newkirk_harmonic_num"] = pd.to_numeric(
        data["newkirk_harmonic"], errors="coerce"
    )
    data["x_rsun"] = data["center_x_arcsec_num"] / float(solar_radius_arcsec)
    data["y_rsun"] = data["center_y_arcsec_num"] / float(solar_radius_arcsec)
    data["rho_rsun"] = np.sqrt(data["x_rsun"] ** 2 + data["y_rsun"] ** 2)
    data["model_label"] = [
        _format_model_label(multiplier, harmonic)
        for multiplier, harmonic in zip(
            data["newkirk_multiplier_num"],
            data["newkirk_harmonic_num"],
            strict=False,
        )
    ]
    data["newkirk_geometry_valid_bool"] = data["newkirk_geometry_valid"].map(_truthy)

    with np.errstate(invalid="ignore", divide="ignore"):
        scale = data["newkirk_r_rsun_num"] / data["rho_rsun"]
    scale = scale.where(np.isfinite(scale), 1.0)
    data["newkirk_radial_x_arcsec"] = data["center_x_arcsec_num"] * scale
    data["newkirk_radial_y_arcsec"] = data["center_y_arcsec_num"] * scale
    return data


def _write_newkirk_spatial_model_summary(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    rows = []
    if not df.empty:
        for label, group in df.groupby("model_label", sort=False):
            valid = group[group["newkirk_geometry_valid_bool"]]
            total_points = int(len(group))
            valid_points = int(len(valid))
            heights = valid["newkirk_height_rsun_num"]
            rows.append(
                {
                    "model_label": label,
                    "total_points": total_points,
                    "geometry_valid_points": valid_points,
                    "geometry_invalid_points": total_points - valid_points,
                    "valid_fraction": (
                        valid_points / total_points if total_points else np.nan
                    ),
                    "min_height_rsun": heights.min() if not heights.empty else np.nan,
                    "max_height_rsun": heights.max() if not heights.empty else np.nan,
                    "median_height_rsun": (
                        heights.median() if not heights.empty else np.nan
                    ),
                }
            )
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(
            by="model_label", key=lambda labels: labels.map(_model_label_sort_key)
        )
    summary.to_csv(path, index=False)
    return summary


def _plot_newkirk_spatial_overlay_aia(
    df: pd.DataFrame,
    path: Path,
    aia_config: dict | None = None,
    solar_radius_arcsec: float = 959.63,
) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 7.5), dpi=180)
    _draw_aia_or_solar_context(ax, df, aia_config, solar_radius_arcsec)

    projected = _unique_projected_centers(df)
    if not projected.empty:
        sc = ax.scatter(
            projected["center_x_arcsec_num"],
            projected["center_y_arcsec_num"],
            c=projected["freq_num"],
            cmap="viridis",
            s=18,
            marker="o",
            edgecolors="black",
            linewidths=0.2,
            alpha=0.75,
            label="Projected Gaussian centers",
            zorder=3,
        )
        fig.colorbar(sc, ax=ax, label="Frequency (MHz)", fraction=0.046, pad=0.04)

    valid = _valid_spatial_rows(df)
    for label, group in _iter_model_groups(valid):
        marker = _model_marker(label)
        ax.scatter(
            group["newkirk_radial_x_arcsec"],
            group["newkirk_radial_y_arcsec"],
            c=group["freq_num"],
            cmap="viridis",
            s=34,
            marker=marker,
            edgecolors="white",
            linewidths=0.45,
            alpha=0.9,
            label=label,
            zorder=4,
        )

    ax.set_xlabel("Solar X (arcsec)")
    ax.set_ylabel("Solar Y (arcsec)")
    ax.set_title("Illustrative Gaussian-anchored Newkirk projection schematic")
    ax.legend(fontsize=7, loc="best", framealpha=0.82, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_newkirk_3d_trajectory(df: pd.DataFrame, path: Path) -> None:
    fig = plt.figure(figsize=(9, 7), dpi=180)
    ax = fig.add_subplot(111, projection="3d")
    valid = _valid_spatial_rows(df)
    if not valid.empty:
        norm = plt.Normalize(valid["freq_num"].min(), valid["freq_num"].max())
        cmap = plt.get_cmap("viridis")
        for label, group in _iter_model_groups(valid):
            group = group.sort_values("time_dt")
            color = cmap(norm(group["freq_num"].median()))
            ax.plot(
                group["x_rsun"],
                group["y_rsun"],
                group["newkirk_height_rsun_num"],
                color=color,
                linewidth=1.2,
                alpha=0.85,
                label=label,
            )
            ax.scatter(
                group["x_rsun"],
                group["y_rsun"],
                group["newkirk_height_rsun_num"],
                c=group["freq_num"],
                cmap="viridis",
                norm=norm,
                s=14,
                marker=_model_marker(label),
                depthshade=False,
            )
        xlim = ax.get_xlim3d()
        ylim = ax.get_ylim3d()
        xx, yy = np.meshgrid(
            np.linspace(xlim[0], xlim[1], 2), np.linspace(ylim[0], ylim[1], 2)
        )
        ax.plot_surface(xx, yy, np.zeros_like(xx), color="0.85", alpha=0.18)
        sm = plt.cm.ScalarMappable(norm=norm, cmap="viridis")
        sm.set_array([])
        fig.colorbar(sm, ax=ax, label="Frequency (MHz)", shrink=0.68, pad=0.08)

    ax.set_xlabel("X (Rsun)")
    ax.set_ylabel("Y (Rsun)")
    ax.set_zlabel("Newkirk height (Rsun)")
    ax.set_title(
        "3D trajectories of Gaussian radio sources extrapolated with the Newkirk model"
    )
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_newkirk_rho_z_slice(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 6), dpi=180)
    valid = _valid_spatial_rows(df)
    if not valid.empty:
        norm = plt.Normalize(valid["freq_num"].min(), valid["freq_num"].max())
        for label, group in _iter_model_groups(valid):
            ax.scatter(
                group["rho_rsun"],
                group["newkirk_height_rsun_num"],
                c=group["freq_num"],
                cmap="viridis",
                norm=norm,
                s=28,
                marker=_model_marker(label),
                edgecolors="black",
                linewidths=0.25,
                alpha=0.85,
                label=label,
            )
        sm = plt.cm.ScalarMappable(norm=norm, cmap="viridis")
        sm.set_array([])
        fig.colorbar(sm, ax=ax, label="Frequency (MHz)")
    ax.set_xlabel("Projected radial distance rho (Rsun)")
    ax.set_ylabel("Newkirk height (Rsun above photosphere)")
    ax.set_title("Projected distance vs Newkirk-extrapolated source height")
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_newkirk_spatial_overlay_per_model(
    df: pd.DataFrame,
    path: Path,
    aia_config: dict | None = None,
    solar_radius_arcsec: float = 959.63,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12, 8), dpi=180, sharex=True, sharey=True)
    models = _ordered_model_labels(df)
    for ax, label in zip(axes.ravel(), models, strict=False):
        _draw_aia_or_solar_context(ax, df, aia_config, solar_radius_arcsec)
        group = df[
            (df["model_label"] == label)
            & df["newkirk_geometry_valid_bool"]
            & np.isfinite(df["newkirk_radial_x_arcsec"])
            & np.isfinite(df["newkirk_radial_y_arcsec"])
        ].sort_values("time_dt")
        if group.empty:
            ax.text(
                0.5,
                0.5,
                "No geometry-valid sources",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="0.25",
            )
        else:
            sc = ax.scatter(
                group["newkirk_radial_x_arcsec"],
                group["newkirk_radial_y_arcsec"],
                c=group["freq_num"],
                cmap="viridis",
                s=24,
                marker=_model_marker(label),
                edgecolors="white",
                linewidths=0.35,
                alpha=0.9,
                zorder=4,
            )
        ax.set_title(f"{label}  valid count={len(group)}", fontsize=10)
        ax.set_xlabel("Solar X (arcsec)")
        ax.set_ylabel("Solar Y (arcsec)")
    if "sc" in locals():
        fig.colorbar(sc, ax=axes.ravel().tolist(), label="Frequency (MHz)", shrink=0.8)
    fig.suptitle("Illustrative Newkirk projection schematic by density model", y=0.99)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _draw_aia_or_solar_context(
    ax,
    df: pd.DataFrame,
    aia_config: dict | None,
    solar_radius_arcsec: float,
) -> None:
    image, extent = _load_aia171_context(aia_config)
    if image is not None and extent is not None:
        finite = image[np.isfinite(image)]
        if finite.size:
            vmin, vmax = np.nanpercentile(finite, [1, 99.6])
        else:
            vmin, vmax = None, None
        ax.imshow(
            image,
            extent=extent,
            origin="lower",
            cmap="magma",
            vmin=vmin,
            vmax=vmax,
            alpha=0.88,
            zorder=0,
        )
    else:
        ax.set_facecolor("0.965")
        ax.text(
            0.02,
            0.98,
            "AIA 171 context unavailable",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=7,
            color="0.35",
        )

    theta = np.linspace(0, 2 * np.pi, 360)
    ax.plot(
        solar_radius_arcsec * np.cos(theta),
        solar_radius_arcsec * np.sin(theta),
        color="white" if image is not None else "0.5",
        linestyle="--",
        linewidth=0.8,
        alpha=0.7,
        zorder=1,
    )
    xlim, ylim = _spatial_axis_limits(df, aia_config)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(
        True, linestyle=":", alpha=0.25, color="white" if image is not None else "0.6"
    )


def _load_aia171_context(aia_config: dict | None):
    if not aia_config:
        return None, None
    try:
        from astropy.io import fits
    except Exception:
        return None, None

    aia_dir = Path((aia_config.get("paths") or {}).get("aia_base_dir", ""))
    if not aia_dir.exists():
        return None, None
    files = sorted(aia_dir.glob("*.fits"))
    if not files:
        return None, None

    aia_settings = aia_config.get("aia") or {}
    start_idx = int(aia_settings.get("aia_file_start_idx", 0) or 0)
    end_idx = int(aia_settings.get("aia_file_end_idx", start_idx) or start_idx)
    file_idx = min(max((start_idx + end_idx) // 2, 0), len(files) - 1)
    path = files[file_idx]

    try:
        with fits.open(path, memmap=False) as hdul:
            image_hdu = next((hdu for hdu in hdul if hdu.data is not None), None)
            if image_hdu is None:
                return None, None
            image = np.asarray(image_hdu.data, dtype=float)
            header = image_hdu.header
    except Exception:
        return None, None
    if image.ndim != 2:
        return None, None

    roi = aia_config.get("wcs_reproject") or {}
    bottom_left = roi.get("roi_bottom_left")
    top_right = roi.get("roi_top_right")
    if bottom_left and top_right:
        xmin, ymin = map(float, bottom_left)
        xmax, ymax = map(float, top_right)
    else:
        ny, nx = image.shape
        xmin, xmax = _pixel_to_arcsec([0, nx - 1], header, axis=1)
        ymin, ymax = _pixel_to_arcsec([0, ny - 1], header, axis=2)

    x0, x1 = _arcsec_to_pixel_bounds(
        xmin, xmax, header, axis=1, max_size=image.shape[1]
    )
    y0, y1 = _arcsec_to_pixel_bounds(
        ymin, ymax, header, axis=2, max_size=image.shape[0]
    )
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return None, None

    x_extent = _pixel_to_arcsec([x0, x1 - 1], header, axis=1)
    y_extent = _pixel_to_arcsec([y0, y1 - 1], header, axis=2)
    extent = [min(x_extent), max(x_extent), min(y_extent), max(y_extent)]
    crop = np.log1p(np.clip(crop, a_min=0, a_max=None))
    return crop, extent


def _arcsec_to_pixel_bounds(v0, v1, header, axis: int, max_size: int):
    crpix = float(header.get(f"CRPIX{axis}", (max_size + 1) / 2.0))
    cdelt = float(header.get(f"CDELT{axis}", 1.0))
    crval = float(header.get(f"CRVAL{axis}", 0.0))
    p0 = int(np.floor((float(v0) - crval) / cdelt + crpix - 1))
    p1 = int(np.ceil((float(v1) - crval) / cdelt + crpix - 1))
    lo, hi = sorted((p0, p1))
    lo = max(lo, 0)
    hi = min(max(hi + 1, lo + 1), max_size)
    return lo, hi


def _pixel_to_arcsec(pixels, header, axis: int):
    max_size = int(header.get(f"NAXIS{axis}", 1))
    crpix = float(header.get(f"CRPIX{axis}", (max_size + 1) / 2.0))
    cdelt = float(header.get(f"CDELT{axis}", 1.0))
    crval = float(header.get(f"CRVAL{axis}", 0.0))
    pix = np.asarray(pixels, dtype=float)
    return (pix + 1 - crpix) * cdelt + crval


def _spatial_axis_limits(df: pd.DataFrame, aia_config: dict | None):
    roi = (aia_config or {}).get("wcs_reproject") or {}
    bottom_left = roi.get("roi_bottom_left")
    top_right = roi.get("roi_top_right")
    if bottom_left and top_right:
        xmin, ymin = map(float, bottom_left)
        xmax, ymax = map(float, top_right)
        return (xmin, xmax), (ymin, ymax)

    values_x = pd.concat(
        [
            pd.to_numeric(df.get("center_x_arcsec_num"), errors="coerce"),
            pd.to_numeric(df.get("newkirk_radial_x_arcsec"), errors="coerce"),
        ],
        ignore_index=True,
    )
    values_y = pd.concat(
        [
            pd.to_numeric(df.get("center_y_arcsec_num"), errors="coerce"),
            pd.to_numeric(df.get("newkirk_radial_y_arcsec"), errors="coerce"),
        ],
        ignore_index=True,
    )
    values_x = values_x[np.isfinite(values_x)]
    values_y = values_y[np.isfinite(values_y)]
    if values_x.empty or values_y.empty:
        return (-1000, 1000), (-1000, 1000)
    xpad = max(80.0, 0.12 * (values_x.max() - values_x.min()))
    ypad = max(80.0, 0.12 * (values_y.max() - values_y.min()))
    return (values_x.min() - xpad, values_x.max() + xpad), (
        values_y.min() - ypad,
        values_y.max() + ypad,
    )


def _valid_spatial_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    required = [
        "newkirk_geometry_valid_bool",
        "time_dt",
        "freq_num",
        "x_rsun",
        "y_rsun",
        "rho_rsun",
        "newkirk_height_rsun_num",
        "newkirk_radial_x_arcsec",
        "newkirk_radial_y_arcsec",
    ]
    valid = df[df["newkirk_geometry_valid_bool"]].copy()
    valid = valid.dropna(subset=required)
    return valid[np.isfinite(valid["newkirk_height_rsun_num"])]


def _unique_projected_centers(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    cols = ["time", "freq", "center_x_arcsec_num", "center_y_arcsec_num"]
    data = df.dropna(subset=["freq_num", "center_x_arcsec_num", "center_y_arcsec_num"])
    return data.drop_duplicates(subset=cols).sort_values("time_dt")


def _iter_model_groups(df: pd.DataFrame):
    for label in _ordered_model_labels(df):
        group = df[df["model_label"] == label]
        if not group.empty:
            yield label, group


def _ordered_model_labels(df: pd.DataFrame):
    if df.empty or "model_label" not in df.columns:
        return ["1x H1", "1x H2", "2x H1", "2x H2", "4x H1", "4x H2"]
    labels = list(dict.fromkeys(df["model_label"].dropna().astype(str)))
    return sorted(labels, key=_model_label_sort_key)


def _format_model_label(multiplier, harmonic) -> str:
    return f"{float(multiplier):g}x H{float(harmonic):g}"


def _model_label_sort_key(label: str):
    match = re.match(r"([0-9.]+)x H([0-9.]+)", str(label))
    if not match:
        return (float("inf"), float("inf"), str(label))
    return (float(match.group(1)), float(match.group(2)), str(label))


def _model_marker(label: str) -> str:
    markers = {
        "1x H1": "o",
        "1x H2": "s",
        "2x H1": "^",
        "2x H2": "D",
        "4x H1": "P",
        "4x H2": "X",
    }
    return markers.get(label, "o")


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "ok"}
    return bool(value)


if __name__ == "__main__":
    main()
