"""Match TrackMate XML files with their movies by file name."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from trackmate_spotiflow_analysis.video import VIDEO_SUFFIXES


@dataclass(frozen=True)
class MoviePair:
    name: str
    xml_path: Path
    video_path: Path | None
    note: str = ""
    recorded_video: str = ""  # source movie name written in the XML, if any


@dataclass
class PairingPlan:
    pairs: list[MoviePair]
    unused_videos: list[Path] = field(default_factory=list)
    ignored_files: list[Path] = field(default_factory=list)

    def messages(self) -> list[str]:
        """Japanese notes on what was matched and what was left out."""
        lines = [pair.note for pair in self.pairs if pair.note]
        lines += [_missing_video_message(pair) for pair in self.pairs if pair.video_path is None]
        lines += [
            f"{path.name}: 対応する XML がないので使いません。XML のファイル名を動画と同じ名前に"
            "してください。"
            for path in self.unused_videos
        ]
        lines += [
            f"{path.name}: XML でも動画でもないので使いません。" for path in self.ignored_files
        ]
        return lines


def _missing_video_message(pair: MoviePair) -> str:
    head = f"{pair.xml_path.name}: 対応する動画が見つかりません。"
    if pair.recorded_video:
        head += f"この XML に記録された元の動画は {pair.recorded_video} です。"
        wanted = "その動画"
    else:
        wanted = "XML と同じ名前の動画"
    return (
        f"{head}overlay の GIF は作らず、拡散係数と図だけを出します。"
        f"GIF も欲しいときは、{wanted}を一緒に入れてください。"
    )


def collect_input_files(inputs: Iterable[Path]) -> list[Path]:
    """Expand folders into the files they contain (recursively)."""
    files: list[Path] = []
    for path in inputs:
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif path.is_file():
            files.append(path)
    return [p for p in files if not p.name.startswith(".")]


def plan_pairs(files: Iterable[Path]) -> PairingPlan:
    files = list(files)
    xml_files = [p for p in files if p.suffix.lower() == ".xml"]
    videos = [p for p in files if p.suffix.lower() in VIDEO_SUFFIXES]
    ignored = [p for p in files if p not in xml_files and p not in videos]
    names = _unique_names(xml_files)
    pairs = [_pair(xml_path, names[xml_path], videos) for xml_path in xml_files]
    # Guess only when the XML does not name its movie; a named movie that is missing
    # usually means a different file (e.g. a TrackMate capture) was dropped instead.
    if (
        len(xml_files) == 1
        and len(videos) == 1
        and pairs[0].video_path is None
        and not pairs[0].recorded_video
    ):
        pairs[0] = MoviePair(
            name=pairs[0].name,
            xml_path=xml_files[0],
            video_path=videos[0],
            note=(
                f"{xml_files[0].name} と {videos[0].name} は名前が違いますが、1 組だけなので"
                "対応付けました。違う動画なら入れ直してください。"
            ),
        )
    used = {pair.video_path for pair in pairs if pair.video_path is not None}
    unused = [video for video in videos if video not in used]
    return PairingPlan(pairs=pairs, unused_videos=unused, ignored_files=ignored)


def _pair(xml_path: Path, name: str, videos: list[Path]) -> MoviePair:
    """Match by the movie name recorded in the XML first, then by the XML's own name."""
    source = _source_image_name(xml_path)
    recorded = PureWindowsPath(source) if source else None
    if recorded is not None:
        by_source = [video for video in videos if _same_movie(video, recorded)]
        if by_source:
            video = _closest(xml_path, by_source)
            note = ""
            if video.stem.lower() != xml_path.stem.lower():
                note = (
                    f"{xml_path.name} は、XML に記録された元の動画の名前（{recorded.name}）から "
                    f"{video.name} と対応付けました。"
                )
            return MoviePair(name=name, xml_path=xml_path, video_path=video, note=note)
    by_stem = [video for video in videos if video.stem.lower() == xml_path.stem.lower()]
    if by_stem:
        video = _closest(xml_path, by_stem)
        note = ""
        if recorded is not None:
            note = (
                f"{xml_path.name} に記録された元の動画は {recorded.name} ですが、名前が同じ "
                f"{video.name} と対応付けました。違う動画なら入れ直してください。"
            )
        return MoviePair(name=name, xml_path=xml_path, video_path=video, note=note)
    return MoviePair(
        name=name,
        xml_path=xml_path,
        video_path=None,
        recorded_video=recorded.name if recorded is not None else "",
    )


def _same_movie(video: Path, recorded: PureWindowsPath) -> bool:
    return video.name.lower() == recorded.name.lower() or (
        video.stem.lower() == recorded.stem.lower()
    )


def _closest(xml_path: Path, candidates: list[Path]) -> Path:
    """Prefer the candidate that shares the longest folder path with the XML."""

    def shared(video: Path) -> int:
        count = 0
        for a, b in zip(xml_path.parent.parts, video.parent.parts, strict=False):
            if a != b:
                break
            count += 1
        return count

    return max(candidates, key=shared)


def _source_image_name(xml_path: Path) -> str:
    try:
        for _event, element in ET.iterparse(xml_path, events=("end",)):
            if element.tag == "ImageData":
                return element.attrib.get("filename", "")
            if element.tag in {"Spot", "SpotsInFrame", "Edge", "Track"}:
                element.clear()
    except ET.ParseError:
        return ""
    return ""


def _unique_names(xml_files: list[Path]) -> dict[Path, str]:
    """Output folder names; compared case-insensitively for Windows and macOS."""
    names: dict[Path, str] = {}
    taken: set[str] = set()
    for xml_path in xml_files:
        candidates = [xml_path.stem, f"{xml_path.parent.name}_{xml_path.stem}"]
        name = next((c for c in candidates if c.casefold() not in taken), None)
        index = 2
        while name is None or name.casefold() in taken:
            name = f"{xml_path.stem}_{index}"
            index += 1
        names[xml_path] = name
        taken.add(name.casefold())
    return names
