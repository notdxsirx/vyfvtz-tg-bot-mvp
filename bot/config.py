from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    db_dsn: str  # postgresql+asyncpg://user:pass@host:5432/memes
    admin_ids: list[int]
    phash_distance_threshold: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter=",")


settings = Settings()
