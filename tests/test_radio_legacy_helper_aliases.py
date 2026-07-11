"""Compatibility identities for the historical Radio source-map workflow."""

from __future__ import annotations

from scripts.radio.legacy import radio_source_map_plot_gaussian_overlay as legacy
from solar_toolkit.modeling import gaussian as gaussian_model
from solar_toolkit.radio import (
    coordinates,
    drift_rate,
    gaussian,
    gaussian_background,
    gaussian_masks,
    gaussian_models,
    output_paths,
    spectrogram,
)
from solar_toolkit.radio import io as radio_io


def test_legacy_gaussian_and_coordinate_helpers_are_canonical_objects():
    aliases = {
        "GaussianFitResult": gaussian.GaussianFitResult,
        "elliptical_gaussian_2d": gaussian_model.elliptical_gaussian_2d,
        "elliptical_gaussian_2d_with_constant_bg": (
            gaussian_models.elliptical_gaussian_2d_with_constant_bg
        ),
        "elliptical_gaussian_2d_with_plane_bg": (
            gaussian_models.elliptical_gaussian_2d_with_plane_bg
        ),
        "gaussian_only_from_popt": gaussian_models.gaussian_only_from_popt,
        "estimate_background_noise": gaussian_background.estimate_background_noise,
        "_safe_rms_map": gaussian_background._safe_rms_map,
        "_unravel_2d_index": coordinates.unravel_2d_index,
        "_true_indices": gaussian_model.true_indices,
        "_select_peak_connected_mask": (gaussian_masks._select_peak_connected_mask),
        "create_source_mask": gaussian_masks.create_source_mask,
        "_gaussian_fit_diag_defaults": gaussian._gaussian_fit_diag_defaults,
        "_roi_slices_from_mask": gaussian._roi_slices_from_mask,
        "_weighted_moment_initial_guess": gaussian._weighted_moment_initial_guess,
        "_limit_fit_pixels": gaussian._limit_fit_pixels,
        "_attach_gaussian_fit_metadata": gaussian._attach_gaussian_fit_metadata,
        "_gaussian_fwhm_arcsec": gaussian._gaussian_fwhm_arcsec,
        "_center_peak_distance_arcsec": gaussian._center_peak_distance_arcsec,
        "_gaussian_quality_config": gaussian._gaussian_quality_config,
        "_update_gaussian_quality": gaussian._update_gaussian_quality,
        "_set_gaussian_failure_diag": gaussian._set_gaussian_failure_diag,
        "fit_elliptical_gaussian_on_radio_image": (
            gaussian.fit_elliptical_gaussian_on_radio_image
        ),
        "overlay_gaussian_fit_on_axis": gaussian.overlay_gaussian_fit_on_axis,
        "_acquire_csv_lock": gaussian._acquire_csv_lock,
        "_release_csv_lock": gaussian._release_csv_lock,
        "save_gaussian_diagnostics_row": gaussian.save_gaussian_diagnostics_row,
        "pixel_to_data_coord": coordinates.pixel_to_data_coord,
        "data_coord_to_pixel": coordinates.data_coord_to_pixel,
        "coordinate_roundtrip_error_pixel": (
            coordinates.coordinate_roundtrip_error_pixel
        ),
    }

    for legacy_name, canonical_object in aliases.items():
        assert getattr(legacy, legacy_name) is canonical_object, legacy_name


def test_legacy_spectrogram_helpers_are_canonical_objects():
    aliases = {
        "SpectrogramCache": spectrogram.SpectrogramCache,
        "_parse_datetime_value": radio_io.parse_datetime_value,
        "_index_range_from_values": radio_io.index_range_from_values,
        "_index_range_from_time_values": radio_io.index_range_from_time_values,
        "_spectrogram_panel_enabled": output_paths.spectrogram_panel_enabled,
        "_normalize_spectrogram_paths": spectrogram._normalize_spectrogram_paths,
        "_read_spectrogram_file_metadata": (
            spectrogram._read_spectrogram_file_metadata
        ),
        "resolve_spectrogram_time_window_multi": (
            spectrogram.resolve_spectrogram_time_window_multi
        ),
        "_spectrogram_overlap_segments": spectrogram._spectrogram_overlap_segments,
        "_rebinned_axis_values": spectrogram._rebinned_axis_values,
        "_read_rebinned_plane": spectrogram._read_rebinned_plane,
        "build_spectrogram_cache": spectrogram.build_spectrogram_cache,
        "_spectrogram_time_locator": spectrogram._spectrogram_time_locator,
        "_date_num_to_datetime": spectrogram._date_num_to_datetime,
        "_spectrogram_display_data_extent": (
            spectrogram._spectrogram_display_data_extent
        ),
    }

    for legacy_name, canonical_object in aliases.items():
        assert getattr(legacy, legacy_name) is canonical_object, legacy_name


def test_legacy_drift_helpers_are_canonical_objects():
    aliases = {
        "DriftRateResult": drift_rate.DriftRateResult,
        "_datetime_iso_ms": drift_rate._datetime_iso_ms,
        "_drift_line_time": drift_rate._drift_line_time,
        "calculate_drift_rate_from_line": drift_rate.calculate_drift_rate_from_line,
        "_mark_drift_range_warnings": drift_rate._mark_drift_range_warnings,
        "_spectrogram_coord_from_pixel": drift_rate._spectrogram_coord_from_pixel,
        "assert_spectrogram_mapping_not_flipped": (
            drift_rate.assert_spectrogram_mapping_not_flipped
        ),
        "save_drift_selection_json": drift_rate.save_drift_selection_json,
        "load_drift_selection_json": drift_rate.load_drift_selection_json,
        "_load_drift_selection_payload": drift_rate._load_drift_selection_payload,
        "render_spectrogram_selection_preview": (
            drift_rate.render_spectrogram_selection_preview
        ),
        "_drift_selection_html": drift_rate._drift_selection_html,
        "launch_drift_selection_server": drift_rate.launch_drift_selection_server,
        "overlay_drift_rate_results": drift_rate.overlay_drift_rate_results,
        "save_drift_rate_diagnostics_once": (
            drift_rate.save_drift_rate_diagnostics_once
        ),
    }

    for legacy_name, canonical_object in aliases.items():
        assert getattr(legacy, legacy_name) is canonical_object, legacy_name


def test_stateful_or_behavior_different_helpers_remain_legacy_owned():
    """Do not silently change cache ownership, defaults, or historical CLI hints."""
    assert (
        legacy.resolve_background_workflow
        is not output_paths.resolve_background_workflow
    )
    assert legacy.get_spectrogram_cache is not spectrogram.get_spectrogram_cache
    assert legacy.overlay_spectrogram_panel is not spectrogram.overlay_spectrogram_panel
    assert legacy.get_or_load_drift_rate_results is not (
        drift_rate.get_or_load_drift_rate_results
    )
    assert legacy._fit_failure_warning is not gaussian._fit_failure_warning
    assert legacy._gaussian_diagnostics_row is not (
        gaussian._gaussian_result_diagnostics_row
    )
