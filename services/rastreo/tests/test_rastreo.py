from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from comun.bd import crear_motor
from comun.canonico import ZONA_COLOMBIA, EnvioEstadoActualizado, EstadoEnvio
from comun.errores import ErrorPlataforma
from comun.eventos import ENVIO_ESTADO_ACTUALIZADO, Evento
from comun.pruebas import BusFalso, token_de_prueba
from rastreo.config import Config
from rastreo.main import crear_app
from rastreo.modelos import Base
from rastreo.servicio import ServicioRastreo, crear_manejador

GUIA = "900000000001"


def _evento(estado: EstadoEnvio, hora: int, numero: str = GUIA) -> Evento:
    datos = EnvioEstadoActualizado(numero_guia=numero, transportadora="coordinadora", estado=estado,
                                   ocurrido_en=datetime(2026, 10, 12, hora, 0, tzinfo=ZONA_COLOMBIA))
    return Evento(tipo=ENVIO_ESTADO_ACTUALIZADO, datos=datos.model_dump(mode="json"))


@pytest.fixture
def servicio() -> ServicioRastreo:
    motor = crear_motor("sqlite://")
    Base.metadata.create_all(motor)
    return ServicioRastreo(sessionmaker(motor, expire_on_commit=False))


@pytest.fixture
def cliente(llaves):
    app = crear_app(Config(url_bd="sqlite://", jwt_publica=llaves[1]), bus=BusFalso(), iniciar_fondo=False)
    with TestClient(app) as c:
        yield c


def _token(llaves, rol: str) -> dict:
    return {"Authorization": f"Bearer {token_de_prueba(llaves[0], 'usuario', [rol])}"}


def test_el_historial_queda_en_orden_cronologico(servicio):
    servicio.registrar(_evento(EstadoEnvio.EN_REPARTO, 15))
    servicio.registrar(_evento(EstadoEnvio.CREADA, 9))
    rastreo = servicio.consultar(GUIA)
    assert [e.estado for e in rastreo.historial] == [EstadoEnvio.CREADA, EstadoEnvio.EN_REPARTO]
    assert rastreo.estado_actual == EstadoEnvio.EN_REPARTO
    assert rastreo.transportadora == "coordinadora"


def test_un_evento_repetido_no_duplica_el_historial(servicio):
    evento = _evento(EstadoEnvio.CREADA, 9)
    assert servicio.registrar(evento) is True
    assert servicio.registrar(evento) is False
    assert len(servicio.consultar(GUIA).historial) == 1


def test_guia_sin_estados_es_404(servicio):
    with pytest.raises(ErrorPlataforma) as exc:
        servicio.consultar("0000000000")
    assert exc.value.estado_http == 404
    assert exc.value.error.codigo == "GUIA_NO_ENCONTRADA"


def test_el_manejador_descarta_un_evento_invalido(servicio):
    crear_manejador(servicio)(Evento(tipo=ENVIO_ESTADO_ACTUALIZADO, datos={"numero_guia": GUIA}))
    with pytest.raises(ErrorPlataforma):
        servicio.consultar(GUIA)


def test_el_cliente_consulta_el_rastreo_con_fechas_de_colombia(cliente, llaves):
    cliente.app.state.servicio.registrar(_evento(EstadoEnvio.CREADA, 9))
    r = cliente.get(f"/api/v1/rastreo/{GUIA}", headers=_token(llaves, "cliente"))
    assert r.status_code == 200
    assert r.json() == {"numero_guia": GUIA, "transportadora": "coordinadora", "estado_actual": "CREADA",
                        "historial": [{"estado": "CREADA", "ocurrido_en": "2026-10-12T09:00:00-05:00"}]}


def test_rastreo_exige_token_y_rol(cliente, llaves):
    assert cliente.get(f"/api/v1/rastreo/{GUIA}").status_code == 401
    assert cliente.get(f"/api/v1/rastreo/{GUIA}", headers=_token(llaves, "admin_integraciones")).status_code == 403


def test_guia_desconocida_por_la_api_es_404_canonico(cliente, llaves):
    r = cliente.get("/api/v1/rastreo/0000000000", headers=_token(llaves, "agente_servicio"))
    assert r.status_code == 404
    assert r.json()["codigo"] == "GUIA_NO_ENCONTRADA"
