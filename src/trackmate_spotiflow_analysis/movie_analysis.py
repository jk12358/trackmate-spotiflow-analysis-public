"""Diffusion analysis of every track in one TrackMate XML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from trackmate_spotiflow_analysis.calibration import Calibration, resolve_calibration
from trackmate_spotiflow_analysis.diffusion import fit_diffusion_coefficient
from trackmate_spotiflow_analysis.msd import (
    MSD_COLUMNS,
    SQUARED_DISPLACEMENT_COLUMNS,
    msd_by_frame_lag,
    squared_displacements_by_frame_lag,
)
from trackmate_spotiflow_analysis.settings import AnalysisSettings
from trackmate_spotiflow_analysis.trackmate_xml import TrackMateData, read_trackmate_xml
from trackmate_spotiflow_analysis.trajectories import build_trajectories, frame_gap_stats

TRACK_RESULT_COLUMNS = [
    "movie_name",
    "track_id",
    "track_name",
    "trackmate_number_spots",
    "trackmate_number_gaps",
    "trackmate_longest_gap",
    "start_frame",
    "stop_frame",
    "n_spots",
    "frame_span",
    "missing_frame_gap_count",
    "max_observed_frame_gap",
    "status",
    "fit_points_used",
    "slope_um2_per_s",
    "intercept_um2",
    "diffusion_coefficient_um2_s",
    "fit_r_squared",
    "is_immobile",
]
MSD_POINT_COLUMNS = ["movie_name", "track_id", *MSD_COLUMNS, "used_for_fit"]
TRACK_SQUARED_DISPLACEMENT_COLUMNS = ["movie_name", "track_id", *SQUARED_DISPLACEMENT_COLUMNS]

STATUS_FITTED = "fitted"
STATUS_TOO_SHORT = "too_short"
STATUS_INSUFFICIENT_MSD = "insufficient_msd_points"


@dataclass
class MovieAnalysis:
    movie_name: str
    data: TrackMateData
    calibration: Calibration
    trajectories: pd.DataFrame
    track_results: pd.DataFrame
    msd_points: pd.DataFrame
    squared_displacements: pd.DataFrame
    track_count: int
    warnings: list[str] = field(default_factory=list)

    @property
    def fitted(self) -> pd.DataFrame:
        return self.track_results[self.track_results["status"] == STATUS_FITTED]


def analyze_movie(xml_path: Path, settings: AnalysisSettings, movie_name: str) -> MovieAnalysis:
    data = read_trackmate_xml(xml_path)
    calibration = resolve_calibration(data, settings)
    track_ids = (
        data.filtered_track_ids
        if settings.use_filtered_tracks
        else frozenset(int(track_id) for track_id in data.tracks["track_id"])
    )
    trajectories = build_trajectories(
        data.spots,
        data.edges,
        track_ids,
        position_units_per_px=calibration.position_units_per_px,
    )
    tracks_by_id = data.tracks.set_index("track_id")
    results, msd_frames, displacement_frames = [], [], []
    for track_id, trajectory in trajectories.groupby("track_id", sort=True):
        row, msd, displacements = _analyze_track(
            int(track_id), trajectory, settings, tracks_by_id, movie_name
        )
        results.append(row)
        msd_frames.append(msd)
        displacement_frames.append(displacements)
    return MovieAnalysis(
        movie_name=movie_name,
        data=data,
        calibration=calibration,
        trajectories=trajectories,
        track_results=pd.DataFrame(results, columns=TRACK_RESULT_COLUMNS),
        msd_points=_concat(msd_frames, MSD_POINT_COLUMNS),
        squared_displacements=_concat(displacement_frames, TRACK_SQUARED_DISPLACEMENT_COLUMNS),
        track_count=len(track_ids),
        warnings=list(calibration.warnings),
    )


def _analyze_track(
    track_id: int,
    trajectory: pd.DataFrame,
    settings: AnalysisSettings,
    tracks_by_id: pd.DataFrame,
    movie_name: str,
) -> tuple[dict[str, Any], pd.DataFrame | None, pd.DataFrame | None]:
    row = _base_row(track_id, trajectory, tracks_by_id, movie_name)
    if len(trajectory) < settings.min_spots:
        row["status"] = STATUS_TOO_SHORT
        return row, None, None
    kwargs = {
        "frame_interval_s": settings.frame_interval_s,
        "pixel_size_um": settings.pixel_size_um,
    }
    msd = msd_by_frame_lag(trajectory, **kwargs)
    if len(msd) < settings.fit_initial_points:
        row["status"] = STATUS_INSUFFICIENT_MSD
        return row, None, None
    fit = fit_diffusion_coefficient(
        msd,
        fit_initial_points=settings.fit_initial_points,
        include_intercept=settings.include_intercept,
    )
    row.update(
        status=STATUS_FITTED,
        fit_points_used=len(fit.fit_lags),
        slope_um2_per_s=fit.slope_um2_per_s,
        intercept_um2=fit.intercept_um2,
        diffusion_coefficient_um2_s=fit.diffusion_coefficient_um2_s,
        fit_r_squared=fit.r_squared,
        is_immobile=fit.diffusion_coefficient_um2_s < settings.immobile_threshold_um2_s,
    )
    msd = msd.assign(used_for_fit=msd["lag"].isin(fit.fit_lags))
    displacements = squared_displacements_by_frame_lag(trajectory, lags=fit.fit_lags, **kwargs)
    identifiers = {"movie_name": movie_name, "track_id": track_id}
    return row, msd.assign(**identifiers), displacements.assign(**identifiers)


def _base_row(
    track_id: int, trajectory: pd.DataFrame, tracks_by_id: pd.DataFrame, movie_name: str
) -> dict[str, Any]:
    track = tracks_by_id.loc[track_id] if track_id in tracks_by_id.index else None
    start, stop = int(trajectory["frame"].min()), int(trajectory["frame"].max())
    row: dict[str, Any] = dict.fromkeys(TRACK_RESULT_COLUMNS, pd.NA)
    row.update(
        movie_name=movie_name,
        track_id=track_id,
        track_name=track["track_name"] if track is not None else "",
        trackmate_number_spots=track["number_spots"] if track is not None else pd.NA,
        trackmate_number_gaps=track["number_gaps"] if track is not None else pd.NA,
        trackmate_longest_gap=track["longest_gap"] if track is not None else pd.NA,
        start_frame=start,
        stop_frame=stop,
        n_spots=len(trajectory),
        frame_span=stop - start + 1,
        **frame_gap_stats(trajectory),
    )
    return row


def _concat(frames: list[pd.DataFrame | None], columns: list[str]) -> pd.DataFrame:
    frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)[columns]


def summarize_movie(analysis: MovieAnalysis) -> dict[str, Any]:
    """One row of summary.csv for this movie."""
    fitted = analysis.fitted
    values = pd.to_numeric(fitted["diffusion_coefficient_um2_s"], errors="coerce").dropna()
    immobile = int(fitted["is_immobile"].astype(bool).sum())
    fitted_count = len(fitted)
    return {
        "movie_name": analysis.movie_name,
        "xml_file": analysis.data.xml_path.name,
        "track_count": analysis.track_count,
        "analyzed_track_count": len(analysis.track_results),
        "fitted_track_count": fitted_count,
        "immobile_track_count": immobile,
        "immobile_fraction": immobile / fitted_count if fitted_count else pd.NA,
        "mean_diffusion_coefficient_um2_s": values.mean() if len(values) else pd.NA,
        "median_diffusion_coefficient_um2_s": values.median() if len(values) else pd.NA,
        "q1_diffusion_coefficient_um2_s": values.quantile(0.25) if len(values) else pd.NA,
        "q3_diffusion_coefficient_um2_s": values.quantile(0.75) if len(values) else pd.NA,
        **analysis.data.run.summary_fields(),
    }
