from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIP_", env_file=".env")

    database_url: str = "postgresql+psycopg://localhost/fip_dev"
    test_database_url: str = "postgresql+psycopg://localhost/fip_test"
    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias=AliasChoices("FIP_ENV", "environment")
    )
    worker_lease_seconds: int = Field(default=60, ge=5)
    worker_poll_seconds: float = Field(default=1.0, gt=0)
    max_page_size: int = Field(default=100, ge=1, le=500)
    rate_limit_per_minute: int = Field(default=120, gt=0)
    require_verified_principal: bool = False
    enable_m2_rebalance: bool = False

    @model_validator(mode="after")
    def production_requires_verified_principal(self) -> "Settings":
        if self.environment == "production":
            self.require_verified_principal = True
        return self


settings = Settings()
