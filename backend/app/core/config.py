from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AgentOrder 3D Print Farm API"
    app_env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    host: str = "127.0.0.1"
    port: int = 8000

    sqlserver_host: str = "127.0.0.1"
    sqlserver_port: int = 1433
    sqlserver_database: str = "AgentOrder"
    sqlserver_user: str = "sa"
    sqlserver_password: str = "YourStrongPassword"
    sqlserver_driver: str = "ODBC Driver 18 for SQL Server"
    sqlserver_trust_certificate: bool = True

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    upload_root: Path = Path("./uploads")
    max_upload_size_mb: int = 300
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def database_url(self) -> str:
        driver = quote_plus(self.sqlserver_driver)
        trust = "yes" if self.sqlserver_trust_certificate else "no"
        password = quote_plus(self.sqlserver_password)
        return (
            f"mssql+pyodbc://{self.sqlserver_user}:{password}"
            f"@{self.sqlserver_host}:{self.sqlserver_port}/{self.sqlserver_database}"
            f"?driver={driver}&TrustServerCertificate={trust}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
