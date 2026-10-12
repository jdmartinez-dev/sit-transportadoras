from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from comun.errores import registrar_manejador_errores
from comun.pruebas import generar_llaves, token_de_prueba
from comun.seguridad import Principal, Rol, ValidadorJWT


def _cliente(publica: str) -> TestClient:
    validador = ValidadorJWT(publica)
    app = FastAPI()
    registrar_manejador_errores(app)

    @app.get("/operacion")
    def operacion(principal: Principal = Depends(validador.requiere_roles(Rol.OPERADOR_LOGISTICO))):
        return {"sub": principal.sub}

    return TestClient(app)


def _con(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_token_valido_con_el_rol_permitido(llaves):
    privada, publica = llaves
    r = _cliente(publica).get("/operacion", headers=_con(token_de_prueba(privada, "despachos", ["operador_logistico"])))
    assert r.status_code == 200
    assert r.json() == {"sub": "despachos"}


def test_sin_token_es_401(llaves):
    r = _cliente(llaves[1]).get("/operacion")
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_AUSENTE"


def test_token_vencido_es_401(llaves):
    privada, publica = llaves
    token = token_de_prueba(privada, "despachos", ["operador_logistico"], vence_en_seg=-10)
    r = _cliente(publica).get("/operacion", headers=_con(token))
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_VENCIDO"


def test_token_firmado_con_otra_llave_es_401(llaves):
    otra_privada, _ = generar_llaves()
    token = token_de_prueba(otra_privada, "intruso", ["operador_logistico"])
    r = _cliente(llaves[1]).get("/operacion", headers=_con(token))
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_INVALIDO"


def test_token_de_otro_emisor_es_401(llaves):
    privada, publica = llaves
    token = token_de_prueba(privada, "despachos", ["operador_logistico"], emisor="otro-emisor")
    r = _cliente(publica).get("/operacion", headers=_con(token))
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_INVALIDO"


def test_rol_no_permitido_es_403(llaves):
    privada, publica = llaves
    r = _cliente(publica).get("/operacion", headers=_con(token_de_prueba(privada, "cliente1", ["cliente"])))
    assert r.status_code == 403
    assert r.json()["codigo"] == "ACCESO_DENEGADO"
