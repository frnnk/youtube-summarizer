"""
CLI entrypoint and orchestrator: the only module that imports the feature modules.

Parses CLI arguments, builds a `Settings` object, and wires the modules together.
"""

import argparse
import sys

from youtube_summarizer import fetch, summary, ui, util
from youtube_summarizer.settings import load_settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Define and parse the command-line interface.
    """
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
    """
    Load settings, then apply CLI overrides (CLI wins over env and defaults).
    """
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
    """
    Fetch the transcript, summarize it, and render the result.
    """
    settings = build_settings(args)

    video_id = util.extract_video_id(args.url)

    snippets = fetch.get_transcript(video_id, settings.languages)
    text = fetch.transcript_to_text(snippets)

    if args.show_transcript:
        ui.show_summary(text, title="Transcript", meta=f"video {video_id}")

    # Inject ui's progress callback so summary can report progress without importing ui
    with ui.status("Summarizing"):
        result = summary.summarize(
            text, settings, on_progress=ui.progress_callback
        )

    ui.show_summary(
        result, title="Video Summary", meta=f"{settings.model} · video {video_id}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """
    CLI entrypoint: parse args, run, and map errors to clean messages and exit codes.
    """
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
