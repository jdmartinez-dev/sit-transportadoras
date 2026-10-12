import base64

import jwt
import pytest
from fastapi.testclient import TestClient

from auth.config import Config
from auth.main import crear_app
from comun.pruebas import generar_llaves

CLAVE_DEMO = "clave-demo"


@pytest.fixture(scope="module")
def llaves():
    return generar_llaves()


@pytest.fixture
def cliente(llaves):
    config = Config(url_bd="sqlite://", jwt_privada=llaves[0], usuarios_demo_password=CLAVE_DEMO,
                    cliente_despachos_secret="secreto-despachos", cliente_mock_dhl_secret="secreto-dhl",
                    rondas_bcrypt=4)
    with TestClient(crear_app(config)) as c:
        yield c


def _datos(token: str, publica: str) -> dict:
    return jwt.decode(token, publica, algorithms=["RS256"], issuer="auth-plataforma")


def test_flujo_password_emite_un_token_con_el_rol_del_usuario(cliente, llaves):
    r = cliente.post("/oauth/token", data={"grant_type": "password", "username": "agente1", "password": CLAVE_DEMO})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["token_type"] == "Bearer" and cuerpo["expires_in"] == 900
    datos = _datos(cuerpo["access_token"], llaves[1])
    assert datos["sub"] == "agente1"
    assert datos["roles"] == ["agente_servicio"]
    assert r.headers["cache-control"] == "no-store"


def test_contrasena_incorrecta_es_invalid_grant(cliente):
    r = cliente.post("/oauth/token", data={"grant_type": "password", "username": "agente1", "password": "otra"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_grant"


def test_credenciales_de_cliente_en_el_cuerpo(cliente, llaves):
    r = cliente.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": "despachos",
                                           "client_secret": "secreto-despachos"})
    assert r.status_code == 200
    datos = _datos(r.json()["access_token"], llaves[1])
    assert datos["sub"] == "despachos"
    assert datos["roles"] == ["operador_logistico"]


def test_credenciales_de_cliente_con_autenticacion_basica(cliente, llaves):
    basica = base64.b64encode(b"mock-dhl:secreto-dhl").decode()
    r = cliente.post("/oauth/token", data={"grant_type": "client_credentials"},
                     headers={"Authorization": f"Basic {basica}"})
    assert r.status_code == 200
    assert _datos(r.json()["access_token"], llaves[1])["sub"] == "mock-dhl"


def test_cliente_con_secreto_incorrecto_es_401(cliente):
    r = cliente.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": "despachos",
                                           "client_secret": "incorrecto"})
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_client"


def test_un_usuario_no_sirve_como_cliente_de_servicio(cliente):
    r = cliente.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": "agente1",
                                           "client_secret": CLAVE_DEMO})
    assert r.status_code == 401


def test_flujo_no_soportado(cliente):
    r = cliente.post("/oauth/token", data={"grant_type": "authorization_code"})
    assert r.status_code == 400
    assert r.json()["error"] == "unsupported_grant_type"


def test_sin_grant_type_es_invalid_request(cliente):
    r = cliente.post("/oauth/token", data={})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_request"


def test_salud(cliente):
    assert cliente.get("/salud").json() == {"estado": "ok"}
