"""How TrackMate produced an XML: version, detector, tracker settings and counts."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from trackmate_spotiflow_analysis.errors import UserFacingError

UNIT_SYMBOLS = {"pixel": "px", "pixels": "px", "micron": "µm", "microns": "µm", "µm": "µm"}


@dataclass(frozen=True)
class TrackMateRun:
    trackmate_version: str = ""
    detector: str = ""
    spotiflow_model: str = ""
    quality_threshold: float | None = None
    spatial_units: str = ""
    linking_max_distance: float | None = None
    gap_closing: bool | None = None
    gap_closing_max_distance: float | None = None
    max_frame_gap: int | None = None
    spot_count: int | None = None
    track_count: int | None = None

    def summary_fields(self) -> dict[str, Any]:
        """Columns added to summary.csv (English names, raw values)."""
        return {f"trackmate_{key}": value for key, value in asdict(self).items()}

    def display_fields(self) -> dict[str, str]:
        """Short Japanese labels and values for tables shown to users."""
        unit = UNIT_SYMBOLS.get(self.spatial_units.lower(), self.spatial_units)
        return {
            "spot 数": _text(self.spot_count),
            "track 数": _text(self.track_count),
            "検出": self.spotiflow_model or self.detector or "不明",
            "linking": _distance(self.linking_max_distance, unit),
            "gap closing": self._gap_closing_text(unit),
        }

    def _gap_closing_text(self, unit: str) -> str:
        if self.gap_closing is False:
            return "なし"
        if self.gap_closing_max_distance is None:
            return "不明"
        frames = f" / {self.max_frame_gap} フレーム" if self.max_frame_gap is not None else ""
        return _distance(self.gap_closing_max_distance, unit) + frames


def read_trackmate_run(xml_path: Path) -> TrackMateRun:
    """Read only what describes the run, streaming through the spots and tracks."""
    version, model_attrib, settings = "", {}, None
    spots = tracks = 0
    try:
        for event, element in ET.iterparse(xml_path, events=("start", "end")):
            if event == "start":
                if element.tag == "TrackMate":
                    version = element.attrib.get("version", "")
                elif element.tag == "Model":
                    model_attrib = dict(element.attrib)
                continue
            if element.tag == "Spot":
                spots += 1
                element.clear()
            elif element.tag == "Track":
                tracks += 1
                element.clear()
            elif element.tag == "Settings":
                settings = element
    except ET.ParseError as exc:
        raise UserFacingError(
            f"{xml_path.name} を XML として読めませんでした。ファイルが壊れているか、"
            "途中までしか保存されていない可能性があります。TrackMate で保存し直してください。"
        ) from exc
    return run_from_parts(version, model_attrib, settings, spots, tracks)


def run_from_parts(
    version: str,
    model_attrib: dict[str, str],
    settings: ET.Element | None,
    spot_count: int | None,
    track_count: int | None,
) -> TrackMateRun:
    def attrib(path: str) -> dict[str, str]:
        element = settings.find(path) if settings is not None else None
        return dict(element.attrib) if element is not None else {}

    detector = attrib("DetectorSettings")
    initial_filter = attrib("InitialSpotFilter")
    linking = attrib("TrackerSettings/Linking")
    gap = attrib("TrackerSettings/GapClosing")
    return TrackMateRun(
        trackmate_version=version,
        detector=detector.get("DETECTOR_NAME", ""),
        spotiflow_model=detector.get("SPOTIFLOW_PRETRAINED_MODEL", ""),
        quality_threshold=_float(initial_filter.get("value")),
        spatial_units=model_attrib.get("spatialunits", ""),
        linking_max_distance=_float(linking.get("LINKING_MAX_DISTANCE")),
        gap_closing=_bool(gap.get("ALLOW_GAP_CLOSING")),
        gap_closing_max_distance=_float(gap.get("GAP_CLOSING_MAX_DISTANCE")),
        max_frame_gap=_int(gap.get("MAX_FRAME_GAP")),
        spot_count=spot_count,
        track_count=track_count,
    )


def _distance(value: float | None, unit: str) -> str:
    return "不明" if value is None else f"{value:g} {unit}".strip()


def _text(value: int | None) -> str:
    return "不明" if value is None else str(value)


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _bool(value: str | None) -> bool | None:
    text = (value or "").strip().lower()
    return {"true": True, "false": False}.get(text)
