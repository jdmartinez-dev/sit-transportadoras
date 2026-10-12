import pytest
from fastapi.testclient import TestClient

from comun.errores import ErrorPlataforma
from comun.pruebas import token_de_prueba
from despachos.config import Config
from despachos.main import crear_app

PEDIDO = {"pedido_id": "PED-1001", "transportadora": "dhl",
          "destino": {"divipola": "05001", "direccion": "Carrera 43A # 1-50", "nombre": "Ana Pérez",
                      "telefono": "3001234567"},
          "paquetes": [{"peso_kg": 2.0, "largo_cm": 30, "ancho_cm": 20, "alto_cm": 10}]}


@pytest.fixture
def cliente(llaves, sit, bus):
    app = crear_app(Config(url_bd="sqlite://", jwt_publica=llaves[1]), bus=bus, sit=sit, iniciar_fondo=False)
    with TestClient(app) as c:
        yield c


def _token(llaves, rol: str) -> dict:
    return {"Authorization": f"Bearer {token_de_prueba(llaves[0], 'usuario', [rol])}"}


def test_despachar_crea_y_repetir_devuelve_el_mismo_despacho(cliente, llaves):
    agente = _token(llaves, "agente_servicio")
    r = cliente.post("/api/v1/despachos", headers=agente, json=PEDIDO)
    assert r.status_code == 201
    assert r.json()["estado"] == "RECOGIDA_PROGRAMADA"
    assert r.json()["numero_guia"] == "5300000001"
    r2 = cliente.post("/api/v1/despachos", headers=agente, json=PEDIDO)
    assert r2.status_code == 200
    assert r2.json()["numero_guia"] == "5300000001"


def test_un_despacho_fallido_responde_502_con_el_error(cliente, llaves, sit):
    sit.fallas["crear_envio"] = ErrorPlataforma(502, "TRANSPORTADORA_SIN_RESPUESTA", "DHL no responde", "dhl")
    r = cliente.post("/api/v1/despachos", headers=_token(llaves, "operador_logistico"), json=PEDIDO)
    assert r.status_code == 502
    assert r.json()["estado"] == "FALLIDO"
    assert r.json()["error"]["codigo"] == "TRANSPORTADORA_SIN_RESPUESTA"


def test_consultar_un_despacho(cliente, llaves):
    agente = _token(llaves, "agente_servicio")
    cliente.post("/api/v1/despachos", headers=agente, json=PEDIDO)
    r = cliente.get("/api/v1/despachos/PED-1001", headers=agente)
    assert r.status_code == 200
    assert r.json()["transportadora"] == "dhl"
    r = cliente.get("/api/v1/despachos/PED-9999", headers=agente)
    assert r.status_code == 404
    assert r.json()["codigo"] == "DESPACHO_NO_ENCONTRADO"


def test_un_cliente_no_puede_despachar(cliente, llaves):
    r = cliente.post("/api/v1/despachos", headers=_token(llaves, "cliente"), json=PEDIDO)
    assert r.status_code == 403


def test_pedido_invalido_es_422_canonico(cliente, llaves):
    r = cliente.post("/api/v1/despachos", headers=_token(llaves, "agente_servicio"), json={**PEDIDO, "paquetes": []})
    assert r.status_code == 422
    assert r.json()["codigo"] == "SOLICITUD_INVALIDA"
