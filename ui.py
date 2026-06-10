"""
Presentation module (Rich): owns all terminal rendering.
"""

from contextlib import contextmanager

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

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
