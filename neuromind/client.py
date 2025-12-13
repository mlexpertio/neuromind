import json
from dataclasses import dataclass
from enum import Enum
from typing import Generator, List, Tuple

import httpx

from neuromind.config import Persona


class StreamEventType(str, Enum):
    REASONING = "reasoning"
    CONTENT = "content"
    DONE = "done"
    ERROR = "error"


@dataclass
class ThreadInfo:
    id: int
    name: str
    persona: str


@dataclass
class StreamEvent:
    """Represents a streaming event from the chat endpoint."""

    type: StreamEventType
    content: str = ""
    error: str | None = None
    message: str | None = None


class APIError(Exception):
    """Raised when API request fails."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NeuroMindClient:
    """Client for interacting with the NeuroMind REST API."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health_check(self) -> dict:
        """Check if the API server is healthy."""
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise APIError("Could not connect to API server. Is it running?")
        except httpx.TimeoutException:
            raise APIError("Health check timed out.")

    def list_personas(self) -> List[dict]:
        """List all available personas."""
        response = httpx.get(f"{self.base_url}/personas", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def list_threads(self) -> List[Tuple[str, str, int]]:
        """
        List all threads.
        Returns list of (name, persona, message_count) tuples.
        """
        response = httpx.get(f"{self.base_url}/threads", timeout=self.timeout)
        response.raise_for_status()
        threads = response.json()
        return [(t["name"], t["persona"], t["message_count"]) for t in threads]

    def get_or_create_thread(
        self, name: str, persona: Persona = Persona.NEUROMIND
    ) -> ThreadInfo:
        """Get or create a thread by name."""
        # First try to get existing thread
        response = httpx.get(f"{self.base_url}/threads/{name}", timeout=self.timeout)

        if response.status_code == 200:
            data = response.json()
            return ThreadInfo(id=data["id"], name=data["name"], persona=data["persona"])

        # Create new thread if it doesn't exist
        response = httpx.post(
            f"{self.base_url}/threads",
            json={"name": name, "persona": persona.value},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return ThreadInfo(id=data["id"], name=data["name"], persona=data["persona"])

    def clear_messages(self, thread_name: str) -> None:
        """Clear all messages in a thread."""
        response = httpx.delete(
            f"{self.base_url}/threads/{thread_name}/messages", timeout=self.timeout
        )
        response.raise_for_status()

    def stream_chat(
        self, thread_name: str, content: str
    ) -> Generator[StreamEvent, None, None]:
        """
        Send a message and stream the response via SSE.
        Yields StreamEvent objects for each chunk.
        """
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/threads/{thread_name}/chat",
                json={"content": content},
                timeout=self.timeout,
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue

                    try:
                        event_data = json.loads(line[5:].strip())
                        event_type = event_data.get("type", "unknown")

                        if event_type == "reasoning":
                            yield StreamEvent(
                                type=StreamEventType.REASONING,
                                content=event_data["content"],
                            )
                        elif event_type == "content":
                            yield StreamEvent(
                                type=StreamEventType.CONTENT,
                                content=event_data["content"],
                            )
                        elif event_type == "error":
                            yield StreamEvent(
                                type=StreamEventType.ERROR,
                                error=event_data.get("error"),
                                message=event_data.get("message"),
                            )
                        elif event_type == "done":
                            yield StreamEvent(type=StreamEventType.DONE)
                    except json.JSONDecodeError:
                        continue
        except httpx.ConnectError:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                error="connection_failed",
                message="Could not connect to API server.",
            )
        except httpx.TimeoutException:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                error="timeout",
                message="Request timed out.",
            )
