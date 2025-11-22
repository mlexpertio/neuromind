import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ModelProvider(str, Enum):
    OLLAMA = "ollama"
    GOOGLE_GENAI = "google_genai"


@dataclass
class ModelConfig:
    name: str
    temperature: float
    provider: ModelProvider
    reasoning: bool


QWEN_3 = ModelConfig(
    "qwen3:8b", temperature=0.6, provider=ModelProvider.OLLAMA, reasoning=True
)
GEMINI_2_5_FLASH = ModelConfig(
    "gemini-2.5-flash",
    temperature=0.0,
    provider=ModelProvider.GOOGLE_GENAI,
    reasoning=True,
)


class Persona(str, Enum):
    NEUROMIND = "neuromind"
    CODER = "coder"
    ROASTER = "roaster"
    TEACHER = "teacher"
    LOGICIAN = "logician"


class Config:
    MODEL = QWEN_3
    CONTEXT_WINDOW = 4096
    DEFAULT_THREAD = "master"

    class Path:
        APP_HOME = Path(os.getenv("APP_HOME", Path(__file__).parent.parent))
        DATA_DIR = APP_HOME / "data"
        DATABASE_FILE = DATA_DIR / "neuromind.db"
        PERSONAS_DIR = DATA_DIR / "personas"
