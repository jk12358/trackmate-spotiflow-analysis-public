"""A single HTML page (report.html) that shows every result of one run.

Images are linked with relative paths, so the page works after the result
folder is unzipped anywhere, without a server.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import pandas as pd

from trackmate_spotiflow_analysis.labels import SETTING_LABELS, summary_for_display
from trackmate_spotiflow_analysis.outputs import ALL_TRACKS_GIF, FITTED_TRACKS_GIF
from trackmate_spotiflow_analysis.settings import Settings

if TYPE_CHECKING:
    from trackmate_spotiflow_analysis.batch import MovieOutcome

REPORT_FILE = "report.html"
LOG_AXIS_NOTE = "D が 0 以下の track は対数軸に描けないので除く"
COMBINED_FIGURES = [
    (
        "figures/diffusion_strip_plot_log_all_movies.png",
        f"拡散係数（動画ごと、対数軸。赤線は中央値。{LOG_AXIS_NOTE}）",
    ),
    ("figures/diffusion_cumulative_distribution_all_movies.png", "拡散係数の累積分布"),
]
MOVIE_FIGURES = [
    (
        "figures/diffusion_strip_plot_log.png",
        f"拡散係数（対数軸。赤線は中央値。{LOG_AXIS_NOTE}）",
    ),
    ("figures/diffusion_cumulative_distribution.png", "拡散係数の累積分布"),
    ("figures/squared_displacements_all_tracks.png", "fit に使った二乗変位と平均 MSD"),
]
MOVIE_GIFS = [
    (ALL_TRACKS_GIF, "TrackMate で追跡した全 track"),
    (FITTED_TRACKS_GIF, "拡散係数を計算できた track（赤: mobile、水色: immobile）"),
]

STYLE = """
body { font-family: sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px; color: #222; }
h1 { font-size: 1.5em; } h2 { margin-top: 2em; border-bottom: 1px solid #ccc; }
table { border-collapse: collapse; font-size: 0.9em; }
td, th { border: 1px solid #ccc; padding: 4px 8px; }
figure { display: inline-block; width: 46%; margin: 8px; vertical-align: top; }
figure img { width: 100%; border: 1px solid #ddd; } figcaption { font-size: 0.85em; }
.messages li { color: #8a5300; } .error { color: #b00020; }
"""


def write_report(
    output_dir: Path, outcomes: list[MovieOutcome], messages: list[str], settings: Settings
) -> Path:
    parts = [
        "<h1>拡散係数の解析結果</h1>",
        f"<p>作成日時: {datetime.now():%Y-%m-%d %H:%M}</p>",
        _messages_section(messages),
        _summary_section(output_dir),
        _figures(output_dir, COMBINED_FIGURES),
        *[_movie_section(output_dir, outcome) for outcome in outcomes],
        _settings_section(settings),
        _trackmate_section(outcomes),
    ]
    page = (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        "<title>拡散係数の解析結果</title>"
        f"<style>{STYLE}</style></head><body>{''.join(parts)}</body></html>"
    )
    path = output_dir / REPORT_FILE
    path.write_text(page, encoding="utf-8")
    return path


def _messages_section(messages: list[str]) -> str:
    if not messages:
        return ""
    items = "".join(f"<li>{html.escape(message)}</li>" for message in messages)
    return f'<h2>お知らせ</h2><ul class="messages">{items}</ul>'


def _summary_section(output_dir: Path) -> str:
    path = output_dir / "summary_all_movies.csv"
    if not path.exists() or path.stat().st_size == 0:
        return ""
    try:
        summary = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return ""
    table = summary_for_display(summary).to_html(index=False, float_format=lambda v: f"{v:.4g}")
    return f"<h2>全動画の要約</h2>{table}"


def _movie_section(output_dir: Path, outcome: MovieOutcome) -> str:
    name = html.escape(outcome.pair.name)
    if outcome.error:
        return f'<h2>{name}</h2><p class="error">{html.escape(outcome.error)}</p>'
    movie_dir = outcome.output_dir.relative_to(output_dir)
    figures = [(f"{movie_dir.as_posix()}/{path}", caption) for path, caption in MOVIE_FIGURES]
    gifs = [(f"{movie_dir.as_posix()}/{path}", caption) for path, caption in MOVIE_GIFS]
    return f"<h2>{name}</h2>{_figures(output_dir, gifs)}{_figures(output_dir, figures)}"


def _figures(output_dir: Path, items: list[tuple[str, str]]) -> str:
    figures = [
        f'<figure><img src="{html.escape(quote(path))}" alt="{html.escape(caption)}">'
        f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        for path, caption in items
        if (output_dir / path).exists()
    ]
    return "".join(figures)


def _settings_section(settings: Settings) -> str:
    rows = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{_format(getattr(settings.analysis, key))}</td></tr>"
        for key, label in SETTING_LABELS.items()
    )
    return f"<h2>解析条件</h2><table>{rows}</table>"


def _trackmate_section(outcomes: list[MovieOutcome]) -> str:
    rows = [
        {"動画": outcome.pair.name, **outcome.trackmate_run.display_fields()}
        for outcome in outcomes
        if outcome.trackmate_run is not None
    ]
    if not rows:
        return ""
    table = pd.DataFrame(rows).to_html(index=False)
    return f"<h2>TrackMate の設定（XML に記録された値）</h2>{table}"


def _format(value: object) -> str:
    if isinstance(value, bool):
        return "はい" if value else "いいえ"
    return html.escape(str(value))
