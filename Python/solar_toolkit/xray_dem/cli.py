"""Import-safe command entry points for X-ray and DEM recipes.

English: Keep repository scripts as thin compatibility launchers while the
installed package owns their implementations.

中文：仓库脚本仅保留兼容启动入口，实际实现由可安装包统一维护。
"""

from __future__ import annotations

from collections.abc import Sequence


def goes_lightcurve_main(argv: Sequence[str] | None = None) -> int:
    """Run the GOES soft X-ray light-curve recipe."""

    from ._goes_lightcurve import main

    return main(argv)


def neupert_timing_main(argv: Sequence[str] | None = None) -> int:
    """Run the four-panel Neupert timing recipe."""

    from ._neupert_timing import main

    return main(argv)


def neupert_comparison_main(argv: Sequence[str] | None = None) -> int:
    """Run the SXR derivative comparison recipe."""

    from ._neupert_comparison import main

    return main(argv)


def flare_summary_main(argv: Sequence[str] | None = None) -> int:
    """Run the combined SXR/HXI/AIA summary recipe."""

    from ._flare_summary import main

    return main(argv)


__all__ = [
    "flare_summary_main",
    "goes_lightcurve_main",
    "neupert_comparison_main",
    "neupert_timing_main",
]
