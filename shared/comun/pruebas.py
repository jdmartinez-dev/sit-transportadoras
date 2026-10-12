"""Utilidades para las pruebas automáticas de los servicios (no se usan en ejecución)."""
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel

from comun.eventos import Evento
from comun.seguridad import ALGORITMO, EMISOR


def generar_llaves() -> tuple[str, str]:
    """Devuelve (privada_pem, publica_pem) RSA de 2048 bits."""
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    privada = llave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode()
    publica = llave.public_key().public_bytes(serialization.Encoding.PEM,
                                              serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return privada, publica


def token_de_prueba(privada_pem: str, sub: str, roles: list[str], vence_en_seg: int = 300,
                    emisor: str = EMISOR) -> str:
    momento = datetime.now(timezone.utc)
    return jwt.encode({"iss": emisor, "sub": sub, "roles": roles, "iat": momento,
                       "exp": momento + timedelta(seconds=vence_en_seg)}, privada_pem, algorithm=ALGORITMO)


class BusFalso:
    """Doble del Bus: guarda en memoria los eventos publicados; con `falla` simula Redis caído."""

    def __init__(self, falla: Exception | None = None):
        self.publicados: list[tuple[str, BaseModel]] = []
        self.falla = falla

    def publicar(self, tipo: str, datos: BaseModel) -> Evento:
        if self.falla is not None:
            raise self.falla
        self.publicados.append((tipo, datos))
        return Evento(tipo=tipo, datos=datos.model_dump(mode="json"))

    def tipos(self) -> list[str]:
        return [tipo for tipo, _ in self.publicados]
