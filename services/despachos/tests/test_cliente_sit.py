import json

import httpx
import pytest

from comun.canonico import Direccion, Paquete, SolicitudCotizacion, SolicitudEnvio
from comun.errores import ErrorPlataforma
from despachos.cliente_sit import ClienteSIT, ProveedorToken

PAQUETE = Paquete(peso_kg=2.0, largo_cm=30, ancho_cm=20, alto_cm=10)
DIRECCION = Direccion(divipola="05001", direccion="Carrera 43A # 1-50", nombre="Ana Pérez", telefono="3001234567")
TOKEN = httpx.Response(200, json={"access_token": "tok", "token_type": "Bearer", "expires_in": 900})


def _cliente(manejar) -> ClienteSIT:
    http = httpx.Client(transport=httpx.MockTransport(manejar))
    return ClienteSIT("http://sit:8000", ProveedorToken("http://auth:8000/oauth/token", "despachos", "s", http), http)


def test_reutiliza_el_token_y_envia_json_canonico():
    pedidos = []

    def manejar(request):
        pedidos.append(request)
        if request.url.path == "/oauth/token":
            return TOKEN
        return httpx.Response(200, json=[{"transportadora": "dhl", "valor_cop": 47250, "peso_facturable_kg": 2.0,
                                          "dias_estimados": 2}])

    sit = _cliente(manejar)
    solicitud = SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE])
    assert sit.cotizar(solicitud)[0].valor_cop == 47250
    sit.cotizar(solicitud)
    assert [p.url.path for p in pedidos] == ["/oauth/token", "/api/v1/cotizaciones", "/api/v1/cotizaciones"]
    assert pedidos[1].headers["authorization"] == "Bearer tok"
    assert json.loads(pedidos[1].content)["destino"] == "05001"


def test_propaga_el_error_canonico_del_sit():
    def manejar(request):
        if request.url.path == "/oauth/token":
            return TOKEN
        return httpx.Response(422, json={"codigo": "DESTINO_NO_CUBIERTO", "mensaje": "No cubre 66001",
                                         "transportadora": "dhl"})

    with pytest.raises(ErrorPlataforma) as exc:
        _cliente(manejar).crear_envio(SolicitudEnvio(pedido_id="PED-1", transportadora="dhl", origen=DIRECCION,
                                                     destino=DIRECCION, paquetes=[PAQUETE]))
    assert exc.value.estado_http == 422
    assert (exc.value.error.codigo, exc.value.error.transportadora) == ("DESTINO_NO_CUBIERTO", "dhl")


def test_sit_inalcanzable_es_sit_no_disponible():
    def manejar(request):
        if request.url.path == "/oauth/token":
            return TOKEN
        raise httpx.ConnectError("sin conexión")

    with pytest.raises(ErrorPlataforma) as exc:
        _cliente(manejar).cotizar(SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE]))
    assert exc.value.error.codigo == "SIT_NO_DISPONIBLE"


def test_autenticacion_inalcanzable_es_auth_no_disponible():
    def manejar(request):
        raise httpx.ConnectError("sin conexión")

    with pytest.raises(ErrorPlataforma) as exc:
        _cliente(manejar).cotizar(SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE]))
    assert exc.value.error.codigo == "AUTH_NO_DISPONIBLE"
