import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from neuromind.config import Config, Persona
from neuromind.thread_manager import Thread, ThreadManager

logger = logging.getLogger(__name__)

load_dotenv()


class ThreadCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    persona: Persona = Persona.NEUROMIND


class ThreadListItem(BaseModel):
    name: str
    persona: str
    message_count: int


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    role: str
    content: str


class PersonaResponse(BaseModel):
    name: str
    description: str


def get_db() -> ThreadManager:
    return ThreadManager(Config.Path.DATABASE_FILE)


def get_llm():
    model = Config.MODEL
    return init_chat_model(
        model.name,
        model_provider=model.provider.value,
        reasoning=True,
        num_ctx=Config.CONTEXT_WINDOW,
    )


def get_personas() -> dict[str, str]:
    return {
        p.value: (Config.Path.PERSONAS_DIR / f"{p.value}.md").read_text()
        for p in Persona
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.personas = get_personas()
    yield


app = FastAPI(
    title="NeuroMind API",
    description="AI Assistant REST API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/personas", response_model=list[PersonaResponse])
def list_personas():
    """List all available personas."""
    return [
        PersonaResponse(name=p.value, description=f"{p.value.title()} persona")
        for p in Persona
    ]


@app.get("/threads", response_model=list[ThreadListItem])
def list_threads(db: ThreadManager = Depends(get_db)):
    """List all conversation threads."""
    threads = db.list_threads()
    return [
        ThreadListItem(name=name, persona=persona, message_count=count)
        for name, persona, count in threads
    ]


@app.post("/threads", response_model=Thread, status_code=201)
def create_thread(data: ThreadCreate, db: ThreadManager = Depends(get_db)):
    """Create a new conversation thread."""
    return db.get_or_create_thread(data.name, data.persona)


@app.get("/threads/{thread_name}", response_model=Thread)
def get_thread_endpoint(thread_name: str, db: ThreadManager = Depends(get_db)):
    """Get a thread by name."""
    thread = db.get_thread(thread_name)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@app.get("/threads/{thread_name}/messages", response_model=list[MessageResponse])
def get_messages(thread_name: str, db: ThreadManager = Depends(get_db)):
    """Get message history for a thread."""
    thread = db.get_thread(thread_name)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    history = db.get_history(thread.id)
    return [MessageResponse(role=msg.type, content=msg.content) for msg in history]


@app.delete("/threads/{thread_name}/messages", status_code=204)
def clear_messages(thread_name: str, db: ThreadManager = Depends(get_db)):
    """Clear all messages in a thread."""
    thread = db.get_thread(thread_name)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    db.clear_messages(thread.id)


def _build_context(thread: Thread, user_input: str, personas: dict, db: ThreadManager):
    sys_prompt = personas.get(thread.persona, personas[Persona.NEUROMIND.value])
    messages = [SystemMessage(content=sys_prompt)]
    messages.extend(db.get_history(thread.id))
    messages.append(HumanMessage(content=user_input))
    return messages


@app.post("/threads/{thread_name}/chat")
async def chat(
    thread_name: str,
    data: MessageCreate,
    db: ThreadManager = Depends(get_db),
    llm=Depends(get_llm),
):
    """Send a message and stream the AI response via Server-Sent Events."""
    thread = db.get_or_create_thread(thread_name)
    context = _build_context(thread, data.content, app.state.personas, db)

    async def generate() -> AsyncGenerator[str, None]:
        full_content = ""

        try:
            async for chunk in llm.astream(context):
                if not chunk.content and not chunk.additional_kwargs.get(
                    "reasoning_content"
                ):
                    continue

                if chunk.content:
                    full_content += chunk.content

                if chunk.additional_kwargs.get("reasoning_content"):
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': chunk.additional_kwargs['reasoning_content']})}\n\n"
                elif chunk.content:
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk.content})}\n\n"

            db.add_message(thread.id, "human", data.content)
            db.add_message(thread.id, "ai", full_content)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except ConnectionError as e:
            logger.error(f"LLM connection failed during stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': 'connection_failed', 'message': f'AI model unavailable. Please ensure {Config.MODEL.name} is running.'})}\n\n"
        except TimeoutError as e:
            logger.error(f"LLM request timed out during stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': 'timeout', 'message': 'AI model request timed out. Please try again.'})}\n\n"
        except Exception as e:
            logger.exception(f"Unexpected error during stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': 'internal_error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "model": Config.MODEL.name}
