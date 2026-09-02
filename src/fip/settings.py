from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIP_", env_file=".env")

    database_url: str = "postgresql+psycopg://localhost/fip_dev"
    test_database_url: str = "postgresql+psycopg://localhost/fip_test"


settings = Settings()
