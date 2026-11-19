"""Japanese labels for tables shown to users (the CSV files keep English columns)."""

from __future__ import annotations

import pandas as pd

SUMMARY_LABELS = {
    "movie_name": "動画",
    "trackmate_spot_count": "spot 数",
    "fitted_track_count": "D を計算できた track 数",
    "track_count": "対象の track 数",
    "immobile_track_count": "immobile の数",
    "immobile_fraction": "immobile の割合",
    "median_diffusion_coefficient_um2_s": "D の中央値 (um²/s)",
    "mean_diffusion_coefficient_um2_s": "D の平均 (um²/s)",
    "q1_diffusion_coefficient_um2_s": "D の第 1 四分位 (um²/s)",
    "q3_diffusion_coefficient_um2_s": "D の第 3 四分位 (um²/s)",
}

SETTING_LABELS = {
    "frame_interval_s": "フレーム間隔（Frame interval, s）",
    "pixel_size_um": "ピクセルサイズ（Pixel size, um）",
    "fit_initial_points": "MSD の fit 点数",
    "include_intercept": "切片を含めて fit する",
    "min_spots": "最短の track の spot 数",
    "immobile_threshold_um2_s": "Immobile と判定する D の上限（um²/s）",
    "use_filtered_tracks": "TrackMate の track filter を通った track だけを使う",
}


def summary_for_display(summary: pd.DataFrame) -> pd.DataFrame:
    """Columns that biologists read first, renamed to Japanese."""
    columns = [column for column in SUMMARY_LABELS if column in summary.columns]
    return summary[columns].rename(columns=SUMMARY_LABELS)
