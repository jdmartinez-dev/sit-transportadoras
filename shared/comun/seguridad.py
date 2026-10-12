"""Validación de los JWT emitidos por el servicio de autenticación (OAuth 2.0) y control de acceso por roles."""
from enum import Enum

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from comun.errores import ErrorPlataforma

EMISOR = "auth-plataforma"
ALGORITMO = "RS256"


class Rol(str, Enum):
    """Roles de la sección Seguridad del documento."""

    CLIENTE = "cliente"
    AGENTE_SERVICIO = "agente_servicio"
    OPERADOR_LOGISTICO = "operador_logistico"
    ADMIN_INTEGRACIONES = "admin_integraciones"


class Principal(BaseModel):
    sub: str
    roles: list[str]


_bearer = HTTPBearer(auto_error=False)


class ValidadorJWT:
    """Cada servicio valida la firma con la llave pública; la privada solo la tiene el servicio de autenticación."""

    def __init__(self, llave_publica_pem: str, emisor: str = EMISOR):
        self._llave = llave_publica_pem
        self._emisor = emisor

    def validar(self, token: str) -> Principal:
        try:
            datos = jwt.decode(token, self._llave, algorithms=[ALGORITMO], issuer=self._emisor,
                               options={"require": ["exp", "iss", "sub"]})
        except jwt.ExpiredSignatureError as exc:
            raise ErrorPlataforma(401, "TOKEN_VENCIDO", "El token venció; solicite uno nuevo") from exc
        except jwt.PyJWTError as exc:
            raise ErrorPlataforma(401, "TOKEN_INVALIDO", f"Token inválido: {exc}") from exc
        return Principal(sub=datos["sub"], roles=list(datos.get("roles", [])))

    def requiere_roles(self, *roles: Rol):
        permitidos = {rol.value for rol in roles}

        def dependencia(credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
            if credenciales is None:
                raise ErrorPlataforma(401, "TOKEN_AUSENTE", "Falta el encabezado Authorization: Bearer <token>")
            principal = self.validar(credenciales.credentials)
            if permitidos.isdisjoint(principal.roles):
                raise ErrorPlataforma(403, "ACCESO_DENEGADO",
                                      f"Se requiere uno de estos roles: {', '.join(sorted(permitidos))}")
            return principal

        return dependencia
