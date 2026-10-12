import os

from pydantic_settings import BaseSettings, SettingsConfigDict

DIRECTORIO_SECRETOS = "/run/secrets"


class Config(BaseSettings):
    """El simulador representa a un tercero: no usa el paquete `comun` de la plataforma."""

    model_config = SettingsConfigDict(
        secrets_dir=DIRECTORIO_SECRETOS if os.path.isdir(DIRECTORIO_SECRETOS) else None, extra="ignore")

    usuario_api: str = "tienda"
    dhl_api_password: str = ""
    url_webhook: str = "http://sit:8000/api/v1/webhooks/dhl"
    url_token: str = "http://auth:8000/oauth/token"
    cliente_id: str = "mock-dhl"
    cliente_mock_dhl_secret: str = ""
