# -*- coding: utf-8 -*-
"""递归规范命名 SDO/AIA 与 SDO/HMI FITS 文件。

脚本会扫描用户给定文件夹及其子文件夹，根据文件名中的产品类型和波段
自动补充 JSOC 风格前缀。已规范命名、无法识别或目标文件已存在的文件
会被跳过，不会覆盖已有数据。
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

# 用户配置区：直接运行本脚本时会使用这里的路径和 dry-run 设置。
TARGET_FOLDER = r"D:\spike_topping_type_III\2025\20250803\SDO"
DRY_RUN = False

AIA_UV_PREFIX = "aia.lev1_uv_24s"
AIA_EUV_PREFIX = "aia.lev1_euv_12s"
HMI_PREFIX = "hmi.M_45s"

AIA_UV_WAVELENGTHS = {"1600"}
AIA_EUV_WAVELENGTHS = {"94", "131", "171", "193", "211", "304", "335"}
KNOWN_PREFIXES = (AIA_UV_PREFIX, AIA_EUV_PREFIX, HMI_PREFIX)

AIA_IMAGE_PATTERN = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2}T\d{6}Z)\." r"(?P<wavelength>\d+)\.image_lev1\.fits$",
    re.IGNORECASE,
)
HMI_MAGNETOGRAM_PATTERN = re.compile(
    r"^\d{8}_\d{6}_TAI\.\d+\.magnetogram\.fits$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RenameDecision:
    """单个 FITS 文件的命名判断结果。"""

    action: str
    source: Path
    target: Path | None
    message: str


@dataclass
class RenameSummary:
    """批量重命名统计。"""

    renamed: int = 0
    planned: int = 0
    skipped: int = 0
    unrecognized: int = 0
    conflicts: int = 0


def strip_known_prefix(filename: str) -> tuple[str | None, str]:
    """拆分已有标准前缀，返回 (前缀, 剩余文件名)。"""
    for prefix in KNOWN_PREFIXES:
        prefix_with_dot = f"{prefix}."
        if filename.startswith(prefix_with_dot):
            return prefix, filename[len(prefix_with_dot) :]
    return None, filename.lstrip(".")


def expected_prefix_for_payload(payload: str) -> str | None:
    """根据去掉前缀后的文件名判断应使用的标准前缀。"""
    aia_match = AIA_IMAGE_PATTERN.match(payload)
    if aia_match:
        wavelength = aia_match.group("wavelength")
        if wavelength in AIA_UV_WAVELENGTHS:
            return AIA_UV_PREFIX
        if wavelength in AIA_EUV_WAVELENGTHS:
            return AIA_EUV_PREFIX
        return None

    if HMI_MAGNETOGRAM_PATTERN.match(payload):
        return HMI_PREFIX

    return None


def build_target_name(filename: str) -> tuple[str | None, str]:
    """返回目标文件名和跳过原因。"""
    existing_prefix, payload = strip_known_prefix(filename)
    expected_prefix = expected_prefix_for_payload(payload)

    if expected_prefix is None:
        return None, "无法从文件名判断 AIA/HMI 产品类型"

    if existing_prefix == expected_prefix:
        return None, "已是规范文件名"

    if existing_prefix is not None:
        return None, f"已有前缀 {existing_prefix}，但期望前缀为 {expected_prefix}"

    return f"{expected_prefix}.{payload}", ""


def decide_rename(path: Path) -> RenameDecision:
    """判断单个路径是否需要重命名。"""
    if path.suffix.lower() != ".fits":
        return RenameDecision("skipped", path, None, "不是 FITS 文件")

    target_name, reason = build_target_name(path.name)
    if target_name is None:
        action = "unrecognized" if reason.startswith("无法") else "skipped"
        return RenameDecision(action, path, None, reason)

    target = path.with_name(target_name)
    if target.exists():
        return RenameDecision("conflict", path, target, "目标文件已存在")

    return RenameDecision("rename", path, target, "待重命名")


def iter_fits_files(directory: Path) -> list[Path]:
    """递归获取目录中的 FITS 文件。"""
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".fits"
    )


def rename_fits_files(directory: str | Path, dry_run: bool = False) -> RenameSummary:
    """递归扫描目录并按 AIA/HMI 规则批量重命名 FITS 文件。"""
    root = Path(directory).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"找不到文件夹: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"不是文件夹: {root}")

    summary = RenameSummary()
    for source in iter_fits_files(root):
        decision = decide_rename(source)

        if decision.action == "rename":
            if dry_run:
                print(f"[dry-run] {source} -> {decision.target}")
                summary.planned += 1
            else:
                assert decision.target is not None
                source.rename(decision.target)
                print(f"[renamed] {source} -> {decision.target}")
                summary.renamed += 1
        elif decision.action == "conflict":
            print(f"[conflict] {source} -> {decision.target} ({decision.message})")
            summary.conflicts += 1
        elif decision.action == "unrecognized":
            print(f"[unrecognized] {source} ({decision.message})")
            summary.unrecognized += 1
        else:
            print(f"[skipped] {source} ({decision.message})")
            summary.skipped += 1

    print_summary(summary, dry_run=dry_run)
    return summary


def print_summary(summary: RenameSummary, dry_run: bool = False) -> None:
    """打印批量处理统计。"""
    print("\n处理完成")
    if dry_run:
        print(f"计划重命名: {summary.planned}")
    print(f"成功重命名: {summary.renamed}")
    print(f"已跳过: {summary.skipped}")
    print(f"无法识别: {summary.unrecognized}")
    print(f"命名冲突: {summary.conflicts}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="递归扫描指定文件夹，规范命名 SDO/AIA 与 SDO/HMI FITS 文件。"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="需要扫描和重命名的文件夹；未提供时使用代码中的 TARGET_FOLDER",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要重命名的结果，不实际修改文件名",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    args = parse_args(argv)
    directory = args.directory or TARGET_FOLDER
    dry_run = args.dry_run or DRY_RUN
    try:
        rename_fits_files(directory, dry_run=dry_run)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"错误: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
