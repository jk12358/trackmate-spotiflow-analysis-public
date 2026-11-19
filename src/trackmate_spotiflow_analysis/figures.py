"""Figures for one movie and for the comparison of all movies."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

D_LABEL = "Diffusion coefficient (um^2/s)"
SD_LABEL = "Squared displacement (um^2)"


def positive_values(values: pd.Series) -> np.ndarray:
    """Diffusion coefficients that can be drawn on a log axis."""
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    return np.sort(numeric[numeric > 0].to_numpy(dtype=float))


def cumulative_distribution(values: pd.Series) -> pd.DataFrame:
    sorted_values = np.sort(pd.to_numeric(pd.Series(values), errors="coerce").dropna())
    n = len(sorted_values)
    return pd.DataFrame(
        {
            "rank": np.arange(1, n + 1),
            "diffusion_coefficient_um2_s": sorted_values,
            "cumulative_probability": np.arange(1, n + 1) / n if n else [],
        }
    )


def write_cumulative_distribution(groups: dict[str, pd.Series], output_path: Path) -> bool:
    """CDF of D, one line per movie. Returns False when there is nothing to draw."""
    groups = {name: values for name, values in groups.items() if len(values.dropna())}
    if not groups:
        return False
    fig, ax = plt.subplots(figsize=(6, 4.2))
    for name, values in groups.items():
        cdf = cumulative_distribution(values)
        label = f"{name} (n={len(cdf)})"
        ax.step(
            cdf["diffusion_coefficient_um2_s"],
            cdf["cumulative_probability"],
            where="post",
            label=label,
        )
    ax.set_xlabel(D_LABEL)
    ax.set_ylabel("Cumulative probability")
    ax.set_ylim(0, 1.02)
    ax.grid(color="#e6e6e6", linewidth=0.8)
    ax.legend(fontsize=7, loc="lower right")
    _save(fig, output_path)
    return True


def write_strip_plot_log(
    groups: dict[str, pd.Series],
    output_path: Path,
    *,
    seed: int,
    jitter_width: float = 0.12,
) -> bool:
    """Jittered D per movie on a log axis with the median as a red bar."""
    groups = {name: positive_values(values) for name, values in groups.items()}
    groups = {name: values for name, values in groups.items() if len(values)}
    if not groups:
        return False
    rng = np.random.default_rng(seed)
    width = max(4.8, 1.1 * len(groups) + 1.4)
    fig, ax = plt.subplots(figsize=(width, 4.2))
    for index, (_name, values) in enumerate(groups.items()):
        x = index + rng.uniform(-jitter_width, jitter_width, len(values))
        ax.scatter(x, values, s=14, color="black", alpha=0.75, linewidths=0)
        ax.hlines(np.median(values), index - 0.18, index + 0.18, colors="red", linewidth=1.8)
        ax.text(index, 1.01, f"n={len(values)}", transform=ax.get_xaxis_transform(), ha="center")
    ax.set_yscale("log")
    ax.set_xlim(-0.6, len(groups) - 0.4)
    ax.set_xticks(range(len(groups)))
    if len(groups) > 1:
        ax.set_xticklabels(list(groups), rotation=30, ha="right")
    else:
        ax.set_xticklabels(list(groups))
    ax.set_ylabel(D_LABEL)
    ax.set_title("Diffusion coefficient", pad=18)
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.8)
    _save(fig, output_path)
    return True


def write_squared_displacements_all_tracks(
    displacements: pd.DataFrame, msd_points: pd.DataFrame, output_path: Path, *, seed: int
) -> bool:
    """Every squared displacement used for the fit, with the mean MSD per lag."""
    if displacements.empty:
        return False
    rng = np.random.default_rng(seed)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for lag, group in displacements.groupby("lag", sort=True):
        x = lag + rng.uniform(-0.18, 0.18, len(group))
        ax.scatter(x, group["squared_displacement_um2"], s=7, alpha=0.25, color="black")
    fit_msd = msd_points[msd_points["used_for_fit"].astype(bool)]
    means = fit_msd.groupby("lag", as_index=False)["msd_um2"].mean()
    ax.plot(means["lag"], means["msd_um2"], "o-", color="red", label="Mean MSD")
    _label_lag_axes(ax)
    _save(fig, output_path, dpi=200)
    return True


def write_squared_displacements_by_track(
    displacements: pd.DataFrame, msd_points: pd.DataFrame, output_dir: Path
) -> int:
    """One figure per fitted track. Returns the number of figures written."""
    count = 0
    fit_msd = msd_points[msd_points["used_for_fit"].astype(bool)]
    for track_id, group in displacements.groupby("track_id", sort=True):
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(group["lag"], group["squared_displacement_um2"], s=10, alpha=0.35, color="black")
        track_msd = fit_msd[fit_msd["track_id"] == track_id].sort_values("lag")
        ax.plot(track_msd["lag"], track_msd["msd_um2"], "o-", color="red", label="Mean MSD")
        ax.set_title(f"Track {int(track_id)}")
        _label_lag_axes(ax)
        _save(fig, output_dir / f"track_{int(track_id)}.png", dpi=160)
        count += 1
    return count


def _label_lag_axes(ax: plt.Axes) -> None:
    ax.set_xlabel("Frame lag")
    ax.set_ylabel(SD_LABEL)
    ax.legend()


def _save(fig: plt.Figure, output_path: Path, dpi: int = 200) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
