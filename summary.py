"""Summarization module (model-agnostic, LangChain + LangGraph).

The backend model is selected at runtime from a ``provider:model`` string via
``init_chat_model``, so this module never hard-codes a vendor. Short transcripts
take a single "stuff" prompt; long ones run a LangGraph map-reduce.

Decoupling: this module never imports ``ui``. Progress is reported through an
injected ``on_progress`` callback supplied by ``app.py``.
"""

from __future__ import annotations

import operator
from typing import Annotated, Callable, TypedDict
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
import util

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def build_model(settings) -> BaseChatModel:
    """
    Constructs an agnostic chat model from a primed Settings object.

    Requires Settings.model and Settings.temperature
    """
    return init_chat_model(settings.model, temperature=settings.temperature)


def _style_instruction(settings) -> str:
    """
    Constructs a prompt header pertaining to the style from a primed Settings object.

    Uses `Settings.summary_style` and `Settings.summary_length` but is not required.
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
    """Summarize transcript ``text`` according to ``settings``.

    ``on_progress`` is an injected callback (e.g. from ``ui``) invoked with a short
    status string between steps; pass ``None`` to silence progress.
    """
    progress = on_progress or _noop
    model = build_model(settings)

    if len(text) <= settings.chunk_chars:
        progress("Summarizing transcript")
        return _stuff_summary(text, model, settings)

    chunks = util.chunk_text(text, settings.chunk_chars)
    progress(f"Long transcript: map-reduce over {len(chunks)} chunks")
    return _mapreduce_summary(chunks, model, settings, progress)


def _stuff_summary(text: str, model: BaseChatModel, settings) -> str:
    messages = [
        SystemMessage(
            "You are an expert at summarizing video transcripts. "
            + _style_instruction(settings)
        ),
        HumanMessage(f"Summarize this video transcript:\n\n{text}"),
    ]
    return model.invoke(messages).content


# --- LangGraph map-reduce -------------------------------------------------

class _State(TypedDict):
    chunks: list[str]
    chunk_summaries: Annotated[list[str], operator.add]
    final: str


class _ChunkState(TypedDict):
    chunk: str


def _mapreduce_summary(
    chunks: list[str], model: BaseChatModel, settings, progress: ProgressFn
) -> str:
    """Run a map-reduce summary as a small LangGraph: map chunks, then reduce."""

    def map_chunk(state: _ChunkState) -> dict:
        resp = model.invoke(
            [
                SystemMessage("Summarize this portion of a video transcript faithfully."),
                HumanMessage(state["chunk"]),
            ]
        )
        return {"chunk_summaries": [resp.content]}

    def fan_out(state: _State):
        return [Send("map_chunk", {"chunk": c}) for c in state["chunks"]]

    def reduce(state: _State) -> dict:
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
        return {"final": resp.content}

    graph = StateGraph(_State)
    graph.add_node("map_chunk", map_chunk)
    graph.add_node("reduce", reduce)
    graph.add_conditional_edges(START, fan_out, ["map_chunk"])
    graph.add_edge("map_chunk", "reduce")
    graph.add_edge("reduce", END)
    app = graph.compile()

    result = app.invoke({"chunks": chunks, "chunk_summaries": [], "final": ""})
    return result["final"]
