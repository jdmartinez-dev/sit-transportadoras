"""Casos de uso del SIT, expresados en el modelo canónico: los usan la API canónica y el sincronizador."""
import logging
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from comun.canonico import (ESTADOS_FINALES, Cotizacion, EnvioEstadoActualizado, EventoEstado, Guia, Recogida,
                            SolicitudCotizacion, SolicitudEnvio, SolicitudRecogida, ahora)
from comun.errores import ErrorPlataforma
from comun.eventos import ENVIO_ESTADO_ACTUALIZADO
from sit.catalogo.modelos import EstadoSinEquivalencia, GuiaBD
from sit.motor.motor import Integracion, Motor
from sit.motor.tipos import EstadoLeido

log = logging.getLogger(__name__)
T = TypeVar("T")


class ServicioSIT:
    def __init__(self, Sesiones, motor: Motor, bus):
        self._Sesiones = Sesiones
        self._motor = motor
        self._bus = bus

    # --- API canónica ---

    def cotizar(self, solicitud: SolicitudCotizacion) -> list[Cotizacion]:
        if solicitud.transportadora:
            return [self._cotizar_con(solicitud.transportadora, solicitud)]
        cotizaciones = []
        for codigo in self._motor.activas():
            try:
                cotizaciones.append(self._cotizar_con(codigo, solicitud))
            except ErrorPlataforma as exc:
                log.warning("Sin cotización de %s: %s", codigo, exc.error.mensaje)
        if not cotizaciones:
            raise ErrorPlataforma(502, "SIN_COTIZACIONES", "Ninguna transportadora pudo cotizar el envío")
        return cotizaciones

    def _cotizar_con(self, codigo: str, solicitud: SolicitudCotizacion) -> Cotizacion:
        i = self._motor.integracion(codigo)
        respuesta = i.adaptador.enviar(i.mapeador.cotizacion(solicitud, i.tablas))
        return self._leer(i, lambda: i.mapeador.leer_cotizacion(respuesta, i.tablas))

    def crear_guia(self, solicitud: SolicitudEnvio) -> Guia:
        i = self._motor.integracion(solicitud.transportadora)
        respuesta = i.adaptador.enviar(i.mapeador.envio(solicitud, i.tablas))
        guia = self._leer(i, lambda: i.mapeador.leer_guia(respuesta, solicitud))
        self._registrar_guia(guia.numero_guia, guia.transportadora, guia.pedido_id)
        return guia

    def programar_recogida(self, solicitud: SolicitudRecogida) -> Recogida:
        i = self._motor.integracion(self._transportadora_de(solicitud.numero_guia))
        respuesta = i.adaptador.enviar(i.mapeador.recogida(solicitud))
        return self._leer(i, lambda: i.mapeador.leer_recogida(respuesta, solicitud))

    def consultar_estados(self, numero_guia: str) -> list[EventoEstado]:
        i = self._motor.integracion(self._transportadora_de(numero_guia))
        leidos = self._consultar(i, numero_guia)
        for leido in leidos:
            if leido.sin_equivalencia:
                self._registrar_sin_equivalencia(i.transportadora, leido.codigo_operador, numero_guia)
        return [leido.evento for leido in leidos]

    # --- Sincronizador de estados ---

    def procesar_webhook(self, codigo: str, cuerpo: dict) -> None:
        i = self._motor.integracion(codigo)
        if not hasattr(i.mapeador, "leer_webhook"):
            raise ErrorPlataforma(422, "TRANSPORTADORA_DESCONOCIDA",
                                  f"La transportadora {codigo} no notifica por webhook", codigo)
        numero_guia, leido = i.mapeador.leer_webhook(cuerpo, i.tablas)
        self.procesar_estado(codigo, numero_guia, leido)

    def sincronizar(self, codigo: str) -> None:
        """Consulta programada: procesa, en orden, los eventos del historial de cada guía activa que aún no había
        leído. Así no se pierde ningún estado aunque cambie varias veces entre dos consultas."""
        i = self._motor.integracion(codigo)
        for numero_guia, ya_leidos in self._guias_activas(codigo):
            try:
                leidos = self._consultar(i, numero_guia)
                for indice in range(ya_leidos, len(leidos)):
                    self.procesar_estado(codigo, numero_guia, leidos[indice], eventos_leidos=indice + 1)
            except ErrorPlataforma as exc:
                log.warning("No se pudo sincronizar la guía %s de %s: %s", numero_guia, codigo, exc.error.mensaje)

    def procesar_estado(self, codigo: str, numero_guia: str, leido: EstadoLeido,
                        eventos_leidos: int | None = None) -> bool:
        """Publica `envio.estado.actualizado` solo si cambió el estado canónico de la guía."""
        if leido.sin_equivalencia:
            self._registrar_sin_equivalencia(codigo, leido.codigo_operador, numero_guia)
        self._registrar_guia(numero_guia, codigo, pedido_id=None)
        with self._Sesiones() as sesion:
            guia = sesion.get(GuiaBD, numero_guia, with_for_update=True)
            cambio = guia.ultimo_estado != leido.evento.estado.value
            if cambio:
                # Primero se publica y luego se guarda: si Redis falla, el próximo aviso o consulta lo reintenta.
                self._bus.publicar(ENVIO_ESTADO_ACTUALIZADO, EnvioEstadoActualizado(
                    numero_guia=numero_guia, transportadora=codigo, estado=leido.evento.estado,
                    ocurrido_en=leido.evento.ocurrido_en))
                guia.ultimo_estado = leido.evento.estado.value
                guia.actualizada_en = ahora()
            if eventos_leidos is not None:
                guia.eventos_leidos = eventos_leidos
            sesion.commit()
        return cambio

    # --- Apoyo ---

    def _consultar(self, i: Integracion, numero_guia: str) -> list[EstadoLeido]:
        respuesta = i.adaptador.enviar(i.mapeador.consulta_estados(numero_guia))
        return self._leer(i, lambda: i.mapeador.leer_estados(respuesta, i.tablas))

    def _leer(self, i: Integracion, lectura: Callable[[], T]) -> T:
        """Una respuesta con forma inesperada del operador es un rechazo canónico, nunca un error 500."""
        try:
            return lectura()
        except ErrorPlataforma:
            raise
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            log.exception("Respuesta inesperada de %s", i.transportadora)
            raise ErrorPlataforma(502, "TRANSPORTADORA_RECHAZO",
                                  f"Respuesta inesperada de la transportadora {i.transportadora}",
                                  i.transportadora) from exc

    def _transportadora_de(self, numero_guia: str) -> str:
        with self._Sesiones() as sesion:
            guia = sesion.get(GuiaBD, numero_guia)
        if guia is None:
            raise ErrorPlataforma(404, "GUIA_NO_ENCONTRADA", f"El SIT no conoce la guía {numero_guia}")
        return guia.transportadora

    def _guias_activas(self, codigo: str) -> list[tuple[str, int]]:
        finales = [estado.value for estado in ESTADOS_FINALES]
        with self._Sesiones() as sesion:
            filas = sesion.execute(select(GuiaBD.numero, GuiaBD.eventos_leidos).where(
                GuiaBD.transportadora == codigo,
                or_(GuiaBD.ultimo_estado.is_(None), GuiaBD.ultimo_estado.not_in(finales))))
            return [(numero, leidos or 0) for numero, leidos in filas]

    def _registrar_guia(self, numero_guia: str, codigo: str, pedido_id: str | None) -> None:
        """Upsert: el webhook de creación de DHL puede llegar antes que la respuesta de crear la guía."""
        for _ in range(2):
            with self._Sesiones() as sesion:
                guia = sesion.get(GuiaBD, numero_guia)
                if guia is None:
                    momento = ahora()
                    sesion.add(GuiaBD(numero=numero_guia, transportadora=codigo, pedido_id=pedido_id,
                                      ultimo_estado=None, eventos_leidos=0, creada_en=momento,
                                      actualizada_en=momento))
                elif pedido_id and not guia.pedido_id:
                    guia.pedido_id = pedido_id
                try:
                    sesion.commit()
                    return
                except IntegrityError:
                    sesion.rollback()  # otro hilo la insertó al mismo tiempo: se repite como actualización
        raise RuntimeError(f"No se pudo registrar la guía {numero_guia}")

    def _registrar_sin_equivalencia(self, codigo: str, codigo_operador: str, numero_guia: str) -> None:
        with self._Sesiones() as sesion:
            sesion.add(EstadoSinEquivalencia(transportadora=codigo, codigo_operador=codigo_operador,
                                             numero_guia=numero_guia, registrado_en=ahora()))
            try:
                sesion.commit()
            except IntegrityError:
                sesion.rollback()  # ya estaba registrado
                return
        log.warning("Estado sin equivalencia: transportadora %s, código %s, guía %s. "
                    "Complete la tabla equivalencia_estado.", codigo, codigo_operador, numero_guia)
