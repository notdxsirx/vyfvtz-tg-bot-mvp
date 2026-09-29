from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    db_dsn: str  # postgresql+asyncpg://user:pass@host:5432/memes
    # list[int] fields are parsed as JSON by pydantic-settings, e.g. ADMIN_IDS=[111,222]
    # (env_nested_delimiter is for nested sub-models, not list parsing — dropped, it did nothing here)
    admin_ids: list[int]
    phash_distance_threshold: int = 5
    media_root: Path = Path("media")  # where we keep our own copy of submitted files

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
settings.media_root.mkdir(parents=True, exist_ok=True)
