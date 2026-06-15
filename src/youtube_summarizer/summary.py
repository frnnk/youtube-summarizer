"""
Summarization module (model-agnostic, LangGraph ecosystem).

The backend model is selected at runtime from a `Settings` object.
"""

import operator
from typing import Annotated, Callable, TypedDict
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from youtube_summarizer import util

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def _content_text(resp) -> str:
    """
    Extracts plain text from a model response whose `content` may be a string or a
    list of content blocks, as providers like Gemini return.
    """
    content = resp.content
    if isinstance(content, str):
        return content
    # List form: keep text blocks, drop reasoning/thinking and other block types
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type", "text") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts).strip()


def build_model(settings) -> BaseChatModel:
    """
    Constructs an agnostic chat model from a `Settings` object.
    """
    return init_chat_model(settings.model, temperature=settings.temperature)


def _style_instruction(settings) -> str:
    """
    Constructs a short style guide according to a `Settings` object.
    """
    shape = {
        "bullets": "Format the summary as concise bullet points.",
        "paragraph": "Format the summary as flowing prose paragraphs.",
    }.get(settings.summary_style, "Format the summary as concise bullet points.")
    detail = {
        "short": "Keep it to the 3-5 most important points.",
        "medium": "Cover the main points and key supporting details.",
        "long": "Be thorough and capture nuances, examples, and structure.",
    }.get(settings.summary_length, "Cover the main points and key supporting details.")

    return f"{shape} {detail}"


def summarize(
        text: str, 
        settings, *, 
        on_progress: ProgressFn | None = None
    ) -> str:
    """
    Summarize transcript `text` according to a `Settings` object.

    `on_progress` is an injected callback (e.g. from `ui`) invoked with a short
    status string between steps; pass `None` to silence progress.
    """
    progress = on_progress or _noop
    model = build_model(settings)

    # If transcript is short enough we can resort to direct summarization
    # otherwise we go with a mapreduce strategy
    if len(text) <= settings.chunk_chars:
        progress("Summarizing transcript")
        return _short_summary(text, model, settings)

    chunks = util.chunk_text(text, settings.chunk_chars)
    progress(f"Long transcript: map-reduce over {len(chunks)} chunks")
    return _mapreduce_summary(chunks, model, settings, progress)


def _short_summary(
        text: str, 
        model: BaseChatModel, 
        settings
    ) -> str:
    """
    Perform a simple summary with our model, using configurations specified in the
    `Settings` object.
    """
    messages = [
        SystemMessage(
            "You are an expert at summarizing video transcripts. "
            + _style_instruction(settings)
        ),
        HumanMessage(f"Summarize this video transcript:\n\n{text}"),
    ]
    return _content_text(model.invoke(messages))


# LangGraph map-reduce system

class _State(TypedDict):
    chunks: list[str]
    chunk_summaries: Annotated[list[str], operator.add]
    final: str


class _ChunkState(TypedDict):
    chunk: str


def _mapreduce_summary(
        chunks: list[str], 
        model: BaseChatModel, 
        settings, 
        progress: ProgressFn
    ) -> str:
    """
    Run a map-reduce summary via a small LangGraph system: map chunks, then reduce.

    `progress` is called periodically to send back progress updates.
    """
    def map_chunk(state: _ChunkState) -> dict:
        """
        Summarizes one chunk of a video transcript.
        """
        # State is the output of a Send payload
        resp = model.invoke(
            [
                SystemMessage("Summarize this portion of a video transcript faithfully."),
                HumanMessage(state["chunk"]),
            ]
        )
        return {"chunk_summaries": [_content_text(resp)]}

    def fan_out(state: _State):
        """
        Sends N payloads to map_chunk, where N is the number of chunks.
        """
        return [Send("map_chunk", {"chunk": c}) for c in state["chunks"]]

    def reduce(state: _State) -> dict:
        """
        Aggregates all transcript chunks into one summary.
        """
        progress("Combining chunk summaries")
        combined = "\n\n".join(
            f"- Section {i + 1}: {s}"
            for i, s in enumerate(state["chunk_summaries"])
        )
        resp = model.invoke(
            [
                SystemMessage(
                    "You are an expert summarizer. Combine these section summaries "
                    "of one video into a single coherent summary. "
                    + _style_instruction(settings)
                ),
                HumanMessage(combined),
            ]
        )
        return {"final": _content_text(resp)}

    graph = StateGraph(_State)
    graph.add_node("map_chunk", map_chunk)
    graph.add_node("reduce", reduce)
    graph.add_conditional_edges(START, fan_out, ["map_chunk"])
    graph.add_edge("map_chunk", "reduce")
    graph.add_edge("reduce", END)
    app = graph.compile()

    result = app.invoke({"chunks": chunks, "chunk_summaries": [], "final": ""})
    return result["final"]


if __name__ == '__main__':
    pass
