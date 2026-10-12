"""Eventos de la plataforma sobre Redis Streams: un stream por tipo de evento y grupos de consumidores."""
import logging
import threading
from collections.abc import Callable
from uuid import UUID, uuid4

import redis
from pydantic import AwareDatetime, BaseModel, Field, ValidationError

from comun.canonico import ahora
from comun.errores import ErrorPlataforma

log = logging.getLogger(__name__)

PEDIDO_CONFIRMADO = "pedido.confirmado"
GUIA_CREADA = "guia.creada"
ENVIO_ESTADO_ACTUALIZADO = "envio.estado.actualizado"

CAMPO = "evento"
"""Cada entrada del stream tiene un solo campo con el sobre en JSON."""


class Evento(BaseModel):
    """Sobre común de todos los eventos; `datos` lleva el modelo canónico en JSON."""

    id_evento: UUID = Field(default_factory=uuid4)
    tipo: str
    version: int = 1
    ocurrido_en: AwareDatetime = Field(default_factory=ahora)
    datos: dict


Manejador = Callable[[Evento], None]


class Bus:
    def __init__(self, cliente: redis.Redis):
        self._redis = cliente

    @classmethod
    def desde_url(cls, url: str) -> "Bus":
        return cls(redis.Redis.from_url(url, decode_responses=True))

    def publicar(self, tipo: str, datos: BaseModel) -> Evento:
        evento = Evento(tipo=tipo, datos=datos.model_dump(mode="json"))
        try:
            self._redis.xadd(tipo, {CAMPO: evento.model_dump_json()})
        except redis.RedisError as exc:
            raise ErrorPlataforma(503, "BUS_NO_DISPONIBLE", f"No se pudo publicar {tipo}: Redis no disponible") from exc
        log.info("Evento publicado: %s %s", tipo, evento.id_evento)
        return evento

    def asegurar_grupo(self, tipo: str, grupo: str) -> None:
        try:
            self._redis.xgroup_create(tipo, grupo, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def procesar_lote(self, tipo: str, grupo: str, consumidor: str, manejar: Manejador,
                      desde: str, bloquear_ms: int | None) -> str:
        """Lee y procesa un lote; devuelve desde dónde leer en la siguiente vuelta.

        `desde` es "0" (o el último id visto) mientras se recorren los pendientes propios,
        y ">" para los mensajes nuevos. Avanzar el id evita quedar atrapado en un mensaje
        que falla siempre: queda pendiente y se reintenta en el próximo arranque.
        """
        respuesta = self._redis.xreadgroup(grupo, consumidor, {tipo: desde}, count=10,
                                           block=bloquear_ms if desde == ">" else None)
        entradas = respuesta[0][1] if respuesta else []
        if desde != ">" and not entradas:
            return ">"
        for id_mensaje, campos in entradas:
            if desde != ">":
                desde = id_mensaje
            self._procesar(tipo, grupo, id_mensaje, campos, manejar)
        return desde

    def _procesar(self, tipo: str, grupo: str, id_mensaje: str, campos: dict | None, manejar: Manejador) -> None:
        if not campos or CAMPO not in campos:
            log.error("Mensaje sin campo '%s' en %s (%s); se descarta", CAMPO, tipo, id_mensaje)
            self._redis.xack(tipo, grupo, id_mensaje)
            return
        try:
            evento = Evento.model_validate_json(campos[CAMPO])
        except ValidationError:
            log.error("Evento inválido en %s (%s); se descarta", tipo, id_mensaje)
            self._redis.xack(tipo, grupo, id_mensaje)
            return
        try:
            manejar(evento)
        except Exception:
            log.exception("No se pudo procesar %s %s; queda pendiente", tipo, id_mensaje)
            return
        self._redis.xack(tipo, grupo, id_mensaje)

    def consumir(self, tipo: str, grupo: str, consumidor: str, manejar: Manejador,
                 detener: threading.Event, bloquear_ms: int = 5000) -> None:
        """Bucle del consumidor: primero sus pendientes y luego los mensajes nuevos, hasta `detener`."""
        desde = "0"
        grupo_listo = False
        while not detener.is_set():
            try:
                if not grupo_listo:
                    self.asegurar_grupo(tipo, grupo)
                    grupo_listo = True
                desde = self.procesar_lote(tipo, grupo, consumidor, manejar, desde, bloquear_ms)
            except redis.RedisError as exc:
                log.warning("Redis no disponible para %s (%s); se reintenta en 2 s", tipo, exc)
                grupo_listo = False
                detener.wait(2)

    def iniciar_consumidor(self, tipo: str, grupo: str, consumidor: str, manejar: Manejador,
                           bloquear_ms: int = 5000) -> tuple[threading.Thread, threading.Event]:
        detener = threading.Event()
        hilo = threading.Thread(target=self.consumir, args=(tipo, grupo, consumidor, manejar, detener, bloquear_ms),
                                daemon=True, name=f"consumidor-{tipo}")
        hilo.start()
        return hilo, detener
