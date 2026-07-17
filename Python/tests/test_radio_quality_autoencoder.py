"""Contracts for good-frame-only radio quality autoencoder features."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import solar_toolkit.radio.quality_autoencoder as quality_autoencoder
from solar_toolkit.radio.quality_autoencoder import (
    DEFAULT_MIN_CONFIRMED_GOOD_FRAMES,
    QUALITY_AUTOENCODER_FEATURE_NAMES,
    AutoencoderTrainingConfig,
    QualityAutoencoderDependencyError,
    QualityAutoencoderSample,
    QualityAutoencoderValidationError,
    extract_autoencoder_quality_features,
    prepare_confirmed_good_frames,
    train_good_frame_autoencoder,
)

PYTHON_ROOT = Path(__file__).resolve().parents[1]


def _good_samples(count: int = 12) -> list[QualityAutoencoderSample]:
    y, x = np.mgrid[-1.0:1.0:16j, -1.0:1.0:16j]
    samples = []
    for index in range(count):
        x_offset = (index % 3 - 1) * 0.08
        y_offset = (index % 4 - 1.5) * 0.05
        image = np.exp(-((x - x_offset) ** 2 + (y - y_offset) ** 2) / 0.18)
        image -= 0.08 * np.exp(-((x + 0.35) ** 2 + y**2) / 0.12)
        samples.append(
            QualityAutoencoderSample(
                sample_id=f"good-{index}",
                image=image.astype(np.float32),
                quality_label="good",
                label_source="human",
            )
        )
    return samples


def _small_config() -> AutoencoderTrainingConfig:
    return AutoencoderTrainingConfig(
        min_confirmed_good_frames=8,
        input_size=16,
        latent_dim=4,
        base_channels=2,
        epochs=2,
        batch_size=4,
        learning_rate=2e-3,
        weight_decay=0.0,
        seed=17,
        cpu_threads=1,
    )


def test_import_does_not_eagerly_load_torch():
    code = """
import sys
import solar_toolkit.radio.quality_autoencoder

assert 'torch' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PYTHON_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_only_explicit_human_good_frames_are_selected():
    seed = _good_samples(1)[0]
    selection = prepare_confirmed_good_frames(
        [
            seed,
            replace(
                seed,
                sample_id="automatic-good",
                label_source="automatic",
            ),
            replace(
                seed,
                sample_id="skipped-bad",
                label_source="automatic_on_skip",
                quality_label="bad",
            ),
            replace(seed, sample_id="human-bad", quality_label="bad"),
            replace(
                seed,
                sample_id="human-degraded",
                quality_label="degraded",
            ),
            replace(seed, sample_id="human-uncertain", quality_label="uncertain"),
            replace(
                seed,
                sample_id="pending",
                quality_label=None,
                label_source=None,
            ),
        ]
    )

    assert [sample.sample_id for sample in selection.samples] == [seed.sample_id]
    assert selection.excluded_counts == {
        "automatic_on_skip": 1,
        "non_human": 2,
        "quality_not_good": 3,
    }


def test_default_good_frame_gate_precedes_torch_import():
    assert DEFAULT_MIN_CONFIRMED_GOOD_FRAMES == 500

    with pytest.raises(QualityAutoencoderValidationError, match="at least 500"):
        train_good_frame_autoencoder(_good_samples(4))


def test_missing_torch_has_clear_optional_dependency_error(monkeypatch):
    real_import = quality_autoencoder.import_module

    def fail_torch(name: str):
        if name == "torch":
            raise ModuleNotFoundError("torch")
        return real_import(name)

    monkeypatch.setattr(quality_autoencoder, "import_module", fail_torch)
    with pytest.raises(QualityAutoencoderDependencyError, match="PyTorch"):
        train_good_frame_autoencoder(_good_samples(), config=_small_config())


def test_non_2d_confirmed_good_image_is_rejected():
    invalid = replace(
        _good_samples(1)[0],
        image=np.ones((2, 3, 4), dtype=np.float32),
    )

    with pytest.raises(QualityAutoencoderValidationError, match="2D"):
        prepare_confirmed_good_frames([invalid])


def test_small_cpu_training_is_deterministic_and_emits_features_only():
    pytest.importorskip("torch")
    samples = _good_samples()
    config = _small_config()

    first_bundle = train_good_frame_autoencoder(samples, config=config)
    second_bundle = train_good_frame_autoencoder(samples, config=config)
    first = extract_autoencoder_quality_features(first_bundle, samples[0].image)
    second = extract_autoencoder_quality_features(second_bundle, samples[0].image)

    assert first_bundle.training_sample_count == len(samples)
    assert first_bundle.training_fingerprint == second_bundle.training_fingerprint
    assert first_bundle.epoch_losses == pytest.approx(second_bundle.epoch_losses)
    assert first.as_feature_values() == pytest.approx(second.as_feature_values())
    assert set(first.as_feature_values()) == set(QUALITY_AUTOENCODER_FEATURE_NAMES)
    assert np.isfinite(list(first.as_feature_values().values())).all()
    assert not hasattr(first, "quality_label")
    assert not hasattr(first, "automatic_decision")


def test_autoencoder_features_accept_unseen_image_without_classifying():
    pytest.importorskip("torch")
    bundle = train_good_frame_autoencoder(_good_samples(), config=_small_config())
    striped = np.tile(
        np.where(np.arange(16) % 2 == 0, 1.0, -1.0),
        (16, 1),
    ).astype(np.float32)

    result = extract_autoencoder_quality_features(bundle, striped)

    assert np.isfinite(list(result.as_feature_values().values())).all()
    assert result.reconstruction_p95_abs_error >= 0.0
    assert result.latent_robust_distance >= 0.0
