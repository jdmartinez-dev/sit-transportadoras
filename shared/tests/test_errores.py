from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from comun.errores import ErrorPlataforma, registrar_manejador_errores


class Entrada(BaseModel):
    cantidad: int


def _cliente() -> TestClient:
    app = FastAPI()
    registrar_manejador_errores(app)

    @app.get("/falla")
    def falla():
        raise ErrorPlataforma(422, "DESTINO_NO_CUBIERTO", "No cubre 66001", "dhl")

    @app.post("/valida")
    def valida(entrada: Entrada):
        return entrada

    return TestClient(app)


def test_error_plataforma_se_responde_en_formato_canonico():
    r = _cliente().get("/falla")
    assert r.status_code == 422
    assert r.json() == {"codigo": "DESTINO_NO_CUBIERTO", "mensaje": "No cubre 66001", "transportadora": "dhl"}


def test_los_errores_de_validacion_tambien_son_canonicos():
    r = _cliente().post("/valida", json={"cantidad": "muchas"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "SOLICITUD_INVALIDA"
    assert "cantidad" in r.json()["mensaje"]
