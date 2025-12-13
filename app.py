import sys
from typing import List

from neuromind.client import APIError, NeuroMindClient, StreamEventType, ThreadInfo
from neuromind.config import Config, Persona
from neuromind.ui_manager import UIManager


class NeuroApp:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.client = NeuroMindClient(base_url)
        self.ui = UIManager()
        self.active_thread: ThreadInfo | None = None

        try:
            health = self.client.health_check()
            self.model_name = health.get("model", "unknown")
        except APIError as e:
            self.ui.print_critical_error(
                f"{e.message}\nMake sure the server is running: python start_server.py"
            )
            sys.exit(1)

        self.active_thread = self.client.get_or_create_thread(Config.DEFAULT_THREAD)

    def _cmd_list(self):
        threads = self.client.list_threads()
        self.ui.show_thread_list(threads, self.active_thread.name)

    def _cmd_new(self, args: List[str]):
        if not args:
            self.ui.print_error("Usage: /new <thread_name>")
            return

        name = args[0]
        all_personas = list(Persona)
        choice = self.ui.prompt_choice(
            "Select Persona", [p.value for p in all_personas]
        )
        persona = all_personas[choice]

        self.active_thread = self.client.get_or_create_thread(name, persona)
        self.ui.print_info(f"Switched to '{name}' ({persona.value})")

    def _cmd_switch(self, args: List[str]):
        if not args:
            self.ui.print_error("Usage: /switch <thread_name>")
            return

        name = args[0]
        self.active_thread = self.client.get_or_create_thread(name)
        self.ui.print_info(f"Active thread: {name}")

    def _cmd_clear(self):
        if self.ui.confirm(f"Wipe memory for '{self.active_thread.name}'?"):
            self.client.clear_messages(self.active_thread.name)
            self.ui.print_info("Memory wiped.")

    def _process_stream(self, events) -> None:
        thought_buffer = ""
        response_buffer = ""

        with self.ui.stream_response(self.active_thread.name) as live:
            for event in events:
                if event.type == StreamEventType.REASONING:
                    thought_buffer += event.content
                elif event.type == StreamEventType.CONTENT:
                    response_buffer += event.content
                elif event.type == StreamEventType.ERROR:
                    raise APIError(event.message or "Unknown error")
                elif event.type == StreamEventType.DONE:
                    break

                renderable = self.ui.render_stream_group(
                    thought_buffer, response_buffer
                )
                live.update(renderable)

    def run(self):
        self.ui.show_header(self.model_name, self.active_thread.name)

        while True:
            try:
                user_input = self.ui.get_user_input(self.active_thread.name)

                if user_input.startswith("/"):
                    parts = user_input.strip().split()
                    cmd = parts[0].lower()
                    args = parts[1:]

                    if cmd == "/exit":
                        self.ui.print_info("Goodbye.")
                        break
                    elif cmd == "/list":
                        self._cmd_list()
                    elif cmd == "/new":
                        self._cmd_new(args)
                    elif cmd == "/switch":
                        self._cmd_switch(args)
                    elif cmd == "/clear":
                        self._cmd_clear()
                    else:
                        self.ui.print_error("Unknown command.")
                    continue

                events = self.client.stream_chat(self.active_thread.name, user_input)
                self._process_stream(events)

            except KeyboardInterrupt:
                self.ui.print_info("\nUse /exit to quit.")
            except APIError as e:
                self.ui.print_error(e.message)
            except Exception as e:
                self.ui.print_error(str(e))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NeuroMind CLI")
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    app = NeuroApp(base_url=args.server)
    app.run()
