"""The single page of the Streamlit app."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st

from trackmate_spotiflow_analysis.app.results_view import render_results
from trackmate_spotiflow_analysis.app.settings_form import render_settings_form
from trackmate_spotiflow_analysis.app.workspace import (
    UPLOAD_TYPES,
    clear_workspace,
    fresh_folder,
    release_uploads,
    save_uploads,
    workspace,
)
from trackmate_spotiflow_analysis.batch import run_batch
from trackmate_spotiflow_analysis.errors import UserFacingError
from trackmate_spotiflow_analysis.pairing import PairingPlan, plan_pairs
from trackmate_spotiflow_analysis.settings import Settings, load_settings
from trackmate_spotiflow_analysis.trackmate_run import TrackMateRun, read_trackmate_run

logger = logging.getLogger(__name__)
UPLOAD_ROUND = "upload_round"

# One list item per line: a line break inside Japanese text would show as a space.
INSTRUCTIONS = "\n".join(
    [
        "1. TrackMate で保存した **XML** と、元の **動画**（AVI・TIFF など）を、"
        "下の枠にまとめてドラッグ＆ドロップします。何組でも入れられます。"
        "XML と動画は、ファイル名が同じものどうしを組にします。",
        "2. 組み合わせを確かめて、「解析を始める」を押します。",
        "3. 結果を画面で確かめ、「結果をまとめてダウンロード」で保存します。",
    ]
)


def main() -> None:
    st.set_page_config(page_title="拡散係数の解析", layout="wide")
    st.title("TrackMate の結果から拡散係数を求める")
    st.markdown(INSTRUCTIONS)
    try:
        _page()
    except UserFacingError as exc:
        st.error(str(exc))
    except Exception:
        logger.exception("Unexpected error in the app")
        st.error(
            "予期しないエラーで止まりました。ページを読み込み直してやり直してください。"
            "同じことが起きたら、入れたファイルと一緒に開発者に知らせてください。"
        )


def _page() -> None:
    settings = render_settings_form(load_settings())
    files = st.file_uploader(
        "XML と動画をここに入れてください",
        type=UPLOAD_TYPES,
        accept_multiple_files=True,
        # A new key gives an empty uploader after "新しい解析を始める".
        key=_uploader_key(),
    )
    if not files:
        st.session_state.pop("upload_signature", None)
        st.session_state.pop("result", None)
        return
    root = workspace()
    plan = plan_pairs(save_uploads(files, root / "inputs"))
    _render_plan(plan)
    can_run = bool(plan.pairs) and settings is not None
    if st.button("解析を始める", type="primary", disabled=not can_run):
        _run(plan, settings, root)
    if "result" not in st.session_state:
        return
    result, zip_path, used_settings = st.session_state["result"]
    if used_settings != settings:
        st.warning("解析条件を変えました。新しい条件で「解析を始める」をもう一度押してください。")
    else:
        render_results(result, zip_path)
    st.divider()
    st.button(
        "新しい解析を始める",
        on_click=_start_over,
        help="入れたファイルと結果を消して、最初の画面に戻ります。解析条件はそのまま残ります。",
    )


def _uploader_key() -> str:
    return f"uploads_{st.session_state.get(UPLOAD_ROUND, 0)}"


def _start_over() -> None:
    release_uploads(st.session_state.get(_uploader_key()))
    st.session_state[UPLOAD_ROUND] = st.session_state.get(UPLOAD_ROUND, 0) + 1
    clear_workspace()


def _render_plan(plan: PairingPlan) -> None:
    st.subheader("XML と動画の組み合わせ")
    if not plan.pairs:
        st.error("XML が 1 つもありません。TrackMate で保存した .xml ファイルも入れてください。")
        return
    rows = [
        {
            "動画の名前": pair.name,
            "XML": pair.xml_path.name,
            "動画": pair.video_path.name if pair.video_path else "（なし: GIF は作りません）",
        }
        for pair in plan.pairs
    ]
    st.dataframe(rows, hide_index=True)
    runs = [_trackmate_fields(pair.xml_path) for pair in plan.pairs]
    st.markdown("**XML に記録された TrackMate の設定**")
    st.dataframe(
        [{"動画の名前": pair.name, **run} for pair, run in zip(plan.pairs, runs, strict=True)],
        hide_index=True,
    )
    st.caption("検出は Spotiflow のモデル、gap closing は最大の距離と最大のフレーム数です。")
    messages = plan.messages()
    readable = [run for run in runs if run["検出"] != UNREADABLE]
    if len({tuple(run[key] for key in COMPARED_SETTINGS) for run in readable}) > 1:
        messages.append(
            "XML によって TrackMate の設定（検出・linking・gap closing）が違います。"
            "動画どうしを比べるときは気をつけてください。"
        )
    if messages:
        st.info("\n".join(f"- {message}" for message in messages))


COMPARED_SETTINGS = ("検出", "linking", "gap closing")
UNREADABLE = "読めません"


def _trackmate_fields(xml_path: Path) -> dict[str, str]:
    stat = xml_path.stat()
    return _cached_trackmate_fields(str(xml_path), stat.st_mtime_ns, stat.st_size)


@st.cache_data(max_entries=200, show_spinner=False)
def _cached_trackmate_fields(path: str, mtime_ns: int, size: int) -> dict[str, str]:
    # mtime and size are part of the cache key so a replaced upload is read again
    # (Streamlit leaves arguments starting with "_" out of the key, so no prefix here).
    del mtime_ns, size
    try:
        return read_trackmate_run(Path(path)).display_fields()
    except UserFacingError:
        return dict.fromkeys(TrackMateRun().display_fields(), UNREADABLE)


def _run(plan: PairingPlan, settings: Settings, root: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = fresh_folder(root / "results") / f"diffusion_results_{stamp}"
    bar = st.progress(0.0, text="解析を始めます")
    result = run_batch(
        plan, output_dir, settings, progress=lambda fraction, text: bar.progress(fraction, text)
    )
    bar.progress(1.0, text="ZIP ファイルを作っています")
    archive = shutil.make_archive(str(output_dir), "zip", output_dir.parent, output_dir.name)
    bar.empty()
    st.session_state["result"] = (result, Path(archive), settings)
