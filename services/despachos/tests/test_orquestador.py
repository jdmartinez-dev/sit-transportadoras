from datetime import date

import pytest

from comun.canonico import Cotizacion, Franja, PedidoConfirmado
from comun.errores import ErrorPlataforma
from comun.eventos import GUIA_CREADA
from despachos.modelos import EstadoDespacho
from despachos.orquestador import elegir

DESTINO = {"divipola": "05001", "direccion": "Carrera 43A # 1-50", "nombre": "Ana Pérez", "telefono": "3001234567"}
PAQUETE = {"peso_kg": 2.0, "largo_cm": 30, "ancho_cm": 20, "alto_cm": 10}


def _pedido(pedido_id="PED-1", transportadora=None) -> PedidoConfirmado:
    return PedidoConfirmado.model_validate({"pedido_id": pedido_id, "destino": DESTINO, "paquetes": [PAQUETE],
                                            "transportadora": transportadora})


def _cotizacion(transportadora, valor, dias) -> Cotizacion:
    return Cotizacion(transportadora=transportadora, valor_cop=valor, peso_facturable_kg=2.0, dias_estimados=dias)


def test_elegir_la_cotizacion_mas_barata():
    assert elegir([_cotizacion("dhl", 47250, 2), _cotizacion("coordinadora", 35100, 3)], None).transportadora == \
        "coordinadora"


def test_en_empate_gana_la_mas_rapida_y_luego_el_codigo():
    assert elegir([_cotizacion("a", 100, 3), _cotizacion("b", 100, 2)], None).transportadora == "b"
    assert elegir([_cotizacion("b", 100, 2), _cotizacion("a", 100, 2)], None).transportadora == "a"


def test_elegir_la_transportadora_forzada():
    assert elegir([_cotizacion("dhl", 47250, 2), _cotizacion("coordinadora", 35100, 3)], "dhl").transportadora == "dhl"


def test_forzada_sin_cotizacion_es_422():
    with pytest.raises(ErrorPlataforma) as exc:
        elegir([_cotizacion("coordinadora", 35100, 3)], "dhl")
    assert exc.value.error.codigo == "TRANSPORTADORA_SIN_COTIZACION"


def test_sin_cotizaciones_es_502():
    with pytest.raises(ErrorPlataforma) as exc:
        elegir([], None)
    assert exc.value.error.codigo == "SIN_COTIZACIONES"


def test_despacho_completo_en_el_orden_de_la_orquestacion(orquestador, sit, bus):
    despacho, creado = orquestador.procesar(_pedido())
    assert creado
    assert sit.nombres() == ["cotizar", "crear_envio", "programar_recogida"]
    assert despacho.estado == EstadoDespacho.RECOGIDA_PROGRAMADA
    assert (despacho.transportadora, despacho.numero_guia) == ("coordinadora", "900000000001")
    assert despacho.confirmacion_recogida == "REC-000001"
    assert len(despacho.cotizaciones) == 2
    [(tipo, datos)] = bus.publicados
    assert tipo == GUIA_CREADA
    assert datos.model_dump() == {"pedido_id": "PED-1", "numero_guia": "900000000001",
                                  "transportadora": "coordinadora"}


def test_la_recogida_se_programa_para_el_dia_siguiente_en_la_manana(orquestador, sit):
    orquestador.procesar(_pedido())
    _, solicitud = sit.llamadas[2]
    assert (solicitud.fecha, solicitud.franja) == (date(2026, 10, 12), Franja.MANANA)


def test_la_transportadora_forzada_se_pide_al_sit(orquestador, sit):
    despacho, _ = orquestador.procesar(_pedido(transportadora="dhl"))
    _, solicitud = sit.llamadas[0]
    assert solicitud.transportadora == "dhl"
    assert solicitud.origen == "11001"
    assert despacho.transportadora == "dhl"


def test_un_fallo_deja_el_despacho_fallido_con_el_error_canonico(orquestador, sit, bus):
    sit.fallas["crear_envio"] = ErrorPlataforma(502, "TRANSPORTADORA_SIN_RESPUESTA", "Coordinadora no responde",
                                                "coordinadora")
    despacho, _ = orquestador.procesar(_pedido())
    assert despacho.estado == EstadoDespacho.FALLIDO
    assert despacho.error.codigo == "TRANSPORTADORA_SIN_RESPUESTA"
    assert bus.publicados == []


def test_reintentar_reanuda_desde_el_paso_fallido_sin_duplicar(orquestador, sit, bus):
    sit.fallas["crear_envio"] = ErrorPlataforma(502, "TRANSPORTADORA_SIN_RESPUESTA", "caída", "coordinadora")
    orquestador.procesar(_pedido())
    despacho, creado = orquestador.procesar(_pedido())
    assert not creado
    assert sit.nombres() == ["cotizar", "crear_envio", "crear_envio", "programar_recogida"]
    assert despacho.estado == EstadoDespacho.RECOGIDA_PROGRAMADA
    assert despacho.error is None
    assert len(bus.publicados) == 1


def test_un_despacho_completo_no_se_repite(orquestador, sit, bus):
    orquestador.procesar(_pedido())
    despacho, creado = orquestador.procesar(_pedido())
    assert not creado
    assert sit.nombres() == ["cotizar", "crear_envio", "programar_recogida"]
    assert despacho.estado == EstadoDespacho.RECOGIDA_PROGRAMADA
    assert len(bus.publicados) == 1


def test_si_el_bus_falla_solo_se_reintenta_la_publicacion(orquestador, sit, bus):
    bus.falla = ErrorPlataforma(503, "BUS_NO_DISPONIBLE", "Redis caído")
    despacho, _ = orquestador.procesar(_pedido())
    assert despacho.estado == EstadoDespacho.FALLIDO
    assert despacho.error.codigo == "BUS_NO_DISPONIBLE"
    bus.falla = None
    despacho, _ = orquestador.procesar(_pedido())
    assert despacho.estado == EstadoDespacho.RECOGIDA_PROGRAMADA
    assert sit.nombres() == ["cotizar", "crear_envio", "programar_recogida"]
    assert len(bus.publicados) == 1


def test_dos_solicitudes_simultaneas_del_mismo_pedido_no_duplican(orquestador, sit, bus):
    import threading
    import time

    entro, soltar = threading.Event(), threading.Event()
    cotizar_original = sit.cotizar

    def cotizar_lento(solicitud):
        entro.set()
        soltar.wait(5)
        return cotizar_original(solicitud)

    sit.cotizar = cotizar_lento
    resultados = []
    hilos = [threading.Thread(target=lambda: resultados.append(orquestador.procesar(_pedido()))) for _ in range(2)]
    hilos[0].start()
    entro.wait(5)
    hilos[1].start()  # p. ej. el evento y un POST del mismo pedido, o un doble clic
    time.sleep(0.3)
    soltar.set()
    for hilo in hilos:
        hilo.join(10)
    assert sit.nombres() == ["cotizar", "crear_envio", "programar_recogida"]
    assert len(bus.publicados) == 1
    assert sorted(creado for _, creado in resultados) == [False, True]
