"""Reproducibility record (metadata.yaml) of one batch run."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from trackmate_spotiflow_analysis import __version__
from trackmate_spotiflow_analysis.pairing import PairingPlan
from trackmate_spotiflow_analysis.settings import Settings

if TYPE_CHECKING:
    from trackmate_spotiflow_analysis.batch import MovieOutcome

REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRARIES = ["numpy", "pandas", "matplotlib", "pillow", "imageio", "imageio-ffmpeg", "tifffile"]


def write_metadata(
    output_dir: Path,
    plan: PairingPlan,
    outcomes: list[MovieOutcome],
    settings: Settings,
) -> None:
    record = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": {"version": __version__, "git_commit": git_commit()},
        "environment": {"python": platform.python_version(), "libraries": library_versions()},
        "settings": settings.to_dict(),
        "movies": [_movie_record(outcome) for outcome in outcomes],
        "unused_videos": [_file_record(path) for path in plan.unused_videos],
    }
    with (output_dir / "metadata.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(record, f, sort_keys=False, allow_unicode=True)


def _movie_record(outcome: MovieOutcome) -> dict[str, Any]:
    video = outcome.pair.video_path
    return {
        "name": outcome.pair.name,
        "xml": _file_record(outcome.pair.xml_path),
        "video": _file_record(video) if video is not None else None,
        "xml_calibration": {
            "pixel_size_um": outcome.xml_pixel_size_um,
            "frame_interval_s": outcome.xml_frame_interval_s,
        },
        "trackmate": asdict(outcome.trackmate_run) if outcome.trackmate_run else None,
        "status": "error" if outcome.error else "ok",
        "messages": ([outcome.error] if outcome.error else []) + outcome.warnings,
    }


def _file_record(path: Path) -> dict[str, Any]:
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip()


def library_versions() -> dict[str, str]:
    versions = {}
    for name in LIBRARIES:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions
