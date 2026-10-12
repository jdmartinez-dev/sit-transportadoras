"""Orquestación del despacho (Tabla 2): cotizar → elegir → crear guía → programar recogida → publicar guia.creada.

Los pasos tienen un orden obligatorio y un servicio controlador centraliza la lógica (orquestación). Cada paso guarda
su resultado: un nuevo intento retoma desde el primer paso sin resultado, sin duplicar guías ni recogidas.
"""
import logging
from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from comun.canonico import (Cotizacion, Direccion, Franja, GuiaCreada, PedidoConfirmado, SolicitudCotizacion,
                            SolicitudEnvio, SolicitudRecogida, ahora)
from comun.errores import ErrorPlataforma
from comun.eventos import GUIA_CREADA
from despachos.esquemas import Despacho, a_esquema
from despachos.modelos import DespachoBD, EstadoDespacho

log = logging.getLogger(__name__)


def elegir(cotizaciones: list[Cotizacion], forzada: str | None) -> Cotizacion:
    """La forzada si el pedido la indica; si no, la más barata (empates: menos días y luego código)."""
    if forzada:
        for cotizacion in cotizaciones:
            if cotizacion.transportadora == forzada:
                return cotizacion
        raise ErrorPlataforma(422, "TRANSPORTADORA_SIN_COTIZACION", f"La transportadora {forzada} no cotizó el envío",
                              forzada)
    if not cotizaciones:
        raise ErrorPlataforma(502, "SIN_COTIZACIONES", "No hay cotizaciones para elegir")
    return min(cotizaciones, key=lambda c: (c.valor_cop, c.dias_estimados, c.transportadora))


class Orquestador:
    def __init__(self, Sesiones, sit, bus, origen: Direccion, hoy: Callable[[], date] = lambda: ahora().date()):
        self._Sesiones = Sesiones
        self._sit = sit
        self._bus = bus
        self._origen = origen
        self._hoy = hoy

    def procesar(self, pedido: PedidoConfirmado) -> tuple[Despacho, bool]:
        with self._Sesiones() as sesion:
            despacho, creado = self._obtener_o_crear(sesion, pedido)
            if despacho.estado != EstadoDespacho.RECOGIDA_PROGRAMADA.value:
                try:
                    self._ejecutar_pasos(sesion, despacho)
                    log.info("Despacho %s completo: guía %s de %s", despacho.pedido_id, despacho.numero_guia,
                             despacho.transportadora)
                except ErrorPlataforma as exc:
                    despacho.estado = EstadoDespacho.FALLIDO.value
                    despacho.error = exc.error.model_dump()
                    self._guardar(sesion, despacho)
                    log.warning("Despacho %s FALLIDO: %s", despacho.pedido_id, exc.error.mensaje)
            return a_esquema(despacho), creado

    def _obtener_o_crear(self, sesion: Session, pedido: PedidoConfirmado) -> tuple[DespachoBD, bool]:
        despacho = sesion.get(DespachoBD, pedido.pedido_id)
        if despacho is not None:
            return despacho, False
        momento = ahora()
        despacho = DespachoBD(pedido_id=pedido.pedido_id, estado=EstadoDespacho.PENDIENTE.value,
                              solicitud=pedido.model_dump(mode="json"),
                              transportadora_solicitada=pedido.transportadora, cotizaciones=[],
                              evento_publicado=False, creado_en=momento, actualizado_en=momento)
        sesion.add(despacho)
        try:
            sesion.commit()
            return despacho, True
        except IntegrityError:  # el mismo pedido llegó a la vez por evento y por POST
            sesion.rollback()
            return sesion.get(DespachoBD, pedido.pedido_id), False

    def _ejecutar_pasos(self, sesion: Session, despacho: DespachoBD) -> None:
        pedido = PedidoConfirmado.model_validate(despacho.solicitud)
        despacho.error = None
        if despacho.transportadora is None:
            cotizaciones = self._sit.cotizar(SolicitudCotizacion(
                origen=self._origen.divipola, destino=pedido.destino.divipola, paquetes=pedido.paquetes,
                transportadora=pedido.transportadora))
            elegida = elegir(cotizaciones, pedido.transportadora)
            despacho.cotizaciones = [c.model_dump(mode="json") for c in cotizaciones]
            despacho.transportadora = elegida.transportadora
            self._guardar(sesion, despacho)
        if despacho.numero_guia is None:
            guia = self._sit.crear_envio(SolicitudEnvio(
                pedido_id=despacho.pedido_id, transportadora=despacho.transportadora, origen=self._origen,
                destino=pedido.destino, paquetes=pedido.paquetes))
            despacho.numero_guia = guia.numero_guia
            despacho.estado = EstadoDespacho.GUIA_CREADA.value
            self._guardar(sesion, despacho)
        if despacho.confirmacion_recogida is None:
            recogida = self._sit.programar_recogida(SolicitudRecogida(
                numero_guia=despacho.numero_guia, fecha=self._hoy() + timedelta(days=1), franja=Franja.MANANA))
            despacho.confirmacion_recogida = recogida.confirmacion
            self._guardar(sesion, despacho)
        if not despacho.evento_publicado:
            self._bus.publicar(GUIA_CREADA, GuiaCreada(pedido_id=despacho.pedido_id, numero_guia=despacho.numero_guia,
                                                       transportadora=despacho.transportadora))
            despacho.evento_publicado = True
        despacho.estado = EstadoDespacho.RECOGIDA_PROGRAMADA.value
        self._guardar(sesion, despacho)

    def _guardar(self, sesion: Session, despacho: DespachoBD) -> None:
        despacho.actualizado_en = ahora()
        sesion.commit()
