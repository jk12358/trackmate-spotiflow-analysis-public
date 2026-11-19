"""Read spots, tracks, edges and image calibration from a TrackMate XML file."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trackmate_spotiflow_analysis.errors import UserFacingError
from trackmate_spotiflow_analysis.trackmate_run import TrackMateRun, run_from_parts

SPOT_COLUMNS = ["spot_id", "frame", "x", "y", "quality"]
EDGE_COLUMNS = ["track_id", "source_spot_id", "target_spot_id"]
TRACK_COLUMNS = ["track_id", "track_name", "number_spots", "number_gaps", "longest_gap"]


@dataclass(frozen=True)
class ImageInfo:
    """The `Settings/ImageData` element: the source movie and its calibration."""

    filename: str
    width: int | None
    height: int | None
    n_frames: int | None
    pixel_width: float | None
    time_interval: float | None


@dataclass(frozen=True)
class TrackMateData:
    xml_path: Path
    spatial_units: str
    time_units: str
    image: ImageInfo
    spots: pd.DataFrame
    tracks: pd.DataFrame
    edges: pd.DataFrame
    filtered_track_ids: frozenset[int]
    run: TrackMateRun


def read_trackmate_xml(xml_path: Path | str) -> TrackMateData:
    xml_path = Path(xml_path)
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        raise UserFacingError(
            f"{xml_path.name} を XML として読めませんでした。ファイルが壊れているか、"
            "途中までしか保存されていない可能性があります。TrackMate で保存し直してください。"
        ) from exc
    model = root.find("Model")
    if model is None:
        raise UserFacingError(
            f"{xml_path.name} は TrackMate の XML ではないようです。"
            "TrackMate の「Save」で保存した XML を入れてください。"
        )
    tracks, edges = _read_tracks_and_edges(model)
    spots = _read_spots(model)
    return TrackMateData(
        xml_path=xml_path,
        spatial_units=model.attrib.get("spatialunits", ""),
        time_units=model.attrib.get("timeunits", ""),
        image=_read_image_info(root),
        spots=spots,
        tracks=tracks,
        edges=edges,
        filtered_track_ids=_read_filtered_track_ids(model, tracks),
        run=run_from_parts(
            root.attrib.get("version", ""),
            dict(model.attrib),
            root.find("Settings"),
            len(spots),
            len(tracks),
        ),
    )


def _read_image_info(root: ET.Element) -> ImageInfo:
    element = root.find("Settings/ImageData")
    attrib = element.attrib if element is not None else {}
    return ImageInfo(
        filename=attrib.get("filename", ""),
        width=_to_int(attrib.get("width")),
        height=_to_int(attrib.get("height")),
        n_frames=_to_int(attrib.get("nframes")),
        pixel_width=_to_float(attrib.get("pixelwidth"), default=None),
        time_interval=_to_float(attrib.get("timeinterval"), default=None),
    )


def _read_spots(model: ET.Element) -> pd.DataFrame:
    rows = []
    for spots_in_frame in model.iterfind("AllSpots/SpotsInFrame"):
        parent_frame = _to_int(spots_in_frame.attrib.get("frame"))
        for spot in spots_in_frame.iterfind("Spot"):
            rows.append(
                (
                    _to_int(spot.attrib["ID"]),
                    _to_int(spot.attrib.get("FRAME"), parent_frame),
                    _to_float(spot.attrib.get("POSITION_X")),
                    _to_float(spot.attrib.get("POSITION_Y")),
                    _to_float(spot.attrib.get("QUALITY")),
                )
            )
    return pd.DataFrame(rows, columns=SPOT_COLUMNS)


def _read_tracks_and_edges(model: ET.Element) -> tuple[pd.DataFrame, pd.DataFrame]:
    track_rows = []
    edge_rows = []
    for track in model.iterfind("AllTracks/Track"):
        track_id = _to_int(track.attrib["TRACK_ID"])
        track_rows.append(
            (
                track_id,
                track.attrib.get("name", ""),
                _to_int(track.attrib.get("NUMBER_SPOTS")),
                _to_int(track.attrib.get("NUMBER_GAPS")),
                _to_int(track.attrib.get("LONGEST_GAP")),
            )
        )
        for edge in track.iterfind("Edge"):
            edge_rows.append(
                (
                    track_id,
                    _to_int(edge.attrib["SPOT_SOURCE_ID"]),
                    _to_int(edge.attrib["SPOT_TARGET_ID"]),
                )
            )
    tracks = pd.DataFrame(track_rows, columns=TRACK_COLUMNS)
    edges = pd.DataFrame(edge_rows, columns=EDGE_COLUMNS)
    return tracks, edges


def _read_filtered_track_ids(model: ET.Element, tracks: pd.DataFrame) -> frozenset[int]:
    filtered = model.find("FilteredTracks")
    if filtered is None:
        return frozenset(int(track_id) for track_id in tracks["track_id"])
    return frozenset(_to_int(item.attrib["TRACK_ID"]) for item in filtered.iterfind("TrackID"))


def _to_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    return int(float(str(value)))


def _to_float(value: object, default: float | None = math.nan) -> float | None:
    if value is None:
        return default
    return float(str(value))
