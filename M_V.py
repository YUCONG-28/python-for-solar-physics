# -*- coding: utf-8 -*-
"""

Author: Severus

Created on: Wed Sep 28 23:00:00 2025
"""

"""
Video Generation from Image Sequences for Solar Data Visualization
==================================================================
This module creates high-quality MP4 videos from a sequence of image files,
specifically designed for processing AIA (Atmospheric Imaging Assembly)
multi-band composite images. It supports flexible timestamp parsing from
filenames, automatic resolution detection, parallel processing, and multiple
video encoding backends (FFmpeg, imageio, OpenCV) for maximum compatibility.

Key Features:
- Timestamp extraction from various filename formats (ISO, compact, day-of-year)
- Intelligent image sorting by timestamp or file modification time
- Automatic target resolution detection based on most common image dimensions
- Parallel image loading and preprocessing using multiprocessing
- Multiple video encoding fallbacks (FFmpeg > imageio > OpenCV)
- H.264 encoding with yuv420p pixel format for broad compatibility
- Support for grayscale, RGB, and RGBA image formats
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
# ║                    USER CONFIGURATION                       ║
# ╚══════════════════════════════════════════════════════════════╝

fps           = 22          # Video frame rate
input_dir     = r'D:\spike_topping_type_III\2025\20250124\RS_multi_band\multi_band_RR'
output_dir    = r'D:\spike_topping_type_III\2025\20250124\RS_multi_band\video'
video_name    = "RR.mp4"
target_suffix = ".png"      # Target file extension (case-insensitive)

# Frame range (based on sorted index, starting from 1)
start_frame = 1            # Start frame (inclusive)
end_frame   = None         # End frame (inclusive), None = process until last frame

# ── Sorting method ──────────────────────────────────────────────────
#   'filename'  Parse timestamp from filename for sorting (recommended)
#   'mtime'     Sort by file system modification time
#
# Supported filename timestamp formats (auto-detected, no manual configuration):
#   2025-04-28T030925Z.png          → ISO extended format
#   20250503_072028_071_RR.png      → Compact date+time
#   2025053_071600_353.png          → Year day-of-year (YYYYDDD) + time
#   149MHz_202553_071600_353.png    → Contains only HHMMSS, sorted relatively
#
# When some files cannot be timestamp-parsed, they are appended at the end
# in the default folder order.
sort_by = 'filename'

# ── Target resolution ────────────────────────────────────────────────
# Strategy when frame dimensions are inconsistent:
#   None      Auto-select (use most frequent size, aligned to multiples of 16)
#   (w, h)    Force specified, e.g., (1024, 1024)
target_size = None

# ── Parallel processing ────────────────────────────────────────────────
# Number of CPU cores to use (0 = auto-detect, 1 = single process, >1 = multiprocess)
num_workers = 12            # 0 means use all available cores

# ╚══════════════════════════════════════════════════════════════╝


# ──────────────────────────────────────────────────────────────
# § 1  Filename Timestamp Parsing
# ──────────────────────────────────────────────────────────────

def _dt(year, month, day, hour=0, minute=0, second=0):
    """Construct datetime, return None if parameters are invalid."""
    try:
        return datetime(int(year), int(month), int(day),
                        int(hour), int(minute), int(second))
    except (ValueError, TypeError):
        return None


def _dt_doy(year, doy, hour=0, minute=0, second=0):
    """Construct datetime from year + day-of-year, return None if invalid."""
    try:
        base = datetime(int(year), 1, 1)
        dt   = base + timedelta(days=int(doy) - 1)
        return dt.replace(hour=int(hour), minute=int(minute), second=int(second))
    except (ValueError, TypeError):
        return None


# Ordered by priority: more specific (more informative) patterns first
_TS_PATTERNS = [
    # ISO extended: 2025-04-28T030925Z  /  2025-04-28T03:09:25
    (re.compile(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):?(\d{2}):?(\d{2})'),
     lambda g: _dt(*g[:6])),

    # Compact date+time: 20250503_072028 / 20250503T072028
    (re.compile(r'(\d{4})(\d{2})(\d{2})[_\-T](\d{2})(\d{2})(\d{2})'),
     lambda g: _dt(*g[:6])),

    # Year day-of-year + time: 2025053_071600 (YYYYDDD_HHMMSS)
    (re.compile(r'(\d{4})(\d{3})[_\-T](\d{2})(\d{2})(\d{2})'),
     lambda g: _dt_doy(g[0], g[1], g[2], g[3], g[4])),

    # Year day-of-year: 2025053 (YYYYDDD, not followed by digits to avoid matching 8-digit dates)
    (re.compile(r'(\d{4})(\d{3})(?!\d)'),
     lambda g: _dt_doy(g[0], g[1])),

    # Compact date: 20250428 (not followed by digits to avoid matching longer sequences)
    (re.compile(r'(\d{4})(\d{2})(\d{2})(?!\d)'),
     lambda g: _dt(g[0], g[1], g[2])),

    # Only HHMMSS (no date, use epoch base day for relative sorting)
    # Matches isolated 6-digit groups, e.g., _202553_ → 20:25:53
    (re.compile(r'(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)'),
     lambda g: _dt(1970, 1, 1, g[0], g[1], g[2])),
]


def parse_timestamp(filename: str):
    """
    Extract timestamp from filename, return datetime; returns None if all patterns fail.
    For each pattern, take the first valid match in the filename.
    """
    stem = os.path.splitext(filename)[0]
    for pattern, builder in _TS_PATTERNS:
        for m in pattern.finditer(stem):
            dt = builder(m.groups())
            if dt is not None:
                return dt
    return None


# ──────────────────────────────────────────────────────────────
# § 2  Image Preprocessing
# ──────────────────────────────────────────────────────────────

def normalize_channels(img: np.ndarray) -> np.ndarray:
    """Convert any channel image (grayscale / RGBA / floating point) to RGB uint8."""
    # Data type normalization
    if img.dtype != np.uint8:
        if np.issubdtype(img.dtype, np.floating):
            img = np.clip(img * 255, 0, 255).astype(np.uint8)
        else:
            img = img.astype(np.uint8)

    if img.ndim == 2:                           # Grayscale → RGB
        img = np.stack([img] * 3, axis=-1)
    elif img.ndim == 3:
        c = img.shape[2]
        if c == 1:                              # Single channel → RGB
            img = np.concatenate([img] * 3, axis=-1)
        elif c == 4:                            # RGBA → RGB (black background composition)
            alpha = img[:, :, 3:4].astype(np.float32) / 255.0
            rgb   = img[:, :, :3].astype(np.float32)
            img   = np.clip(rgb * alpha, 0, 255).astype(np.uint8)
        # c == 3: already RGB, no processing needed
    return img


def resize_image(img: np.ndarray, tw: int, th: int) -> np.ndarray:
    """
    Resize image to (tw, th) (tw/th are pre-aligned to multiples of 16).
    Priority: Pillow LANCZOS → OpenCV LANCZOS4 → numpy crop/pad (no extra dependencies).
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

    # Fallback: crop + black padding (no third-party dependencies)
    h, w = img.shape[:2]
    result = np.zeros((th, tw, 3), dtype=img.dtype)
    cy, cx = min(h, th), min(w, tw)
    result[:cy, :cx] = img[:cy, :cx]
    return result


def align16(n: int) -> int:
    """Align down to a multiple of 16 (H.264 macroblock requirement)."""
    return n - n % 16


# ──────────────────────────────────────────────────────────────
# § 3  Video Writing (Triple Fallback)
# ──────────────────────────────────────────────────────────────

def write_video(images: list, output_path: str, fps: int) -> bool:
    """
    Prioritize FFmpeg for video writing to ensure maximum compatibility.
    images: List of RGB uint8 ndarrays, all frames must have identical dimensions.
    """
    h, w = images[0].shape[:2]
    n    = len(images)
    
    # Ensure width and height are even (yuv420p requirement)
    if w % 2 != 0 or h % 2 != 0:
        print(f"[WARN] Video dimensions {w}×{h} are not even, adjusting to {w - w%2}×{h - h%2}")
        new_w = w - w % 2
        new_h = h - h % 2
        # Adjust all image dimensions
        resized_images = []
        for img in images:
            resized_images.append(resize_image(img, new_w, new_h))
        images = resized_images
        w, h = new_w, new_h

    # Option 1: FFmpeg command line (most reliable)
    try:
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save as PNG sequence
            for i, img in enumerate(images):
                # Use imageio to save PNG
                imageio.imwrite(os.path.join(tmpdir, f"{i:06d}.png"), img)
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg', '-y',
                '-framerate', str(fps),
                '-i', os.path.join(tmpdir, '%06d.png'),
                '-c:v', 'libx264',        # H.264 encoding
                '-pix_fmt', 'yuv420p',    # Compatible pixel format
                '-preset', 'medium',      # Balance between encoding speed and quality
                '-crf', '23',             # Quality factor (18-28, lower is better quality)
                '-movflags', '+faststart', # Enable streaming playback
                '-vf', 'format=yuv420p',  # Ensure output is yuv420p
                output_path
            ]
            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
            if result.returncode == 0:
                print(f"[OK] Video saved (FFmpeg): {output_path}")
                print(f"  {n} frames | {fps} fps | {w}×{h}")
                print(f"  Encoding: H.264 (libx264), pixel format: yuv420p")
                return True
            else:
                print(f"  [FFmpeg] Failed: {result.stderr[-500:]}")
    except Exception as e:
        print(f"  [FFmpeg] Exception: {e}")

    # Option 2: imageio (fallback)
    try:
        imageio.mimwrite(output_path, images, fps=fps, codec='libx264', pixelformat='yuv420p')
        print(f"[OK] Video saved (imageio): {output_path}")
        print(f"  {n} frames | {fps} fps | {w}×{h}")
        return True
    except Exception as e:
        print(f"  [imageio] Failed: {e}")

    # Option 3: OpenCV (last attempt)
    try:
        import cv2
        # Use more compatible FourCC encoding
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Alternative H.264 representation
        out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
        if out.isOpened():
            for img in images:
                # Convert to BGR
                out.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            out.release()
            print(f"[OK] Video saved (OpenCV): {output_path}")
            return True
        else:
            print(f"  [OpenCV] Cannot open VideoWriter")
    except Exception as e:
        print(f"  [OpenCV] Failed: {e}")

    print("[ERROR] All writing methods failed, please ensure FFmpeg is installed and added to system PATH")
    print("        Or install imageio[ffmpeg]: pip install imageio[ffmpeg]")
    return False


# ──────────────────────────────────────────────────────────────
# § 4  Helper Function: Single Frame Processing
# ──────────────────────────────────────────────────────────────

def process_single_frame(file_path, target_size_tuple=None):
    """
    Process a single image file: read, normalize, resize (if needed).
    Returns processed image and its original dimensions.
    """
    try:
        img = normalize_channels(imageio.imread(file_path))
        h, w = img.shape[:2]
        if target_size_tuple:
            tw, th = target_size_tuple
            if w != tw or h != th:
                img = resize_image(img, tw, th)
        return img, (w, h)
    except Exception as exc:
        # Extract filename from file path
        file_name = os.path.basename(file_path)
        print(f"  Skipped: {file_name}  [{exc}]")
        return None, None

# ──────────────────────────────────────────────────────────────
# § 5  Main Workflow
# ──────────────────────────────────────────────────────────────

def main():
    global num_workers  # Declare num_workers as global variable
    # ── 5.1 Basic validation ─────────────────────────────────────────────
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")
    os.makedirs(output_dir, exist_ok=True)

    # ── 5.2 File scanning ─────────────────────────────────────────────
    suffix_lower = target_suffix.lower()
    with os.scandir(input_dir) as it:
        all_files = [e for e in it
                     if e.is_file() and e.name.lower().endswith(suffix_lower)]

    if not all_files:
        print(f"No {target_suffix} files found: {input_dir}")
        return
    print(f"Scanned {len(all_files)} files")

    # ── 5.3 Sorting ─────────────────────────────────────────────────
    if sort_by == 'filename':
        print("Sorting method: filename timestamp")
        parsed, failed = [], []
        for f in all_files:
            ts = parse_timestamp(f.name)
            (parsed if ts is not None else failed).append((ts, f))

        parsed.sort(key=lambda x: x[0])

        if failed:
            failed_sorted = failed  # Keep default folder order (os.scandir order)
            sample = ', '.join(f.name for _, f in failed[:3])
            tail   = f' ... total {len(failed)}' if len(failed) > 3 else ''
            print(f"  [WARN] Cannot parse timestamp (appended at end in default folder order): {sample}{tail}")
        else:
            failed_sorted = []

        sorted_files = [f for _, f in parsed] + [f for _, f in failed_sorted]

        if parsed:
            t0 = parsed[0][0].strftime('%Y-%m-%d %H:%M:%S')
            t1 = parsed[-1][0].strftime('%Y-%m-%d %H:%M:%S')
            print(f"  Time range: {t0} → {t1}")

    else:  # 'mtime'
        print("Sorting method: file modification time (mtime)")
        sorted_files = sorted(all_files, key=lambda e: e.stat().st_mtime)

    # ── 5.4 Frame range selection ───────────────────────────────────────────
    total = len(sorted_files)
    s = max(1, min(start_frame, total))
    e = total if end_frame is None else max(s, min(end_frame, total))
    selected_entries = sorted_files[s - 1:e]
    # Extract file path list for parallel processing
    selected_paths = [entry.path for entry in selected_entries]
    print(f"Frame range: frames {s} ~ {e} (total {len(selected_entries)} frames)")

    # ── 5.5 Determine target size (read a few samples first) ───────────────────────────
    # To determine target size, we first process a few frames (up to 10) to get size distribution
    sample_size = min(10, len(selected_entries))
    sample_files = selected_entries[:sample_size]
    print(f"Sampling {sample_size} frames to determine dominant size...")
    sample_images = []
    sample_sizes = []
    for entry in sample_files:
        try:
            img = normalize_channels(imageio.imread(entry.path))
            sample_images.append(img)
            sample_sizes.append((img.shape[1], img.shape[0]))
        except Exception as exc:
            print(f"  Sample skipped: {entry.name}  [{exc}]")

    if not sample_sizes:
        print("Sampling failed, cannot determine size, exiting")
        return

    if target_size:
        tw, th = align16(target_size[0]), align16(target_size[1])
        print(f"Target size (user-specified, 16-aligned): {tw}×{th}")
    else:
        (tw, th), cnt = Counter(sample_sizes).most_common(1)[0]
        tw, th = align16(tw), align16(th)
        print(f"Target size (dominant size, 16-aligned): {tw}×{th}"
              f"  ({cnt} frames out of {len(sample_sizes)} samples natively have this size)")

    # ── 5.6 Parallel processing of all frames ───────────────────────────────────────
    print("Parallel processing images…")
    # Determine number of worker processes
    if num_workers == 0:
        num_workers = mp.cpu_count()
    elif num_workers < 0:
        num_workers = max(1, mp.cpu_count() + num_workers)  # Negative means reduce core count
    num_workers = max(1, min(num_workers, len(selected_paths)))
    print(f"Using {num_workers} worker processes")

    # Use process pool
    images = []
    sizes = []
    n_resized = 0
    with mp.Pool(processes=num_workers) as pool:
        # Use imap to maintain order and stream processing
        # Use partial to fix target_size_tuple parameter
        for i, (img, size) in enumerate(pool.imap(partial(process_single_frame, target_size_tuple=(tw, th)), selected_paths)):
            if img is not None:
                images.append(img)
                sizes.append(size)
                if size != (tw, th):
                    n_resized += 1
            # Optional: show progress
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(selected_paths)} frames")

    if not images:
        print("No valid images read, exiting")
        return

    if n_resized:
        print(f"Resized {n_resized} frames to {tw}×{th}")

    # ── 5.7 Write video ─────────────────────────────────────────────
    output_path = os.path.join(output_dir, video_name)
    write_video(images, output_path, fps)


if __name__ == '__main__':
    # On Windows, multiprocessing requires protecting the main module
    mp.freeze_support()
    main()
