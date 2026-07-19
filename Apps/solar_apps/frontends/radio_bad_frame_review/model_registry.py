"""Fail-closed registry for manually published radio-quality models."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "MODEL_REGISTRY_SCHEMA_VERSION",
    "ModelRegistryError",
    "PromotionGateError",
    "QualityModelRegistry",
]


MODEL_REGISTRY_SCHEMA_VERSION = 1
MODEL_STATES = frozenset({"candidate", "published", "retired"})
MAX_FALSE_REJECTION_RATE = 0.005
MIN_BAD_RECALL = 0.90


class ModelRegistryError(RuntimeError):
    """Raised when a registered model package is missing or untrusted."""


class PromotionGateError(ModelRegistryError):
    """Raised when a candidate does not meet explicit publication gates."""


class QualityModelRegistry:
    """Maintain one active model without ever auto-promoting a training run."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / "registry.json"

    def list_models(self) -> dict[str, Any]:
        """Return a copy of the public registry document."""

        return json.loads(json.dumps(self._load()))

    def register_candidate(
        self,
        model_id: str,
        bundle_directory: str | Path,
        *,
        metrics: dict[str, Any],
        feature_schema_version: int,
        data_fingerprint: str,
    ) -> dict[str, Any]:
        """Register a complete package as a non-active candidate."""

        identifier = _validate_model_id(model_id)
        bundle = self._trusted_bundle_path(bundle_directory)
        manifest_path = bundle / "manifest.json"
        model_card_path = bundle / "MODEL_CARD.md"
        if not manifest_path.is_file():
            raise ModelRegistryError("model package is missing manifest.json")
        if not model_card_path.is_file():
            raise ModelRegistryError("model package is missing MODEL_CARD.md")
        manifest = _read_json_object(manifest_path)
        self._verify_artifacts(bundle, manifest)

        registry = self._load()
        if identifier in registry["models"]:
            raise ModelRegistryError(f"model id already exists: {identifier}")
        now = _utc_now()
        registry["models"][identifier] = {
            "model_id": identifier,
            "status": "candidate",
            "bundle_relative_path": bundle.relative_to(self.root).as_posix(),
            "manifest_sha256": _sha256_file(manifest_path),
            "model_card_sha256": _sha256_file(model_card_path),
            "feature_schema_version": int(feature_schema_version),
            "data_fingerprint": str(data_fingerprint),
            "metrics": dict(metrics),
            "registered_at": now,
            "published_at": None,
        }
        registry["updated_at"] = now
        self._write(registry)
        return registry["models"][identifier]

    def resolve_verified_bundle(self, model_id: str | None = None) -> Path:
        """Verify hashes and containment before a caller deserializes a model."""

        registry = self._load()
        identifier = model_id or registry.get("active_model_id")
        if not identifier:
            raise ModelRegistryError("no published radio-quality model is active")
        entry = registry["models"].get(identifier)
        if not isinstance(entry, dict):
            raise ModelRegistryError(f"unknown model id: {identifier}")
        if model_id is None and entry.get("status") != "published":
            raise ModelRegistryError("active model is not in published state")
        bundle = self._trusted_bundle_path(self.root / entry["bundle_relative_path"])
        manifest_path = bundle / "manifest.json"
        model_card_path = bundle / "MODEL_CARD.md"
        if _sha256_file(manifest_path) != entry.get("manifest_sha256"):
            raise ModelRegistryError("registered manifest SHA256 does not match")
        if _sha256_file(model_card_path) != entry.get("model_card_sha256"):
            raise ModelRegistryError("registered model-card SHA256 does not match")
        manifest = _read_json_object(manifest_path)
        manifest_feature_schema = manifest.get(
            "feature_schema_version", manifest.get("schema_version", -1)
        )
        if int(manifest_feature_schema) != int(entry.get("feature_schema_version", -2)):
            raise ModelRegistryError("feature schema does not match registry")
        self._verify_artifacts(bundle, manifest)
        return bundle

    def publish(
        self, model_id: str, *, acknowledge_evaluation: bool = False
    ) -> dict[str, Any]:
        """Manually publish a candidate after all safety gates pass."""

        if not acknowledge_evaluation:
            raise PromotionGateError("publication requires --acknowledge-evaluation")
        identifier = _validate_model_id(model_id)
        registry = self._load()
        entry = registry["models"].get(identifier)
        if not isinstance(entry, dict):
            raise ModelRegistryError(f"unknown model id: {identifier}")
        if entry.get("status") not in {"candidate", "published"}:
            raise PromotionGateError("only a candidate model can be published")
        self.resolve_verified_bundle(identifier)
        _enforce_promotion_gates(entry.get("metrics", {}))

        previous = registry.get("active_model_id")
        if previous and previous != identifier and previous in registry["models"]:
            registry["models"][previous]["status"] = "retired"
        now = _utc_now()
        entry["status"] = "published"
        entry["published_at"] = now
        registry["active_model_id"] = identifier
        registry["updated_at"] = now
        self._write(registry)
        return entry

    def retire(self, model_id: str) -> dict[str, Any]:
        """Retire a model; retiring the active model disables ML inference."""

        identifier = _validate_model_id(model_id)
        registry = self._load()
        entry = registry["models"].get(identifier)
        if not isinstance(entry, dict):
            raise ModelRegistryError(f"unknown model id: {identifier}")
        entry["status"] = "retired"
        if registry.get("active_model_id") == identifier:
            registry["active_model_id"] = None
        registry["updated_at"] = _utc_now()
        self._write(registry)
        return entry

    def _trusted_bundle_path(self, value: str | Path) -> Path:
        candidate = Path(value).expanduser().resolve(strict=True)
        try:
            candidate.relative_to(self.root.resolve(strict=True))
        except ValueError as exc:
            raise ModelRegistryError("model package escapes the registry root") from exc
        if not candidate.is_dir():
            raise ModelRegistryError("model package is not a directory")
        return candidate

    def _verify_artifacts(self, bundle: Path, manifest: dict[str, Any]) -> None:
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            raise ModelRegistryError("model manifest has no artifact hashes")
        for name, details in artifacts.items():
            if isinstance(details, str):
                relative_path = name
                expected = details
            elif isinstance(details, dict):
                relative_path = details.get("path", details.get("filename", name))
                expected = details.get("sha256")
            else:
                raise ModelRegistryError(f"invalid artifact entry: {name}")
            artifact = (bundle / str(relative_path)).resolve(strict=True)
            try:
                artifact.relative_to(bundle)
            except ValueError as exc:
                raise ModelRegistryError("artifact path escapes model package") from exc
            if not artifact.is_file() or _sha256_file(artifact) != expected:
                raise ModelRegistryError(f"artifact SHA256 mismatch: {name}")

    def _load(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {
                "schema_version": MODEL_REGISTRY_SCHEMA_VERSION,
                "active_model_id": None,
                "models": {},
                "updated_at": None,
            }
        registry = _read_json_object(self.registry_path)
        if registry.get("schema_version") != MODEL_REGISTRY_SCHEMA_VERSION:
            raise ModelRegistryError("unsupported model registry schema")
        if not isinstance(registry.get("models"), dict):
            raise ModelRegistryError("invalid model registry")
        for entry in registry["models"].values():
            if not isinstance(entry, dict) or entry.get("status") not in MODEL_STATES:
                raise ModelRegistryError("invalid model state in registry")
        return registry

    def _write(self, registry: dict[str, Any]) -> None:
        temporary = self.registry_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(registry, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.registry_path)


def _enforce_promotion_gates(metrics: dict[str, Any]) -> None:
    required = {
        "good_false_rejection_rate",
        "event_false_rejection_rate",
        "bad_recall",
        "locked_test_event_rejections",
        "outperforms_rule_at_constraint",
    }
    missing = sorted(required - set(metrics))
    if missing:
        raise PromotionGateError(
            "evaluation is missing promotion metrics: " + ", ".join(missing)
        )
    good_rejection = _finite_metric(metrics, "good_false_rejection_rate")
    event_rejection = _finite_metric(metrics, "event_false_rejection_rate")
    bad_recall = _finite_metric(metrics, "bad_recall")
    if good_rejection > MAX_FALSE_REJECTION_RATE:
        raise PromotionGateError("good-frame false rejection exceeds 0.5%")
    if event_rejection > MAX_FALSE_REJECTION_RATE:
        raise PromotionGateError("science-event false rejection exceeds 0.5%")
    if bad_recall < MIN_BAD_RECALL:
        raise PromotionGateError("bad-frame recall is below 90%")
    if int(metrics["locked_test_event_rejections"]) != 0:
        raise PromotionGateError("locked test rejected a labelled science event")
    if metrics["outperforms_rule_at_constraint"] is not True:
        raise PromotionGateError("model does not beat rules at the same constraint")


def _validate_model_id(value: str) -> str:
    identifier = str(value).strip()
    if not identifier or len(identifier) > 80:
        raise ValueError("model_id must contain 1 to 80 characters")
    if any(not (character.isalnum() or character in "-_.") for character in identifier):
        raise ValueError("model_id contains unsupported characters")
    return identifier


def _finite_metric(metrics: dict[str, Any], name: str) -> float:
    try:
        value = float(metrics[name])
    except (TypeError, ValueError) as exc:
        raise PromotionGateError(f"promotion metric is not numeric: {name}") from exc
    if not math.isfinite(value):
        raise PromotionGateError(f"promotion metric is not finite: {name}")
    return value


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelRegistryError(f"invalid JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ModelRegistryError(f"JSON root must be an object: {path.name}")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
