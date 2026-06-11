"""
Generic helpers (non-module): pure functions safe to import from any module.
"""

import re
from urllib.parse import parse_qs, urlparse

# A YouTube video id is 11 chars of [A-Za-z0-9_-]
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_ID_IN_PATH_RE = re.compile(r"([A-Za-z0-9_-]{11})")


def extract_video_id(url: str) -> str:
    """
    Return the 11-character video id from a YouTube URL or bare id.

    Handles `watch?v=`, `youtu.be/`, `/shorts/`, `/embed/` and `/live/` forms, and
    raises `ValueError` if no id can be found.
    """
    candidate = (url or "").strip()
    if not candidate:
        raise ValueError("No URL or video id provided.")

    # Already a bare id
    if _VIDEO_ID_RE.match(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower().removeprefix("www.")

    # youtu.be/<id>
    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0]
        if _VIDEO_ID_RE.match(vid):
            return vid

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        # /watch?v=<id>
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id and _VIDEO_ID_RE.match(query_id):
            return query_id
        # /shorts/<id>, /embed/<id>, /live/<id>, /v/<id>
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
            if _VIDEO_ID_RE.match(parts[1]):
                return parts[1]

    # Last resort: find an 11-char token anywhere in the string
    match = _ID_IN_PATH_RE.search(candidate)
    if match:
        return match.group(1)

    raise ValueError(f"Could not extract a YouTube video id from: {url!r}")


def join_snippets(snippets: list[dict]) -> str:
    """
    Flatten transcript snippet dicts into a single whitespace-normalized string.
    """
    text = " ".join(s.get("text", "") for s in snippets)

    # Substitutes any series of white spaces with one single white space
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, size: int) -> list[str]:
    """
    Split `text` into chunks of at most `size` chars on word boundaries.
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        # +1 accounts for the joining space
        if current and length + len(word) + 1 > size:
            chunks.append(" ".join(current))
            current, length = [], 0
        current.append(word)
        length += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks
