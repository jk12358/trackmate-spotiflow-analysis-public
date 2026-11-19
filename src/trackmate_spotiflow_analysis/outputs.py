"""Write CSVs, figures and overlays of one movie."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trackmate_spotiflow_analysis import figures
from trackmate_spotiflow_analysis.movie_analysis import MovieAnalysis, summarize_movie
from trackmate_spotiflow_analysis.overlay import (
    ALL_TRACKS_STYLE,
    FITTED_STYLE,
    IMMOBILE_COLOR,
    MOBILE_COLOR,
    render_overlay_gif,
)
from trackmate_spotiflow_analysis.settings import Settings

ALL_TRACKS_GIF = "all_tracks.gif"
FITTED_TRACKS_GIF = "fitted_tracks_with_d.gif"


def write_movie_tables_and_figures(
    analysis: MovieAnalysis, movie_dir: Path, settings: Settings
) -> dict:
    """Write the CSVs and figures that do not need the movie. Returns the summary row."""
    figures_dir = movie_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_movie(analysis)
    pd.DataFrame([summary]).to_csv(movie_dir / "summary.csv", index=False)
    analysis.track_results.to_csv(movie_dir / "track_results.csv", index=False)
    analysis.msd_points.to_csv(movie_dir / "msd_points.csv", index=False)
    analysis.squared_displacements.to_csv(movie_dir / "squared_displacements.csv", index=False)
    if analysis.fitted.empty:
        analysis.warnings.append(
            "拡散係数を計算できた track が 0 本でした。CSV は出しましたが、図と GIF の一部は"
            f"作れませんでした。track_results.csv の status と n_spots を確かめてください"
            f"（{settings.analysis.min_spots} spot 未満の track は too_short になります）。"
        )
        return summary
    values = {analysis.movie_name: analysis.fitted["diffusion_coefficient_um2_s"]}
    seed = settings.figures.jitter_seed
    figures.write_cumulative_distribution(
        values, figures_dir / "diffusion_cumulative_distribution.png"
    )
    figures.write_strip_plot_log(values, figures_dir / "diffusion_strip_plot_log.png", seed=seed)
    figures.write_squared_displacements_all_tracks(
        analysis.squared_displacements,
        analysis.msd_points,
        figures_dir / "squared_displacements_all_tracks.png",
        seed=seed,
    )
    figures.write_squared_displacements_by_track(
        analysis.squared_displacements,
        analysis.msd_points,
        figures_dir / "squared_displacements_by_track",
    )
    return summary


def write_movie_overlays(
    analysis: MovieAnalysis, video_path: Path, movie_dir: Path, settings: Settings
) -> list[Path]:
    """Write the two overlay GIFs. Returns the files written."""
    written = []
    jobs = [
        (_all_track_points(analysis), ALL_TRACKS_GIF, ALL_TRACKS_STYLE),
        (_fitted_track_points(analysis), FITTED_TRACKS_GIF, FITTED_STYLE),
    ]
    for points, file_name, style in jobs:
        if points.empty:
            continue
        result = render_overlay_gif(
            video_path,
            points,
            movie_dir / file_name,
            fps=settings.overlay.fps,
            target_width_px=settings.overlay.target_width_px,
            style=style,
        )
        if result.rendered_frames:
            written.append(movie_dir / file_name)
        if result.video_frames_shorter_than_tracks:
            analysis.warnings.append(
                f"{video_path.name} のフレーム数が XML の track より少なく、"
                f"{file_name} は途中までになりました。"
                "XML を作ったときと同じ動画か確かめてください。"
            )
    return written


def _all_track_points(analysis: MovieAnalysis) -> pd.DataFrame:
    points = analysis.trajectories[["track_id", "frame", "x_px", "y_px"]].copy()
    points["label"] = points["track_id"].astype(str)
    points["color"] = [MOBILE_COLOR] * len(points)
    return points


def _fitted_track_points(analysis: MovieAnalysis) -> pd.DataFrame:
    fitted = analysis.fitted[["track_id", "diffusion_coefficient_um2_s", "is_immobile"]]
    points = analysis.trajectories.merge(fitted, on="track_id", how="inner")
    points["label"] = [
        f"{int(track_id)} D={d:.3g}"
        for track_id, d in zip(
            points["track_id"], points["diffusion_coefficient_um2_s"], strict=True
        )
    ]
    points["color"] = [IMMOBILE_COLOR if flag else MOBILE_COLOR for flag in points["is_immobile"]]
    return points[["track_id", "frame", "x_px", "y_px", "label", "color"]]
