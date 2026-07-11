"""Source-mask construction helpers for radio Gaussian fitting."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, find_objects, label

from .coordinates import unravel_2d_index
from .gaussian_background import _safe_rms_map, estimate_background_noise
from .io import BoolArray, FloatArray

__all__ = ["_select_peak_connected_mask", "create_source_mask"]

_unravel_2d_index = unravel_2d_index


def _select_peak_connected_mask(
    source_mask_bool,
    grow_mask,
    peak_y,
    peak_x,
    use_snr=False,
    snr_map=None,
    work=None,
):
    labeled, _ = label(source_mask_bool)
    peak_label = labeled[peak_y, peak_x]
    if peak_label == 0:
        object_slices = find_objects(labeled)
        if not object_slices:
            main_mask = source_mask_bool
        else:
            labels = np.arange(1, int(labeled.max()) + 1)
            scores = []
            for lab in labels:
                component = labeled == lab
                if use_snr and snr_map is not None:
                    score = float(np.nanmax(np.where(component, snr_map, np.nan)))
                else:
                    score = float(np.nanmax(np.where(component, work, np.nan)))
                if not np.isfinite(score):
                    score = float(np.count_nonzero(component))
                scores.append(score)
            peak_label = int(labels[int(np.argmax(scores))]) if len(scores) else 0
            main_mask = np.asarray(labeled == peak_label, dtype=np.bool_)
    else:
        main_mask = np.asarray(labeled == peak_label, dtype=np.bool_)

    if use_snr:
        grown_labels, _ = label(grow_mask)
        grow_label = grown_labels[peak_y, peak_x]
        if grow_label == 0 and peak_label > 0:
            overlap = grown_labels[main_mask]
            overlap = overlap[overlap > 0]
            if overlap.size:
                grow_label = int(np.bincount(overlap).argmax())
        if grow_label > 0:
            main_mask = np.asarray(grown_labels == grow_label, dtype=np.bool_)
    return np.asarray(main_mask, dtype=np.bool_)


def create_source_mask(
    data: FloatArray | np.ndarray,
    cfg: dict,
    background_map=None,
    rms_map=None,
) -> tuple[BoolArray | None, dict]:
    work = np.asarray(data, dtype=np.float64)
    finite_data = work[np.isfinite(work)]
    diagnostics = {
        "quality_flag": "ok",
        "background_level": np.nan,
        "noise_sigma": np.nan,
        "threshold": np.nan,
        "peak": np.nan,
        "mask_pixel_count": 0,
        "source_snr_peak": np.nan,
        "source_snr_mean": np.nan,
        "background_rms_median": np.nan,
        "background_level_median": np.nan,
        "mask_method": "raw_threshold",
        "fit_peak_fraction_threshold_used": np.nan,
        "fit_peak_fraction_candidate_counts": "",
    }
    if finite_data.size == 0:
        diagnostics["quality_flag"] = "non_finite_data"
        return None, diagnostics

    peak = float(np.max(finite_data))
    if not np.isfinite(peak):
        diagnostics["quality_flag"] = "non_finite_data"
        return None, diagnostics

    use_snr = False
    snr_map = None
    bg = None
    rms = None
    if (
        cfg.get("background_use_for_mask", True)
        and background_map is not None
        and rms_map is not None
    ):
        bg = np.asarray(background_map, dtype=np.float64)
        rms = _safe_rms_map(rms_map)
        use_snr = bg.shape == work.shape and rms.shape == work.shape

    finite_peak_work = np.where(np.isfinite(work), work, -np.inf)
    peak_y, peak_x = _unravel_2d_index(int(np.argmax(finite_peak_work)), work.shape)

    base_peak_fraction = float(cfg.get("fit_peak_fraction_threshold", 0.60))
    grow_peak_fraction = float(cfg.get("fit_grow_peak_fraction_threshold", 0.25))
    min_peak_fraction = float(
        cfg.get("fit_peak_fraction_threshold_min", base_peak_fraction)
    )
    max_peak_fraction = float(
        cfg.get("fit_peak_fraction_threshold_max", base_peak_fraction)
    )
    step_peak_fraction = abs(float(cfg.get("fit_peak_fraction_threshold_step", 0.05)))
    min_peak_fraction, max_peak_fraction = sorted(
        (min_peak_fraction, max_peak_fraction)
    )
    base_peak_fraction = min(
        max(base_peak_fraction, min_peak_fraction), max_peak_fraction
    )
    grow_peak_fraction = min(max(grow_peak_fraction, 0.0), base_peak_fraction)
    target_min_pixels = int(cfg.get("fit_mask_target_min_pixels", 30))
    target_max_pixels = int(cfg.get("fit_mask_target_max_pixels", 300))
    if target_max_pixels < target_min_pixels:
        target_min_pixels, target_max_pixels = target_max_pixels, target_min_pixels

    if use_snr:
        snr_map = (work - bg) / rms
        fit_threshold = float(cfg.get("fit_snr_threshold", 5.0))
        grow_threshold = float(cfg.get("fit_grow_snr_threshold", 3.0))
        diagnostics.update(
            {
                "background_level": float(np.nanmedian(bg[np.isfinite(bg)])),
                "noise_sigma": float(np.nanmedian(rms[np.isfinite(rms) & (rms > 0)])),
                "threshold": fit_threshold,
                "background_rms_median": float(
                    np.nanmedian(rms[np.isfinite(rms) & (rms > 0)])
                ),
                "background_level_median": float(np.nanmedian(bg[np.isfinite(bg)])),
                "mask_method": "snr_mesh",
            }
        )
    else:
        background_level, noise_sigma = estimate_background_noise(work)
        if not np.isfinite(noise_sigma) or noise_sigma <= 0:
            noise_sigma = max(float(np.std(finite_data)), 1e-12)
        diagnostics.update(
            {
                "background_level": background_level,
                "noise_sigma": noise_sigma,
                "threshold": np.nan,
                "background_rms_median": noise_sigma,
                "background_level_median": background_level,
                "mask_method": "raw_threshold",
            }
        )

    def build_mask_for_peak_fraction(peak_fraction):
        intensity_threshold = float(peak_fraction * peak)
        grow_intensity_threshold = float(grow_peak_fraction * peak)
        if use_snr:
            core_intensity_mask = np.isfinite(work) & (work > intensity_threshold)
            grow_intensity_mask = np.isfinite(work) & (work > grow_intensity_threshold)
            core_mask = np.asarray(
                np.isfinite(snr_map) & (snr_map >= fit_threshold) & core_intensity_mask,
                dtype=np.bool_,
            )
            grow_mask_local = np.asarray(
                np.isfinite(snr_map)
                & (snr_map >= grow_threshold)
                & grow_intensity_mask,
                dtype=np.bool_,
            )
            threshold_used = fit_threshold
        else:
            threshold_used = max(
                float(cfg.get("fit_snr_threshold", 5.0)) * noise_sigma,
                intensity_threshold,
            )
            core_mask = np.asarray(
                np.isfinite(work) & (work > threshold_used), dtype=np.bool_
            )
            grow_threshold_used = max(
                float(cfg.get("fit_grow_snr_threshold", 3.0)) * noise_sigma,
                grow_intensity_threshold,
            )
            grow_mask_local = np.asarray(
                np.isfinite(work) & (work > grow_threshold_used), dtype=np.bool_
            )

        if not np.any(core_mask):
            return None, 0, threshold_used

        candidate_mask = _select_peak_connected_mask(
            core_mask,
            grow_mask_local,
            peak_y,
            peak_x,
            use_snr=use_snr,
            snr_map=snr_map,
            work=work,
        )
        dilation_pixels_local = int(cfg.get("fit_mask_dilation_pixels", 3))
        if dilation_pixels_local > 0:
            candidate_mask = np.asarray(
                binary_dilation(candidate_mask, iterations=dilation_pixels_local),
                dtype=np.bool_,
            )
        return candidate_mask, int(np.count_nonzero(candidate_mask)), threshold_used

    candidate_fractions = []
    if step_peak_fraction <= 0:
        candidate_fractions = [base_peak_fraction]
    else:
        frac = min_peak_fraction
        while frac <= max_peak_fraction + 1e-12:
            candidate_fractions.append(round(frac, 10))
            frac += step_peak_fraction
        if candidate_fractions[-1] < max_peak_fraction - 1e-12:
            candidate_fractions.append(max_peak_fraction)
    candidate_fractions = sorted(set(candidate_fractions))

    candidates = []
    for candidate_fraction in candidate_fractions:
        candidate_mask, candidate_count, candidate_threshold = (
            build_mask_for_peak_fraction(candidate_fraction)
        )
        candidates.append(
            {
                "fraction": float(candidate_fraction),
                "mask": candidate_mask,
                "count": int(candidate_count),
                "threshold": float(candidate_threshold),
            }
        )

    target_mid_pixels = 0.5 * (target_min_pixels + target_max_pixels)
    in_target_candidates = [
        item
        for item in candidates
        if item["mask"] is not None
        and target_min_pixels <= item["count"] <= target_max_pixels
    ]
    usable_candidates = [
        item
        for item in candidates
        if item["mask"] is not None
        and item["count"] >= int(cfg.get("fit_min_mask_pixels", 20))
    ]
    nonempty_candidates = [
        item for item in candidates if item["mask"] is not None and item["count"] > 0
    ]

    if in_target_candidates:
        selected = min(
            in_target_candidates,
            key=lambda item: (
                abs(item["count"] - target_mid_pixels),
                abs(item["fraction"] - base_peak_fraction),
            ),
        )
    elif usable_candidates:
        selected = min(
            usable_candidates,
            key=lambda item: (
                abs(item["count"] - target_min_pixels),
                abs(item["fraction"] - base_peak_fraction),
            ),
        )
    elif nonempty_candidates:
        selected = max(nonempty_candidates, key=lambda item: item["count"])
    else:
        selected = {
            "fraction": base_peak_fraction,
            "mask": None,
            "count": 0,
            "threshold": np.nan,
        }

    main_mask = selected["mask"]
    mask_pixel_count = int(selected["count"])
    threshold = selected["threshold"]
    peak_fraction_used = float(selected["fraction"])
    candidate_count_text = ";".join(
        f"{item['fraction']:.3f}:{item['count']}" for item in candidates
    )

    diagnostics["fit_peak_fraction_threshold_used"] = float(peak_fraction_used)
    diagnostics["fit_peak_fraction_candidate_counts"] = candidate_count_text
    diagnostics["threshold"] = threshold

    if main_mask is None or not np.any(main_mask):
        diagnostics.update(
            {
                "quality_flag": "mask_too_small",
                "peak": peak,
            }
        )
        return None, diagnostics

    diagnostics.update(
        {
            "peak": peak,
            "mask_pixel_count": mask_pixel_count,
        }
    )
    if use_snr and snr_map is not None:
        source_snr = snr_map[main_mask & np.isfinite(snr_map)]
        diagnostics["source_snr_peak"] = (
            float(np.nanmax(source_snr)) if source_snr.size else np.nan
        )
        diagnostics["source_snr_mean"] = (
            float(np.nanmean(source_snr)) if source_snr.size else np.nan
        )
    if mask_pixel_count < int(cfg.get("fit_min_mask_pixels", 20)):
        diagnostics["quality_flag"] = "mask_too_small"

    return np.asarray(main_mask, dtype=np.bool_), diagnostics
