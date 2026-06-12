from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Frontend URL for notifications
    FRONTEND_URL: str = "http://192.168.0.69:5173"

    # Home Assistant
    HA_BASE_URL: str = ""
    HA_WEBHOOK_ID: str = ""

    # Gemini API (Direct SDK)
    GEMINI_API_KEY: Optional[str] = None

    # New API (OpenAI-compatible) Configuration
    NEW_API_BASE_URL: Optional[str] = None
    NEW_API_KEY: Optional[str] = None
    NEW_API_MODEL: str = "gemini-2.5-flash"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def gemini_api_keys(self) -> List[str]:
        """Returns a list of parsed Gemini API keys."""
        if not self.GEMINI_API_KEY:
            return []
        # Support API key cycling by comma separation
        return [k.strip() for k in self.GEMINI_API_KEY.split(",") if k.strip()]

settings = Settings()

