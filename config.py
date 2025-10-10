"""Configuration management for free time finder."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""

    # Directory settings
    ICS_DIR: str = os.getenv("ICS_DIR", "ics_files")

    # Timezone settings
    DEFAULT_TIMEZONE: str = os.getenv("TIMEZONE", "America/New_York")

    # Slot settings
    DEFAULT_SLOT_DURATION_MIN: int = int(os.getenv("SLOT_DURATION_MIN", "60"))
    MIN_SLOT_DURATION_MIN: int = 15
    MAX_SLOT_DURATION_MIN: int = 480  # 8 hours

    # Work hours
    DEFAULT_WORK_START: int = int(os.getenv("WORK_START_HOUR", "9"))
    DEFAULT_WORK_END: int = int(os.getenv("WORK_END_HOUR", "21"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Performance limits
    MAX_CALENDARS: int = int(os.getenv("MAX_CALENDARS", "10"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "30"))


config = Config()
