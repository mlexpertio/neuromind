from typing import List, Tuple

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table


class UIManager:
    def __init__(self):
        self.console = Console()

    def show_header(self, model: str, thread: str):
        self.console.clear()
        self.console.print(
            Panel(
                f"[bold cyan]NeuroMind CLI[/bold cyan] [dim]| Terminal AI Assistant [/dim]\n"
                f"Model: [green]{model}[/green] | Thread: [yellow]{thread}[/yellow]\n"
                "Cmds: [magenta]/new, /switch, /list, /clear, /exit[/magenta]",
                border_style="cyan",
            )
        )

    def show_thread_list(self, threads: List[Tuple[str, str, int]], active_name: str):
        table = Table(title="Memory Banks", border_style="dim")
        table.add_column("Status", width=3)
        table.add_column("Name", style="cyan")
        table.add_column("Persona", style="magenta")
        table.add_column("Msgs", justify="right")

        for name, persona, count in threads:
            marker = "➤" if name == active_name else ""
            table.add_row(marker, name, persona, str(count))

        self.console.print(table)

    def get_user_input(self, thread_name: str) -> str:
        return Prompt.ask(f"\n[bold cyan][{thread_name}][/bold cyan] User")

    def stream_response(self, thread_name: str) -> Live:
        self.console.print(f"[bold magenta]Neuro ({thread_name}) > [/bold magenta]")
        return Live(
            Markdown(""),
            refresh_per_second=15,
            transient=False,
            vertical_overflow="visible",
        )

    def render_stream_group(self, thought: str, response: str) -> Group:
        renderables: List[RenderableType] = []

        if thought:
            renderables.append(
                Panel(
                    Markdown(thought, style="italic dim white"),
                    title="[dim]Reasoning[/dim]",
                    border_style="dim",
                    expand=False,
                )
            )

        if response:
            renderables.append(Markdown(response))

        return Group(*renderables)

    def print_error(self, msg: str):
        self.console.print(f"[bold red]Error:[/bold red] {msg}")

    def print_info(self, msg: str):
        self.console.print(f"[green]{msg}[/green]")
