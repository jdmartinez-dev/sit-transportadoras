from comun.config import ConfigBase


class Config(ConfigBase):
    bd_nombre: str = "auth"
    jwt_privada: str = ""
    cliente_despachos_secret: str = ""
    cliente_mock_dhl_secret: str = ""
    usuarios_demo_password: str = ""
    duracion_token_seg: int = 900
    rondas_bcrypt: int = 12
