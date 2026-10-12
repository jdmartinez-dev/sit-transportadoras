from datetime import date, datetime

from comun.canonico import (ZONA_COLOMBIA, Direccion, EstadoEnvio, Franja, Paquete, SolicitudCotizacion,
                            SolicitudEnvio, SolicitudRecogida)
from sit.motor.equivalencias import TablasEquivalencia
from sit.motor.mapeadores import MAPEADORES
from sit.motor.mapeadores.coordinadora import MapeadorCoordinadora

TABLAS = TablasEquivalencia(
    transportadora="coordinadora",
    estados={"1": EstadoEnvio.CREADA, "4": EstadoEnvio.EN_TRANSITO, "6": EstadoEnvio.EN_REPARTO},
    ciudades={"11001": "11001000", "05001": "05001000"},
    unidades={"peso": ("g", 0.001), "longitud": ("cm", 1.0)},
)
PAQUETE = Paquete(peso_kg=2.0, largo_cm=30, ancho_cm=20, alto_cm=10)
ORIGEN = Direccion(divipola="11001", direccion="Calle 13 # 68-50", nombre="Bodega", telefono="6015550100")
DESTINO = Direccion(divipola="05001", direccion="Carrera 43A # 1-50", nombre="Ana Pérez", telefono="3001234567")
SOLICITUD_ENVIO = SolicitudEnvio(pedido_id="PED-2", transportadora="coordinadora", origen=ORIGEN, destino=DESTINO,
                                 paquetes=[PAQUETE])
mapeador = MapeadorCoordinadora()


def test_cotizacion_en_gramos_y_divipola_de_8_digitos():
    mensaje = mapeador.cotizacion(SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE]), TABLAS)
    assert mensaje.operacion == "CotizarFlete"
    assert mensaje.cuerpo == {"ciudadOrigen": "11001000", "ciudadDestino": "05001000",
                              "piezas": [{"pesoGr": 2000, "largoCm": 30, "anchoCm": 20, "altoCm": 10}]}


def test_leer_cotizacion_pasa_de_gramos_a_kg():
    cotizacion = mapeador.leer_cotizacion({"valorFlete": 35100, "pesoLiquidadoGr": 2400, "diasEntrega": 3}, TABLAS)
    assert cotizacion.model_dump() == {"transportadora": "coordinadora", "valor_cop": 35100,
                                       "peso_facturable_kg": 2.4, "dias_estimados": 3}


def test_generar_guia_y_leer_el_codigo_de_remision():
    mensaje = mapeador.envio(SOLICITUD_ENVIO, TABLAS)
    assert mensaje.operacion == "GenerarGuia"
    assert mensaje.cuerpo["referencia"] == "PED-2"
    assert mensaje.cuerpo["ciudadOrigen"] == "11001000"
    assert mensaje.cuerpo["destinatario"] == {"nombre": "Ana Pérez", "direccion": "Carrera 43A # 1-50",
                                              "telefono": "3001234567", "ciudad": "05001000"}
    # zeep entrega el valor directamente cuando la respuesta tiene un solo elemento.
    guia = mapeador.leer_guia("900000000001", SOLICITUD_ENVIO)
    assert (guia.numero_guia, guia.transportadora, guia.estado) == ("900000000001", "coordinadora",
                                                                     EstadoEnvio.CREADA)


def test_recogida_con_franja_am_pm():
    solicitud = SolicitudRecogida(numero_guia="900000000001", fecha=date(2026, 10, 12), franja=Franja.TARDE)
    mensaje = mapeador.recogida(solicitud)
    assert mensaje.operacion == "ProgramarRecogida"
    assert mensaje.cuerpo == {"codigoRemision": "900000000001", "fechaRecogida": "2026-10-12", "franja": "PM"}
    assert mapeador.leer_recogida("REC-000001", solicitud).confirmacion == "REC-000001"


def test_historial_de_estados_numericos_con_fecha_local():
    assert mapeador.consulta_estados("900000000001").cuerpo == {"codigoRemision": "900000000001"}
    respuesta = {"codigoRemision": "900000000001", "estados": [
        {"codigo": "1", "descripcion": "Guía generada", "fecha": "2026-10-12T09:00:00"},
        {"codigo": "4", "descripcion": "En transporte", "fecha": "2026-10-12T15:30:00"},
        {"codigo": "77", "descripcion": "Desconocido", "fecha": "2026-10-12T16:00:00"},
    ]}
    leidos = mapeador.leer_estados(respuesta, TABLAS)
    assert [l.evento.estado for l in leidos] == [EstadoEnvio.CREADA, EstadoEnvio.EN_TRANSITO, EstadoEnvio.NOVEDAD]
    assert leidos[1].evento.ocurrido_en == datetime(2026, 10, 12, 15, 30, tzinfo=ZONA_COLOMBIA)
    assert leidos[2].sin_equivalencia and leidos[2].codigo_operador == "77"


def test_coordinadora_no_tiene_webhook_y_el_registro_tiene_ambos_mapeadores():
    assert not hasattr(mapeador, "leer_webhook")
    assert set(MAPEADORES) == {"dhl", "coordinadora"}


def test_una_respuesta_vacia_no_produce_una_guia_none():
    import pytest

    with pytest.raises(ValueError):
        mapeador.leer_guia(None, SOLICITUD_ENVIO)
    with pytest.raises(ValueError):
        mapeador.leer_recogida("", SolicitudRecogida(numero_guia="900000000001", fecha=date(2026, 10, 12),
                                                     franja=Franja.MANANA))
