"""Command line entry point: `tmsa run <files or folders>`."""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

from trackmate_spotiflow_analysis.batch import ERROR_LOG_FILE, run_batch
from trackmate_spotiflow_analysis.errors import UserFacingError
from trackmate_spotiflow_analysis.pairing import collect_input_files, plan_pairs
from trackmate_spotiflow_analysis.settings import load_settings


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    args.output = args.output or Path("outputs") / datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        return _run(args)
    except UserFacingError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    except Exception:
        log_path = _write_error_log(args.output)
        print(
            f"エラー: 予期しないエラーで止まりました。{log_path} を開発者に送ってください。",
            file=sys.stderr,
        )
        return 1


def _write_error_log(output_dir: Path) -> Path:
    """Append the traceback to the result folder, or to the current folder if that fails."""
    for folder in (output_dir, Path.cwd()):
        log_path = (folder / ERROR_LOG_FILE).resolve()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except OSError:
            continue
        return log_path
    return log_path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tmsa", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Analyze TrackMate XML files and movies.")
    run.add_argument("inputs", nargs="+", type=Path, help="XML/movie files or folders.")
    run.add_argument("--output", type=Path, help="Output folder (default: outputs/<timestamp>).")
    run.add_argument("--config", type=Path, help="Settings YAML (default: configs/default.yaml).")
    run.add_argument("--no-overlay", action="store_true", help="Skip the overlay GIFs.")
    return parser.parse_args(argv)


def _run(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if args.no_overlay:
        settings = settings.with_overlay(enabled=False)
    plan = plan_pairs(collect_input_files(args.inputs))
    result = run_batch(plan, args.output, settings, progress=_print_progress)
    for message in result.messages:
        print(f"- {message}")
    print(f"結果: {result.output_dir}（{len(result.succeeded)}/{len(result.outcomes)} 本を解析）")
    return 0 if result.succeeded else 1


def _print_progress(fraction: float, text: str) -> None:
    print(f"[{fraction:4.0%}] {text}")


if __name__ == "__main__":
    raise SystemExit(main())
