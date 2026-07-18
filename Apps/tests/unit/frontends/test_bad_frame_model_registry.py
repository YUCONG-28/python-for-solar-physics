from __future__ import annotations

import hashlib
import json

import pytest

from solar_apps.frontends.radio_bad_frame_review.model_registry import (
    ModelRegistryError,
    PromotionGateError,
    QualityModelRegistry,
)
from solar_apps.frontends.radio_bad_frame_review.server import create_app


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metrics(**overrides):
    values = {
        "good_false_rejection_rate": 0.004,
        "event_false_rejection_rate": 0.0,
        "bad_recall": 0.94,
        "locked_test_event_rejections": 0,
        "outperforms_rule_at_constraint": True,
    }
    values.update(overrides)
    return values


def _bundle(root, name="quality-v1"):
    bundle = root / name
    bundle.mkdir(parents=True)
    model = bundle / "model.joblib"
    model.write_bytes(b"safe-test-placeholder")
    (bundle / "MODEL_CARD.md").write_text("# Test model\n", encoding="utf-8")
    manifest = {
        "feature_schema_version": 1,
        "artifacts": {
            "model": {"path": "model.joblib", "sha256": _sha(model)},
        },
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundle


def test_candidate_is_never_active_until_manual_publish(tmp_path):
    registry = QualityModelRegistry(tmp_path / "models")
    bundle = _bundle(registry.root)

    entry = registry.register_candidate(
        "quality-v1",
        bundle,
        metrics=_metrics(),
        feature_schema_version=1,
        data_fingerprint="sha256:test",
    )

    assert entry["status"] == "candidate"
    assert registry.list_models()["active_model_id"] is None
    with pytest.raises(PromotionGateError, match="acknowledge"):
        registry.publish("quality-v1")
    published = registry.publish("quality-v1", acknowledge_evaluation=True)
    assert published["status"] == "published"
    assert registry.resolve_verified_bundle() == bundle.resolve()


@pytest.mark.parametrize(
    "metrics, message",
    [
        (_metrics(good_false_rejection_rate=0.006), "good-frame"),
        (_metrics(event_false_rejection_rate=0.006), "science-event"),
        (_metrics(bad_recall=0.89), "below 90%"),
        (_metrics(locked_test_event_rejections=1), "science event"),
        (_metrics(outperforms_rule_at_constraint=False), "does not beat"),
    ],
)
def test_promotion_gates_are_fail_closed(tmp_path, metrics, message):
    registry = QualityModelRegistry(tmp_path / "models")
    bundle = _bundle(registry.root)
    registry.register_candidate(
        "quality-v1",
        bundle,
        metrics=metrics,
        feature_schema_version=1,
        data_fingerprint="sha256:test",
    )

    with pytest.raises(PromotionGateError, match=message):
        registry.publish("quality-v1", acknowledge_evaluation=True)

    assert registry.list_models()["active_model_id"] is None


def test_bundle_tampering_is_rejected_before_deserialization(tmp_path):
    registry = QualityModelRegistry(tmp_path / "models")
    bundle = _bundle(registry.root)
    registry.register_candidate(
        "quality-v1",
        bundle,
        metrics=_metrics(),
        feature_schema_version=1,
        data_fingerprint="sha256:test",
    )
    (bundle / "model.joblib").write_bytes(b"tampered")

    with pytest.raises(ModelRegistryError, match="artifact SHA256"):
        registry.resolve_verified_bundle("quality-v1")


def test_bundle_must_stay_inside_registry_root(tmp_path):
    registry = QualityModelRegistry(tmp_path / "models")
    outside = _bundle(tmp_path / "outside")

    with pytest.raises(ModelRegistryError, match="escapes"):
        registry.register_candidate(
            "outside",
            outside,
            metrics=_metrics(),
            feature_schema_version=1,
            data_fingerprint="sha256:test",
        )


def test_manifest_artifact_cannot_escape_bundle(tmp_path):
    registry = QualityModelRegistry(tmp_path / "models")
    bundle = _bundle(registry.root)
    outside = registry.root / "outside.joblib"
    outside.write_bytes(b"outside")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["model"] = {
        "path": "../outside.joblib",
        "sha256": _sha(outside),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ModelRegistryError, match="escapes model package"):
        registry.register_candidate(
            "quality-v1",
            bundle,
            metrics=_metrics(),
            feature_schema_version=1,
            data_fingerprint="sha256:test",
        )


def test_publishing_a_new_model_retires_the_previous_model(tmp_path):
    registry = QualityModelRegistry(tmp_path / "models")
    for name in ("quality-v1", "quality-v2"):
        bundle = _bundle(registry.root, name)
        registry.register_candidate(
            name,
            bundle,
            metrics=_metrics(),
            feature_schema_version=1,
            data_fingerprint=f"sha256:{name}",
        )
        registry.publish(name, acknowledge_evaluation=True)

    state = registry.list_models()
    assert state["active_model_id"] == "quality-v2"
    assert state["models"]["quality-v1"]["status"] == "retired"
    assert state["models"]["quality-v2"]["status"] == "published"


def test_corrupt_published_model_falls_back_to_rules_and_manual_review(tmp_path):
    registry = QualityModelRegistry(tmp_path / "models")
    bundle = _bundle(registry.root)
    registry.register_candidate(
        "quality-v1",
        bundle,
        metrics=_metrics(),
        feature_schema_version=1,
        data_fingerprint="sha256:test",
    )
    registry.publish("quality-v1", acknowledge_evaluation=True)
    (bundle / "model.joblib").write_bytes(b"tampered")

    app = create_app(
        [tmp_path],
        output_root=tmp_path / "reviews",
        stop_on_client_close=False,
        model_registry=registry,
    )
    config = app.test_client().get("/api/config").get_json()

    assert config["active_model_id"] is None
    assert "Published model unavailable" in config["model_warning"]
