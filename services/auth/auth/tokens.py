"""Emisión de JWT firmados con RS256: la llave privada solo existe en este servicio."""
from datetime import datetime, timedelta, timezone

import jwt

from comun.seguridad import ALGORITMO, EMISOR


class EmisorTokens:
    def __init__(self, llave_privada_pem: str, duracion_seg: int, emisor: str = EMISOR):
        self._llave = llave_privada_pem
        self._duracion = duracion_seg
        self._emisor = emisor

    def emitir(self, sub: str, roles: list[str]) -> str:
        momento = datetime.now(timezone.utc)
        return jwt.encode({"iss": self._emisor, "sub": sub, "roles": roles, "iat": momento,
                           "exp": momento + timedelta(seconds=self._duracion)}, self._llave, algorithm=ALGORITMO)
