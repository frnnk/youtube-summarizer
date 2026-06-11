"""
Transcript fetching module.

Wraps `youtube-transcript-api` and normalizes its several failure modes into a
single `TranscriptError`.
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from youtube_summarizer import util


class TranscriptError(Exception):
    """
    Raised when a transcript cannot be retrieved, for any underlying reason.
    """


def get_transcript(video_id: str, languages: list[str]) -> list[dict]:
    """
    Fetch a transcript as a list of `{text, start, duration}` snippet dicts.

    Tries the preferred `languages` in order, and raises `TranscriptError` with a
    human-readable message on any failure.
    """
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
    except TranscriptsDisabled as exc:
        raise TranscriptError("Captions are disabled for this video.") from exc
    except NoTranscriptFound as exc:
        raise TranscriptError(
            f"No transcript found for languages {languages}."
        ) from exc
    except VideoUnavailable as exc:
        raise TranscriptError("The video is unavailable.") from exc
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptError(f"Could not retrieve transcript: {exc}") from exc

    return fetched.to_raw_data()


def transcript_to_text(snippets: list[dict]) -> str:
    """
    Join snippet dicts into a single clean transcript string.
    """
    return util.join_snippets(snippets)


def list_languages(video_id: str) -> list[str]:
    """
    Return the language codes for which a transcript is available.
    """
    try:
        transcripts = YouTubeTranscriptApi().list(video_id)
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptError(f"Could not list transcripts: {exc}") from exc
    return [t.language_code for t in transcripts]
