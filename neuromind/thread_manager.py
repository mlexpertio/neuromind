from typing import List, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

from neuromind.config import Persona


class Thread(SQLModel, table=True):
    """A conversation thread with a specific persona."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    persona: str


class Message(SQLModel, table=True):
    """A message in a conversation thread."""

    id: int | None = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="thread.id")
    role: str
    content: str


class ThreadManager:
    def __init__(self, db_path: str):
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(self.engine)

    def get_thread(self, name: str) -> Thread | None:
        with Session(self.engine) as session:
            return session.exec(select(Thread).where(Thread.name == name)).first()

    def get_or_create_thread(
        self, name: str, persona: Persona = Persona.NEUROMIND
    ) -> Thread:
        with Session(self.engine) as session:
            thread = session.exec(select(Thread).where(Thread.name == name)).first()
            if thread:
                return thread

            thread = Thread(name=name, persona=persona.value)
            session.add(thread)
            session.commit()
            session.refresh(thread)
            return thread

    def list_threads(self) -> List[Tuple[str, str, int]]:
        """Returns list of (name, persona, message_count) tuples."""
        with Session(self.engine) as session:
            results = session.exec(
                select(Thread.name, Thread.persona, func.count(Message.id))
                .outerjoin(Message, Thread.id == Message.thread_id)
                .group_by(Thread.id)
            ).all()
            return [(name, persona, count) for name, persona, count in results]

    def add_message(self, thread_id: int, role: str, content: str):
        with Session(self.engine) as session:
            message = Message(thread_id=thread_id, role=role, content=content)
            session.add(message)
            session.commit()

    def get_history(self, thread_id: int) -> List[BaseMessage]:
        with Session(self.engine) as session:
            messages = session.exec(
                select(Message)
                .where(Message.thread_id == thread_id)
                .order_by(Message.id)
            ).all()

            return [
                HumanMessage(content=msg.content)
                if msg.role == "human"
                else AIMessage(content=msg.content)
                for msg in messages
            ]

    def clear_messages(self, thread_id: int):
        with Session(self.engine) as session:
            messages = session.exec(
                select(Message).where(Message.thread_id == thread_id)
            ).all()
            for msg in messages:
                session.delete(msg)
            session.commit()
