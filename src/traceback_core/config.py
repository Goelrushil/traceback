"""TRACEBACK V0.1 configuration."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("TRACEBACK_ENV", "development")
    log_level: str = os.getenv("TRACEBACK_LOG_LEVEL", "INFO")
    version: str = "0.1.0"


settings = Settings()
