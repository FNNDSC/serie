from aiochris.types import ChrisURL
from pydantic_settings import BaseSettings
import functools


class Settings(BaseSettings):
    """SERIE settings"""

    chris_url: ChrisURL


@functools.cache
def get_settings() -> Settings:
    """Get settings"""
    return Settings()
