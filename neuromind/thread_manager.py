import sqlite3
from dataclasses import dataclass
from typing import List, Tuple

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)

from neuromind.config import Persona


@dataclass
class Thread:
    id: int
    name: str
    persona: str


class ThreadManager:
    def __init__(self, db_path: str):
        # check_same_thread=False allows connection use across async thread boundaries
        # Safe here since FastAPI creates one ThreadManager per request via Depends()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    persona TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(thread_id) REFERENCES threads(id)
                )
            """)

    def get_thread(self, name: str) -> Thread | None:
        row = self.conn.execute(
            "SELECT * FROM threads WHERE name = ?", (name,)
        ).fetchone()

        if row:
            return Thread(id=row["id"], name=row["name"], persona=row["persona"])
        return None

    def get_or_create_thread(
        self, name: str, persona: Persona = Persona.NEUROMIND
    ) -> Thread:
        thread = self.get_thread(name)
        if thread:
            return thread

        cursor = self.conn.execute(
            "INSERT INTO threads (name, persona) VALUES (?, ?)", (name, persona.value)
        )
        self.conn.commit()
        return Thread(id=cursor.lastrowid, name=name, persona=persona.value)

    def list_threads(self) -> List[Tuple[str, str, int]]:
        """Returns (name, persona, message_count)."""
        query = """
            SELECT t.name, t.persona, COUNT(m.id) as count
            FROM threads t 
            LEFT JOIN messages m ON t.id = m.thread_id 
            GROUP BY t.id
        """
        return [(r["name"], r["persona"], r["count"]) for r in self.conn.execute(query)]

    def add_message(self, thread_id: int, role: str, content: str):
        with self.conn:
            self.conn.execute(
                "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
                (thread_id, role, content),
            )

    def get_history(self, thread_id: int) -> List[BaseMessage]:
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE thread_id = ? ORDER BY id ASC",
            (thread_id,),
        ).fetchall()

        history = []
        for r in rows:
            if r["role"] == "human":
                history.append(HumanMessage(content=r["content"]))
            elif r["role"] == "ai":
                history.append(AIMessage(content=r["content"]))
        return history

    def clear_messages(self, thread_id: int):
        with self.conn:
            self.conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
