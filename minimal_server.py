import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain.chat_models import init_chat_model
from pydantic import BaseModel

from neuromind.config import Config

app = FastAPI()
model = Config.MODEL
llm = init_chat_model(model.name, model_provider=model.provider.value)
conversations = {}


class Message(BaseModel):
    content: str


@app.post("/chat/{session_id}")
def chat(session_id: str, msg: Message):
    if session_id not in conversations:
        conversations[session_id] = []

    conversations[session_id].append({"role": "user", "content": msg.content})

    def stream():
        full_response = ""
        for chunk in llm.stream(conversations[session_id]):
            if chunk.content:
                full_response += chunk.content
                yield f"data: {json.dumps({'content': chunk.content})}\n\n"
        conversations[session_id].append(
            {"role": "assistant", "content": full_response}
        )
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/health")
def health():
    return {"status": "ok"}
