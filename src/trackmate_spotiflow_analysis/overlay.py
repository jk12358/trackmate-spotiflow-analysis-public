"""Draw tracks on the movie and save an animated GIF.

Frames are read one at a time and drawn with Pillow, so memory stays small:
each GIF frame is written to the file as soon as it is drawn.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import GifImagePlugin, Image, ImageDraw, ImageFont

from trackmate_spotiflow_analysis.video import iter_frames, normalize_frame

MOBILE_COLOR = (255, 40, 40)
IMMOBILE_COLOR = (0, 230, 255)
HISTORY_COLOR = (255, 230, 0)
LABEL_BACKGROUND = (0, 0, 0, 115)


@dataclass(frozen=True)
class OverlayStyle:
    history_alpha: float
    circle_radius_px: float
    line_width: int
    label_size: int


ALL_TRACKS_STYLE = OverlayStyle(
    history_alpha=0.35, circle_radius_px=4.5, line_width=1, label_size=11
)
FITTED_STYLE = OverlayStyle(history_alpha=0.6, circle_radius_px=5.5, line_width=2, label_size=12)


@dataclass(frozen=True)
class OverlayResult:
    rendered_frames: int
    video_frames_shorter_than_tracks: bool


def render_overlay_gif(
    video_path: Path,
    points: pd.DataFrame,
    output_path: Path,
    *,
    fps: int,
    target_width_px: int,
    style: OverlayStyle,
) -> OverlayResult:
    """Render a GIF.

    `points` has columns track_id, frame, x_px, y_px, label and color (an RGB
    tuple). Frames from the first to the last frame with a point are drawn.
    """
    points = points.sort_values(["track_id", "frame"])
    first_frame, last_frame = int(points["frame"].min()), int(points["frame"].max())
    tracks = _TrackHistory(points)
    font = ImageFont.load_default(size=style.label_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered, frame_number = 0, -1
    with _GifWriter(output_path, duration_ms=int(round(1000 / fps))) as gif:
        for frame_number, frame in enumerate(iter_frames(video_path)):
            if frame_number < first_frame:
                continue
            if frame_number > last_frame:
                break
            scale = target_width_px / frame.shape[1]
            image = _base_image(frame, scale)
            _draw_tracks(image, tracks, frame_number, scale, style, font)
            gif.add(image.convert("RGB").quantize(colors=128, method=Image.Quantize.MEDIANCUT))
            rendered += 1
    if not rendered:
        output_path.unlink(missing_ok=True)
    return OverlayResult(
        rendered_frames=rendered,
        video_frames_shorter_than_tracks=frame_number < last_frame,
    )


class _GifWriter:
    """Write an animated GIF frame by frame so that frames never pile up in memory.

    Uses Pillow's documented GIF helpers (getheader/getdata); every frame carries
    its own color table, so frames can be quantized independently.
    """

    LOOP_FOREVER = b"!\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"

    def __init__(self, path: Path, *, duration_ms: int) -> None:
        self.path = path
        self.duration_ms = duration_ms
        self.file = None
        self.started = False

    def __enter__(self) -> _GifWriter:
        self.file = self.path.open("wb")
        return self

    def add(self, frame: Image.Image) -> None:
        if not self.started:
            header, _ = GifImagePlugin.getheader(frame, info={"optimize": False})
            self.file.writelines(header)
            self.file.write(self.LOOP_FOREVER)
            self.started = True
        chunks = GifImagePlugin.getdata(frame, duration=self.duration_ms, include_color_table=True)
        self.file.writelines(chunks)

    def __exit__(self, *exc_info: object) -> None:
        if self.started:
            self.file.write(b";")
        self.file.close()


class _TrackHistory:
    """Per-track arrays to look up the path up to a frame quickly."""

    def __init__(self, points: pd.DataFrame) -> None:
        self.tracks = []
        for _track_id, group in points.groupby("track_id", sort=True):
            self.tracks.append(
                (
                    group["frame"].to_numpy(dtype=int),
                    group[["x_px", "y_px"]].to_numpy(dtype=float),
                    str(group["label"].iloc[0]),
                    tuple(group["color"].iloc[0]),
                )
            )


def _base_image(frame: np.ndarray, scale: float) -> Image.Image:
    gray = Image.fromarray(normalize_frame(frame))
    size = (max(1, round(frame.shape[1] * scale)), max(1, round(frame.shape[0] * scale)))
    return gray.resize(size, Image.Resampling.BILINEAR).convert("RGBA")


def _draw_tracks(
    image: Image.Image,
    history: _TrackHistory,
    frame_number: int,
    scale: float,
    style: OverlayStyle,
    font: ImageFont.ImageFont,
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    line_color = (*HISTORY_COLOR, int(255 * style.history_alpha))
    active = []
    for frames, xy, label, color in history.tracks:
        end = int(np.searchsorted(frames, frame_number, side="right"))
        if end == 0:
            continue
        path = [_to_image(x, y, scale) for x, y in xy[:end]]
        if len(path) > 1:
            draw.line(path, fill=line_color, width=style.line_width)
        if frames[end - 1] == frame_number:
            active.append((path[-1], label, color))
    image.alpha_composite(layer)
    _draw_active(image, active, scale, style, font)


def _draw_active(
    image: Image.Image,
    active: list[tuple[tuple[float, float], str, tuple[int, int, int]]],
    scale: float,
    style: OverlayStyle,
    font: ImageFont.ImageFont,
) -> None:
    labels = Image.new("RGBA", image.size, (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(labels)
    draw = ImageDraw.Draw(image)
    radius = style.circle_radius_px * max(scale, 1.0)
    for (x, y), label, color in active:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=2)
        if label:
            position = (x + radius + 2, y - radius - style.label_size)
            box = label_draw.textbbox(position, label, font=font)
            label_draw.rectangle(box, fill=LABEL_BACKGROUND)
            label_draw.text(position, label, fill=color, font=font)
    image.alpha_composite(labels)


def _to_image(x_px: float, y_px: float, scale: float) -> tuple[float, float]:
    # TrackMate positions refer to pixel centers; image coordinates to pixel edges.
    return ((x_px + 0.5) * scale, (y_px + 0.5) * scale)
