# -*- coding: utf-8 -*-
"""
AIA 区域切片时间序列分析 —— 优化版
修复：WCS坐标、循环内重复计算、NaN过滤、统计分发
优化：并行读取、进度显示、科学可视化面板
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import RectangleSelector, PolygonSelector
from matplotlib.patches import Rectangle, Polygon
from matplotlib.path import Path as mplPath
import sunpy.map
from sunpy.net import Fido, attrs as a
import astropy.units as u
import os
import warnings
import argparse
import csv
import sys
import scipy.ndimage
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────
# 统计量注册表：name → (函数, 显示标签)
# ──────────────────────────────────────────────────────────────
_STAT_FUNCS: Dict[str, Tuple[Any, str]] = {
    "mean":   (np.nanmean,   "均值"),
    "max":    (np.nanmax,    "最大值"),
    "min":    (np.nanmin,    "最小值"),
    "sum":    (np.nansum,    "总和"),
    "median": (np.nanmedian, "中位数"),
    "std":    (np.nanstd,    "标准差"),
}

VALID_STATS = list(_STAT_FUNCS.keys())


# ══════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════
@dataclass
class AIASliceConfig:
    """AIA 切片分析配置参数"""
    # 输入
    input_dir:    str           = "./data"
    file_pattern: str           = "*aia.lev1_euv_12s*"
    wavelength:   Optional[int] = None
    use_fido:     bool          = False
    start_time:   Optional[str] = None
    end_time:     Optional[str] = None

    # 区域
    region_type:    str           = "rectangle"   # rectangle | polygon
    manual_coords:  Optional[Any] = None

    # 数据处理
    statistics:  List[str] = field(default_factory=lambda: ["mean", "max", "std"])
    normalize:   bool       = False
    max_workers: int        = 4       # 并行读取线程数

    # 输出
    output_dir: str  = "./output"
    save_csv:   bool = True
    save_plot:  bool = True
    plot_dpi:   int  = 150
    show_plot:  bool = True

    # 显示
    cmap:    str            = "sdoaia94"
    figsize: Tuple[int,int] = (14, 10)

    def validate(self):
        bad = [s for s in self.statistics if s not in VALID_STATS]
        if bad:
            raise ValueError(f"未知统计量: {bad}，可用: {VALID_STATS}")


# ══════════════════════════════════════════════════════════════
# 区域选择器（修复 meshgrid 缓存 & extent 顺序）
# ══════════════════════════════════════════════════════════════
class RegionSelector:
    """
    交互式区域选择。
    修复：
    - meshgrid 在 __init__ 时计算一次，回调直接复用。
    - extent 顺序统一为 [x_left, x_right, y_bottom, y_top]（matplotlib 约定）。
    """

    def __init__(self, image_data: np.ndarray, extent=None, cmap="sdoaia94"):
        self.image_data = image_data
        self.extent     = extent          # [x0, x1, y0, y1]
        self.cmap       = cmap

        self.region_mask: Optional[np.ndarray] = None
        self.region_type: Optional[str]        = None
        self.coords:      Optional[Any]        = None

        # ── 预计算坐标网格，回调中直接用 ──────────────────────────
        ny, nx = image_data.shape
        if extent is not None:
            x0, x1, y0, y1 = extent
            x_vals = np.linspace(x0, x1, nx)
            y_vals = np.linspace(y0, y1, ny)
        else:
            x_vals = np.arange(nx, dtype=float)
            y_vals = np.arange(ny, dtype=float)

        self._xx, self._yy = np.meshgrid(x_vals, y_vals)

    # ── 共用绘图初始化 ─────────────────────────────────────────
    def _make_fig(self, title: str):
        fig, ax = plt.subplots(figsize=(10, 8))
        norm_data = np.log1p(np.clip(self.image_data, 0, None))
        ax.imshow(norm_data, origin="lower", extent=self.extent, cmap=self.cmap,
                  aspect="auto", interpolation="nearest")
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("X (arcsec)")
        ax.set_ylabel("Y (arcsec)")
        return fig, ax

    # ── 矩形选择 ───────────────────────────────────────────────
    def select_rectangle(self):
        fig, ax = self._make_fig("单击并拖动以选择矩形区域，释放后自动关闭")

        def onselect(eclick, erelease):
            x1, y1 = eclick.xdata,   eclick.ydata
            x2, y2 = erelease.xdata, erelease.ydata
            xmin, xmax = sorted([x1, x2])
            ymin, ymax = sorted([y1, y2])
            self.coords = (xmin, xmax, ymin, ymax)

            self.region_mask = (
                (self._xx >= xmin) & (self._xx <= xmax) &
                (self._yy >= ymin) & (self._yy <= ymax)
            )
            self.region_type = "rectangle"

            rect = Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                              fill=False, edgecolor="red", linewidth=2)
            ax.add_patch(rect)
            plt.draw()
            plt.pause(0.6)
            plt.close(fig)

        RectangleSelector(ax, onselect, useblit=True,
                          button=[1], minspanx=5, minspany=5,
                          spancoords="data", interactive=True)
        plt.show()
        return self.region_mask, self.coords

    # ── 多边形选择 ─────────────────────────────────────────────
    def select_polygon(self):
        fig, ax = self._make_fig("单击添加顶点，右键闭合多边形")

        def onselect(vertices):
            self.coords = vertices
            poly_path = mplPath(vertices)
            pts = np.column_stack([self._xx.ravel(), self._yy.ravel()])
            self.region_mask = poly_path.contains_points(pts).reshape(self._xx.shape)
            self.region_type = "polygon"

            patch = Polygon(vertices, fill=False, edgecolor="red", linewidth=2)
            ax.add_patch(patch)
            plt.draw()
            plt.pause(0.6)
            plt.close(fig)

        PolygonSelector(ax, onselect, useblit=True)
        plt.show()
        return self.region_mask, self.coords


# ══════════════════════════════════════════════════════════════
# 核心处理器
# ══════════════════════════════════════════════════════════════
class AIASliceProcessor:
    """AIA 切片处理器（优化版）"""

    def __init__(self, config: AIASliceConfig):
        self.config = config
        self.file_list:    List[str]            = []
        self.region_mask:  Optional[np.ndarray] = None
        self._data_unit:   str                  = "DN"

    # ── 文件查找 ───────────────────────────────────────────────
    def find_aia_files(self) -> List[str]:
        if self.config.use_fido and self.config.start_time:
            return self._find_via_fido()
        return self._find_local_files()

    def _find_local_files(self) -> List[str]:
        data_path = Path(self.config.input_dir)
        if not data_path.exists():
            print(f"[警告] 目录不存在: {self.config.input_dir}")
            return []

        wl = self.config.wavelength
        candidates = (
            [self.config.file_pattern]
            if not wl else
            [f"*{wl}*", f"*aia*{wl}*.fits", f"*AIA*{wl}*.fits"]
        )
        for pat in candidates:
            files = sorted(data_path.glob(pat))
            if files:
                return [str(f) for f in files]

        print(f"[警告] 未找到匹配文件（尝试了 {candidates}）")
        return []

    def _find_via_fido(self) -> List[str]:
        print("[Fido] 正在远程查询…")
        try:
            result = Fido.search(
                a.Time(self.config.start_time, self.config.end_time),
                a.Instrument("AIA"),
                a.Wavelength(self.config.wavelength * u.angstrom),
            )
            if len(result) > 0:
                return [str(f) for f in Fido.fetch(result[0])]
        except Exception as exc:
            print(f"[Fido] 查询失败: {exc}")
        return []

    # ── 区域选择（修复 WCS extent 计算）──────────────────────────
    def select_region(self, aia_map: sunpy.map.Map) -> np.ndarray:
        ny, nx = aia_map.data.shape
        try:
            # pixel_to_world(x_pix, y_pix) — 注意顺序：先列(x)后行(y)
            bl = aia_map.pixel_to_world(0 * u.pix,        0 * u.pix)
            tr = aia_map.pixel_to_world((nx-1) * u.pix,   (ny-1) * u.pix)
            extent = [bl.Tx.value, tr.Tx.value,   # x_left, x_right
                      bl.Ty.value, tr.Ty.value]   # y_bottom, y_top
        except Exception:
            extent = [-nx / 2, nx / 2, -ny / 2, ny / 2]

        # 读取实际数据单位
        try:
            self._data_unit = str(aia_map.unit)
        except Exception:
            self._data_unit = "DN"

        selector = RegionSelector(aia_map.data, extent=extent, cmap=self.config.cmap)

        if self.config.region_type == "rectangle":
            mask, coords = selector.select_rectangle()
        elif self.config.region_type == "polygon":
            mask, coords = selector.select_polygon()
        else:
            raise ValueError(f"不支持的区域类型: {self.config.region_type}")

        if mask is None:
            return None

        n_pixels = int(mask.sum())
        print(f"[区域] 类型={selector.region_type}，有效像素={n_pixels:,}，坐标={coords}")
        return mask

    # ── 单文件读取（线程安全包装）─────────────────────────────────
    def _load_one(self, idx: int, file_path: str,
                  ref_shape: Tuple[int,int],
                  ref_mask: np.ndarray) -> Optional[Dict]:
        try:
            aia_map = sunpy.map.Map(file_path)
            data    = np.array(aia_map.data, dtype=float)

            # 调整 mask 尺寸（仅当形状不匹配时）——只算一次缩放
            if data.shape != ref_shape:
                zf   = (data.shape[0]/ref_shape[0], data.shape[1]/ref_shape[1])
                mask = scipy.ndimage.zoom(ref_mask.astype(float), zf, order=0) > 0.5
            else:
                mask = ref_mask

            region_data = data[mask]

            # 过滤 NaN / 负无穷
            region_data = region_data[np.isfinite(region_data)]
            if region_data.size == 0:
                return None

            row = {"time": aia_map.date.datetime, "idx": idx}
            for stat in self.config.statistics:
                fn, _ = _STAT_FUNCS[stat]
                row[stat] = float(fn(region_data))

            return row
        except Exception as exc:
            print(f"\n[错误] 文件 {Path(file_path).name}: {exc}")
            return None

    # ── 并行提取数据 ───────────────────────────────────────────
    def extract_data(self, file_list: List[str],
                     region_mask: np.ndarray) -> Dict[str, Any]:
        ref_shape = region_mask.shape
        n = len(file_list)
        rows: List[Optional[Dict]] = [None] * n

        print(f"[提取] 并行读取 {n} 个文件（workers={self.config.max_workers}）…")

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as pool:
            futures = {
                pool.submit(self._load_one, i, fp, ref_shape, region_mask): i
                for i, fp in enumerate(file_list)
            }
            done = 0
            for fut in as_completed(futures):
                i = futures[fut]
                rows[i] = fut.result()
                done += 1
                pct = done / n * 100
                bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
                print(f"\r  [{bar}] {pct:5.1f}%  {done}/{n}", end="", flush=True)

        print()  # 换行

        # 过滤失败项并按时间排序
        valid = [r for r in rows if r is not None]
        valid.sort(key=lambda r: r["time"])

        times = [r["time"] for r in valid]
        stats: Dict[str, List[float]] = {s: [r[s] for r in valid]
                                         for s in self.config.statistics}

        if self.config.normalize:
            for s in stats:
                arr = np.array(stats[s])
                rng = arr.max() - arr.min()
                stats[s] = ((arr - arr.min()) / rng).tolist() if rng > 0 else arr.tolist()

        print(f"[提取] 成功 {len(valid)}/{n} 个文件。")
        return {"times": times, "stats": stats}

    # ── 科学可视化 ─────────────────────────────────────────────
    def plot_results(self, results: Dict[str, Any]):
        os.makedirs(self.config.output_dir, exist_ok=True)

        times = results["times"]
        stats = results["stats"]
        n_stats = len(self.config.statistics)

        # 布局：时间序列子图 + 右侧汇总统计面板
        fig = plt.figure(figsize=self.config.figsize, constrained_layout=True)
        fig.suptitle(
            f"AIA 区域切片时间序列分析\n"
            f"波长: {self.config.wavelength or '全部'} Å  |  "
            f"区域类型: {self.config.region_type}  |  "
            f"文件数: {len(times)}",
            fontsize=13, fontweight="bold"
        )

        # 左侧：时间序列（n_stats 行）；右侧：汇总表
        gs = fig.add_gridspec(n_stats, 2, width_ratios=[4, 1], hspace=0.08)
        axes = [fig.add_subplot(gs[i, 0]) for i in range(n_stats)]
        ax_table = fig.add_subplot(gs[:, 1])

        palette = plt.cm.tab10(np.linspace(0, 0.9, n_stats))
        y_label = ("归一化强度" if self.config.normalize
                   else f"强度 [{self._data_unit}]")

        summary_rows = []

        for idx, stat_name in enumerate(self.config.statistics):
            _, label = _STAT_FUNCS[stat_name]
            values = np.array(stats[stat_name])
            ax = axes[idx]
            color = palette[idx]

            # 主曲线
            ax.plot(times, values, "-o", color=color, markersize=2.5,
                    linewidth=1.2, label=label)

            # std 填充带（若 std 也在统计列表中，给 mean 加阴影）
            if stat_name == "mean" and "std" in stats:
                std_arr = np.array(stats["std"])
                ax.fill_between(times, values - std_arr, values + std_arr,
                                color=color, alpha=0.15, label="±1σ")

            # 标注极值
            i_max = int(np.argmax(values))
            i_min = int(np.argmin(values))
            ax.annotate(f"Max\n{values[i_max]:.2g}",
                        xy=(times[i_max], values[i_max]),
                        xytext=(5, 8), textcoords="offset points",
                        fontsize=7, color="darkred",
                        arrowprops=dict(arrowstyle="->", color="darkred", lw=0.8))
            ax.annotate(f"Min\n{values[i_min]:.2g}",
                        xy=(times[i_min], values[i_min]),
                        xytext=(5, -18), textcoords="offset points",
                        fontsize=7, color="steelblue",
                        arrowprops=dict(arrowstyle="->", color="steelblue", lw=0.8))

            ax.set_ylabel(f"{label}\n{y_label}", fontsize=8)
            ax.legend(fontsize=8, loc="upper right")
            ax.grid(True, linestyle="--", alpha=0.4)
            ax.tick_params(axis="x",
                           labelbottom=(idx == n_stats - 1),
                           rotation=25 if idx == n_stats - 1 else 0)

            # 时间轴格式
            if idx == n_stats - 1:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M\n%m-%d"))
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.set_xlabel("时间 (UT)")

            # 汇总行
            summary_rows.append([
                label,
                f"{values.mean():.3g}",
                f"{values.std():.3g}",
                f"{values.min():.3g}",
                f"{values.max():.3g}",
            ])

        # ── 右侧汇总统计表 ──────────────────────────────────────
        ax_table.axis("off")
        col_labels = ["统计量", "均值", "标准差", "最小", "最大"]
        tbl = ax_table.table(
            cellText=summary_rows,
            colLabels=col_labels,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1.1, 1.6)

        # 表头样式
        for j in range(len(col_labels)):
            tbl[(0, j)].set_facecolor("#2c3e50")
            tbl[(0, j)].set_text_props(color="white", fontweight="bold")
        for i in range(1, len(summary_rows) + 1):
            bg = "#ecf0f1" if i % 2 == 0 else "#ffffff"
            for j in range(len(col_labels)):
                tbl[(i, j)].set_facecolor(bg)

        ax_table.set_title("汇总统计", fontsize=9, fontweight="bold", pad=4)

        # ── 保存 ────────────────────────────────────────────────
        if self.config.save_plot:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = Path(self.config.output_dir) / f"AIA_slice_{self.config.region_type}_{ts}.png"
            fig.savefig(out, dpi=self.config.plot_dpi)
            print(f"[输出] 图像 → {out}")

        if self.config.save_csv:
            self._save_csv(results)

        if self.config.show_plot:
            plt.show()
        else:
            plt.close(fig)

    # ── CSV 保存（含元信息头）──────────────────────────────────
    def _save_csv(self, results: Dict[str, Any]):
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path(self.config.output_dir) / f"AIA_slice_{self.config.region_type}_{ts}.csv"
        times = results["times"]
        stats = results["stats"]

        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            # 元信息
            w.writerow(["# AIA 切片时间序列数据"])
            w.writerow([f"# 生成时间: {datetime.now().isoformat()}"])
            w.writerow([f"# 波长: {self.config.wavelength or '全部'} Å"])
            w.writerow([f"# 区域类型: {self.config.region_type}"])
            w.writerow([f"# 单位: {self._data_unit}"])
            w.writerow([])
            w.writerow(["时间 (ISO)"] + self.config.statistics)
            for i, t in enumerate(times):
                row = [t.isoformat()] + [
                    stats[s][i] if i < len(stats[s]) else float("nan")
                    for s in self.config.statistics
                ]
                w.writerow(row)

        print(f"[输出] CSV  → {out}")


# ══════════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AIA 区域切片时间序列分析（优化版）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input_dir",    default="./data",         help="AIA 数据目录")
    p.add_argument("--file_pattern", default="*aia.lev1_euv_12s*", help="文件匹配模式")
    p.add_argument("--wavelength",   type=int, default=None,   help="AIA 波长（Å）")
    p.add_argument("--region_type",  choices=["rectangle","polygon"], default="rectangle")
    p.add_argument("--output_dir",   default="./output",       help="输出目录")
    p.add_argument("--statistics",   nargs="+", default=["mean","max","std"],
                   metavar="STAT",   help=f"统计量列表，可选: {VALID_STATS}")
    p.add_argument("--max_workers",  type=int, default=4,      help="并行读取线程数")
    p.add_argument("--normalize",    action="store_true",      help="对结果归一化")
    p.add_argument("--no_plot",      action="store_true",      help="不显示图形")
    p.add_argument("--no_csv",       action="store_true",      help="不保存 CSV")
    return p


def main():
    args   = build_parser().parse_args()
    config = AIASliceConfig(
        input_dir    = args.input_dir,
        file_pattern = args.file_pattern,
        wavelength   = args.wavelength,
        region_type  = args.region_type,
        output_dir   = args.output_dir,
        statistics   = args.statistics,
        max_workers  = args.max_workers,
        normalize    = args.normalize,
        show_plot    = not args.no_plot,
        save_csv     = not args.no_csv,
    )
    config.validate()

    proc = AIASliceProcessor(config)

    # 1. 查找文件
    print("[步骤 1/4] 查找 AIA 文件…")
    files = proc.find_aia_files()
    if not files:
        print("[错误] 未找到符合条件的文件。")
        sys.exit(1)
    print(f"  → 找到 {len(files)} 个文件。")

    # 2. 加载第一幅图用于区域选择
    print("[步骤 2/4] 加载参考图像…")
    try:
        ref_map = sunpy.map.Map(files[0])
        print(f"  → 参考文件: {Path(files[0]).name}  "
              f"({ref_map.data.shape[0]}×{ref_map.data.shape[1]} px)")
    except Exception as exc:
        print(f"[错误] 加载参考图像失败: {exc}")
        sys.exit(1)

    # 3. 区域选择
    print("[步骤 3/4] 请在弹出窗口中选择分析区域…")
    mask = proc.select_region(ref_map)
    if mask is None:
        print("[错误] 区域选择失败或已取消。")
        sys.exit(1)

    # 4. 提取 & 绘图
    print("[步骤 4/4] 提取时间序列数据…")
    results = proc.extract_data(files, mask)
    if not results["times"]:
        print("[错误] 未提取到有效数据。")
        sys.exit(1)

    print("绘制结果…")
    proc.plot_results(results)
    print("[完成] 全部处理完毕。")


if __name__ == "__main__":
    main()