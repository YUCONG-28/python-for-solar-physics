"""Human-reviewed machine learning for radio-image quality assessment.

The module deliberately keeps ``scikit-learn`` and ``joblib`` optional.  They
are imported only by training, evaluation, persistence, or inference calls;
the public data-selection and split helpers remain usable in a base install.

Automatic rule labels are never treated as supervision here.  Training data
must have an explicit ``human`` source and one of the three supported quality
labels: ``good``, ``degraded``, or ``bad``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import platform
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "QUALITY_FEATURE_SCHEMA_VERSION",
    "QUALITY_LABELS",
    "QUALITY_ML_SCHEMA_VERSION",
    "QualityBundleSaveResult",
    "QualityDatasetSplit",
    "QualityEvaluation",
    "QualityMLDependencyError",
    "QualityMLValidationError",
    "QualityModelBundle",
    "QualityModelCompatibilityError",
    "QualityModelPrediction",
    "QualityModelSecurityError",
    "QualitySample",
    "QualitySampleSelection",
    "QualityTrainingConfig",
    "evaluate_quality_model",
    "load_quality_model_bundle",
    "predict_quality_model",
    "prepare_human_quality_samples",
    "save_quality_model_bundle",
    "split_quality_samples",
    "train_quality_model",
]

QUALITY_LABELS = ("good", "degraded", "bad")
QUALITY_ML_SCHEMA_VERSION = 1
QUALITY_FEATURE_SCHEMA_VERSION = 1
_MODEL_KIND = "hist_gradient_boosting_with_sigmoid_calibration"
_MANIFEST_FILENAME = "manifest.json"
_MODEL_FILENAME = "model.joblib"
_SHA256_HEX_LENGTH = 64


class QualityMLDependencyError(RuntimeError):
    """Raised when the optional machine-learning dependencies are unavailable."""


class QualityMLValidationError(ValueError):
    """Raised when samples or split policy violate the training contract."""


class QualityModelSecurityError(RuntimeError):
    """Raised before deserialization when a bundle fails integrity checks."""


class QualityModelCompatibilityError(RuntimeError):
    """Raised when a verified bundle is incompatible with the current runtime."""


@dataclass(frozen=True)
class QualitySample:
    """One feature row plus optional human-review metadata.

    ``observed_at`` must be an ISO-8601 value (or ``datetime``) when samples are
    split.  ``observation_id`` identifies a complete observing batch, while
    ``slot_id`` identifies synchronized frequency/polarization frames inside
    that batch.
    """

    sample_id: str
    observation_id: str
    slot_id: str
    observed_at: str | datetime | None
    frequency_mhz: float | None
    polarization: str | None
    shape: tuple[int, int] | None
    feature_values: Mapping[str, float]
    quality_label: str | None = None
    label_source: str | None = None
    event_tags: tuple[str, ...] = ()

    @property
    def group_key(self) -> str:
        """Return the indivisible observation/slot group key."""

        return f"{self.observation_id}\x1f{self.slot_id}"


@dataclass(frozen=True)
class QualitySampleSelection:
    """Human-reviewed samples and an auditable exclusion summary."""

    samples: tuple[QualitySample, ...]
    excluded_counts: Mapping[str, int]


@dataclass(frozen=True)
class QualityDatasetSplit:
    """Chronological batch split with observation/slot groups kept intact."""

    train: tuple[QualitySample, ...]
    calibration: tuple[QualitySample, ...]
    test: tuple[QualitySample, ...]
    train_observation_ids: tuple[str, ...]
    calibration_observation_id: str
    test_observation_id: str
    excluded_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityTrainingConfig:
    """Conservative defaults for supervised radio-quality training."""

    min_human_samples: int = 1000
    min_observation_batches: int = 4
    min_samples_per_class: int = 20
    min_calibration_samples_per_class: int = 5
    learning_rate: float = 0.05
    max_iter: int = 200
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 20
    l2_regularization: float = 1.0
    random_state: int = 0
    ood_missing_fraction: float = 0.25


@dataclass(frozen=True)
class QualityModelBundle:
    """A calibrated estimator and its JSON-safe reproducibility manifest."""

    estimator: Any
    manifest: Mapping[str, Any]


@dataclass(frozen=True)
class QualityModelPrediction:
    """Calibrated probabilities plus input-domain and anomaly diagnostics."""

    probabilities: Mapping[str, float]
    predicted_label: str
    ood: bool
    ood_reasons: tuple[str, ...]
    top_anomalous_features: tuple[str, ...]


@dataclass(frozen=True)
class QualityEvaluation:
    """Locked-test metrics for human-reviewed samples."""

    sample_count: int
    metrics: Mapping[str, float]
    class_support: Mapping[str, int]


@dataclass(frozen=True)
class QualityBundleSaveResult:
    """Integrity values that the trusted Local registry must retain."""

    directory: Path
    manifest_sha256: str
    model_sha256: str


class _IndependentSigmoidEstimator:
    """Frozen base estimator plus one-vs-rest sigmoid calibration models."""

    def __init__(self, base_estimator: Any, classes: Sequence[str], calibrators):
        self.base_estimator = base_estimator
        self.classes_ = np.asarray(tuple(classes), dtype=object)
        self.calibrators = tuple(calibrators)
        self.n_features_in_ = getattr(base_estimator, "n_features_in_", None)

    def predict_proba(self, values: np.ndarray) -> np.ndarray:
        scores = np.asarray(self.base_estimator.decision_function(values), dtype=float)
        if scores.ndim == 1:
            scores = np.column_stack((-scores, scores))
        if scores.shape[1] != len(self.classes_):
            raise QualityModelCompatibilityError(
                "base estimator returned an unexpected decision score shape"
            )
        calibrated = np.column_stack(
            [
                calibrator.predict_proba(scores[:, [index]])[:, 1]
                for index, calibrator in enumerate(self.calibrators)
            ]
        )
        totals = calibrated.sum(axis=1, keepdims=True)
        invalid = ~np.isfinite(totals[:, 0]) | (totals[:, 0] <= 0.0)
        if np.any(invalid):
            calibrated[invalid, :] = 1.0
            totals = calibrated.sum(axis=1, keepdims=True)
        return calibrated / totals


def prepare_human_quality_samples(
    samples: Iterable[QualitySample | Mapping[str, Any]],
) -> QualitySampleSelection:
    """Keep only explicit human ``good/degraded/bad`` labels.

    Pending, uncertain, skipped, and other automatic rows are excluded and
    counted.  An unsupported *human* label is rejected instead of silently
    changing its meaning.
    """

    accepted: list[QualitySample] = []
    excluded: Counter[str] = Counter()
    seen_ids: set[str] = set()

    for raw_sample in samples:
        sample = _coerce_sample(raw_sample)
        label = _normalize_text(sample.quality_label)
        source = _normalize_text(sample.label_source)

        if source == "automatic_on_skip":
            excluded["automatic_on_skip"] += 1
            continue
        if label == "uncertain":
            excluded["uncertain"] += 1
            continue
        if not label:
            excluded["unlabeled"] += 1
            continue
        if source != "human":
            excluded["non_human"] += 1
            continue
        if label not in QUALITY_LABELS:
            raise QualityMLValidationError(
                f"unsupported human quality label {sample.quality_label!r}"
            )
        if sample.sample_id in seen_ids:
            raise QualityMLValidationError(
                f"duplicate human sample_id {sample.sample_id!r}"
            )
        _validate_sample_identity(sample)
        normalized_features = {
            str(key): value for key, value in sample.feature_values.items()
        }
        if len(normalized_features) != len(sample.feature_values):
            raise QualityMLValidationError(
                f"sample {sample.sample_id!r} has colliding feature names"
            )
        seen_ids.add(sample.sample_id)
        accepted.append(
            replace(
                sample,
                quality_label=label,
                label_source="human",
                feature_values=normalized_features,
                polarization=(
                    str(sample.polarization).strip().upper()
                    if sample.polarization not in (None, "")
                    else None
                ),
            )
        )

    return QualitySampleSelection(
        samples=tuple(accepted),
        excluded_counts=dict(sorted(excluded.items())),
    )


def split_quality_samples(
    samples: Iterable[QualitySample | Mapping[str, Any]],
    *,
    min_observation_batches: int = 4,
) -> QualityDatasetSplit:
    """Use the newest batch for test and the second newest for calibration.

    All older observation batches form the training set.  Consequently every
    ``observation_id + slot_id`` group, including all frequencies and
    polarizations in that slot, is kept in exactly one partition.
    """

    if min_observation_batches < 3:
        raise QualityMLValidationError("min_observation_batches must be at least 3")
    selection = prepare_human_quality_samples(samples)
    if not selection.samples:
        raise QualityMLValidationError("no eligible human-reviewed samples")

    by_observation: dict[str, list[QualitySample]] = {}
    observation_times: dict[str, float] = {}
    for sample in selection.samples:
        timestamp = _observation_timestamp(sample)
        by_observation.setdefault(sample.observation_id, []).append(sample)
        observation_times[sample.observation_id] = max(
            timestamp,
            observation_times.get(sample.observation_id, -math.inf),
        )

    if len(by_observation) < min_observation_batches:
        raise QualityMLValidationError(
            "supervised training requires at least "
            f"{min_observation_batches} observation batches; got "
            f"{len(by_observation)}"
        )

    ordered_ids = sorted(
        by_observation,
        key=lambda item: (observation_times[item], item),
    )
    test_id = ordered_ids[-1]
    calibration_id = ordered_ids[-2]
    train_ids = tuple(ordered_ids[:-2])

    train = tuple(
        sample
        for observation_id in train_ids
        for sample in by_observation[observation_id]
    )
    calibration = tuple(by_observation[calibration_id])
    test = tuple(by_observation[test_id])
    _assert_disjoint_groups(train, calibration, test)

    return QualityDatasetSplit(
        train=train,
        calibration=calibration,
        test=test,
        train_observation_ids=train_ids,
        calibration_observation_id=calibration_id,
        test_observation_id=test_id,
        excluded_counts=selection.excluded_counts,
    )


def train_quality_model(
    samples: Iterable[QualitySample | Mapping[str, Any]],
    *,
    config: QualityTrainingConfig | None = None,
) -> QualityModelBundle:
    """Train HGB, calibrate on the next-newest batch, and lock-test newest.

    The function never derives labels from rule decisions.  It validates and
    chronologically partitions explicit human labels before importing the
    optional machine-learning dependencies.
    """

    cfg = config or QualityTrainingConfig()
    _validate_training_config(cfg)
    split = split_quality_samples(
        samples,
        min_observation_batches=cfg.min_observation_batches,
    )
    all_samples = split.train + split.calibration + split.test
    if len(all_samples) < cfg.min_human_samples:
        raise QualityMLValidationError(
            f"at least {cfg.min_human_samples} eligible human samples are required; "
            f"got {len(all_samples)}"
        )

    feature_names = _feature_names(all_samples)
    x_train = _feature_matrix(split.train, feature_names)
    y_train = _quality_labels(split.train)
    x_calibration = _feature_matrix(split.calibration, feature_names)
    y_calibration = _quality_labels(split.calibration)
    _require_class_counts(
        y_train,
        cfg.min_samples_per_class,
        partition="training",
    )
    _require_class_counts(
        y_calibration,
        cfg.min_calibration_samples_per_class,
        partition="calibration",
    )

    dependencies = _require_ml_dependencies()
    classifier_type = dependencies["HistGradientBoostingClassifier"]
    base_estimator = classifier_type(
        loss="log_loss",
        learning_rate=cfg.learning_rate,
        max_iter=cfg.max_iter,
        max_leaf_nodes=cfg.max_leaf_nodes,
        min_samples_leaf=cfg.min_samples_leaf,
        l2_regularization=cfg.l2_regularization,
        early_stopping=False,
        class_weight="balanced",
        random_state=cfg.random_state,
    )
    base_estimator.fit(x_train, y_train)
    estimator = _fit_independent_sigmoid_calibrator(
        base_estimator,
        x_calibration,
        y_calibration,
        dependencies,
    )
    classes = tuple(str(value) for value in estimator.classes_)
    if set(classes) != set(QUALITY_LABELS):
        raise QualityMLValidationError(
            f"calibrated estimator classes {classes!r} do not match {QUALITY_LABELS!r}"
        )

    fingerprint = _training_fingerprint(split, feature_names)
    runtime = _runtime_versions(dependencies)
    reference = _training_reference(split.train, feature_names)
    manifest: dict[str, Any] = {
        "schema_version": QUALITY_ML_SCHEMA_VERSION,
        "feature_schema_version": QUALITY_FEATURE_SCHEMA_VERSION,
        "model_kind": _MODEL_KIND,
        "model_id": f"radio-quality-hgb-{fingerprint[:16]}",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "feature_names": list(feature_names),
        "classes": list(classes),
        "runtime": runtime,
        "config": asdict(cfg),
        "training": {
            "data_fingerprint": fingerprint,
            "eligible_sample_count": len(all_samples),
            "excluded_counts": dict(split.excluded_counts),
            "train_observation_ids": list(split.train_observation_ids),
            "calibration_observation_id": split.calibration_observation_id,
            "test_observation_id": split.test_observation_id,
            "partition_counts": {
                "train": len(split.train),
                "calibration": len(split.calibration),
                "test": len(split.test),
            },
        },
        "domain": {
            **_training_domain(split.train, cfg),
            "feature_reference": reference,
        },
    }
    bundle = QualityModelBundle(estimator=estimator, manifest=manifest)
    evaluation = evaluate_quality_model(bundle, split.test)
    manifest["locked_test"] = {
        "sample_count": evaluation.sample_count,
        "metrics": _json_safe(evaluation.metrics),
        "class_support": dict(evaluation.class_support),
    }
    return QualityModelBundle(estimator=estimator, manifest=manifest)


def predict_quality_model(
    bundle: QualityModelBundle,
    sample: QualitySample | Mapping[str, Any],
) -> QualityModelPrediction:
    """Return probabilities without modifying any rule or human quality flag."""

    _validate_in_memory_bundle(bundle)
    feature_sample = _coerce_sample(sample)
    feature_names = tuple(str(item) for item in bundle.manifest["feature_names"])
    matrix = _feature_matrix((feature_sample,), feature_names)
    probabilities_array = np.asarray(
        bundle.estimator.predict_proba(matrix),
        dtype=np.float64,
    )
    if probabilities_array.shape != (1, len(bundle.estimator.classes_)):
        raise QualityModelCompatibilityError(
            "estimator returned an unexpected probability shape"
        )
    estimator_classes = tuple(str(item) for item in bundle.estimator.classes_)
    probabilities = {
        label: float(probabilities_array[0, estimator_classes.index(label)])
        for label in QUALITY_LABELS
    }
    if not np.isfinite(list(probabilities.values())).all():
        raise QualityModelCompatibilityError(
            "estimator returned non-finite probabilities"
        )
    total = float(sum(probabilities.values()))
    if total <= 0:
        raise QualityModelCompatibilityError(
            "estimator returned zero total probability"
        )
    probabilities = {key: value / total for key, value in probabilities.items()}

    ood_reasons = _ood_reasons(bundle.manifest, feature_sample, matrix[0])
    predicted_label = max(QUALITY_LABELS, key=probabilities.__getitem__)
    return QualityModelPrediction(
        probabilities=probabilities,
        predicted_label=predicted_label,
        ood=bool(ood_reasons),
        ood_reasons=tuple(ood_reasons),
        top_anomalous_features=_top_anomalous_features(
            bundle.manifest,
            feature_names,
            matrix[0],
        ),
    )


def evaluate_quality_model(
    bundle: QualityModelBundle,
    samples: Iterable[QualitySample | Mapping[str, Any]],
) -> QualityEvaluation:
    """Evaluate calibrated bad-frame discrimination on human labels only."""

    selection = prepare_human_quality_samples(samples)
    if not selection.samples:
        raise QualityMLValidationError("no eligible human samples to evaluate")
    dependencies = _require_ml_dependencies()
    metrics_module = dependencies["metrics"]

    predictions = [
        predict_quality_model(bundle, sample) for sample in selection.samples
    ]
    true_labels = np.asarray(_quality_labels(selection.samples), dtype=object)
    predicted_labels = np.asarray(
        [prediction.predicted_label for prediction in predictions],
        dtype=object,
    )
    true_bad = true_labels == "bad"
    predicted_bad = predicted_labels == "bad"
    bad_probabilities = np.asarray(
        [prediction.probabilities["bad"] for prediction in predictions],
        dtype=float,
    )

    if np.unique(true_bad).size == 2:
        pr_auc = float(
            metrics_module.average_precision_score(true_bad, bad_probabilities)
        )
        mcc = float(metrics_module.matthews_corrcoef(true_bad, predicted_bad))
    else:
        pr_auc = math.nan
        mcc = math.nan
    precision = float(
        metrics_module.precision_score(true_bad, predicted_bad, zero_division=0)
    )
    recall = float(
        metrics_module.recall_score(true_bad, predicted_bad, zero_division=0)
    )
    f2 = float(
        metrics_module.fbeta_score(true_bad, predicted_bad, beta=2, zero_division=0)
    )

    good_mask = true_labels == "good"
    false_positive_count = int(np.sum(good_mask & predicted_bad))
    good_count = int(np.sum(good_mask))
    good_false_rejection_rate = (
        float(false_positive_count) / float(good_count) if good_count else math.nan
    )
    false_positives_per_10000_good = (
        float(false_positive_count) * 10000.0 / float(good_count)
        if good_count
        else math.nan
    )
    event_mask = np.asarray(
        [
            bool(sample.event_tags) and sample.quality_label in {"good", "degraded"}
            for sample in selection.samples
        ],
        dtype=bool,
    )
    event_count = int(np.sum(event_mask))
    event_false_rejection_count = int(np.sum(event_mask & predicted_bad))
    event_false_reject_rate = (
        float(event_false_rejection_count) / float(event_count)
        if event_count
        else math.nan
    )
    ood_fraction = float(np.mean([prediction.ood for prediction in predictions]))

    return QualityEvaluation(
        sample_count=len(selection.samples),
        metrics={
            "bad_pr_auc": pr_auc,
            "bad_precision": precision,
            "bad_recall": recall,
            "bad_f2": f2,
            "bad_mcc": mcc,
            "good_false_rejection_rate": good_false_rejection_rate,
            "false_positives_per_10000_good": false_positives_per_10000_good,
            "event_false_reject_rate": event_false_reject_rate,
            "event_false_rejection_rate": event_false_reject_rate,
            "event_false_rejection_count": float(event_false_rejection_count),
            "event_sample_count": float(event_count),
            "ood_fraction": ood_fraction,
        },
        class_support={
            label: int(np.sum(true_labels == label)) for label in QUALITY_LABELS
        },
    )


def save_quality_model_bundle(
    bundle: QualityModelBundle,
    directory: str | Path,
) -> QualityBundleSaveResult:
    """Atomically save a trusted local bundle and return its registry hash."""

    _validate_in_memory_bundle(bundle)
    dependencies = _require_ml_dependencies()
    _assert_runtime_compatible(bundle.manifest, dependencies)
    destination = Path(directory)
    if destination.exists():
        raise FileExistsError(f"model bundle destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        model_path = temporary / _MODEL_FILENAME
        dependencies["joblib"].dump(bundle.estimator, model_path, compress=3)
        model_sha256 = _sha256_file(model_path)
        manifest = dict(bundle.manifest)
        manifest["artifacts"] = {
            "model": {
                "filename": _MODEL_FILENAME,
                "sha256": model_sha256,
            }
        }
        _validate_manifest_structure(manifest)
        manifest_bytes = _canonical_json_bytes(manifest)
        manifest_path = temporary / _MANIFEST_FILENAME
        manifest_path.write_bytes(manifest_bytes)
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return QualityBundleSaveResult(
        directory=destination,
        manifest_sha256=manifest_sha256,
        model_sha256=model_sha256,
    )


def load_quality_model_bundle(
    directory: str | Path,
    *,
    expected_manifest_sha256: str,
) -> QualityModelBundle:
    """Verify both hashes and runtime compatibility before ``joblib.load``.

    The expected manifest digest must come from a trusted Local model registry;
    accepting a digest stored beside an untrusted pickle would not establish a
    trust boundary.
    """

    expected_digest = _validated_sha256(
        expected_manifest_sha256,
        field_name="expected_manifest_sha256",
    )
    root = Path(directory).resolve(strict=True)
    if not root.is_dir():
        raise QualityModelSecurityError(f"model bundle is not a directory: {root}")
    manifest_path = root / _MANIFEST_FILENAME
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise QualityModelSecurityError("model bundle manifest is missing") from exc
    actual_manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if not hmac.compare_digest(expected_digest, actual_manifest_sha256):
        raise QualityModelSecurityError("model bundle manifest SHA256 mismatch")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualityModelSecurityError(
            "model bundle manifest is invalid JSON"
        ) from exc
    _validate_manifest_structure(manifest)

    model_record = manifest["artifacts"]["model"]
    model_filename = str(model_record["filename"])
    if model_filename != _MODEL_FILENAME or Path(model_filename).name != model_filename:
        raise QualityModelSecurityError("model artifact path is not allowed")
    try:
        model_path = (root / model_filename).resolve(strict=True)
    except OSError as exc:
        raise QualityModelSecurityError("model artifact is missing") from exc
    if model_path.parent != root:
        raise QualityModelSecurityError("model artifact escapes its bundle directory")
    expected_model_sha256 = _validated_sha256(
        model_record["sha256"],
        field_name="model_sha256",
    )
    actual_model_sha256 = _sha256_file(model_path)
    if not hmac.compare_digest(expected_model_sha256, actual_model_sha256):
        raise QualityModelSecurityError("model artifact SHA256 mismatch")

    dependencies = _require_ml_dependencies()
    _assert_runtime_compatible(manifest, dependencies)

    estimator = dependencies["joblib"].load(model_path)
    classes = tuple(str(item) for item in getattr(estimator, "classes_", ()))
    if classes != tuple(str(item) for item in manifest["classes"]):
        raise QualityModelCompatibilityError(
            "deserialized estimator classes do not match manifest"
        )
    if not callable(getattr(estimator, "predict_proba", None)):
        raise QualityModelCompatibilityError(
            "deserialized estimator does not provide predict_proba"
        )
    return QualityModelBundle(estimator=estimator, manifest=manifest)


def _coerce_sample(raw: QualitySample | Mapping[str, Any]) -> QualitySample:
    if isinstance(raw, QualitySample):
        return raw
    if not isinstance(raw, Mapping):
        raise TypeError("quality samples must be QualitySample or mapping objects")
    features = raw.get("feature_values", raw.get("features"))
    if not isinstance(features, Mapping):
        raise QualityMLValidationError("sample feature_values must be a mapping")
    shape_value = raw.get("shape")
    shape = None
    if shape_value not in (None, ""):
        try:
            shape = tuple(int(value) for value in shape_value)
        except (TypeError, ValueError) as exc:
            raise QualityMLValidationError(
                "sample shape must contain two integers"
            ) from exc
        if len(shape) != 2:
            raise QualityMLValidationError("sample shape must contain two integers")
    event_tags_value = raw.get("event_tags", ())
    if isinstance(event_tags_value, str):
        event_tags = (event_tags_value,) if event_tags_value else ()
    else:
        event_tags = tuple(str(item) for item in (event_tags_value or ()))
    return QualitySample(
        sample_id=str(raw.get("sample_id", "")).strip(),
        observation_id=str(raw.get("observation_id", "")).strip(),
        slot_id=str(raw.get("slot_id", "")).strip(),
        observed_at=raw.get("observed_at", raw.get("time")),
        frequency_mhz=_optional_float(raw.get("frequency_mhz")),
        polarization=(
            str(raw.get("polarization")).strip()
            if raw.get("polarization") not in (None, "")
            else None
        ),
        shape=shape,
        feature_values={str(key): value for key, value in features.items()},
        quality_label=raw.get("quality_label", raw.get("human_label")),
        label_source=raw.get("label_source", raw.get("decision_source")),
        event_tags=event_tags,
    )


def _validate_sample_identity(sample: QualitySample) -> None:
    for field_name in ("sample_id", "observation_id", "slot_id"):
        if not str(getattr(sample, field_name)).strip():
            raise QualityMLValidationError(f"sample {field_name} is required")


def _observation_timestamp(sample: QualitySample) -> float:
    value = sample.observed_at
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise QualityMLValidationError(
                f"sample {sample.sample_id!r} has invalid observed_at"
            ) from exc
    else:
        raise QualityMLValidationError(
            f"sample {sample.sample_id!r} requires observed_at for chronological split"
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


def _assert_disjoint_groups(*partitions: Sequence[QualitySample]) -> None:
    seen: dict[str, int] = {}
    for partition_index, partition in enumerate(partitions):
        for sample in partition:
            previous = seen.setdefault(sample.group_key, partition_index)
            if previous != partition_index:
                raise QualityMLValidationError(
                    "observation/slot group leaked across dataset partitions"
                )


def _validate_training_config(config: QualityTrainingConfig) -> None:
    integer_fields = {
        "min_human_samples": config.min_human_samples,
        "min_observation_batches": config.min_observation_batches,
        "min_samples_per_class": config.min_samples_per_class,
        "min_calibration_samples_per_class": (config.min_calibration_samples_per_class),
        "max_iter": config.max_iter,
        "max_leaf_nodes": config.max_leaf_nodes,
        "min_samples_leaf": config.min_samples_leaf,
    }
    if any(value <= 0 for value in integer_fields.values()):
        raise QualityMLValidationError(
            "training sample and estimator integer settings must be positive"
        )
    if config.min_observation_batches < 3:
        raise QualityMLValidationError("min_observation_batches must be at least 3")
    if config.learning_rate <= 0 or config.l2_regularization < 0:
        raise QualityMLValidationError("invalid HGB learning or regularization setting")
    if not 0 <= config.ood_missing_fraction <= 1:
        raise QualityMLValidationError("ood_missing_fraction must be within [0, 1]")


def _feature_names(samples: Sequence[QualitySample]) -> tuple[str, ...]:
    if not samples:
        raise QualityMLValidationError("cannot derive feature schema from no samples")
    names = tuple(sorted(str(key) for key in samples[0].feature_values))
    if not names:
        raise QualityMLValidationError("quality feature schema is empty")
    if len(names) != len(set(names)):
        raise QualityMLValidationError("quality feature names are not unique")
    expected = set(names)
    for sample in samples:
        actual = {str(key) for key in sample.feature_values}
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise QualityMLValidationError(
                f"sample {sample.sample_id!r} feature schema mismatch; "
                f"missing={missing}, extra={extra}"
            )
    return names


def _feature_matrix(
    samples: Sequence[QualitySample],
    feature_names: Sequence[str],
) -> np.ndarray:
    expected = set(feature_names)
    matrix = np.empty((len(samples), len(feature_names)), dtype=np.float64)
    for row_index, sample in enumerate(samples):
        actual = {str(key) for key in sample.feature_values}
        if actual != expected:
            raise QualityModelCompatibilityError(
                f"sample {sample.sample_id!r} does not match model feature schema"
            )
        for column_index, name in enumerate(feature_names):
            raw_value = sample.feature_values[name]
            if raw_value is None:
                value = math.nan
            else:
                try:
                    value = float(raw_value)
                except (TypeError, ValueError) as exc:
                    raise QualityMLValidationError(
                        f"feature {name!r} is not numeric in sample {sample.sample_id!r}"
                    ) from exc
            if math.isinf(value):
                raise QualityMLValidationError(
                    f"feature {name!r} is infinite in sample {sample.sample_id!r}"
                )
            matrix[row_index, column_index] = value
    return matrix


def _quality_labels(samples: Sequence[QualitySample]) -> list[str]:
    labels = [str(sample.quality_label) for sample in samples]
    if any(label not in QUALITY_LABELS for label in labels):
        raise QualityMLValidationError(
            "non-human or unsupported labels reached ML input"
        )
    return labels


def _require_class_counts(
    labels: Sequence[str],
    minimum: int,
    *,
    partition: str,
) -> None:
    counts = Counter(labels)
    missing = {
        label: counts.get(label, 0)
        for label in QUALITY_LABELS
        if counts.get(label, 0) < minimum
    }
    if missing:
        raise QualityMLValidationError(
            f"{partition} partition lacks required human labels: {missing}; "
            f"minimum per class is {minimum}"
        )


def _fit_independent_sigmoid_calibrator(
    base_estimator: Any,
    x_calibration: np.ndarray,
    y_calibration: Sequence[str],
    dependencies: Mapping[str, Any],
) -> Any:
    scores = np.asarray(base_estimator.decision_function(x_calibration), dtype=float)
    if scores.ndim == 1:
        scores = np.column_stack((-scores, scores))
    classes = tuple(str(value) for value in base_estimator.classes_)
    if scores.shape != (len(x_calibration), len(classes)):
        raise QualityMLValidationError(
            "base estimator returned an unexpected calibration score shape"
        )
    calibrator_type = dependencies["LogisticRegression"]
    labels = np.asarray(y_calibration, dtype=object)
    calibrators = []
    for index, label in enumerate(classes):
        binary_target = (labels == label).astype(np.int8)
        calibrator = calibrator_type(
            C=1.0,
            solver="lbfgs",
            max_iter=1000,
            random_state=0,
        )
        calibrator.fit(scores[:, [index]], binary_target)
        calibrators.append(calibrator)
    return _IndependentSigmoidEstimator(base_estimator, classes, calibrators)


def _require_ml_dependencies() -> dict[str, Any]:
    try:
        sklearn = import_module("sklearn")
        ensemble = import_module("sklearn.ensemble")
        linear_model = import_module("sklearn.linear_model")
        metrics = import_module("sklearn.metrics")
        joblib = import_module("joblib")
    except ImportError as exc:
        raise QualityMLDependencyError(
            "radio quality ML requires the optional 'quality-ml' dependencies "
            "(scikit-learn and joblib)"
        ) from exc
    return {
        "sklearn": sklearn,
        "HistGradientBoostingClassifier": ensemble.HistGradientBoostingClassifier,
        "LogisticRegression": linear_model.LogisticRegression,
        "metrics": metrics,
        "joblib": joblib,
    }


def _runtime_versions(dependencies: Mapping[str, Any]) -> dict[str, str]:
    scipy = import_module("scipy")
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "platform": platform.system(),
        "numpy": str(np.__version__),
        "scipy": str(scipy.__version__),
        "scikit_learn": str(dependencies["sklearn"].__version__),
        "joblib": str(dependencies["joblib"].__version__),
    }


def _assert_runtime_compatible(
    manifest: Mapping[str, Any],
    dependencies: Mapping[str, Any],
) -> None:
    current_runtime = _runtime_versions(dependencies)
    recorded_runtime = manifest["runtime"]
    mismatches = {
        key: (recorded_runtime.get(key), current_runtime.get(key))
        for key in current_runtime
        if recorded_runtime.get(key) != current_runtime.get(key)
    }
    if mismatches:
        details = ", ".join(
            f"{key}={recorded!r} (current {current!r})"
            for key, (recorded, current) in sorted(mismatches.items())
        )
        raise QualityModelCompatibilityError(
            f"model bundle runtime does not match: {details}"
        )


def _training_reference(
    samples: Sequence[QualitySample],
    feature_names: Sequence[str],
) -> dict[str, dict[str, float | None]]:
    matrix = _feature_matrix(samples, feature_names)
    reference: dict[str, dict[str, float | None]] = {}
    for index, name in enumerate(feature_names):
        values = matrix[:, index]
        finite = values[np.isfinite(values)]
        if finite.size:
            median = float(np.median(finite))
            scale = float(1.4826 * np.median(np.abs(finite - median)))
            if not np.isfinite(scale) or scale <= 1e-12:
                scale = float(np.std(finite))
            if not np.isfinite(scale) or scale <= 1e-12:
                scale = 1.0
            reference[name] = {"median": median, "scale": scale}
        else:
            reference[name] = {"median": None, "scale": None}
    return reference


def _training_domain(
    samples: Sequence[QualitySample],
    config: QualityTrainingConfig,
) -> dict[str, Any]:
    shapes = sorted({sample.shape for sample in samples if sample.shape is not None})
    frequencies = sorted(
        {
            float(sample.frequency_mhz)
            for sample in samples
            if sample.frequency_mhz is not None and np.isfinite(sample.frequency_mhz)
        }
    )
    polarizations = sorted(
        {
            str(sample.polarization).strip().upper()
            for sample in samples
            if sample.polarization not in (None, "")
        }
    )
    return {
        "shapes": [list(shape) for shape in shapes],
        "frequencies_mhz": frequencies,
        "polarizations": polarizations,
        "max_missing_feature_fraction": config.ood_missing_fraction,
    }


def _ood_reasons(
    manifest: Mapping[str, Any],
    sample: QualitySample,
    feature_row: np.ndarray,
) -> list[str]:
    domain = manifest.get("domain", {})
    reasons: list[str] = []
    known_shapes = {tuple(value) for value in domain.get("shapes", [])}
    if sample.shape is None:
        reasons.append("missing_shape")
    elif tuple(sample.shape) not in known_shapes:
        reasons.append("unseen_shape")

    known_frequencies = [float(value) for value in domain.get("frequencies_mhz", [])]
    if sample.frequency_mhz is None or not np.isfinite(sample.frequency_mhz):
        reasons.append("missing_frequency")
    elif not any(
        math.isclose(float(sample.frequency_mhz), value, rel_tol=0.0, abs_tol=1e-6)
        for value in known_frequencies
    ):
        reasons.append("unseen_frequency")

    known_polarizations = {
        str(value).strip().upper() for value in domain.get("polarizations", [])
    }
    if sample.polarization in (None, ""):
        reasons.append("missing_polarization")
    elif str(sample.polarization).strip().upper() not in known_polarizations:
        reasons.append("unseen_polarization")

    missing_fraction = float(np.mean(~np.isfinite(feature_row)))
    maximum_missing = float(domain.get("max_missing_feature_fraction", 0.0))
    if missing_fraction > maximum_missing:
        reasons.append("excessive_missing_features")
    return reasons


def _top_anomalous_features(
    manifest: Mapping[str, Any],
    feature_names: Sequence[str],
    feature_row: np.ndarray,
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    reference = manifest.get("domain", {}).get("feature_reference", {})
    scores: list[tuple[float, str]] = []
    for name, value in zip(feature_names, feature_row, strict=True):
        item = reference.get(name, {})
        median = item.get("median")
        scale = item.get("scale")
        if not np.isfinite(value) or median is None or scale in (None, 0):
            continue
        score = abs((float(value) - float(median)) / float(scale))
        if np.isfinite(score):
            scores.append((score, name))
    scores.sort(key=lambda item: (-item[0], item[1]))
    return tuple(name for _, name in scores[:limit])


def _training_fingerprint(
    split: QualityDatasetSplit,
    feature_names: Sequence[str],
) -> str:
    rows = []
    for partition_name, samples in (
        ("train", split.train),
        ("calibration", split.calibration),
        ("test", split.test),
    ):
        for sample in samples:
            rows.append(
                {
                    "partition": partition_name,
                    "sample_id": sample.sample_id,
                    "observation_id": sample.observation_id,
                    "slot_id": sample.slot_id,
                    "quality_label": sample.quality_label,
                    "features": {
                        name: _json_safe(sample.feature_values[name])
                        for name in feature_names
                    },
                }
            )
    rows.sort(key=lambda item: (item["partition"], item["sample_id"]))
    return hashlib.sha256(_canonical_json_bytes(rows)).hexdigest()


def _validate_in_memory_bundle(bundle: QualityModelBundle) -> None:
    if not isinstance(bundle, QualityModelBundle):
        raise TypeError("bundle must be a QualityModelBundle")
    _validate_manifest_structure(bundle.manifest, require_artifacts=False)
    if not callable(getattr(bundle.estimator, "predict_proba", None)):
        raise QualityModelCompatibilityError("bundle estimator lacks predict_proba")
    estimator_classes = tuple(
        str(item) for item in getattr(bundle.estimator, "classes_", ())
    )
    manifest_classes = tuple(str(item) for item in bundle.manifest["classes"])
    if estimator_classes != manifest_classes:
        raise QualityModelCompatibilityError(
            "bundle estimator classes do not match manifest"
        )


def _validate_manifest_structure(
    manifest: Mapping[str, Any],
    *,
    require_artifacts: bool = True,
) -> None:
    if not isinstance(manifest, Mapping):
        raise QualityModelSecurityError("model manifest must be a mapping")
    if manifest.get("schema_version") != QUALITY_ML_SCHEMA_VERSION:
        raise QualityModelCompatibilityError("unsupported model manifest schema")
    if manifest.get("feature_schema_version") != QUALITY_FEATURE_SCHEMA_VERSION:
        raise QualityModelCompatibilityError("unsupported feature schema")
    if manifest.get("model_kind") != _MODEL_KIND:
        raise QualityModelCompatibilityError("unsupported model kind")
    feature_names = manifest.get("feature_names")
    if (
        not isinstance(feature_names, list)
        or not feature_names
        or len(feature_names) != len(set(feature_names))
        or not all(isinstance(item, str) and item for item in feature_names)
    ):
        raise QualityModelCompatibilityError("invalid model feature schema")
    classes = manifest.get("classes")
    if (
        not isinstance(classes, list)
        or len(classes) != len(QUALITY_LABELS)
        or set(classes) != set(QUALITY_LABELS)
    ):
        raise QualityModelCompatibilityError("invalid model class schema")
    runtime = manifest.get("runtime")
    required_runtime = {
        "python",
        "platform",
        "numpy",
        "scipy",
        "scikit_learn",
        "joblib",
    }
    if not isinstance(runtime, Mapping) or not required_runtime <= set(runtime):
        raise QualityModelCompatibilityError("model runtime metadata is incomplete")
    if require_artifacts:
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, Mapping) or not isinstance(
            artifacts.get("model"), Mapping
        ):
            raise QualityModelSecurityError("model artifact metadata is missing")


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validated_sha256(value: Any, *, field_name: str) -> str:
    digest = str(value).strip().lower()
    if len(digest) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise QualityModelSecurityError(f"{field_name} is not a SHA256 digest")
    return digest


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise QualityMLValidationError(f"invalid numeric value {value!r}") from exc
