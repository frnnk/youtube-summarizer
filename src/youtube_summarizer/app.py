"""
CLI entrypoint and orchestrator: the only module that imports the feature modules.

Parses CLI arguments, builds a `Settings` object, and wires the modules together.
"""

import argparse
import os
import sys

from youtube_summarizer import fetch, settings, summary, ui, util


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Define and parse the command-line interface.
    """
    parser = argparse.ArgumentParser(
        prog="yt-summarize",
        description="Summarize a YouTube video from its link.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="YouTube video URL or 11-character video id",
    )
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
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to a JSON config file (overrides the default resolution)",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Open an interactive editor to change saved preferences",
    )
    return parser.parse_args(argv)


def build_settings(args: argparse.Namespace):
    """
    Load settings, then apply CLI overrides (CLI wins over env, JSON and defaults).
    """
    s = settings.load_settings()
    if args.model:
        s.model = args.model
    if args.languages:
        s.languages = args.languages
    if args.style:
        s.summary_style = args.style
    if args.length:
        s.summary_length = args.length
    return s


def edit_settings_command() -> int:
    """
    Open the interactive settings editor and persist the result atomically.
    """
    effective = settings.load_settings()
    current = {field: getattr(effective, field) for field in settings.CONFIG_FIELDS}

    new_values = ui.edit_settings(current)
    if new_values is None:
        ui.show_info("No changes made", title="Cancelled")
        return 0

    path = settings.save_config(new_values)
    ui.show_info(f"Saved preferences to {path}", title="Settings updated")
    return 0


def run(args: argparse.Namespace) -> int:
    """
    Fetch the transcript, summarize it, and render the result.
    """
    s = build_settings(args)

    video_id = util.extract_video_id(args.url)

    snippets = fetch.get_transcript(video_id, s.languages)
    text = fetch.transcript_to_text(snippets)

    if args.show_transcript:
        ui.show_summary(text, title="Transcript", meta=f"video {video_id}")

    # Inject ui's progress callback so summary can report progress without importing ui
    with ui.status("Summarizing"):
        result = summary.summarize(text, s, on_progress=ui.progress_callback)

    ui.show_summary(
        result, title="Video Summary", meta=f"{s.model} · video {video_id}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """
    CLI entrypoint: parse args, dispatch, and map errors to clean messages and exit codes.
    """
    args = parse_args(argv)

    # A --config path takes priority over any ambient YTS_CONFIG for this run
    if args.config:
        os.environ["YTS_CONFIG"] = args.config

    try:
        if args.settings:
            return edit_settings_command()
        if not args.url:
            ui.show_error("A YouTube URL or video id is required.")
            return 2
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
