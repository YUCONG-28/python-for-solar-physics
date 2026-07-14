"""Import-safe SOHO/LASCO download and rendering workflows.

The module keeps optional plotting, SunPy, and Helioviewer dependencies inside
the functions that use them so importing :mod:`solar_toolkit.cme` stays light.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .files import scan_lasco_files
from .processing import running_difference


def download_lasco_jp2_sequence(
    *,
    start_time: dt.datetime,
    end_time: dt.datetime,
    interval: dt.timedelta,
    output_dir: str | Path,
) -> tuple[int, int]:
    """Download an inclusive LASCO C2 JP2 time sequence through Helioviewer."""

    if interval.total_seconds() <= 0:
        raise ValueError("interval must be positive")

    import hvpy
    from hvpy.datasource import DataSource

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    attempted = 0
    saved = 0
    current_time = start_time
    while current_time <= end_time:
        attempted += 1
        filename = f"LASCO_C2_{current_time.strftime('%Y%m%d_%H%M%S')}.jp2"
        try:
            hvpy.save_file(
                hvpy.getJP2Image(current_time, DataSource.LASCO_C2.value),
                filename=str(root / filename),
                overwrite=True,
            )
            saved += 1
            print(f"Saved file: {filename}")
        except Exception as exc:
            print(f"Failed at {current_time}: {exc}")
        current_time += interval
    return attempted, saved


def plot_lasco_images(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    show_plot: bool = False,
) -> list[Path]:
    """Render each LASCO JP2 file using its SunPy WCS projection."""

    import matplotlib.pyplot as plt
    from sunpy.map import Map

    root = Path(input_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    files = _scan_jp2(root, recursive=False)
    outputs: list[Path] = []
    for file_path in files:
        lasco_map = Map(file_path)
        figure = plt.figure()
        axes = figure.add_subplot(projection=lasco_map)
        lasco_map.plot(axes=axes)
        output_path = output_root / f"{file_path.stem}.png"
        plt.savefig(output_path, dpi=200, bbox_inches="tight")
        if show_plot:
            plt.show()
        plt.close(figure)
        outputs.append(output_path)
    return outputs


def render_lasco_running_differences(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    show_plot: bool = False,
    recursive: bool = True,
    vmin: float = -49,
    vmax: float = 49,
) -> list[Path]:
    """Render adjacent LASCO JP2 running differences with legacy styling."""

    import matplotlib.colors as colors
    import matplotlib.pyplot as plt
    from sunpy.map import Map

    plt.rcParams["axes.unicode_minus"] = False
    try:
        plt.rcParams["font.family"] = ["SimHei"]
    except Exception:
        pass

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    files = _scan_jp2(Path(input_dir), recursive=recursive)
    print(f"=== Found {len(files)} JP2 files ===")
    for index, file_path in enumerate(files, start=1):
        print(f"{index:2d}. {file_path.name}")
    print("=" * 50)
    if len(files) < 2:
        print(f"Only {len(files)} JP2 file(s) found; at least two are required.")
        return []

    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    outputs: list[Path] = []
    for index, (previous_path, current_path) in enumerate(
        zip(files, files[1:], strict=False), start=1
    ):
        figure = None
        try:
            print(
                f"\nProcessing pair {index}: "
                f"{previous_path.name} -> {current_path.name}"
            )
            previous_map = Map(previous_path)
            current_map = Map(current_path)
            if previous_map.data.shape != current_map.data.shape:
                print(
                    "Skipping shape mismatch: "
                    f"{previous_map.data.shape} vs {current_map.data.shape}"
                )
                continue
            difference_map = Map(
                running_difference(current_map.data, previous_map.data),
                current_map.meta,
            )
            figure = plt.figure(figsize=(10, 8))
            axes = figure.add_subplot(projection=difference_map)
            image = difference_map.plot(axes=axes, norm=norm, cmap="gray")
            colorbar = plt.colorbar(image, ax=axes)
            colorbar.set_label("差分强度")
            output_path = output_root / f"diff_bw_{current_path.stem}.png"
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            if show_plot:
                plt.show()
            print(f"Saved: {output_path.name}")
            outputs.append(output_path)
        except Exception as exc:
            print(
                f"Failed {previous_path.name} -> {current_path.name}: "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            if figure is not None:
                plt.close(figure)
    print("\nAll files processed.")
    return outputs


def _scan_jp2(root: Path, *, recursive: bool) -> list[Path]:
    if not root.is_dir():
        return []
    return [
        path
        for path in scan_lasco_files(root, recursive=recursive)
        if path.suffix.casefold() == ".jp2"
    ]


__all__ = [
    "download_lasco_jp2_sequence",
    "plot_lasco_images",
    "render_lasco_running_differences",
]
