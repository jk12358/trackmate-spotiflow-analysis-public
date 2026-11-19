"""Squared displacements and MSD by actual frame lag (gaps allowed).

With frames 1, 2, 4, 5, 6, lag 2 uses only 2->4 and 4->6. A pair such as 1->4
belongs to lag 3, so missing frames never shift the time axis.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

SQUARED_DISPLACEMENT_COLUMNS = [
    "lag",
    "dt_s",
    "source_frame",
    "target_frame",
    "dx_um",
    "dy_um",
    "squared_displacement_um2",
]
MSD_COLUMNS = ["lag", "dt_s", "msd_um2", "n_displacements"]


class _Positions:
    """Frames and positions (um) of one trajectory, one spot per frame."""

    def __init__(self, trajectory: pd.DataFrame, pixel_size_um: float) -> None:
        trajectory = trajectory.sort_values(["frame", "spot_id"]).drop_duplicates("frame")
        self.frames = trajectory["frame"].to_numpy(dtype=int)
        self.x_um = trajectory["x_px"].to_numpy(dtype=float) * pixel_size_um
        self.y_um = trajectory["y_px"].to_numpy(dtype=float) * pixel_size_um

    def pairs(self, lag: int) -> tuple[np.ndarray, np.ndarray]:
        """Indices (source, target) of spot pairs exactly `lag` frames apart."""
        wanted = self.frames + lag
        target = np.searchsorted(self.frames, wanted)
        target_clipped = np.minimum(target, len(self.frames) - 1)
        found = (target < len(self.frames)) & (self.frames[target_clipped] == wanted)
        return np.nonzero(found)[0], target_clipped[found]

    def max_lag(self) -> int:
        return int(self.frames[-1] - self.frames[0]) if len(self.frames) > 1 else 0


def msd_by_frame_lag(
    trajectory: pd.DataFrame,
    *,
    frame_interval_s: float,
    pixel_size_um: float,
) -> pd.DataFrame:
    """Mean squared displacement for every frame lag that has at least one pair."""
    positions = _Positions(trajectory, pixel_size_um)
    rows = []
    for lag in range(1, positions.max_lag() + 1):
        source, target = positions.pairs(lag)
        if len(source) == 0:
            continue
        squared = (positions.x_um[target] - positions.x_um[source]) ** 2 + (
            positions.y_um[target] - positions.y_um[source]
        ) ** 2
        rows.append((lag, lag * frame_interval_s, float(squared.mean()), len(source)))
    return pd.DataFrame(rows, columns=MSD_COLUMNS)


def squared_displacements_by_frame_lag(
    trajectory: pd.DataFrame,
    *,
    lags: Iterable[int],
    frame_interval_s: float,
    pixel_size_um: float,
) -> pd.DataFrame:
    """Every individual squared displacement for the given frame lags."""
    positions = _Positions(trajectory, pixel_size_um)
    pieces = []
    for lag in sorted(set(lags)):
        source, target = positions.pairs(lag)
        dx = positions.x_um[target] - positions.x_um[source]
        dy = positions.y_um[target] - positions.y_um[source]
        pieces.append(
            pd.DataFrame(
                {
                    "lag": lag,
                    "dt_s": lag * frame_interval_s,
                    "source_frame": positions.frames[source],
                    "target_frame": positions.frames[target],
                    "dx_um": dx,
                    "dy_um": dy,
                    "squared_displacement_um2": dx**2 + dy**2,
                }
            )
        )
    if not pieces:
        return pd.DataFrame(columns=SQUARED_DISPLACEMENT_COLUMNS)
    return pd.concat(pieces, ignore_index=True)[SQUARED_DISPLACEMENT_COLUMNS]
