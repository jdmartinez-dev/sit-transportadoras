import socket

from pydantic import Field

from comun.canonico import Direccion
from comun.config import ConfigBase


class Config(ConfigBase):
    bd_nombre: str = "despachos"
    url_redis: str = "redis://redis:6379/0"
    jwt_publica: str = ""
    url_sit: str = "http://sit:8000"
    url_token: str = "http://auth:8000/oauth/token"
    cliente_id: str = "despachos"
    cliente_despachos_secret: str = ""
    timeout_sit_seg: float = 60.0
    origen_divipola: str = "11001"
    origen_direccion: str = "Calle 13 # 68-50, Bodega principal"
    origen_nombre: str = "Tienda en línea - Bodega Bogotá"
    origen_telefono: str = "6015550100"
    nombre_consumidor: str = Field(default_factory=socket.gethostname)

    def origen(self) -> Direccion:
        return Direccion(divipola=self.origen_divipola, direccion=self.origen_direccion, nombre=self.origen_nombre,
                         telefono=self.origen_telefono)
