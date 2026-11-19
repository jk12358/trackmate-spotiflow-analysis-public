"""Fit the diffusion coefficient to the initial MSD points."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DiffusionFit:
    slope_um2_per_s: float
    intercept_um2: float
    diffusion_coefficient_um2_s: float
    r_squared: float
    fit_lags: tuple[int, ...]


def fit_diffusion_coefficient(
    msd: pd.DataFrame,
    *,
    fit_initial_points: int,
    include_intercept: bool,
) -> DiffusionFit:
    """Fit MSD(dt) = 4D * dt (+ b) to the first `fit_initial_points` lags."""
    if len(msd) < fit_initial_points:
        raise ValueError(f"Need at least {fit_initial_points} MSD points, got {len(msd)}.")
    fit_data = msd.sort_values("lag").head(fit_initial_points)
    x = fit_data["dt_s"].to_numpy(dtype=float)
    y = fit_data["msd_um2"].to_numpy(dtype=float)
    if include_intercept:
        design = np.column_stack([x, np.ones_like(x)])
        slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    else:
        slope = float(np.dot(x, y) / np.dot(x, x))
        intercept = 0.0
    return DiffusionFit(
        slope_um2_per_s=float(slope),
        intercept_um2=float(intercept),
        diffusion_coefficient_um2_s=float(slope / 4.0),
        r_squared=_r_squared(y, slope * x + intercept),
        fit_lags=tuple(int(lag) for lag in fit_data["lag"]),
    )


def _r_squared(y: np.ndarray, predicted: np.ndarray) -> float:
    total = float(np.sum((y - np.mean(y)) ** 2))
    if math.isclose(total, 0.0):
        return math.nan
    return 1.0 - float(np.sum((y - predicted) ** 2)) / total
