"""
Supabase client configuration for FastAPI backend.
Connects to the existing Supabase PostgreSQL database.
"""
import os
from functools import lru_cache

from supabase import create_client, Client
from pydantic_settings import BaseSettings


class SupabaseSettings(BaseSettings):
    """Supabase configuration from environment variables."""
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str | None = None
    
    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_supabase_settings() -> SupabaseSettings:
    """Get cached Supabase settings."""
    return SupabaseSettings()


@lru_cache()
def get_supabase_client() -> Client:
    """Get cached Supabase client instance."""
    settings = get_supabase_settings()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def get_supabase() -> Client:
    """Dependency injection for Supabase client."""
    return get_supabase_client()
