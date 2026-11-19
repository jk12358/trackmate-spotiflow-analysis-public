"""Show the results of one run and offer them as a ZIP file."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from trackmate_spotiflow_analysis.batch import BatchResult, MovieOutcome
from trackmate_spotiflow_analysis.labels import summary_for_display
from trackmate_spotiflow_analysis.report import COMBINED_FIGURES, MOVIE_FIGURES, MOVIE_GIFS

IMAGES_PER_ROW = 2  # wider rows squeeze figures until their labels are unreadable


def render_results(result: BatchResult, zip_path: Path) -> None:
    done, total = len(result.succeeded), len(result.outcomes)
    if done == total:
        st.success(f"{total} 本の動画をすべて解析しました。")
    else:
        st.error(
            f"{total} 本のうち {total - done} 本を解析できませんでした。"
            "下のお知らせを見てください。"
        )
    st.download_button(
        "結果をまとめてダウンロード（ZIP）",
        data=zip_path.read_bytes,  # read only when the button is clicked
        file_name=zip_path.name,
        mime="application/zip",
        type="primary",
    )
    st.caption("ZIP を展開して report.html を開くと、この画面と同じ内容をあとから見られます。")
    if result.messages:
        st.warning("\n".join(f"- {message}" for message in result.messages))
    _render_combined(result.output_dir)
    _render_movies(result.outcomes)


def _render_combined(output_dir: Path) -> None:
    st.subheader("全動画の要約")
    summary_path = output_dir / "summary_all_movies.csv"
    if summary_path.stat().st_size > 1:
        summary = pd.read_csv(summary_path)
        st.dataframe(summary_for_display(summary), hide_index=True)
    _render_images(output_dir, COMBINED_FIGURES)


def _render_movies(outcomes: list[MovieOutcome]) -> None:
    st.subheader("動画ごとの結果")
    names = [outcome.pair.name for outcome in outcomes]
    selected = st.selectbox("動画を選んでください", names)
    outcome = outcomes[names.index(selected)]
    if outcome.error:
        st.error(outcome.error)
        return
    _render_images(outcome.output_dir, MOVIE_GIFS)
    _render_images(outcome.output_dir, MOVIE_FIGURES)


def _render_images(folder: Path, items: list[tuple[str, str]]) -> None:
    """Show images in rows, each scaled to its column so neighbours never overlap."""
    present = [(folder / path, caption) for path, caption in items if (folder / path).exists()]
    for start in range(0, len(present), IMAGES_PER_ROW):
        row = present[start : start + IMAGES_PER_ROW]
        for column, (path, caption) in zip(st.columns(IMAGES_PER_ROW), row, strict=False):
            column.image(str(path), caption=caption, width="stretch")
