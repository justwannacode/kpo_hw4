from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    orders_service_url: str = "http://orders:8000"
    payments_service_url: str = "http://payments:8000"


settings = Settings()
