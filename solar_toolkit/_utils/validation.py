"""Internal validation and legacy configuration helpers."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import yaml


def validate_time_range(start_time: dt.datetime, end_time: dt.datetime) -> bool:
    """Validate that ``start_time`` strictly precedes ``end_time``."""

    if start_time >= end_time:
        raise ValueError(
            f"Start time ({start_time}) must precede end time ({end_time})"
        )

    time_diff = (end_time - start_time).total_seconds()
    if time_diff <= 0:
        raise ValueError(f"Time difference must be positive; got {time_diff} seconds")
    return True


def validate_frequency_range(f_start: float, f_end: float) -> bool:
    """Validate a strictly increasing, non-negative frequency range in MHz."""

    if f_start >= f_end:
        raise ValueError(
            f"Start frequency ({f_start} MHz) must be less than end frequency "
            f"({f_end} MHz)"
        )
    if f_start < 0 or f_end < 0:
        raise ValueError(
            f"Frequencies must be non-negative; got {f_start} - {f_end} MHz"
        )
    return True


class SolarDataConfig:
    """Legacy unified configuration object for solar-data workflows."""

    def __init__(self, config_dict: dict[str, Any] | None = None):
        self.defaults = {
            "data_dir": "D:/solar_data",
            "output_dir": "D:/solar_data/output",
            "roi_bounds": (-700, -100, -100, 400),
            "dpi": 300,
            "fig_width": 10.0,
            "use_parallel": True,
            "max_workers": None,
            "chunk_mem_mb": 50,
            "save_images": True,
            "show_images": False,
        }
        if config_dict:
            self.defaults.update(config_dict)
        for key, value in self.defaults.items():
            setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        """Return the current configuration as a dictionary."""

        return {key: getattr(self, key) for key in self.defaults}

    def save_to_file(self, filepath: str) -> None:
        """Save configuration to a JSON or YAML file."""

        config_dict = self.to_dict()
        if filepath.endswith(".json"):
            with open(filepath, "w", encoding="utf-8") as handle:
                json.dump(config_dict, handle, indent=2, ensure_ascii=False)
        elif filepath.endswith((".yaml", ".yml")):
            with open(filepath, "w", encoding="utf-8") as handle:
                yaml.dump(
                    config_dict,
                    handle,
                    default_flow_style=False,
                    allow_unicode=True,
                )
        else:
            raise ValueError(f"Unsupported configuration file format: {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> SolarDataConfig:
        """Load configuration from a JSON or YAML file."""

        if filepath.endswith(".json"):
            with open(filepath, encoding="utf-8") as handle:
                config_dict = json.load(handle)
        elif filepath.endswith((".yaml", ".yml")):
            with open(filepath, encoding="utf-8") as handle:
                config_dict = yaml.safe_load(handle)
        else:
            raise ValueError(f"Unsupported configuration file format: {filepath}")
        return cls(config_dict)


__all__ = ["SolarDataConfig", "validate_frequency_range", "validate_time_range"]
