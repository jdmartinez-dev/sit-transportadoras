import pytest
from pydantic import ValidationError

from comun.canonico import (ZONA_COLOMBIA, Direccion, EstadoEnvio, EventoEstado, Paquete, PedidoConfirmado,
                            ahora)

DESTINO = {"divipola": "05001", "direccion": "Carrera 43A # 1-50", "nombre": "Ana Pérez", "telefono": "3001234567"}
PAQUETE = {"peso_kg": 2.0, "largo_cm": 30, "ancho_cm": 20, "alto_cm": 10}


def test_divipola_canonico_tiene_5_digitos():
    with pytest.raises(ValidationError):
        Direccion(**{**DESTINO, "divipola": "05001000"})
    assert Direccion(**DESTINO).divipola == "05001"


def test_paquete_exige_valores_positivos():
    with pytest.raises(ValidationError):
        Paquete(**{**PAQUETE, "peso_kg": 0})


def test_las_fechas_canonicas_llevan_zona_horaria():
    with pytest.raises(ValidationError):
        EventoEstado(estado=EstadoEnvio.CREADA, ocurrido_en="2026-10-12T09:00:00")
    evento = EventoEstado(estado=EstadoEnvio.CREADA, ocurrido_en="2026-10-12T09:00:00-05:00")
    assert evento.model_dump_json() == '{"estado":"CREADA","ocurrido_en":"2026-10-12T09:00:00-05:00"}'


def test_estados_canonicos_de_la_tabla_2():
    assert [e.value for e in EstadoEnvio] == [
        "CREADA", "RECOGIDA", "EN_TRANSITO", "EN_REPARTO", "ENTREGADA", "NOVEDAD", "DEVUELTA"]


def test_pedido_confirmado_sin_transportadora_forzada():
    pedido = PedidoConfirmado.model_validate({"pedido_id": "PED-1", "destino": DESTINO, "paquetes": [PAQUETE]})
    assert pedido.transportadora is None


def test_ahora_usa_la_hora_de_colombia():
    assert ahora().utcoffset() == ZONA_COLOMBIA.utcoffset(None)
