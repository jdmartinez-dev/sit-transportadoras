"""Modelo canónico de la plataforma (patrón Canonical Schema).

Es el modelo destino del patrón Data Model Transformation: los servicios internos
solo conocen estas clases y solo los mapeadores del SIT conocen el modelo propio
de cada transportadora.
"""
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field

ZONA_COLOMBIA = timezone(timedelta(hours=-5), "COT")
"""Colombia no tiene horario de verano: UTC-5 todo el año."""


def ahora() -> datetime:
    return datetime.now(ZONA_COLOMBIA)


Divipola = Annotated[str, Field(pattern=r"^\d{5}$", description="Código DIVIPOLA del municipio (DANE), 5 dígitos")]


class EstadoEnvio(str, Enum):
    """Catálogo canónico de estados (nota de la Tabla 2)."""

    CREADA = "CREADA"
    RECOGIDA = "RECOGIDA"
    EN_TRANSITO = "EN_TRANSITO"
    EN_REPARTO = "EN_REPARTO"
    ENTREGADA = "ENTREGADA"
    NOVEDAD = "NOVEDAD"
    DEVUELTA = "DEVUELTA"


ESTADOS_FINALES = frozenset({EstadoEnvio.ENTREGADA, EstadoEnvio.DEVUELTA})


class Direccion(BaseModel):
    """Datos del destinatario limitados a lo necesario para la entrega (Ley 1581 de 2012)."""

    divipola: Divipola
    direccion: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    telefono: str = Field(min_length=7)


class Paquete(BaseModel):
    peso_kg: float = Field(gt=0)
    largo_cm: float = Field(gt=0)
    ancho_cm: float = Field(gt=0)
    alto_cm: float = Field(gt=0)


class SolicitudCotizacion(BaseModel):
    origen: Divipola
    destino: Divipola
    paquetes: list[Paquete] = Field(min_length=1)
    transportadora: str | None = None


class Cotizacion(BaseModel):
    transportadora: str
    valor_cop: int
    peso_facturable_kg: float
    dias_estimados: int


class SolicitudEnvio(BaseModel):
    pedido_id: str = Field(min_length=1)
    transportadora: str
    origen: Direccion
    destino: Direccion
    paquetes: list[Paquete] = Field(min_length=1)


class Guia(BaseModel):
    numero_guia: str
    transportadora: str
    pedido_id: str
    estado: EstadoEnvio
    creada_en: AwareDatetime


class Franja(str, Enum):
    MANANA = "MANANA"
    TARDE = "TARDE"


class SolicitudRecogida(BaseModel):
    numero_guia: str
    fecha: date
    franja: Franja


class Recogida(BaseModel):
    numero_guia: str
    transportadora: str
    confirmacion: str
    fecha: date
    franja: Franja


class EventoEstado(BaseModel):
    estado: EstadoEnvio
    ocurrido_en: AwareDatetime


class Transportadora(BaseModel):
    codigo: str
    nombre: str
    protocolo: str
    version_api: str
    adaptador: str
    frecuencia_sincronizacion_seg: int | None
    version_equivalencias: str
    activa: bool


class ErrorCanonico(BaseModel):
    codigo: str
    mensaje: str
    transportadora: str | None = None


# --- Datos de los eventos (spec §6) ---

class PedidoConfirmado(BaseModel):
    pedido_id: str = Field(min_length=1)
    destino: Direccion
    paquetes: list[Paquete] = Field(min_length=1)
    transportadora: str | None = None


class GuiaCreada(BaseModel):
    pedido_id: str
    numero_guia: str
    transportadora: str


class EnvioEstadoActualizado(BaseModel):
    """Nunca lleva el código del operador: Despachos y Rastreo no conocen el formato de las transportadoras."""

    numero_guia: str
    transportadora: str
    estado: EstadoEnvio
    ocurrido_en: AwareDatetime
