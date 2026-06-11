"""
Presentation module (Rich): owns all terminal rendering.
"""

from contextlib import contextmanager

import questionary
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from youtube_summarizer import settings

console = Console()


def show_summary(summary: str, *, title: str = "Summary", meta: str | None = None) -> None:
    """
    Render `summary` inside a titled panel, with an optional metadata subtitle.
    """
    console.print(
        Panel(
            Markdown(summary),
            title=f"[bold]{title}[/bold]",
            subtitle=meta or None,
            border_style="cyan",
            padding=(1, 2),
        )
    )


def show_error(message: str) -> None:
    """
    Render an error message to stderr in a red panel.
    """
    Console(stderr=True).print(
        Panel(message, title="[bold red]Error[/bold red]", border_style="red")
    )


@contextmanager
def status(label: str):
    """
    Spinner context manager for long-running steps.
    """
    with console.status(f"[cyan]{label}…[/cyan]", spinner="dots") as st:
        yield st


def progress_callback(message: str) -> None:
    """
    Injectable progress sink that prints a dim status line.
    """
    console.print(f"[dim]› {message}[/dim]")


def show_info(message: str, *, title: str = "Done") -> None:
    """
    Render an informational message in a green panel.
    """
    console.print(
        Panel(message, title=f"[bold green]{title}[/bold green]", border_style="green")
    )


# Interactive settings editor

def _validate_positive_int(text: str):
    """
    questionary validator: accept a positive whole number.
    """
    return (text.strip().isdigit() and int(text) > 0) or "Enter a positive whole number"


def _validate_float(text: str):
    """
    questionary validator: accept any number.
    """
    try:
        float(text)
        return True
    except ValueError:
        return "Enter a number"


def _ask_model(current_model: str | None) -> str | None:
    """
    Prompt for a model: pick a preset or enter a custom `provider:model` id.
    """
    custom = "Custom…"
    choices = list(settings.MODEL_PRESETS)
    if current_model and current_model not in choices:
        choices.insert(0, current_model)
    choices.append(custom)

    choice = questionary.select("Model", choices=choices, default=current_model).ask()
    if choice is None or choice != custom:
        return choice
    return questionary.text(
        "Model id (provider:model)", default=current_model or ""
    ).ask()


def edit_settings(current: dict) -> dict | None:
    """
    Interactively edit preferences with questionary, returning the new values or
    `None` if the user cancels.
    """
    style = questionary.select(
        "Summary style",
        choices=list(settings.STYLE_CHOICES),
        default=current.get("summary_style"),
    ).ask()
    if style is None:
        return None

    length = questionary.select(
        "Summary length",
        choices=list(settings.LENGTH_CHOICES),
        default=current.get("summary_length"),
    ).ask()
    if length is None:
        return None

    model = _ask_model(current.get("model"))
    if model is None:
        return None

    languages = questionary.text(
        "Languages (comma-separated, priority order)",
        default=",".join(current.get("languages", [])),
    ).ask()
    if languages is None:
        return None
    languages = [part.strip() for part in languages.split(",") if part.strip()]

    chunk = questionary.text(
        "Chunk size in characters (map-reduce threshold)",
        default=str(current.get("chunk_chars", "")),
        validate=_validate_positive_int,
    ).ask()
    if chunk is None:
        return None

    temperature = questionary.text(
        "Temperature",
        default=str(current.get("temperature", "")),
        validate=_validate_float,
    ).ask()
    if temperature is None:
        return None

    return {
        "model": model,
        "temperature": float(temperature),
        "chunk_chars": int(chunk),
        "summary_style": style,
        "summary_length": length,
        "languages": languages,
    }
