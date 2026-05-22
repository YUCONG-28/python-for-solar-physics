"""Configuration tests for AIA difference compatibility wrappers.

These tests do not read FITS files, call the real AIA processor, or generate
plot outputs. They only verify that legacy defaults are mapped into the shared
processor configuration.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_legacy_wrapper(module_name: str, filename: str):
    wrapper_path = REPO_ROOT / "legacy" / "scripts" / "aia_hmi" / filename
    spec = spec_from_file_location(module_name, wrapper_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base_wrapper = _load_legacy_wrapper(
    "legacy_sdo_aia_base_difference",
    "sdo_aia_base_difference.py",
)
running_wrapper = _load_legacy_wrapper(
    "legacy_sdo_aia_running_difference",
    "sdo_aia_running_difference.py",
)


class FakeConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for name, value in kwargs.items():
            setattr(self, name, value)


def test_base_difference_wrapper_builds_legacy_config_kwargs():
    kwargs = base_wrapper.build_legacy_config_kwargs()

    assert base_wrapper.LEGACY_DEFAULTS["wavelength"] == 131
    assert base_wrapper.LEGACY_DEFAULTS["roi_bounds"] == (180, 520, -340, 20)
    assert base_wrapper.LEGACY_DEFAULTS["difference_vmin"] == -888
    assert base_wrapper.LEGACY_DEFAULTS["difference_vmax"] == 888
    assert base_wrapper.LEGACY_DEFAULTS["start_idx"] == 99
    assert base_wrapper.LEGACY_DEFAULTS["end_idx"] == 200

    assert kwargs["difference_method"] == "base"
    assert kwargs["multi_band_wavelengths"] == (131,)
    assert kwargs["difference_wavelengths"] == (131,)
    assert kwargs["roi_bounds"] == (180, 520, -340, 20)
    assert kwargs["start_idx"] == 99
    assert kwargs["end_idx"] == 200
    assert kwargs["difference_norm_mode"] == "fixed"
    assert kwargs["difference_vmin"] == -888.0
    assert kwargs["difference_vmax"] == 888.0
    assert kwargs["use_band_subdirs"] is False
    assert kwargs["difference_derotate"] is False
    assert kwargs["draw_original"] is False
    assert kwargs["draw_difference"] is True


def test_running_difference_wrapper_builds_legacy_config_kwargs():
    kwargs = running_wrapper.build_legacy_config_kwargs()

    assert running_wrapper.LEGACY_DEFAULTS["wavelength"] == 94
    assert running_wrapper.LEGACY_DEFAULTS["roi_bounds"] == (600, 1210, -280, 100)
    assert running_wrapper.LEGACY_DEFAULTS["difference_vmin"] == -777
    assert running_wrapper.LEGACY_DEFAULTS["difference_vmax"] == 777
    assert running_wrapper.LEGACY_DEFAULTS["start_idx"] == 150
    assert running_wrapper.LEGACY_DEFAULTS["end_idx"] == 450

    assert kwargs["difference_method"] == "running"
    assert kwargs["multi_band_wavelengths"] == (94,)
    assert kwargs["difference_wavelengths"] == (94,)
    assert kwargs["roi_bounds"] == (600, 1210, -280, 100)
    assert kwargs["start_idx"] == 150
    assert kwargs["end_idx"] == 450
    assert kwargs["difference_norm_mode"] == "fixed"
    assert kwargs["difference_vmin"] == -777.0
    assert kwargs["difference_vmax"] == 777.0
    assert kwargs["use_band_subdirs"] is False
    assert kwargs["difference_derotate"] is False
    assert kwargs["draw_original"] is False
    assert kwargs["draw_difference"] is True


def test_build_legacy_config_uses_loaded_processor(monkeypatch):
    base_calls = []

    def fake_process(cfg):
        base_calls.append(cfg)

    monkeypatch.setattr(
        base_wrapper,
        "_load_processor",
        lambda: (FakeConfig, fake_process),
    )

    cfg = base_wrapper.build_legacy_config()

    assert isinstance(cfg, FakeConfig)
    assert cfg.difference_method == "base"
    assert base_calls == []


def test_wrapper_main_delegates_to_processor_without_real_fits(monkeypatch):
    base_calls = []
    running_calls = []

    def fake_base_process(cfg):
        base_calls.append(cfg)

    def fake_running_process(cfg):
        running_calls.append(cfg)

    monkeypatch.setattr(
        base_wrapper,
        "_load_processor",
        lambda: (FakeConfig, fake_base_process),
    )
    monkeypatch.setattr(
        running_wrapper,
        "_load_processor",
        lambda: (FakeConfig, fake_running_process),
    )
    base_wrapper.main()
    running_wrapper.main()

    assert len(base_calls) == 1
    assert base_calls[0].difference_method == "base"
    assert len(running_calls) == 1
    assert running_calls[0].difference_method == "running"


def test_imported_wrappers_do_not_auto_run_processing():
    assert callable(base_wrapper.build_legacy_config)
    assert callable(base_wrapper.build_legacy_config_kwargs)
    assert callable(running_wrapper.build_legacy_config)
    assert callable(running_wrapper.build_legacy_config_kwargs)
