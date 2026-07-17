"""Contracts for human-reviewed radio quality machine learning."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from solar_toolkit.radio.quality_ml import (
    QUALITY_LABELS,
    QualityMLDependencyError,
    QualityMLValidationError,
    QualityModelSecurityError,
    QualitySample,
    QualityTrainingConfig,
    evaluate_quality_model,
    load_quality_model_bundle,
    predict_quality_model,
    prepare_human_quality_samples,
    save_quality_model_bundle,
    split_quality_samples,
    train_quality_model,
)

PYTHON_ROOT = Path(__file__).resolve().parents[1]


def _samples() -> list[QualitySample]:
    rows: list[QualitySample] = []
    class_centers = {"good": -3.0, "degraded": 0.0, "bad": 3.0}
    for observation_index in range(4):
        observation_id = f"observation-{observation_index + 1}"
        observed_at = f"2025-01-{observation_index + 1:02d}T00:00:00Z"
        for label_index, label in enumerate(QUALITY_LABELS):
            for repeat in range(4):
                slot_id = f"slot-{label_index}-{repeat}"
                for polarization_index, polarization in enumerate(("RR", "LL")):
                    center = class_centers[label]
                    jitter = observation_index * 0.02 + repeat * 0.01
                    rows.append(
                        QualitySample(
                            sample_id=(f"{observation_id}-{slot_id}-{polarization}"),
                            observation_id=observation_id,
                            slot_id=slot_id,
                            observed_at=observed_at,
                            frequency_mhz=149.0 + 15.0 * polarization_index,
                            polarization=polarization,
                            shape=(256, 256),
                            feature_values={
                                "tail_balance": center + jitter,
                                "stripe_score": center * 0.8 - jitter,
                                "context_missing": 0.0,
                            },
                            quality_label=label,
                            label_source="human",
                            event_tags=(
                                ("solar_event",)
                                if label == "good" and repeat == 0
                                else ()
                            ),
                        )
                    )
    return rows


def _small_config() -> QualityTrainingConfig:
    return QualityTrainingConfig(
        min_human_samples=24,
        min_observation_batches=4,
        min_samples_per_class=4,
        min_calibration_samples_per_class=2,
        max_iter=60,
        max_leaf_nodes=7,
        min_samples_leaf=2,
        random_state=7,
    )


def _require_test_ml_dependencies() -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")


def test_import_does_not_eagerly_load_sklearn_or_joblib():
    code = """
import sys
import solar_toolkit.radio.quality_ml

assert 'sklearn' not in sys.modules
assert 'joblib' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PYTHON_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_only_human_supported_labels_are_selected():
    seed = _samples()[0]
    selection = prepare_human_quality_samples(
        [
            seed,
            replace(
                seed,
                sample_id="uncertain",
                quality_label="uncertain",
            ),
            replace(
                seed,
                sample_id="skipped",
                label_source="automatic_on_skip",
                quality_label="bad",
            ),
            replace(
                seed,
                sample_id="automatic",
                label_source="automatic",
                quality_label="bad",
            ),
            replace(
                seed,
                sample_id="pending",
                label_source=None,
                quality_label=None,
            ),
        ]
    )

    assert selection.samples == (seed,)
    assert selection.excluded_counts == {
        "automatic_on_skip": 1,
        "non_human": 1,
        "uncertain": 1,
        "unlabeled": 1,
    }


def test_unsupported_human_label_is_rejected():
    with pytest.raises(QualityMLValidationError, match="unsupported human"):
        prepare_human_quality_samples([replace(_samples()[0], quality_label="keep")])


def test_latest_observation_is_test_and_second_latest_is_calibration():
    rows = _samples()
    skipped = replace(
        rows[0],
        sample_id="excluded-skipped",
        label_source="automatic_on_skip",
    )
    split = split_quality_samples([*rows, skipped], min_observation_batches=4)

    assert split.test_observation_id == "observation-4"
    assert split.calibration_observation_id == "observation-3"
    assert split.train_observation_ids == ("observation-1", "observation-2")
    assert {sample.observation_id for sample in split.test} == {"observation-4"}
    assert {sample.observation_id for sample in split.calibration} == {"observation-3"}
    assert {sample.observation_id for sample in split.train} == {
        "observation-1",
        "observation-2",
    }
    assert split.excluded_counts == {"automatic_on_skip": 1}

    group_sets = [
        {sample.group_key for sample in partition}
        for partition in (split.train, split.calibration, split.test)
    ]
    assert group_sets[0].isdisjoint(group_sets[1])
    assert group_sets[0].isdisjoint(group_sets[2])
    assert group_sets[1].isdisjoint(group_sets[2])


def test_training_reports_optional_dependency_when_extra_is_absent():
    if importlib.util.find_spec("sklearn") and importlib.util.find_spec("joblib"):
        pytest.skip("quality-ml dependencies are installed")

    with pytest.raises(QualityMLDependencyError, match="quality-ml"):
        train_quality_model(_samples(), config=_small_config())


@pytest.fixture(scope="module")
def trained_bundle():
    _require_test_ml_dependencies()
    return train_quality_model(_samples(), config=_small_config())


def test_hgb_is_calibrated_on_independent_batch_and_evaluated(trained_bundle):
    manifest = trained_bundle.manifest

    assert manifest["model_kind"] == ("hist_gradient_boosting_with_sigmoid_calibration")
    assert manifest["training"]["calibration_observation_id"] == "observation-3"
    assert manifest["training"]["test_observation_id"] == "observation-4"
    assert set(manifest["classes"]) == set(QUALITY_LABELS)
    assert manifest["locked_test"]["sample_count"] == 24
    assert {
        "bad_pr_auc",
        "bad_precision",
        "bad_recall",
        "bad_f2",
        "bad_mcc",
        "false_positives_per_10000_good",
        "event_false_reject_rate",
        "ood_fraction",
    } <= set(manifest["locked_test"]["metrics"])


def test_prediction_probabilities_and_metadata_ood(trained_bundle):
    known = replace(
        _samples()[0],
        sample_id="inference-known",
        quality_label=None,
        label_source=None,
    )
    prediction = predict_quality_model(trained_bundle, known)

    assert not prediction.ood
    assert set(prediction.probabilities) == set(QUALITY_LABELS)
    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)
    assert prediction.predicted_label in QUALITY_LABELS
    assert prediction.top_anomalous_features

    unknown = replace(
        known,
        sample_id="inference-ood",
        shape=(512, 512),
        frequency_mhz=999.0,
    )
    ood_prediction = predict_quality_model(trained_bundle, unknown)

    assert ood_prediction.ood
    assert set(ood_prediction.ood_reasons) >= {"unseen_shape", "unseen_frequency"}
    assert sum(ood_prediction.probabilities.values()) == pytest.approx(1.0)


def test_locked_test_metrics_use_only_human_labels(trained_bundle):
    test_rows = split_quality_samples(_samples(), min_observation_batches=4).test
    automatic = replace(
        test_rows[0],
        sample_id="automatic-test-row",
        label_source="automatic_on_skip",
        quality_label="bad",
    )

    evaluation = evaluate_quality_model(trained_bundle, [*test_rows, automatic])

    assert evaluation.sample_count == len(test_rows)
    assert sum(evaluation.class_support.values()) == len(test_rows)
    assert np.isfinite(evaluation.metrics["bad_pr_auc"])


def test_bundle_round_trip_requires_registry_hash_and_rejects_tampering(
    trained_bundle,
    tmp_path: Path,
):
    destination = tmp_path / "quality-model"
    saved = save_quality_model_bundle(trained_bundle, destination)
    loaded = load_quality_model_bundle(
        destination,
        expected_manifest_sha256=saved.manifest_sha256,
    )

    sample = replace(
        _samples()[0],
        sample_id="round-trip",
        quality_label=None,
        label_source=None,
    )
    before = predict_quality_model(trained_bundle, sample)
    after = predict_quality_model(loaded, sample)
    assert after.probabilities == pytest.approx(before.probabilities)

    model_path = destination / "model.joblib"
    model_path.write_bytes(model_path.read_bytes() + b"tamper")
    with pytest.raises(QualityModelSecurityError, match="artifact SHA256"):
        load_quality_model_bundle(
            destination,
            expected_manifest_sha256=saved.manifest_sha256,
        )


def test_manifest_hash_is_checked_before_deserialization(tmp_path: Path):
    bundle_dir = tmp_path / "untrusted"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(QualityModelSecurityError, match="manifest SHA256"):
        load_quality_model_bundle(
            bundle_dir,
            expected_manifest_sha256="0" * 64,
        )
