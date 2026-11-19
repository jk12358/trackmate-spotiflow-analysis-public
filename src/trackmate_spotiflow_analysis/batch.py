"""Analyze several XML/movie pairs and write per-movie and combined results."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from trackmate_spotiflow_analysis import figures
from trackmate_spotiflow_analysis.errors import UserFacingError
from trackmate_spotiflow_analysis.metadata import write_metadata
from trackmate_spotiflow_analysis.movie_analysis import MovieAnalysis, analyze_movie
from trackmate_spotiflow_analysis.outputs import (
    write_movie_overlays,
    write_movie_tables_and_figures,
)
from trackmate_spotiflow_analysis.pairing import MoviePair, PairingPlan
from trackmate_spotiflow_analysis.report import write_report
from trackmate_spotiflow_analysis.settings import Settings
from trackmate_spotiflow_analysis.trackmate_run import TrackMateRun

logger = logging.getLogger(__name__)

Progress = Callable[[float, str], None]
MOVIES_DIR = "movies"
MESSAGES_FILE = "messages.txt"
ERROR_LOG_FILE = "error_log.txt"


@dataclass
class MovieOutcome:
    pair: MoviePair
    output_dir: Path
    summary: dict[str, Any] | None = None
    gifs: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    xml_pixel_size_um: float | None = None
    xml_frame_interval_s: float | None = None
    trackmate_run: TrackMateRun | None = None


@dataclass
class BatchResult:
    output_dir: Path
    outcomes: list[MovieOutcome]
    messages: list[str]

    @property
    def succeeded(self) -> list[MovieOutcome]:
        return [outcome for outcome in self.outcomes if outcome.error is None]


def run_batch(
    plan: PairingPlan,
    output_dir: Path,
    settings: Settings,
    progress: Progress | None = None,
) -> BatchResult:
    if not plan.pairs:
        raise UserFacingError(
            "TrackMate の XML が 1 つもありません。TrackMate で保存した .xml ファイルを入れて"
            "ください。"
        )
    report = progress or (lambda _fraction, _text: None)
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes = []
    for index, pair in enumerate(plan.pairs):
        report(
            index / len(plan.pairs),
            f"{pair.name} を解析しています（{index + 1}/{len(plan.pairs)}）",
        )
        outcomes.append(_run_movie(pair, output_dir / MOVIES_DIR / pair.name, settings, output_dir))
    report(0.98, "全動画のまとめを作っています")
    _write_combined(outcomes, output_dir, settings)
    messages = plan.messages() + _outcome_messages(outcomes)
    (output_dir / MESSAGES_FILE).write_text("\n".join(messages) + "\n", encoding="utf-8")
    write_metadata(output_dir, plan, outcomes, settings)
    write_report(output_dir, outcomes, messages, settings)
    report(1.0, "完了しました")
    return BatchResult(output_dir=output_dir, outcomes=outcomes, messages=messages)


def _run_movie(pair: MoviePair, movie_dir: Path, settings: Settings, root: Path) -> MovieOutcome:
    outcome = MovieOutcome(pair=pair, output_dir=movie_dir)
    try:
        analysis = analyze_movie(pair.xml_path, settings.analysis, pair.name)
        outcome.xml_pixel_size_um = analysis.calibration.xml_pixel_size_um
        outcome.xml_frame_interval_s = analysis.calibration.xml_frame_interval_s
        outcome.trackmate_run = analysis.data.run
        outcome.summary = write_movie_tables_and_figures(analysis, movie_dir, settings)
        if pair.video_path is not None and settings.overlay.enabled and not analysis.fitted.empty:
            outcome.gifs = _overlays(analysis, pair.video_path, movie_dir, settings)
        outcome.warnings = analysis.warnings
    except UserFacingError as exc:
        outcome.error = str(exc)
    except Exception:
        _log_unexpected(root, pair)
        outcome.error = (
            "予期しないエラーで解析できませんでした。入力のファイルと、結果フォルダの "
            f"{ERROR_LOG_FILE} を開発者に送ってください。"
        )
    return outcome


def _overlays(
    analysis: MovieAnalysis, video_path: Path, movie_dir: Path, settings: Settings
) -> list[Path]:
    try:
        return write_movie_overlays(analysis, video_path, movie_dir, settings)
    except UserFacingError as exc:
        analysis.warnings.append(f"overlay の GIF を作れませんでした: {exc}")
        return []


def _log_unexpected(root: Path, pair: MoviePair) -> None:
    logger.exception("Unexpected error while analyzing %s", pair.xml_path)
    with (root / ERROR_LOG_FILE).open("a", encoding="utf-8") as f:
        f.write(f"== {pair.name} ({pair.xml_path.name}) ==\n{traceback.format_exc()}\n")


def _write_combined(outcomes: list[MovieOutcome], output_dir: Path, settings: Settings) -> None:
    succeeded = [o for o in outcomes if o.summary is not None]
    summaries = pd.DataFrame([o.summary for o in succeeded])
    summaries.to_csv(output_dir / "summary_all_movies.csv", index=False)
    track_tables = [
        pd.read_csv(o.output_dir / "track_results.csv")
        for o in succeeded
        if (o.output_dir / "track_results.csv").exists()
    ]
    tracks = pd.concat(track_tables, ignore_index=True) if track_tables else pd.DataFrame()
    tracks.to_csv(output_dir / "track_results_all_movies.csv", index=False)
    if tracks.empty or "status" not in tracks:
        return
    fitted = tracks[tracks["status"] == "fitted"]
    groups = {
        name: group["diffusion_coefficient_um2_s"]
        for name, group in fitted.groupby("movie_name", sort=False)
    }
    figures_dir = output_dir / "figures"
    figures.write_strip_plot_log(
        groups,
        figures_dir / "diffusion_strip_plot_log_all_movies.png",
        seed=settings.figures.jitter_seed,
    )
    figures.write_cumulative_distribution(
        groups, figures_dir / "diffusion_cumulative_distribution_all_movies.png"
    )


def _outcome_messages(outcomes: list[MovieOutcome]) -> list[str]:
    lines = []
    for outcome in outcomes:
        if outcome.error:
            lines.append(f"{outcome.pair.name}: {outcome.error}")
        lines += [f"{outcome.pair.name}: {warning}" for warning in outcome.warnings]
    return lines
