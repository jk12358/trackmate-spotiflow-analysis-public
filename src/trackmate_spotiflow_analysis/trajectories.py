"""Build per-track trajectories from TrackMate spots and edges."""

from __future__ import annotations

import pandas as pd

TRAJECTORY_COLUMNS = ["track_id", "spot_id", "frame", "x_px", "y_px", "quality"]


def build_trajectories(
    spots: pd.DataFrame,
    edges: pd.DataFrame,
    track_ids: set[int] | frozenset[int],
    *,
    position_units_per_px: float = 1.0,
) -> pd.DataFrame:
    """Return all spots of the given tracks, sorted by track and frame.

    A track keeps every spot linked by its edges, even when frames are missing
    (gap closing), so one TrackMate TRACK_ID is one trajectory.
    """
    edges = edges[edges["track_id"].isin(track_ids)]
    if spots.empty or edges.empty:
        return pd.DataFrame(columns=TRAJECTORY_COLUMNS)
    members = pd.concat(
        [
            edges[["track_id", "source_spot_id"]].rename(columns={"source_spot_id": "spot_id"}),
            edges[["track_id", "target_spot_id"]].rename(columns={"target_spot_id": "spot_id"}),
        ]
    ).drop_duplicates()
    merged = members.merge(spots, on="spot_id", how="inner")
    merged["x_px"] = merged["x"] / position_units_per_px
    merged["y_px"] = merged["y"] / position_units_per_px
    merged = merged.astype({"track_id": int, "spot_id": int, "frame": int})
    return (
        merged[TRAJECTORY_COLUMNS]
        .sort_values(["track_id", "frame", "spot_id"])
        .reset_index(drop=True)
    )


def frame_gap_stats(trajectory: pd.DataFrame) -> dict[str, int]:
    """Count missing-frame gaps and the largest frame step in one trajectory."""
    frames = trajectory["frame"].drop_duplicates().sort_values().to_numpy()
    if len(frames) < 2:
        return {"missing_frame_gap_count": 0, "max_observed_frame_gap": 0}
    steps = frames[1:] - frames[:-1]
    return {
        "missing_frame_gap_count": int((steps != 1).sum()),
        "max_observed_frame_gap": int(steps.max()),
    }
