"""Tipos que comparten el motor, los mapeadores y los adaptadores."""
from dataclasses import dataclass, field
from typing import Any, Protocol

from comun.canonico import (Cotizacion, EventoEstado, Guia, Recogida, SolicitudCotizacion, SolicitudEnvio,
                            SolicitudRecogida)


@dataclass(frozen=True)
class MensajeOperador:
    """Mensaje ya expresado en el modelo del operador, listo para que un adaptador lo envíe.

    REST: `operacion` es "MÉTODO /ruta" (p. ej. "POST /shipments"). SOAP: el nombre de la operación del WSDL.
    """

    operacion: str
    cuerpo: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EstadoLeido:
    evento: EventoEstado
    codigo_operador: str
    sin_equivalencia: bool


class Mapeador(Protocol):
    codigo: str

    def cotizacion(self, solicitud: SolicitudCotizacion, tablas) -> MensajeOperador: ...
    def leer_cotizacion(self, respuesta: Any, tablas) -> Cotizacion: ...
    def envio(self, solicitud: SolicitudEnvio, tablas) -> MensajeOperador: ...
    def leer_guia(self, respuesta: Any, solicitud: SolicitudEnvio) -> Guia: ...
    def recogida(self, solicitud: SolicitudRecogida) -> MensajeOperador: ...
    def leer_recogida(self, respuesta: Any, solicitud: SolicitudRecogida) -> Recogida: ...
    def consulta_estados(self, numero_guia: str) -> MensajeOperador: ...
    def leer_estados(self, respuesta: Any, tablas) -> list[EstadoLeido]: ...
