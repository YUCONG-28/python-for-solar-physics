"""Explicit CLI for gold-label datasets and radio-quality model publication."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from solar_apps.platform.layout import RuntimeLayout
from solar_toolkit.radio.quality_ml import QualityTrainingConfig

from .model_registry import QualityModelRegistry
from .training import collect_gold_quality_dataset, train_review_quality_model

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    local_root = RuntimeLayout.discover().local_root
    parser = argparse.ArgumentParser(
        prog="solar-apps tools bad-frame-ml",
        description=(
            "Build human-only radio-quality datasets, train shadow models, and "
            "manually publish models that pass locked-test gates."
        ),
    )
    parser.add_argument(
        "--reviews-root",
        type=Path,
        default=local_root / "outputs" / "bad_frame_reviews",
        help="Completed review directory (default: Local outputs).",
    )
    parser.add_argument(
        "--models-root",
        type=Path,
        default=local_root / "outputs" / "bad_frame_models",
        help="Local model registry directory.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("dataset", help="Audit eligible human gold labels.")
    commands.add_parser("models", help="List candidate, published and retired models.")

    train = commands.add_parser(
        "train", help="Train and register a candidate in shadow mode."
    )
    train.add_argument("--model-id", required=True)
    train.add_argument("--min-human-samples", type=int, default=1200)
    train.add_argument("--min-observation-batches", type=int, default=4)
    train.add_argument("--min-samples-per-class", type=int, default=20)
    train.add_argument("--min-calibration-samples-per-class", type=int, default=5)
    train.add_argument("--random-state", type=int, default=0)

    evaluate = commands.add_parser(
        "evaluate", help="Show the stored locked-test report for a model."
    )
    evaluate.add_argument("--model-id", required=True)

    publish = commands.add_parser(
        "publish", help="Explicitly activate a gate-passing candidate."
    )
    publish.add_argument("--model-id", required=True)
    publish.add_argument(
        "--acknowledge-evaluation",
        action="store_true",
        help="Confirm that the human-reviewed locked-test report was inspected.",
    )

    retire = commands.add_parser("retire", help="Disable a registered model.")
    retire.add_argument("--model-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    registry = QualityModelRegistry(args.models_root)
    try:
        if args.command == "dataset":
            dataset = collect_gold_quality_dataset(args.reviews_root)
            payload: dict[str, Any] = {
                "eligible_human_samples": len(dataset.samples),
                "independent_observation_batches": len(
                    {sample.observation_id for sample in dataset.samples}
                ),
                "review_ids": list(dataset.review_ids),
                "excluded_counts": dataset.excluded_counts,
                "data_fingerprint": dataset.data_fingerprint,
            }
        elif args.command == "models":
            payload = registry.list_models()
        elif args.command == "train":
            config = QualityTrainingConfig(
                min_human_samples=args.min_human_samples,
                min_observation_batches=args.min_observation_batches,
                min_samples_per_class=args.min_samples_per_class,
                min_calibration_samples_per_class=(
                    args.min_calibration_samples_per_class
                ),
                random_state=args.random_state,
            )
            payload = train_review_quality_model(
                args.reviews_root,
                registry,
                model_id=args.model_id,
                config=config,
            )
        elif args.command == "evaluate":
            state = registry.list_models()
            entry = state["models"].get(args.model_id)
            if not entry:
                raise KeyError(f"unknown model id: {args.model_id}")
            registry.resolve_verified_bundle(args.model_id)
            payload = {
                "model_id": args.model_id,
                "status": entry["status"],
                "metrics": entry["metrics"],
                "data_fingerprint": entry["data_fingerprint"],
            }
        elif args.command == "publish":
            payload = registry.publish(
                args.model_id,
                acknowledge_evaluation=args.acknowledge_evaluation,
            )
        elif args.command == "retire":
            payload = registry.retire(args.model_id)
        else:  # pragma: no cover - argparse prevents this branch
            parser.error(f"unknown command: {args.command}")
            return 2
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"radio-quality-ml: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(payload), indent=2, sort_keys=True))
    return 0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


if __name__ == "__main__":
    raise SystemExit(main())
