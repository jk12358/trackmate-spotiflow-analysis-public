"""Read movies one frame at a time so that a whole movie never sits in memory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np

from trackmate_spotiflow_analysis.errors import UserFacingError

TIFF_SUFFIXES = {".tif", ".tiff", ".stk"}
FFMPEG_SUFFIXES = {".avi", ".mp4", ".mov", ".mkv"}
VIDEO_SUFFIXES = TIFF_SUFFIXES | FFMPEG_SUFFIXES


def iter_frames(video_path: Path) -> Iterator[np.ndarray]:
    """Yield 2D grayscale frames in order (frame 0 first)."""
    suffix = video_path.suffix.lower()
    try:
        if suffix in TIFF_SUFFIXES:
            yield from _iter_tiff(video_path)
        elif suffix in FFMPEG_SUFFIXES:
            yield from _iter_ffmpeg(video_path)
        else:
            raise UserFacingError(
                f"{video_path.name} は対応していない動画の形式です。"
                f"{'、'.join(sorted(VIDEO_SUFFIXES))} のどれかにしてください。"
            )
    except UserFacingError:
        raise
    except Exception as exc:
        raise UserFacingError(
            f"{video_path.name} を動画として読めませんでした。"
            "Fiji で開けるか確かめ、開けるなら AVI（非圧縮）か TIFF で保存し直してください。"
        ) from exc


def _iter_tiff(video_path: Path) -> Iterator[np.ndarray]:
    import tifffile

    with tifffile.TiffFile(video_path) as tif:
        series = tif.series[0]
        try:
            stack = tifffile.memmap(video_path, mode="r", series=0)
        except ValueError:
            stack = None  # compressed or not contiguous: read page by page
        if stack is not None:
            for frame in _as_frames(stack):
                yield _to_gray(np.asarray(frame))
            return
        if len(series.pages) > 1:
            for page in series.pages:
                yield _to_gray(page.asarray())
            return
        for frame in _as_frames(series.asarray()):
            yield _to_gray(frame)


def _as_frames(stack: np.ndarray) -> Iterator[np.ndarray]:
    """Split a TIFF series into frames; a trailing axis of 3 or 4 is treated as color."""
    is_color = stack.shape[-1] in (3, 4)
    frame_ndim = 3 if is_color else 2
    if stack.ndim == frame_ndim:
        yield stack
        return
    yield from stack.reshape(-1, *stack.shape[-frame_ndim:])


def _iter_ffmpeg(video_path: Path) -> Iterator[np.ndarray]:
    import imageio.v3 as iio

    for frame in iio.imiter(video_path, plugin="FFMPEG"):
        yield _to_gray(frame)


def _to_gray(frame: np.ndarray) -> np.ndarray:
    frame = np.asarray(frame)
    if frame.ndim == 3:
        frame = frame[..., :3].mean(axis=-1)
    return frame.astype(np.float32, copy=False)


def normalize_frame(frame: np.ndarray) -> np.ndarray:
    """Scale intensities to 0-255 using the 1st and 99.5th percentiles."""
    low, high = np.percentile(frame, [1, 99.5])
    if high <= low:
        return np.zeros(frame.shape, dtype=np.uint8)
    scaled = np.clip((frame - low) / (high - low), 0, 1)
    return (scaled * 255).astype(np.uint8)
