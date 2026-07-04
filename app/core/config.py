"""
Application settings loaded from environment variables.
Uses pydantic-settings so every value is typed and validated at startup.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # TMDB
    movies_api_key: str = "d071e08228154bfc3226692bdbd5318e"
    tmdb_base_url: str = "https://api.themoviedb.org/3"

    # Spotify
    spotify_client_id: str = "49f4ca2258414e498596139510cce326"
    spotify_client_secret: str = "3ffe2874c6484a7aa6180d3b2e818d07"

    # App
    app_title: str = "RecoHub API"
    app_version: str = "2.0.0"
    cache_ttl_seconds: int = 3600
    request_timeout: int = 10
    max_movies: int = 8
    max_music: int = 6
    max_books: int = 6

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
