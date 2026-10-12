"""Carga idempotente de los usuarios de demo y de los clientes de servicio (secretos desde Docker secrets)."""
import logging

import bcrypt
from sqlalchemy.orm import Session

from auth.config import Config
from auth.modelos import Identidad
from comun.seguridad import Rol

log = logging.getLogger(__name__)

USUARIOS_DEMO = {
    "cliente1": [Rol.CLIENTE],
    "agente1": [Rol.AGENTE_SERVICIO],
    "operador1": [Rol.OPERADOR_LOGISTICO],
    "admin1": [Rol.ADMIN_INTEGRACIONES],
}


def cargar_identidades(sesion: Session, config: Config) -> None:
    for nombre, roles in USUARIOS_DEMO.items():
        _guardar(sesion, nombre, "usuario", config.usuarios_demo_password, roles, config.rondas_bcrypt)
    _guardar(sesion, "despachos", "cliente", config.cliente_despachos_secret, [Rol.OPERADOR_LOGISTICO],
             config.rondas_bcrypt)
    _guardar(sesion, "mock-dhl", "cliente", config.cliente_mock_dhl_secret, [Rol.OPERADOR_LOGISTICO],
             config.rondas_bcrypt)
    sesion.commit()


def _guardar(sesion: Session, nombre: str, tipo: str, secreto: str, roles: list[Rol], rondas: int) -> None:
    if not secreto:
        log.warning("No hay secreto para %s; la identidad no se crea", nombre)
        return
    identidad = sesion.get(Identidad, nombre) or Identidad(nombre=nombre)
    identidad.tipo = tipo
    identidad.roles = ",".join(rol.value for rol in roles)
    identidad.hash_secreto = bcrypt.hashpw(secreto.encode(), bcrypt.gensalt(rounds=rondas)).decode()
    sesion.add(identidad)


def verificar_secreto(secreto: str, hash_secreto: str) -> bool:
    return bcrypt.checkpw(secreto.encode(), hash_secreto.encode())
