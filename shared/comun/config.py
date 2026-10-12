"""Configuración común: variables de entorno y Docker secrets (/run/secrets)."""
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

DIRECTORIO_SECRETOS = "/run/secrets"


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        secrets_dir=DIRECTORIO_SECRETOS if os.path.isdir(DIRECTORIO_SECRETOS) else None,
        extra="ignore",
    )

    bd_host: str = "postgres"
    bd_usuario: str = "plataforma"
    bd_nombre: str = ""
    postgres_password: str = ""
    url_bd: str | None = None
    """Si se define (por ejemplo sqlite:// en las pruebas), reemplaza la conexión a PostgreSQL."""

    def url_bd_efectiva(self) -> str:
        if self.url_bd:
            return self.url_bd
        return (f"postgresql+psycopg://{self.bd_usuario}:{self.postgres_password}"
                f"@{self.bd_host}:5432/{self.bd_nombre}")
