# src/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from src.core.enums.cost_method import CostMethod

class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    COST_BASIS_METHOD: CostMethod = CostMethod.FIFO
    # You can add other settings here as needed, e.g., DATABASE_URL, LOG_LEVEL

# Instantiate settings to be imported throughout the application
settings = Settings()