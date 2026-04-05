"""
Created on Wed Sep 28 23:00:00 2025

@author: Severus
"""

import os
import re
import imageio.v2 as imageio
import numpy as np
from datetime import datetime, timedelta
from collections import Counter
import multiprocessing as mp
from functools import partial
import sys


# ╔══════════════════════════════════════════════════════════════╗
# ║                      用 户 配 置 区                         ║
# ╚══════════════════════════════════════════════════════════════╝

fps           = 12          # 视频帧率
input_dir     = r'<PROJECT_ROOT>\2025\20250428\AIA\multi_band'
output_dir    = r'<PROJECT_ROOT>\2025\20250428\AIA\video'
video_name    = "AIA_multi_band.mp4"
target_suffix = ".png"      # 目标文件扩展名（大小写不敏感）

# 帧范围（基于排序后的索引，从 1 开始）
start_frame = 1             # 起始帧（含）
end_frame   = None          # 结束帧（含），None = 处理到最后一帧

# ── 排序方式 ──────────────────────────────────────────────────
#   'filename'  解析文件名中的时间戳排序（推荐，见下方说明）
#   'mtime'     按文件系统修改时间排序
#
# 支持的文件名时间戳格式（自动识别，无需手动配置）：
#   2025-04-28T030925Z.png          → ISO 扩展格式
#   20250503_072028_071_RR.png      → 紧凑日期+时间
#   2025053_071600_353.png          → 年积日（YYYYDDD）+时间
#   149MHz_202553_071600_353.png    → 仅含 HHMMSS，按时间相对排序
#
# 当部分文件无法解析时间戳时，这些文件将按 mtime 追加到末尾。
sort_by = 'filename'

# ── 目标分辨率 ────────────────────────────────────────────────
# 帧尺寸不一致时的处理策略：
#   None      自动选择（使用出现次数最多的尺寸，并对齐到 16 的倍数）
#   (w, h)    强制指定，例如 (1024, 1024)
target_size = None

# ── 并行处理 ────────────────────────────────────────────────
# 使用的 CPU 核心数（0 = 自动检测，1 = 单进程，>1 = 多进程）
num_workers = 0             # 0 表示使用所有可用核心

# ╚══════════════════════════════════════════════════════════════╝


# ──────────────────────────────────────────────────────────────
# § 1  文件名时间戳解析
# ──────────────────────────────────────────────────────────────

def _dt(year, month, day, hour=0, minute=0, second=0):
    """构造 datetime，参数非法时返回 None。"""
    try:
        return datetime(int(year), int(month), int(day),
                        int(hour), int(minute), int(second))
    except (ValueError, TypeError):
        return None


def _dt_doy(year, doy, hour=0, minute=0, second=0):
    """由年份 + 年积日（Day-of-Year）构造 datetime，非法时返回 None。"""
    try:
        base = datetime(int(year), 1, 1)
        dt   = base + timedelta(days=int(doy) - 1)
        return dt.replace(hour=int(hour), minute=int(minute), second=int(second))
    except (ValueError, TypeError):
        return None


# 按优先级排列：越具体（信息量越大）越靠前
_TS_PATTERNS = [
    # ISO 扩展：2025-04-28T030925Z  /  2025-04-28T03:09:25
    (re.compile(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):?(\d{2}):?(\d{2})'),
     lambda g: _dt(*g[:6])),

    # 紧凑日期+时间：20250503_072028 / 20250503T072028
    (re.compile(r'(\d{4})(\d{2})(\d{2})[_\-T](\d{2})(\d{2})(\d{2})'),
     lambda g: _dt(*g[:6])),

    # 年积日+时间：2025053_071600（YYYYDDD_HHMMSS）
    (re.compile(r'(\d{4})(\d{3})[_\-T](\d{2})(\d{2})(\d{2})'),
     lambda g: _dt_doy(g[0], g[1], g[2], g[3], g[4])),

    # 年积日：2025053（YYYYDDD，后面不跟数字，避免误匹配 8 位日期）
    (re.compile(r'(\d{4})(\d{3})(?!\d)'),
     lambda g: _dt_doy(g[0], g[1])),

    # 紧凑日期：20250428（后面不跟数字，避免误匹配更长序列）
    (re.compile(r'(\d{4})(\d{2})(\d{2})(?!\d)'),
     lambda g: _dt(g[0], g[1], g[2])),

    # 仅含 HHMMSS（无日期，用 epoch 基准日相对排序）
    # 匹配独立的 6 位数字段，如 _202553_ → 20:25:53
    (re.compile(r'(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)'),
     lambda g: _dt(1970, 1, 1, g[0], g[1], g[2])),
]


def parse_timestamp(filename: str):
    """
    从文件名中提取时间戳，返回 datetime；所有模式均失败则返回 None。
    对每个模式取文件名中第一个有效匹配。
    """
    stem = os.path.splitext(filename)[0]
    for pattern, builder in _TS_PATTERNS:
        for m in pattern.finditer(stem):
            dt = builder(m.groups())
            if dt is not None:
                return dt
    return None


# ──────────────────────────────────────────────────────────────
# § 2  图像预处理
# ──────────────────────────────────────────────────────────────

def normalize_channels(img: np.ndarray) -> np.ndarray:
    """将任意通道图像（灰度 / RGBA / 浮点）统一转为 RGB uint8。"""
    # 数据类型归一化
    if img.dtype != np.uint8:
        if np.issubdtype(img.dtype, np.floating):
            img = np.clip(img * 255, 0, 255).astype(np.uint8)
        else:
            img = img.astype(np.uint8)

    if img.ndim == 2:                           # 灰度 → RGB
        img = np.stack([img] * 3, axis=-1)
    elif img.ndim == 3:
        c = img.shape[2]
        if c == 1:                              # 单通道 → RGB
            img = np.concatenate([img] * 3, axis=-1)
        elif c == 4:                            # RGBA → RGB（黑底合成）
            alpha = img[:, :, 3:4].astype(np.float32) / 255.0
            rgb   = img[:, :, :3].astype(np.float32)
            img   = np.clip(rgb * alpha, 0, 255).astype(np.uint8)
        # c == 3：已是 RGB，无需处理
    return img


def resize_image(img: np.ndarray, tw: int, th: int) -> np.ndarray:
    """
    将图像缩放到 (tw, th)（tw/th 已预先对齐到 16 的倍数）。
    优先 Pillow LANCZOS → OpenCV LANCZOS4 → numpy crop/pad（无额外依赖）。
    """
    if img.shape[0] == th and img.shape[1] == tw:
        return img

    try:
        from PIL import Image as PILImage
        return np.array(PILImage.fromarray(img).resize((tw, th), PILImage.LANCZOS))
    except ImportError:
        pass

    try:
        import cv2
        return cv2.resize(img, (tw, th), interpolation=cv2.INTER_LANCZOS4)
    except ImportError:
        pass

    # Fallback：裁剪 + 黑色填充（不依赖第三方库）
    h, w = img.shape[:2]
    result = np.zeros((th, tw, 3), dtype=img.dtype)
    cy, cx = min(h, th), min(w, tw)
    result[:cy, :cx] = img[:cy, :cx]
    return result


def align16(n: int) -> int:
    """向下对齐到 16 的倍数（H.264 宏块要求）。"""
    return n - n % 16


# ──────────────────────────────────────────────────────────────
# § 3  视频写入（三重 fallback）
# ──────────────────────────────────────────────────────────────

def write_video(images: list, output_path: str, fps: int) -> bool:
    """
    依次尝试 imageio → OpenCV → FFmpeg 写出视频。
    images: RGB uint8 ndarray 列表，所有帧尺寸必须一致。
    """
    h, w = images[0].shape[:2]
    n    = len(images)

    # 方案 1：imageio
    try:
        imageio.mimwrite(output_path, images, fps=fps)
        print(f"✓ 视频已保存：{output_path}")
        print(f"  {n} 帧 | {fps} fps | {w}×{h}")
        return True
    except Exception as e:
        print(f"  [imageio] 失败：{e}")

    # 方案 2：OpenCV
    try:
        import cv2
        out = cv2.VideoWriter(output_path,
                              cv2.VideoWriter_fourcc(*'mp4v'),
                              fps, (w, h))
        for img in images:
            out.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        out.release()
        print(f"✓ 视频已保存（OpenCV）：{output_path}")
        return True
    except Exception as e:
        print(f"  [OpenCV] 失败：{e}")

    # 方案 3：FFmpeg 命令行
    try:
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, img in enumerate(images):
                imageio.imwrite(os.path.join(tmpdir, f"{i:06d}.png"), img)
            cmd = [
                'ffmpeg', '-y',
                '-framerate', str(fps),
                '-i', os.path.join(tmpdir, '%06d.png'),
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-preset', 'slow', '-crf', '18',
                output_path
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0:
                print(f"✓ 视频已保存（FFmpeg）：{output_path}")
                return True
            print(f"  [FFmpeg] 失败：{r.stderr[-400:]}")
    except Exception as e:
        print(f"  [FFmpeg] 异常：{e}")

    print("✗ 所有写入方案均失败，请检查 imageio / opencv-python / ffmpeg 安装情况")
    return False


# ──────────────────────────────────────────────────────────────
# § 4  辅助函数：单帧处理
# ──────────────────────────────────────────────────────────────

def process_single_frame(args, target_size_tuple=None):
    """
    处理单个图像文件：读取、标准化、调整大小（如果需要）。
    返回处理后的图像及其原始尺寸。
    """
    entry, target_size_tuple = args
    try:
        img = normalize_channels(imageio.imread(entry.path))
        h, w = img.shape[:2]
        if target_size_tuple:
            tw, th = target_size_tuple
            if w != tw or h != th:
                img = resize_image(img, tw, th)
        return img, (w, h)
    except Exception as exc:
        print(f"  跳过：{entry.name}  [{exc}]")
        return None, None

# ──────────────────────────────────────────────────────────────
# § 5  主流程
# ──────────────────────────────────────────────────────────────

def main():
    # ── 5.1 基本校验 ─────────────────────────────────────────────
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入文件夹不存在：{input_dir}")
    os.makedirs(output_dir, exist_ok=True)

    # ── 5.2 扫描文件 ─────────────────────────────────────────────
    suffix_lower = target_suffix.lower()
    with os.scandir(input_dir) as it:
        all_files = [e for e in it
                     if e.is_file() and e.name.lower().endswith(suffix_lower)]

    if not all_files:
        print(f"未找到 {target_suffix} 文件：{input_dir}")
        return
    print(f"扫描到 {len(all_files)} 个文件")

    # ── 5.3 排序 ─────────────────────────────────────────────────
    if sort_by == 'filename':
        print("排序方式：文件名时间戳")
        parsed, failed = [], []
        for f in all_files:
            ts = parse_timestamp(f.name)
            (parsed if ts is not None else failed).append((ts, f))

        parsed.sort(key=lambda x: x[0])

        if failed:
            failed_sorted = sorted(failed, key=lambda x: x[1].stat().st_mtime)
            sample = ', '.join(f.name for _, f in failed[:3])
            tail   = f' … 共 {len(failed)} 个' if len(failed) > 3 else ''
            print(f"  ⚠ 无法解析时间戳（按 mtime 追加到末尾）：{sample}{tail}")
        else:
            failed_sorted = []

        sorted_files = [f for _, f in parsed] + [f for _, f in failed_sorted]

        if parsed:
            t0 = parsed[0][0].strftime('%Y-%m-%d %H:%M:%S')
            t1 = parsed[-1][0].strftime('%Y-%m-%d %H:%M:%S')
            print(f"  时间范围：{t0} → {t1}")

    else:  # 'mtime'
        print("排序方式：文件修改时间（mtime）")
        sorted_files = sorted(all_files, key=lambda e: e.stat().st_mtime)

    # ── 5.4 帧范围截取 ───────────────────────────────────────────
    total = len(sorted_files)
    s = max(1, min(start_frame, total))
    e = total if end_frame is None else max(s, min(end_frame, total))
    selected = sorted_files[s - 1:e]
    print(f"帧范围：第 {s} ~ {e} 帧（共 {len(selected)} 帧）")

    # ── 5.5 确定目标尺寸（先读取部分样本）──────────────────────────
    # 为了确定目标尺寸，我们先处理前几帧（最多10帧）来获取尺寸分布
    sample_size = min(10, len(selected))
    sample_files = selected[:sample_size]
    print(f"采样 {sample_size} 帧以确定主流尺寸...")
    sample_images = []
    sample_sizes = []
    for entry in sample_files:
        try:
            img = normalize_channels(imageio.imread(entry.path))
            sample_images.append(img)
            sample_sizes.append((img.shape[1], img.shape[0]))
        except Exception as exc:
            print(f"  采样跳过：{entry.name}  [{exc}]")

    if not sample_sizes:
        print("采样失败，无法确定尺寸，退出")
        return

    if target_size:
        tw, th = align16(target_size[0]), align16(target_size[1])
        print(f"目标尺寸（用户指定，16 对齐）：{tw}×{th}")
    else:
        (tw, th), cnt = Counter(sample_sizes).most_common(1)[0]
        tw, th = align16(tw), align16(th)
        print(f"目标尺寸（主流尺寸，16 对齐）：{tw}×{th}"
              f"  （在 {len(sample_sizes)} 个样本中 {cnt} 帧原生此尺寸）")

    # ── 5.6 并行处理所有帧 ───────────────────────────────────────
    print("并行处理图像…")
    # 确定工作进程数
    if num_workers == 0:
        num_workers = mp.cpu_count()
    elif num_workers < 0:
        num_workers = max(1, mp.cpu_count() + num_workers)  # 负数表示减少核心数
    num_workers = max(1, min(num_workers, len(selected)))
    print(f"使用 {num_workers} 个工作进程")

    # 准备参数
    process_args = [(entry, (tw, th)) for entry in selected]

    # 使用进程池
    images = []
    sizes = []
    n_resized = 0
    with mp.Pool(processes=num_workers) as pool:
        # 使用 imap 以保持顺序并流式处理
        for i, (img, size) in enumerate(pool.imap(partial(process_single_frame, target_size_tuple=(tw, th)), selected)):
            if img is not None:
                images.append(img)
                sizes.append(size)
                if size != (tw, th):
                    n_resized += 1
            # 可选：显示进度
            if (i + 1) % 10 == 0:
                print(f"  已处理 {i + 1}/{len(selected)} 帧")

    if not images:
        print("未读取到有效图片，退出")
        return

    if n_resized:
        print(f"已缩放 {n_resized} 帧至 {tw}×{th}")

    # ── 5.7 写出视频 ─────────────────────────────────────────────
    output_path = os.path.join(output_dir, video_name)
    write_video(images, output_path, fps)


if __name__ == '__main__':
    # 在 Windows 上，multiprocessing 需要保护主模块
    mp.freeze_support()
    main()
