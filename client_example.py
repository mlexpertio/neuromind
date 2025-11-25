import json

import requests

BASE_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}\n")


def health_check():
    """Check if the API is running."""
    print_section("Health Check")

    response = requests.get(f"{BASE_URL}/health")
    data = response.json()

    print(f"Status: {data['status']}")
    print(f"Model: {data['model']}")


def list_personas():
    """List all available personas."""
    print_section("Available Personas")

    response = requests.get(f"{BASE_URL}/personas")
    personas = response.json()

    for persona in personas:
        print(f"  • {persona['name']}: {persona['description']}")


def create_thread(name: str, persona: str = "neuromind"):
    """Create a new conversation thread."""
    print_section(f"Creating Thread: {name}")

    response = requests.post(
        f"{BASE_URL}/threads",
        json={"name": name, "persona": persona},
    )
    thread = response.json()

    print("Created thread:")
    print(f"  ID: {thread['id']}")
    print(f"  Name: {thread['name']}")
    print(f"  Persona: {thread['persona']}")

    return thread


def list_threads():
    """List all conversation threads."""
    print_section("All Threads")

    response = requests.get(f"{BASE_URL}/threads")
    threads = response.json()

    if not threads:
        print("  No threads found.")
        return

    for thread in threads:
        print(
            f"  • {thread['name']} ({thread['persona']}) - {thread['message_count']} messages"
        )


def get_thread(name: str):
    """Get a specific thread by name."""
    print_section(f"Thread Details: {name}")

    response = requests.get(f"{BASE_URL}/threads/{name}")
    thread = response.json()

    print(f"  ID: {thread['id']}")
    print(f"  Name: {thread['name']}")
    print(f"  Persona: {thread['persona']}")


def send_message(thread_name: str, content: str):
    """Send a message and get a complete response."""
    print_section(f"Chat in '{thread_name}'")

    print(f"User: {content}")
    print("\nWaiting for response...")

    response = requests.post(
        f"{BASE_URL}/threads/{thread_name}/chat",
        json={"content": content},
    )
    data = response.json()

    if data.get("reasoning"):
        print(f"\n[Reasoning]\n{data['reasoning'][:200]}...")

    print(f"\nAssistant: {data['response']}")


def send_message_streaming(thread_name: str, content: str):
    """Send a message and stream the response via SSE."""
    print_section(f"Streaming Chat in '{thread_name}'")

    print(f"User: {content}")
    print("\nAssistant: ", end="", flush=True)

    response = requests.post(
        f"{BASE_URL}/threads/{thread_name}/chat/stream",
        json={"content": content},
        stream=True,
    )

    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue

        # Parse SSE data (simple parsing for demo)
        json_str = line[5:].strip().replace("'", '"')
        try:
            event = json.loads(json_str)

            if event["type"] == "content":
                print(event["content"], end="", flush=True)
            elif event["type"] == "done":
                print("\n\n[Stream complete]")
        except json.JSONDecodeError:
            continue


def get_message_history(thread_name: str):
    """Get the message history for a thread."""
    print_section(f"Message History: {thread_name}")

    response = requests.get(f"{BASE_URL}/threads/{thread_name}/messages")
    messages = response.json()

    if not messages:
        print("  No messages yet.")
        return

    for msg in messages:
        role = "User" if msg["role"] == "human" else "Assistant"
        content = (
            msg["content"][:100] + "..."
            if len(msg["content"]) > 100
            else msg["content"]
        )
        print(f"  [{role}]: {content}")


def clear_messages(thread_name: str):
    """Clear all messages in a thread."""
    print_section(f"Clearing Messages: {thread_name}")

    response = requests.delete(f"{BASE_URL}/threads/{thread_name}/messages")

    if response.status_code == 204:
        print("  Messages cleared successfully.")
    else:
        print(f"  Error: {response.status_code}")


def main():
    """Run a complete demo of the API."""
    print("\n" + "=" * 50)
    print("  NEUROMIND API CLIENT DEMO")
    print("=" * 50)

    # 1. Check API health
    health_check()

    # 2. List available personas
    list_personas()

    # 3. Create a new thread with coder persona
    thread = create_thread("api-demo", "coder")

    # 4. List all threads
    list_threads()

    # 5. Get thread details
    get_thread(thread["name"])

    # 6. Send a regular chat message
    send_message(thread["name"], "What is a Python decorator in one sentence?")

    # 7. Get message history
    get_message_history(thread["name"])

    # 8. Send a streaming message
    send_message_streaming(thread["name"], "Give me a simple example of a decorator.")

    # 9. Show updated history
    get_message_history(thread["name"])

    # 10. Clear messages (optional - uncomment to test)
    # clear_messages("api-demo")
    # get_message_history("api-demo")

    print_section("Demo Complete!")
    print("Explore the API docs at: http://localhost:8000/docs")


if __name__ == "__main__":
    main()
