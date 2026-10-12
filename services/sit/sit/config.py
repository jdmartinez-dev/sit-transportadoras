from comun.config import ConfigBase


class Config(ConfigBase):
    bd_nombre: str = "sit"
    url_redis: str = "redis://redis:6379/0"
    jwt_publica: str = ""
    usuario_dhl: str = "tienda"
    dhl_api_password: str = ""
    reintentos: int = 3
    timeout_seg: float = 10.0

    def credenciales(self, codigo: str) -> tuple[str, str] | None:
        """Convención: usuario en `usuario_<codigo>` (entorno) y clave en el Docker secret `<codigo>_api_password`."""
        clave = getattr(self, f"{codigo}_api_password", "")
        if not clave:
            return None
        return getattr(self, f"usuario_{codigo}", ""), clave
