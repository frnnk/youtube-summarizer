"""CLI entrypoint and orchestrator.

This is the *only* module that imports the feature modules. It parses arguments,
builds a `Settings` object, and wires the modules together — including the
dependency-injection points (config passed down, and ``ui.progress_callback``
injected into ``summary.summarize``). Modules never import each other.
"""

from __future__ import annotations

import argparse
import sys

import fetch
import summary
import ui
import util
from settings import load_settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="yt-summarize",
        description="Summarize a YouTube video from its link.",
    )
    parser.add_argument("url", help="YouTube video URL or 11-character video id")
    parser.add_argument(
        "--model",
        help="Model id as provider:model, e.g. anthropic:claude-haiku-4-5 "
        "or openai:gpt-4o-mini",
    )
    parser.add_argument(
        "-l",
        "--language",
        action="append",
        dest="languages",
        help="Preferred transcript language code (repeatable, in priority order)",
    )
    parser.add_argument(
        "--style", choices=["bullets", "paragraph"], help="Summary format"
    )
    parser.add_argument(
        "--length", choices=["short", "medium", "long"], help="Summary length"
    )
    parser.add_argument(
        "--show-transcript",
        action="store_true",
        help="Print the raw transcript before summarizing",
    )
    return parser.parse_args(argv)


def build_settings(args: argparse.Namespace):
    """Load settings, then apply CLI overrides (CLI wins over env/defaults)."""
    settings = load_settings()
    if args.model:
        settings.model = args.model
    if args.languages:
        settings.languages = args.languages
    if args.style:
        settings.summary_style = args.style
    if args.length:
        settings.summary_length = args.length
    return settings


def run(args: argparse.Namespace) -> int:
    settings = build_settings(args)

    video_id = util.extract_video_id(args.url)

    snippets = fetch.get_transcript(video_id, settings.languages)
    text = fetch.transcript_to_text(snippets)

    if args.show_transcript:
        ui.show_summary(text, title="Transcript", meta=f"video {video_id}")

    # Dependency injection: the summarizer reports progress via ui's callback
    # without ever importing ui.
    with ui.status("Summarizing"):
        result = summary.summarize(
            text, settings, on_progress=ui.progress_callback
        )

    ui.show_summary(
        result, title="Video Summary", meta=f"{settings.model} · video {video_id}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except ValueError as exc:  # bad URL / id
        ui.show_error(str(exc))
        return 2
    except fetch.TranscriptError as exc:
        ui.show_error(str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001 - surface anything else cleanly
        ui.show_error(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
