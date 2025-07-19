# config/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class AppSettings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # General App Settings
    APP_NAME: str = "Transaction Cost Engine API"
    APP_VERSION: str = "0.1.0"
    DEBUG_MODE: bool = False # Set to True for development, False for production

    # API Specific Settings
    API_V1_STR: str = "/api/v1"

    # Logging Settings
    LOG_LEVEL: str = "INFO" # e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Pydantic-settings configuration
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding='utf-8',
        case_sensitive=False, # Allows env vars like APP_NAME or app_name
        extra='ignore' # Ignore extra environment variables not defined in the model
    )

settings = AppSettings()