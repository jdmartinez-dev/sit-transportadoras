from datetime import date, datetime

import pytest

from comun.canonico import (ZONA_COLOMBIA, Direccion, EstadoEnvio, Franja, Paquete, SolicitudCotizacion,
                            SolicitudEnvio, SolicitudRecogida)
from comun.errores import ErrorPlataforma
from sit.motor.equivalencias import TablasEquivalencia
from sit.motor.mapeadores.dhl import MapeadorDHL

TABLAS = TablasEquivalencia(
    transportadora="dhl",
    estados={"SD": EstadoEnvio.CREADA, "PU": EstadoEnvio.RECOGIDA, "OH": EstadoEnvio.NOVEDAD},
    ciudades={"11001": "BOG", "05001": "MDE"},
    unidades={"peso": ("lb", 0.45359237), "longitud": ("in", 2.54)},
)
PAQUETE = Paquete(peso_kg=2.0, largo_cm=30, ancho_cm=20, alto_cm=10)
ORIGEN = Direccion(divipola="11001", direccion="Calle 13 # 68-50", nombre="Bodega", telefono="6015550100")
DESTINO = Direccion(divipola="05001", direccion="Carrera 43A # 1-50", nombre="Ana Pérez", telefono="3001234567")
SOLICITUD_ENVIO = SolicitudEnvio(pedido_id="PED-1", transportadora="dhl", origen=ORIGEN, destino=DESTINO,
                                 paquetes=[PAQUETE])
mapeador = MapeadorDHL()


def test_cotizacion_en_unidades_imperiales_y_codigos_propios():
    mensaje = mapeador.cotizacion(SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE]), TABLAS)
    assert mensaje.operacion == "POST /rates"
    assert mensaje.cuerpo == {
        "originCityCode": "BOG",
        "destinationCityCode": "MDE",
        "packages": [{"weight": 4.41, "dimensions": {"length": 11.8, "width": 7.9, "height": 3.9}}],
    }


def test_leer_cotizacion_normaliza_a_cop_y_kg():
    respuesta = {"products": [{"totalPrice": [{"price": 47250.0, "priceCurrency": "COP"}],
                               "weight": {"volumetric": 2.62, "provided": 4.41, "unitOfMeasurement": "imperial"},
                               "totalTransitDays": 2}]}
    cotizacion = mapeador.leer_cotizacion(respuesta, TABLAS)
    assert cotizacion.model_dump() == {"transportadora": "dhl", "valor_cop": 47250, "peso_facturable_kg": 2.0,
                                       "dias_estimados": 2}


def test_envio_en_el_modelo_de_dhl():
    mensaje = mapeador.envio(SOLICITUD_ENVIO, TABLAS)
    assert mensaje.operacion == "POST /shipments"
    assert mensaje.cuerpo["originCityCode"] == "BOG"
    assert mensaje.cuerpo["receiver"] == {"cityCode": "MDE", "name": "Ana Pérez", "address": "Carrera 43A # 1-50",
                                          "phone": "3001234567"}
    assert mensaje.cuerpo["reference"] == "PED-1"
    assert mensaje.cuerpo["packages"][0]["weight"] == 4.41


def test_leer_guia():
    guia = mapeador.leer_guia({"shipmentTrackingNumber": "5300000001"}, SOLICITUD_ENVIO)
    assert (guia.numero_guia, guia.transportadora, guia.pedido_id, guia.estado) == \
        ("5300000001", "dhl", "PED-1", EstadoEnvio.CREADA)


def test_recogida_en_la_franja_de_la_manana_con_zona_horaria():
    solicitud = SolicitudRecogida(numero_guia="5300000001", fecha=date(2026, 10, 12), franja=Franja.MANANA)
    mensaje = mapeador.recogida(solicitud)
    assert mensaje.operacion == "POST /pickups"
    assert mensaje.cuerpo == {"shipmentTrackingNumber": "5300000001",
                              "plannedPickupDateAndTime": "2026-10-12T09:00:00-05:00"}
    recogida = mapeador.leer_recogida({"dispatchConfirmationNumbers": ["CBJ000000001"]}, solicitud)
    assert (recogida.confirmacion, recogida.transportadora, recogida.franja) == ("CBJ000000001", "dhl", Franja.MANANA)


def test_estados_con_fecha_y_hora_separadas():
    assert mapeador.consulta_estados("5300000001").operacion == "GET /shipments/5300000001/tracking"
    respuesta = {"shipments": [{"events": [
        {"date": "2026-10-12", "time": "09:30:00", "typeCode": "PU", "description": "Shipment picked up"}]}]}
    [leido] = mapeador.leer_estados(respuesta, TABLAS)
    assert leido.evento.estado == EstadoEnvio.RECOGIDA
    assert leido.evento.ocurrido_en == datetime(2026, 10, 12, 9, 30, tzinfo=ZONA_COLOMBIA)
    assert leido.codigo_operador == "PU"
    assert not leido.sin_equivalencia


def test_webhook_con_codigo_desconocido_es_novedad():
    cuerpo = {"shipmentTrackingNumber": "5300000001",
              "event": {"date": "2026-10-12", "time": "10:00:00", "typeCode": "XX", "description": "?"}}
    numero, leido = mapeador.leer_webhook(cuerpo, TABLAS)
    assert numero == "5300000001"
    assert leido.evento.estado == EstadoEnvio.NOVEDAD
    assert leido.sin_equivalencia and leido.codigo_operador == "XX"


def test_webhook_mal_formado_es_error_canonico():
    with pytest.raises(ErrorPlataforma) as exc:
        mapeador.leer_webhook({"event": {}}, TABLAS)
    assert exc.value.estado_http == 400
    assert exc.value.error.codigo == "WEBHOOK_INVALIDO"
