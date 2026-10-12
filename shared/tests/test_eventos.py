import os
import threading
import time
from uuid import uuid4

import fakeredis
import pytest
import redis

from comun.canonico import GuiaCreada
from comun.errores import ErrorPlataforma
from comun.eventos import CAMPO, GUIA_CREADA, Bus, Evento


@pytest.fixture
def cliente():
    return fakeredis.FakeRedis(decode_responses=True)


def _guia(numero: str = "5300000001") -> GuiaCreada:
    return GuiaCreada(pedido_id="PED-1", numero_guia=numero, transportadora="dhl")


def test_publicar_escribe_el_sobre_en_el_stream_del_tipo(cliente):
    evento = Bus(cliente).publicar(GUIA_CREADA, _guia())
    [(_, campos)] = cliente.xrange(GUIA_CREADA)
    leido = Evento.model_validate_json(campos[CAMPO])
    assert leido.id_evento == evento.id_evento
    assert leido.tipo == GUIA_CREADA and leido.version == 1
    assert leido.datos == {"pedido_id": "PED-1", "numero_guia": "5300000001", "transportadora": "dhl"}


def test_procesar_lote_entrega_el_evento_y_lo_confirma(cliente):
    bus = Bus(cliente)
    bus.asegurar_grupo(GUIA_CREADA, "g")
    bus.publicar(GUIA_CREADA, _guia())
    recibidos = []
    bus.procesar_lote(GUIA_CREADA, "g", "c1", recibidos.append, desde=">", bloquear_ms=None)
    assert [e.datos["numero_guia"] for e in recibidos] == ["5300000001"]
    assert cliente.xpending(GUIA_CREADA, "g")["pending"] == 0


def test_si_el_manejador_falla_el_mensaje_queda_pendiente(cliente):
    bus = Bus(cliente)
    bus.asegurar_grupo(GUIA_CREADA, "g")
    bus.publicar(GUIA_CREADA, _guia())

    def falla(evento):
        raise RuntimeError("base de datos caída")

    bus.procesar_lote(GUIA_CREADA, "g", "c1", falla, desde=">", bloquear_ms=None)
    assert cliente.xpending(GUIA_CREADA, "g")["pending"] == 1


def test_un_mensaje_invalido_se_descarta_sin_bloquear_el_stream(cliente):
    bus = Bus(cliente)
    bus.asegurar_grupo(GUIA_CREADA, "g")
    cliente.xadd(GUIA_CREADA, {CAMPO: "esto no es json"})
    cliente.xadd(GUIA_CREADA, {"otro_campo": "x"})
    recibidos = []
    bus.procesar_lote(GUIA_CREADA, "g", "c1", recibidos.append, desde=">", bloquear_ms=None)
    assert recibidos == []
    assert cliente.xpending(GUIA_CREADA, "g")["pending"] == 0


def test_asegurar_grupo_es_idempotente(cliente):
    bus = Bus(cliente)
    bus.asegurar_grupo(GUIA_CREADA, "g")
    bus.asegurar_grupo(GUIA_CREADA, "g")


def test_el_consumidor_en_segundo_plano_recibe_y_se_detiene(cliente):
    bus = Bus(cliente)
    recibidos = []
    hilo, detener = bus.iniciar_consumidor(GUIA_CREADA, "g", "c1", recibidos.append, bloquear_ms=50)
    bus.publicar(GUIA_CREADA, _guia())
    limite = time.monotonic() + 3
    while not recibidos and time.monotonic() < limite:
        time.sleep(0.05)
    detener.set()
    hilo.join(timeout=3)
    assert len(recibidos) == 1
    assert not hilo.is_alive()


def test_publicar_sin_redis_es_error_canonico():
    bus = Bus(redis.Redis.from_url("redis://localhost:1/0", socket_connect_timeout=0.2))
    with pytest.raises(ErrorPlataforma) as exc:
        bus.publicar(GUIA_CREADA, _guia())
    assert exc.value.estado_http == 503
    assert exc.value.error.codigo == "BUS_NO_DISPONIBLE"


@pytest.mark.redis
@pytest.mark.skipif(not os.environ.get("REDIS_URL_PRUEBAS"), reason="requiere REDIS_URL_PRUEBAS")
def test_al_reiniciar_procesa_primero_los_pendientes():
    cliente = redis.Redis.from_url(os.environ["REDIS_URL_PRUEBAS"], decode_responses=True)
    stream = f"prueba.pendientes.{uuid4().hex}"
    bus = Bus(cliente)
    bus.asegurar_grupo(stream, "g")
    bus.publicar(stream, _guia("1"))
    bus.publicar(stream, _guia("2"))

    def falla(evento):
        raise RuntimeError("caída")

    bus.procesar_lote(stream, "g", "c1", falla, desde=">", bloquear_ms=None)
    assert cliente.xpending(stream, "g")["pending"] == 2

    recibidos = []
    desde = "0"
    while desde != ">":
        desde = bus.procesar_lote(stream, "g", "c1", recibidos.append, desde=desde, bloquear_ms=None)
    assert [e.datos["numero_guia"] for e in recibidos] == ["1", "2"]
    assert cliente.xpending(stream, "g")["pending"] == 0
    cliente.delete(stream)
