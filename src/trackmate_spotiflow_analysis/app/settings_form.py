"""Sidebar form for the analysis settings."""

from __future__ import annotations

from typing import Any

import streamlit as st

from trackmate_spotiflow_analysis.errors import UserFacingError
from trackmate_spotiflow_analysis.labels import SETTING_LABELS
from trackmate_spotiflow_analysis.settings import AnalysisSettings, Settings

# key -> (step, format) of the number inputs shown in the sidebar
BASIC_NUMBERS = {
    "frame_interval_s": (0.001, "%.4f"),
    "pixel_size_um": (0.0001, "%.5f"),
    "min_spots": (1, None),
    "immobile_threshold_um2_s": (0.0001, "%.5f"),
}


def render_settings_form(defaults: Settings) -> Settings | None:
    """Show the settings in the sidebar. Returns None when the values are invalid."""
    sidebar = st.sidebar
    sidebar.header("解析条件")
    sidebar.caption("研究室の標準の値が入っています。撮影条件が違うときだけ変えてください。")
    analysis = defaults.analysis
    values = {
        key: _number_input(sidebar, key, getattr(analysis, key), step, number_format)
        for key, (step, number_format) in BASIC_NUMBERS.items()
    }
    with sidebar.expander("詳しい設定"):
        values.update(_advanced_values(analysis))
        make_gifs = st.checkbox("overlay の GIF を作る", value=defaults.overlay.enabled)
    try:
        return defaults.with_analysis(**values).with_overlay(enabled=make_gifs)
    except UserFacingError as exc:
        sidebar.error(str(exc))
        return None


def _number_input(
    container: Any, key: str, default: float | int, step: float, number_format: str | None
) -> float | int:
    if isinstance(default, int):
        return int(container.number_input(SETTING_LABELS[key], value=default, min_value=2, step=1))
    return container.number_input(
        SETTING_LABELS[key], value=default, min_value=0.0, step=step, format=number_format
    )


def _advanced_values(analysis: AnalysisSettings) -> dict[str, Any]:
    return {
        "fit_initial_points": _number_input(
            st, "fit_initial_points", analysis.fit_initial_points, 1, None
        ),
        "include_intercept": st.checkbox(
            SETTING_LABELS["include_intercept"], value=analysis.include_intercept
        ),
        "use_filtered_tracks": st.checkbox(
            SETTING_LABELS["use_filtered_tracks"], value=analysis.use_filtered_tracks
        ),
    }
