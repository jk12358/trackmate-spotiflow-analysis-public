"""Analysis settings loaded from configs/default.yaml."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from trackmate_spotiflow_analysis.errors import UserFacingError

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"


@dataclass(frozen=True)
class AnalysisSettings:
    frame_interval_s: float
    pixel_size_um: float
    fit_initial_points: int
    include_intercept: bool
    min_spots: int
    immobile_threshold_um2_s: float
    use_filtered_tracks: bool


@dataclass(frozen=True)
class OverlaySettings:
    enabled: bool
    fps: int
    target_width_px: int


@dataclass(frozen=True)
class FigureSettings:
    jitter_seed: int


@dataclass(frozen=True)
class Settings:
    analysis: AnalysisSettings
    overlay: OverlaySettings
    figures: FigureSettings

    def with_analysis(self, **changes: Any) -> Settings:
        """Return a copy with some analysis values replaced."""
        settings = replace(self, analysis=replace(self.analysis, **changes))
        validate_settings(settings)
        return settings

    def with_overlay(self, **changes: Any) -> Settings:
        """Return a copy with some overlay values replaced."""
        settings = replace(self, overlay=replace(self.overlay, **changes))
        validate_settings(settings)
        return settings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_settings(path: Path | str | None = None) -> Settings:
    """Load settings from a YAML file (the standard config by default)."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    try:
        with config_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        settings = Settings(
            analysis=AnalysisSettings(**raw["analysis"]),
            overlay=OverlaySettings(**raw["overlay"]),
            figures=FigureSettings(**raw["figures"]),
        )
    except OSError as exc:
        raise UserFacingError(f"設定ファイル {config_path} を開けませんでした。") from exc
    except (yaml.YAMLError, TypeError, KeyError) as exc:
        raise UserFacingError(
            f"設定ファイル {config_path.name} の書き方が正しくありません。"
            "configs/default.yaml と同じ項目と形になっているか確かめてください。"
        ) from exc
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    analysis = settings.analysis
    checks = [
        (analysis.frame_interval_s > 0, "Frame interval は 0 より大きい値にしてください。"),
        (analysis.pixel_size_um > 0, "Pixel size は 0 より大きい値にしてください。"),
        (analysis.fit_initial_points >= 2, "MSD の fit 点数は 2 以上にしてください。"),
        (
            analysis.min_spots > analysis.fit_initial_points,
            "最短 track の spot 数は、fit 点数より大きくしてください。",
        ),
        (settings.overlay.fps > 0, "GIF の fps は 1 以上にしてください。"),
    ]
    for ok, message in checks:
        if not ok:
            raise UserFacingError(message)
