"""Local adapter to the public AIA configuration model."""

from solar_apps.platform.config import apply_config_to_object
from solar_toolkit.aia.config import *  # noqa: F403
from solar_toolkit.aia.config import AIAConfig as _PublicAIAConfig
from solar_toolkit.aia.config import _normalize_wave_float_dict  # noqa: F401


class AIAConfig(_PublicAIAConfig):
    """AIA configuration with Local-only path overrides."""

    def __post_init__(self):
        apply_config_to_object(self, "sdo_aia_euv_processor")
        super().__post_init__()
