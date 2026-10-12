"""Suscripción a pedido.confirmado (Tabla 2): cada evento inicia la orquestación del despacho."""
import logging
from collections.abc import Callable

from pydantic import ValidationError

from comun.canonico import PedidoConfirmado
from comun.eventos import Evento
from despachos.orquestador import Orquestador

log = logging.getLogger(__name__)


def crear_manejador(orquestador: Orquestador) -> Callable[[Evento], None]:
    def manejar(evento: Evento) -> None:
        try:
            pedido = PedidoConfirmado.model_validate(evento.datos)
        except ValidationError:
            log.error("Evento pedido.confirmado inválido (%s); se descarta", evento.id_evento)
            return
        despacho, _ = orquestador.procesar(pedido)
        log.info("Pedido %s procesado desde el evento: %s", pedido.pedido_id, despacho.estado.value)

    return manejar
