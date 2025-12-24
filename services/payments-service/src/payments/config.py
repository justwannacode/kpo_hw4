from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    rabbitmq_url: str

    exchange_events: str = "gozon.events"

    outbox_poll_interval_sec: float = 1.0
    consumer_prefetch: int = 10


settings = Settings()
