from typing import Tuple

from langchain_core.messages import AIMessageChunk


class StreamProcessor:
    def __init__(self):
        self.full_content = ""
        self.thought_buffer = ""
        self.response_buffer = ""
        self._is_thinking = False

    def process_chunk(self, chunk: AIMessageChunk) -> Tuple[str, str]:
        if chunk.content:
            self.full_content += chunk.content

        is_thinking = chunk.additional_kwargs.get("reasoning_content", False)
        if is_thinking:
            self.thought_buffer += chunk.additional_kwargs["reasoning_content"]
        else:
            self.response_buffer += chunk.content

        return self.thought_buffer, self.response_buffer
