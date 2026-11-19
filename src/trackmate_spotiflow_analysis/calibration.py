"""Convert TrackMate positions to pixels and check the XML calibration.

The analysis always uses the frame interval and pixel size from the settings.
TrackMate stores positions in pixels when the movie is uncalibrated and in
physical units (for example um) when it is calibrated, so positions are first
converted back to pixels with the XML's own pixel width. When the XML's
calibration disagrees with the settings, a warning is returned for the user.
"""

from __future__ import annotations

from dataclasses import dataclass

from trackmate_spotiflow_analysis.errors import UserFacingError
from trackmate_spotiflow_analysis.settings import AnalysisSettings
from trackmate_spotiflow_analysis.trackmate_xml import TrackMateData

PIXEL_UNITS = {"pixel", "pixels", "px", ""}
UM_PER_UNIT = {
    "µm": 1.0,  # micro sign
    "μm": 1.0,  # Greek small letter mu
    "um": 1.0,
    "micron": 1.0,
    "microns": 1.0,
    "nm": 1e-3,
    "mm": 1e3,
}
FRAME_UNITS = {"frame", "frames", ""}
S_PER_UNIT = {"s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0, "ms": 1e-3, "min": 60.0}
RELATIVE_TOLERANCE = 0.01


@dataclass(frozen=True)
class Calibration:
    position_units_per_px: float
    xml_pixel_size_um: float | None
    xml_frame_interval_s: float | None
    warnings: tuple[str, ...]


def resolve_calibration(data: TrackMateData, settings: AnalysisSettings) -> Calibration:
    position_units_per_px, xml_pixel_size_um = _spatial(data)
    xml_frame_interval_s = _temporal(data)
    warnings = []
    if xml_pixel_size_um is not None and _differs(xml_pixel_size_um, settings.pixel_size_um):
        warnings.append(
            f"XML の pixel size（{xml_pixel_size_um:.5g} um）が、設定の値"
            f"（{settings.pixel_size_um:.5g} um）と違います。解析には設定の値を使いました。"
            "顕微鏡や倍率が違う動画なら、設定の値を直して実行し直してください。"
        )
    if xml_frame_interval_s is not None and _differs(
        xml_frame_interval_s, settings.frame_interval_s
    ):
        warnings.append(
            f"XML の frame interval（{xml_frame_interval_s:.5g} s）が、設定の値"
            f"（{settings.frame_interval_s:.5g} s）と違います。解析には設定の値を使いました。"
            "撮影条件が違う動画なら、設定の値を直して実行し直してください。"
        )
    return Calibration(
        position_units_per_px=position_units_per_px,
        xml_pixel_size_um=xml_pixel_size_um,
        xml_frame_interval_s=xml_frame_interval_s,
        warnings=tuple(warnings),
    )


def _spatial(data: TrackMateData) -> tuple[float, float | None]:
    units = data.spatial_units.strip()
    if units.lower() in PIXEL_UNITS:
        return 1.0, None
    um_per_unit = UM_PER_UNIT.get(units) or UM_PER_UNIT.get(units.lower())
    pixel_width = data.image.pixel_width
    if um_per_unit is None or not pixel_width or pixel_width <= 0:
        raise UserFacingError(
            f"{data.xml_path.name} の座標の単位（{units}）または pixel 幅を読み取れませんでした。"
            "Fiji の Image > Properties で単位を pixel か um にしてから、TrackMate で保存し直して"
            "ください。"
        )
    return pixel_width, pixel_width * um_per_unit


def _temporal(data: TrackMateData) -> float | None:
    units = data.time_units.strip().lower()
    interval = data.image.time_interval
    if units in FRAME_UNITS or interval is None or interval <= 0:
        return None
    s_per_unit = S_PER_UNIT.get(units)
    return None if s_per_unit is None else interval * s_per_unit


def _differs(value: float, reference: float) -> bool:
    return abs(value - reference) > RELATIVE_TOLERANCE * abs(reference)
