from pydantic_settings import BaseSettings
from pydantic import HttpUrl
import functools


class Settings(BaseSettings):
    """SERIE settings"""

    chris_host: HttpUrl

    def get_host(self) -> str:
        # remove the trailing flash which is added by pydantic.HttpUrl
        return str(self.chris_host)[:-1]


@functools.cache
def get_settings() -> Settings:
    """Get settings"""
    return Settings()
