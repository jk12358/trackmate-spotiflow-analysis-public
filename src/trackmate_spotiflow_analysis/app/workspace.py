"""Per-session folders for uploaded files and results."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.runtime.memory_uploaded_file_manager import MemoryUploadedFileManager
from streamlit.runtime.scriptrunner import get_script_run_ctx

from trackmate_spotiflow_analysis.errors import UserFacingError
from trackmate_spotiflow_analysis.video import VIDEO_SUFFIXES

UPLOAD_TYPES = sorted({"xml", *(suffix.lstrip(".") for suffix in VIDEO_SUFFIXES)})
WORKSPACE_PREFIX = "tmsa-"
MAX_WORKSPACE_AGE_S = 24 * 60 * 60
MAX_TOTAL_UPLOAD_BYTES = 1000 * 1024 * 1024


def workspace() -> Path:
    """A temporary folder for this browser session, refreshed on every use."""
    folder = st.session_state.get("workspace")
    if folder is None:
        remove_old_workspaces(Path(tempfile.gettempdir()))
        folder = Path(tempfile.mkdtemp(prefix=WORKSPACE_PREFIX))
        st.session_state["workspace"] = folder
    elif not folder.is_dir():
        # Removed by the server (restart or cleanup): start again with this session.
        for key in ("workspace", "upload_signature", "result"):
            st.session_state.pop(key, None)
        raise UserFacingError(
            "時間がたったため、入れたファイルがサーバーから消えました。"
            "ページを読み込み直して、ファイルを入れ直してください。"
        )
    os.utime(folder)  # keep the folder of an active session from being cleaned up
    return folder


def clear_workspace() -> None:
    """Delete this session's uploads and results from the server and forget them."""
    folder = st.session_state.get("workspace")
    if folder is not None and Path(folder).is_dir():
        for child in Path(folder).iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    for key in ("upload_signature", "result"):
        st.session_state.pop(key, None)


def release_uploads(files: list[Any] | None) -> None:
    """Free the server memory that Streamlit keeps for these uploaded files.

    Changing the uploader's key hides the files but Streamlit keeps them in memory
    until the session ends. Streamlit's own chat input frees files the same way.
    """
    ctx = get_script_run_ctx()
    if ctx is None or not isinstance(ctx.uploaded_file_mgr, MemoryUploadedFileManager):
        return
    for uploaded in files or []:
        ctx.uploaded_file_mgr.remove_file(session_id=ctx.session_id, file_id=uploaded.file_id)


def remove_old_workspaces(temp_root: Path, max_age_s: float = MAX_WORKSPACE_AGE_S) -> None:
    """Delete workspaces of earlier sessions so that the server disk does not fill up."""
    limit = time.time() - max_age_s
    for folder in temp_root.glob(f"{WORKSPACE_PREFIX}*"):
        try:
            if folder.is_dir() and folder.stat().st_mtime < limit:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            continue


def save_uploads(files: list[Any], folder: Path) -> list[Path]:
    """Save uploaded files once; a different set of files clears old inputs and results."""
    # file_id changes on every upload, so a replaced file with the same name and
    # size is still detected as new.
    check_uploads(files)
    signature = tuple(sorted((f.file_id, f.name, f.size) for f in files))
    if st.session_state.get("upload_signature") != signature:
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        for uploaded in files:
            (folder / Path(uploaded.name).name).write_bytes(uploaded.getbuffer())
        st.session_state["upload_signature"] = signature
        st.session_state.pop("result", None)
    return sorted(path for path in folder.iterdir() if path.is_file())


def check_uploads(files: list[Any]) -> None:
    """Reject uploads that would overwrite each other or exhaust the server."""
    names = [Path(f.name).name for f in files]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise UserFacingError(
            f"同じ名前のファイルが 2 つ以上あります（{'、'.join(duplicates)}）。"
            "どれか 1 つの名前を変えてから入れ直してください。"
        )
    if sum(f.size for f in files) > MAX_TOTAL_UPLOAD_BYTES:
        raise UserFacingError(
            "入れたファイルの合計が 1 GB を超えています。何回かに分けて解析するか、"
            "自分の PC の起動ファイル（launchers/解析アプリを起動.bat）で解析してください。"
        )


def fresh_folder(path: Path) -> Path:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path
