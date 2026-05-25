"""Gaussian + spectrogram + drift-rate + Newkirk extrapolation pipeline."""

from __future__ import annotations

import copy
import os
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
    from scripts.radio import radio_source_map_plot_gaussian_overlay as legacy
    from scripts.radio.radio_drift_rate import (
        get_or_load_drift_rate_results,
        save_drift_rate_diagnostics_once,
    )
    from scripts.radio.radio_newkirk_extrapolation import (
        attach_newkirk_height_to_gaussian,
        extrapolate_drift_line_with_newkirk,
    )
    from scripts.radio.radio_spectrogram import build_spectrogram_cache
else:
    from . import radio_source_map_plot_gaussian_overlay as legacy
    from .radio_drift_rate import (
        get_or_load_drift_rate_results,
        save_drift_rate_diagnostics_once,
    )
    from .radio_newkirk_extrapolation import (
        attach_newkirk_height_to_gaussian,
        extrapolate_drift_line_with_newkirk,
    )
    from .radio_spectrogram import build_spectrogram_cache


USER_CONFIG = copy.deepcopy(legacy.USER_CONFIG)
USER_CONFIG["newkirk"] = {
    "enabled": True,
    "multipliers": [1, 2, 4],
    "harmonics": [1, 2],
    "solar_radius_arcsec": 959.63,
    "los_sign": 1,
    "output_csv": "radio_gaussian_newkirk_extrapolated.csv",
    "drift_speed_csv": "radio_drift_newkirk_speed.csv",
}


def main():
    cfg = legacy.build_config(USER_CONFIG, legacy.DEFAULT_CONFIG)
    cfg = legacy._migrate_config(cfg)
    cfg["enable_gaussian_overlay"] = True
    cfg["save_gaussian_diagnostics"] = True
    if USER_CONFIG.get("drift_rate", {}).get("enabled", False):
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

    newkirk_cfg = dict(USER_CONFIG.get("newkirk", {}) or {})
    if newkirk_cfg.get("enabled", True):
        newkirk_df = _build_gaussian_newkirk_table(valid_df, newkirk_cfg)
        newkirk_csv = analysis_dir / newkirk_cfg.get(
            "output_csv", "radio_gaussian_newkirk_extrapolated.csv"
        )
        newkirk_df.to_csv(newkirk_csv, index=False)
    else:
        newkirk_df = pd.DataFrame()
        newkirk_csv = None

    drift_df = _load_or_create_drift_diagnostics(cfg)
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
    _plot_drift_speed_comparison(
        drift_speed_df, analysis_dir / "drift_newkirk_speed_comparison.png"
    )

    print("[Pipeline] outputs:")
    print(f"  Gaussian diagnostics: {gaussian_csv}")
    print(f"  Valid Gaussian centers: {valid_csv}")
    if newkirk_csv is not None:
        print(f"  Gaussian Newkirk extrapolation: {newkirk_csv}")
    print(f"  Drift Newkirk speeds: {drift_speed_csv}")


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


def _load_or_create_drift_diagnostics(cfg: dict) -> pd.DataFrame:
    csv_path = Path(legacy._drift_output_path(cfg, "drift_rate_diagnostics_csv"))
    if csv_path.exists():
        return pd.read_csv(csv_path)
    if not cfg.get("enable_drift_rate_overlay", False):
        return pd.DataFrame()
    cache = build_spectrogram_cache(cfg)
    if cache is None:
        return pd.DataFrame()
    results = get_or_load_drift_rate_results(cache, cfg)
    save_drift_rate_diagnostics_once(results, cfg, cache.source_file)
    return pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame()


def _build_drift_newkirk_table(
    drift_df: pd.DataFrame, newkirk_cfg: dict
) -> pd.DataFrame:
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


def _plot_gaussian_newkirk_height_time(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5), dpi=180)
    if not df.empty:
        data = df.copy()
        data["time_dt"] = pd.to_datetime(data["time"], errors="coerce")
        for (multiplier, harmonic), group in data.groupby(
            ["newkirk_multiplier", "newkirk_harmonic"]
        ):
            group = group.sort_values("time_dt")
            ax.plot(
                group["time_dt"],
                group["newkirk_height_rsun"],
                marker="o",
                linewidth=1.2,
                markersize=3,
                label=f"{multiplier:g}x H{harmonic:g}",
            )
        ax.legend(fontsize=8, ncol=2)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.set_xlabel("Time (UT)")
    ax.set_ylabel("Newkirk height (Rsun above photosphere)")
    ax.set_title("Gaussian Newkirk height evolution")
    ax.grid(True, linestyle=":", alpha=0.35)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_drift_speed_comparison(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5), dpi=180)
    if not df.empty:
        data = df.copy()
        data["combo"] = (
            data["label"].astype(str)
            + " "
            + data["newkirk_multiplier"].map(lambda v: f"{float(v):g}x")
            + " H"
            + data["newkirk_harmonic"].map(lambda v: f"{float(v):g}")
        )
        ax.bar(data["combo"], pd.to_numeric(data["speed_km_s"], errors="coerce"))
        ax.tick_params(axis="x", rotation=35, labelsize=8)
    ax.set_ylabel("Radial speed (km/s)")
    ax.set_title("Drift-rate Newkirk speed comparison")
    ax.grid(True, axis="y", linestyle=":", alpha=0.35)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "ok"}
    return bool(value)


if __name__ == "__main__":
    main()
