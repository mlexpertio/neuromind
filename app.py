import sys
from typing import List

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from rich.prompt import Confirm, Prompt

from neuromind.config import Config, ModelConfig, Persona
from neuromind.stream_processor import StreamProcessor
from neuromind.thread_manager import Thread, ThreadManager
from neuromind.ui_manager import UIManager

load_dotenv()


class NeuroApp:
    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config
        self.db = ThreadManager(Config.Path.DATABASE_FILE)
        self.ui = UIManager()
        self.personas = {
            item.value: (Config.Path.PERSONAS_DIR / f"{item.value}.md").read_text()
            for item in list(Persona)
        }

        self.active_thread: Thread = self.db.get_or_create_thread(Config.DEFAULT_THREAD)

        try:
            self.llm = init_chat_model(
                model_config.name,
                model_provider=model_config.provider.value,
                reasoning=True,
                num_ctx=Config.CONTEXT_WINDOW,
            )
        except Exception as e:
            self.ui.console.print(
                f"[bold red]Critical Error:[/bold red] Could not connect to {model_config.provider.value} model {model_config.name}. {e}"
            )
            sys.exit(1)

    def _build_context(self, user_input: str) -> List[BaseMessage]:
        sys_prompt = self.personas.get(
            self.active_thread.persona, Persona.NEUROMIND.value
        )

        messages = [SystemMessage(content=sys_prompt)]
        messages.extend(self.db.get_history(self.active_thread.id))
        messages.append(HumanMessage(content=user_input))

        return messages

    def _cmd_list(self):
        threads = self.db.list_threads()
        self.ui.show_thread_list(threads, self.active_thread.name)

    def _cmd_new(self):
        name = Prompt.ask("[bold]Thread Name[/bold]")

        self.ui.console.print("\n[bold]Select Persona:[/bold]")
        all_personas = list(Persona)
        for idx, persona in enumerate(all_personas, 1):
            self.ui.console.print(f"  [green]{idx}.[/green] {persona.value}")

        choice = Prompt.ask(
            "Choice",
            choices=[str(i) for i in range(1, len(all_personas) + 1)],
            default="1",
        )
        persona = all_personas[int(choice) - 1]

        self.active_thread = self.db.get_or_create_thread(name, persona)
        self.ui.print_info(f"Switched to '{name}' ({persona.value})")

    def _cmd_switch(self, args: List[str]):
        if not args:
            self.ui.print_error("Usage: /switch <thread_name>")
            return

        name = args[0]
        self.active_thread = self.db.get_or_create_thread(name)
        self.ui.print_info(f"Active thread: {name}")

    def _cmd_clear(self):
        if Confirm.ask(f"Wipe memory for '{self.active_thread.name}'?"):
            self.db.clear_messages(self.active_thread.id)
            self.ui.print_info("Memory wiped.")

    def run(self):
        self.ui.show_header(self.model_config.name, self.active_thread.name)

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
                        self._cmd_new()
                    elif cmd == "/switch":
                        self._cmd_switch(args)
                    elif cmd == "/clear":
                        self._cmd_clear()
                    else:
                        self.ui.print_error("Unknown command.")
                    continue

                context = self._build_context(user_input)
                processor = StreamProcessor()

                with self.ui.stream_response(self.active_thread.name) as live:
                    for chunk in self.llm.stream(context):
                        if not chunk.content and not chunk.additional_kwargs.get(
                            "reasoning_content", False
                        ):
                            continue

                        thought, response = processor.process_chunk(chunk)
                        renderable = self.ui.render_stream_group(thought, response)
                        live.update(renderable)

                self.db.add_message(self.active_thread.id, "human", user_input)
                self.db.add_message(self.active_thread.id, "ai", processor.full_content)

            except KeyboardInterrupt:
                self.ui.print_info("\nUse /exit to quit.")
            except Exception as e:
                self.ui.print_error(str(e))


if __name__ == "__main__":
    app = NeuroApp(Config.MODEL)
    app.run()
