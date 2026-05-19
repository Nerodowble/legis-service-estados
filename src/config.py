"""Configurações via variáveis de ambiente (pydantic-settings)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Aplicação
    APP_NAME: str = "legis-service-estados"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "info"

    # HTTP
    USER_AGENT: str = "LegalBot/1.0 (+contato@legalbot.com.br)"
    HTTP_TIMEOUT_SECONDS: int = 15

    # Rate limit (multiplicador global)
    RATE_LIMIT_FATOR: float = 1.0

    # Circuit breaker
    CB_FAIL_THRESHOLD: int = 5
    CB_RESET_TIMEOUT_SECONDS: int = 60

    # Observabilidade
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "legis-service-estados"


settings = Settings()
