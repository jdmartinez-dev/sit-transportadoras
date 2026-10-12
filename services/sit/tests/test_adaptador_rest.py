import json

import httpx
import pytest

from comun.errores import ErrorPlataforma
from sit.adaptadores.rest import AdaptadorREST
from sit.motor.tipos import MensajeOperador


def _adaptador(manejar, esperas=None) -> AdaptadorREST:
    esperas = esperas if esperas is not None else []
    return AdaptadorREST("dhl", "http://mock-dhl:8000/mydhlapi", ("tienda", "clave"), reintentos=3,
                         cliente_http=httpx.Client(transport=httpx.MockTransport(manejar)), dormir=esperas.append)


def test_envia_json_con_autenticacion_basica_y_devuelve_la_respuesta():
    vistos = []

    def manejar(request):
        vistos.append(request)
        return httpx.Response(201, json={"shipmentTrackingNumber": "5300000001"})

    respuesta = _adaptador(manejar).enviar(MensajeOperador("POST /shipments", {"reference": "PED-1"}))
    assert respuesta == {"shipmentTrackingNumber": "5300000001"}
    assert str(vistos[0].url) == "http://mock-dhl:8000/mydhlapi/shipments"
    assert vistos[0].headers["authorization"].startswith("Basic ")
    assert json.loads(vistos[0].content) == {"reference": "PED-1"}


def test_get_sin_cuerpo():
    vistos = []

    def manejar(request):
        vistos.append(request)
        return httpx.Response(200, json={"shipments": []})

    _adaptador(manejar).enviar(MensajeOperador("GET /shipments/5300000001/tracking"))
    assert vistos[0].method == "GET"
    assert vistos[0].content == b""


def test_reintenta_ante_errores_de_conexion_y_5xx():
    respuestas = iter([httpx.ConnectError("caído"), httpx.Response(503), httpx.Response(200, json={"ok": True})])

    def manejar(request):
        siguiente = next(respuestas)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    esperas = []
    assert _adaptador(manejar, esperas).enviar(MensajeOperador("POST /rates", {})) == {"ok": True}
    assert esperas == [0.5, 1.0]


def test_agota_los_reintentos_con_error_canonico():
    esperas = []
    with pytest.raises(ErrorPlataforma) as exc:
        _adaptador(lambda request: httpx.Response(500), esperas).enviar(MensajeOperador("POST /rates", {}))
    assert exc.value.estado_http == 502
    assert exc.value.error.codigo == "TRANSPORTADORA_SIN_RESPUESTA"
    assert esperas == [0.5, 1.0]


def test_un_4xx_no_se_reintenta_ni_se_reenvia_el_error_crudo():
    llamadas = []

    def manejar(request):
        llamadas.append(request)
        return httpx.Response(400, json={"detail": "City not covered: PEI"})

    with pytest.raises(ErrorPlataforma) as exc:
        _adaptador(manejar).enviar(MensajeOperador("POST /rates", {}))
    assert len(llamadas) == 1
    assert exc.value.error.codigo == "TRANSPORTADORA_RECHAZO"
    assert "PEI" not in exc.value.error.mensaje


def test_una_respuesta_2xx_que_no_es_json_es_rechazo_canonico():
    with pytest.raises(ErrorPlataforma) as exc:
        _adaptador(lambda request: httpx.Response(200, text="<html>proxy</html>")).enviar(
            MensajeOperador("POST /rates", {}))
    assert exc.value.estado_http == 502
    assert exc.value.error.codigo == "TRANSPORTADORA_RECHAZO"

def test_no_expone_datos_personales_en_logs(caplog):
    datos_personales = {
        "receiver": {
            "name": "Ana Perez",
            "phone": "3001234567",
            "address": "Calle 123"
        },
        "reference": "PED-1001"
    }

    def manejar(request):
        return httpx.Response(
            201,
            json={"shipmentTrackingNumber": "5300000001"}
        )

    with caplog.at_level("INFO", logger="sit.adaptadores.rest"):
        _adaptador(manejar).enviar(
            MensajeOperador("POST /shipments", datos_personales)
        )

    registros = caplog.text

    assert "Ana Perez" not in registros
    assert "3001234567" not in registros
    assert "Calle 123" not in registros

    # Debemos conservar información técnica útil.
    assert "PED-1001" in registros


def test_no_expone_datos_personales_en_respuesta(caplog):
    def manejar(request):
        return httpx.Response(
            201,
            json={
                "shipmentTrackingNumber": "5300000001",
                "receiver": {
                    "name": "Ana Perez",
                    "phone": "3001234567",
                },
            },
        )

    with caplog.at_level("INFO", logger="sit.adaptadores.rest"):
        _adaptador(manejar).enviar(
            MensajeOperador(
                "POST /shipments",
                {"reference": "PED-1001"},
            )
        )

    registros = caplog.text

    assert "Ana Perez" not in registros
    assert "3001234567" not in registros
    assert "5300000001" in registros



def test_no_expone_datos_en_error_http(caplog):
    def manejar(request):
        return httpx.Response(
            400,
            text="Error: telefono 3001234567 no valido",
        )

    with caplog.at_level("WARNING", logger="sit.adaptadores.rest"):
        with pytest.raises(ErrorPlataforma):
            _adaptador(manejar).enviar(
                MensajeOperador(
                    "POST /shipments",
                    {"reference": "PED-1001"},
                )
            )

    assert "3001234567" not in caplog.text
    assert "rechazo HTTP 400" in caplog.text


def test_no_expone_datos_en_respuesta_no_json(caplog):
    def manejar(request):
        return httpx.Response(
            200,
            text="Respuesta con datos privados 3001234567",
        )

    with caplog.at_level("WARNING", logger="sit.adaptadores.rest"):
        with pytest.raises(ErrorPlataforma):
            _adaptador(manejar).enviar(
                MensajeOperador(
                    "POST /shipments",
                    {"reference": "PED-1001"},
                )
            )

    assert "3001234567" not in caplog.text
    assert "JSON inválido" in caplog.text