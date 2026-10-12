import socket

from pydantic import Field

from comun.config import ConfigBase


class Config(ConfigBase):
    bd_nombre: str = "rastreo"
    url_redis: str = "redis://redis:6379/0"
    jwt_publica: str = ""
    nombre_consumidor: str = Field(default_factory=socket.gethostname)
