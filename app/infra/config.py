"""Environment-only provider configuration, validated before any network request."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WORKFLOW_", env_file=".env", extra="ignore")

    provider: Literal["mock", "openai"] = "mock"
    model: str = "mock-fixture-v1"
    base_url: str = ""
    api_key: SecretStr = SecretStr("")
    response_mode: Literal["json_schema", "json_object", "text"] = "json_schema"
    timeout_seconds: float = Field(default=30, ge=0.01, le=300)
    max_repairs: int = Field(default=1, ge=0, le=2)
    max_bytes: int = Field(default=2_097_152, ge=100, le=10_485_760)
    max_chars: int = Field(default=200_000, ge=100, le=1_000_000)
    max_pages: int = Field(default=50, ge=1, le=200)
    chunk_tokens: int = Field(default=1200, ge=256, le=16_000)
    max_calls: int = Field(default=512, ge=4, le=4096)
    context_tokens: int = Field(default=8192, ge=4096, le=1_000_000)
    cache_enabled: bool = False
    cache_dir: Path = Path(".cache/workflow")
    price_file: Path = Path("config/prices.json")

    @model_validator(mode="after")
    def validate_provider(self) -> "Settings":
        if self.provider == "openai":
            url = urlsplit(self.base_url)
            if (
                url.scheme not in {"https", "http"}
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("Set a valid base URL without credentials, query, or fragment")
            if not self.model.strip() or self.model == "mock-fixture-v1":
                raise ValueError("Set WORKFLOW_MODEL to your provider's model name")
        return self
