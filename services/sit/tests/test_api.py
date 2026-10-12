import pytest
from fastapi.testclient import TestClient

from comun.eventos import ENVIO_ESTADO_ACTUALIZADO
from comun.pruebas import BusFalso, token_de_prueba
from sit.config import Config
from sit.main import crear_app

DESTINO = {"divipola": "05001", "direccion": "Carrera 43A # 1-50", "nombre": "Ana Pérez", "telefono": "3001234567"}
ORIGEN = {"divipola": "11001", "direccion": "Calle 13 # 68-50", "nombre": "Bodega", "telefono": "6015550100"}
PAQUETE = {"peso_kg": 2.0, "largo_cm": 30, "ancho_cm": 20, "alto_cm": 10}


@pytest.fixture
def bus():
    return BusFalso()


@pytest.fixture
def cliente(llaves, bus, adaptadores_falsos):
    app = crear_app(Config(url_bd="sqlite://", jwt_publica=llaves[1]), bus=bus,
                    crear_adaptador=lambda t: adaptadores_falsos[t.codigo], iniciar_fondo=False)
    with TestClient(app) as c:
        yield c


def _token(llaves, rol: str, sub: str = "usuario") -> dict:
    return {"Authorization": f"Bearer {token_de_prueba(llaves[0], sub, [rol])}"}


def test_sin_token_es_401_canonico(cliente):
    r = cliente.post("/api/v1/cotizaciones", json={"origen": "11001", "destino": "05001", "paquetes": [PAQUETE]})
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_AUSENTE"


def test_un_cliente_no_puede_cotizar(cliente, llaves):
    r = cliente.post("/api/v1/cotizaciones", headers=_token(llaves, "cliente"),
                     json={"origen": "11001", "destino": "05001", "paquetes": [PAQUETE]})
    assert r.status_code == 403


def test_cotizaciones_comparables(cliente, llaves):
    r = cliente.post("/api/v1/cotizaciones", headers=_token(llaves, "operador_logistico"),
                     json={"origen": "11001", "destino": "05001", "paquetes": [PAQUETE]})
    assert r.status_code == 200
    assert {c["transportadora"]: c["valor_cop"] for c in r.json()} == {"dhl": 47250, "coordinadora": 35100}


def test_envio_recogida_y_estados(cliente, llaves):
    operador = _token(llaves, "operador_logistico")
    r = cliente.post("/api/v1/envios", headers=operador, json={"pedido_id": "PED-1", "transportadora": "dhl",
                                                               "origen": ORIGEN, "destino": DESTINO,
                                                               "paquetes": [PAQUETE]})
    assert r.status_code == 201
    assert r.json()["numero_guia"] == "5300000001" and r.json()["estado"] == "CREADA"
    r = cliente.post("/api/v1/recogidas", headers=operador,
                     json={"numero_guia": "5300000001", "fecha": "2026-10-12", "franja": "MANANA"})
    assert r.status_code == 201 and r.json()["confirmacion"] == "CBJ000000001"
    r = cliente.get("/api/v1/envios/5300000001/estados", headers=operador)
    assert [e["estado"] for e in r.json()] == ["CREADA", "RECOGIDA"]


def test_webhook_publica_el_evento_y_responde_204(cliente, llaves, bus):
    r = cliente.post("/api/v1/webhooks/dhl", headers=_token(llaves, "operador_logistico", "mock-dhl"),
                     json={"shipmentTrackingNumber": "5300000009",
                           "event": {"date": "2026-10-12", "time": "09:00:00", "typeCode": "SD", "description": "-"}})
    assert r.status_code == 204
    assert bus.tipos() == [ENVIO_ESTADO_ACTUALIZADO]


def test_el_catalogo_para_el_administrador(cliente, llaves):
    r = cliente.get("/api/v1/transportadoras", headers=_token(llaves, "admin_integraciones"))
    assert r.status_code == 200
    dhl = next(t for t in r.json() if t["codigo"] == "dhl")
    assert dhl == {"codigo": "dhl", "nombre": "DHL Express (simulada)", "protocolo": "REST",
                   "version_api": "MyDHL API 2 (simulada)", "adaptador": "rest",
                   "frecuencia_sincronizacion_seg": None, "version_equivalencias": "2026.10-1", "activa": True}


def test_solicitud_invalida_es_422_canonico(cliente, llaves):
    r = cliente.post("/api/v1/envios", headers=_token(llaves, "operador_logistico"),
                     json={"pedido_id": "PED-1", "transportadora": "dhl", "origen": ORIGEN,
                           "destino": {**DESTINO, "divipola": "BOG"}, "paquetes": [PAQUETE]})
    assert r.status_code == 422
    assert r.json()["codigo"] == "SOLICITUD_INVALIDA"


def test_salud_sin_token(cliente):
    assert cliente.get("/salud").json() == {"estado": "ok"}
