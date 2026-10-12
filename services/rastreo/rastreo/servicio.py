"""Historial canónico de cada envío, alimentado por el evento envio.estado.actualizado."""
import logging
from collections.abc import Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from comun.canonico import EnvioEstadoActualizado, EstadoEnvio, EventoEstado, ahora
from comun.errores import ErrorPlataforma
from comun.eventos import Evento
from rastreo.modelos import EstadoRegistradoBD

log = logging.getLogger(__name__)


class Rastreo(BaseModel):
    numero_guia: str
    transportadora: str
    estado_actual: EstadoEnvio
    historial: list[EventoEstado]


class ServicioRastreo:
    def __init__(self, Sesiones):
        self._Sesiones = Sesiones

    def registrar(self, evento: Evento) -> bool:
        datos = EnvioEstadoActualizado.model_validate(evento.datos)
        with self._Sesiones() as sesion:
            sesion.add(EstadoRegistradoBD(id_evento=str(evento.id_evento), numero_guia=datos.numero_guia,
                                          transportadora=datos.transportadora, estado=datos.estado.value,
                                          ocurrido_en=datos.ocurrido_en, recibido_en=ahora()))
            try:
                sesion.commit()
            except IntegrityError:
                sesion.rollback()
                log.info("Evento repetido ignorado: %s", evento.id_evento)
                return False
        log.info("Guía %s: %s", datos.numero_guia, datos.estado.value)
        return True

    def consultar(self, numero_guia: str) -> Rastreo:
        with self._Sesiones() as sesion:
            filas = list(sesion.scalars(select(EstadoRegistradoBD)
                                        .where(EstadoRegistradoBD.numero_guia == numero_guia)
                                        .order_by(EstadoRegistradoBD.ocurrido_en, EstadoRegistradoBD.id)))
        if not filas:
            raise ErrorPlataforma(404, "GUIA_NO_ENCONTRADA", f"No hay estados registrados para la guía {numero_guia}")
        return Rastreo(numero_guia=numero_guia, transportadora=filas[-1].transportadora,
                       estado_actual=EstadoEnvio(filas[-1].estado),
                       historial=[EventoEstado(estado=EstadoEnvio(f.estado), ocurrido_en=f.ocurrido_en)
                                  for f in filas])


def crear_manejador(servicio: ServicioRastreo) -> Callable[[Evento], None]:
    def manejar(evento: Evento) -> None:
        try:
            servicio.registrar(evento)
        except ValidationError:
            log.error("Evento envio.estado.actualizado inválido (%s); se descarta", evento.id_evento)

    return manejar
