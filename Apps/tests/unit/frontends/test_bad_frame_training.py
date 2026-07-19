from __future__ import annotations

import json

from solar_toolkit.radio.quality_ml import QualityTrainingConfig

from solar_apps.frontends.radio_bad_frame_review.model_registry import (
    QualityModelRegistry,
)
from solar_apps.frontends.radio_bad_frame_review.training import (
    collect_gold_quality_dataset,
    train_review_quality_model,
)


def _write_review(root, observation_index, *, status="completed"):
    review_id = f"review-{observation_index}"
    directory = root / review_id
    directory.mkdir(parents=True)
    candidates = []
    centers = {"good": -3.0, "degraded": 0.0, "bad": 3.0}
    for label_index, (label, center) in enumerate(centers.items()):
        for repeat in range(4):
            sample_id = f"sample-{observation_index}-{label}-{repeat}"
            candidates.append(
                {
                    "candidate_id": sample_id,
                    "sample_sha256": sample_id,
                    "frequency_mhz": 149.0,
                    "polarization": "RR" if repeat % 2 == 0 else "LL",
                    "time": (
                        f"2025-01-{observation_index:02d}T00:{label_index}{repeat}:00Z"
                    ),
                    "slot_index": label_index * 10 + repeat,
                    "automatic_decision": "good_candidate",
                    "features": {
                        "image_height": 64.0,
                        "image_width": 64.0,
                        "tail_balance": center + repeat * 0.01,
                        "stripe_score": center * 0.8 - repeat * 0.01,
                    },
                    "human_label": {
                        "quality_label": label,
                        "event_tags": ["solar_burst"] if label == "good" else [],
                        "artifact_tags": [],
                        "source": "human",
                    },
                    "ml_prediction": None,
                }
            )
    manifest = {
        "schema_version": 2,
        "review_id": review_id,
        "status": status,
        "created_at": f"2025-01-{observation_index:02d}T00:00:00Z",
        "input": {"root": f"D:/radio/observation-{observation_index}"},
        "candidates": candidates,
    }
    (directory / "review.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def _config():
    return QualityTrainingConfig(
        min_human_samples=24,
        min_observation_batches=4,
        min_samples_per_class=4,
        min_calibration_samples_per_class=2,
        max_iter=60,
        max_leaf_nodes=7,
        min_samples_leaf=2,
        random_state=9,
    )


def test_collector_excludes_skipped_draft_uncertain_and_automatic_labels(tmp_path):
    completed = _write_review(tmp_path, 1)
    _write_review(tmp_path, 2, status="skipped")
    manifest_path = completed / "review.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidates"][0]["human_label"]["quality_label"] = "uncertain"
    manifest["candidates"][1]["human_label"]["source"] = "automatic_on_skip"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    dataset = collect_gold_quality_dataset(tmp_path)

    assert len(dataset.samples) == 10
    assert dataset.excluded_counts == {
        "non_human": 1,
        "review_skipped": 12,
        "uncertain": 1,
    }
    assert all(sample.label_source == "human" for sample in dataset.samples)
    assert all(
        sample.quality_label in {"good", "degraded", "bad"}
        for sample in dataset.samples
    )


def test_training_registers_shadow_candidate_but_never_activates_it(tmp_path):
    reviews = tmp_path / "reviews"
    for observation_index in range(1, 5):
        _write_review(reviews, observation_index)
    registry = QualityModelRegistry(tmp_path / "models")

    result = train_review_quality_model(
        reviews,
        registry,
        model_id="quality-test-v1",
        config=_config(),
    )

    assert result["eligible_human_samples"] == 48
    assert result["model"]["status"] == "candidate"
    assert registry.list_models()["active_model_id"] is None
    bundle = registry.resolve_verified_bundle("quality-test-v1")
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "model.joblib").is_file()
    assert (bundle / "MODEL_CARD.md").is_file()
