import pytest
from fastapi.testclient import TestClient

from mock_dhl.config import Config
from mock_dhl.main import crear_app
from mock_dhl.tarifas import peso_facturable_lb, peso_volumetrico_lb, precio_cop

PAQUETE = {"weight": 4.41, "dimensions": {"length": 11.8, "width": 7.9, "height": 3.9}}
RECEPTOR = {"cityCode": "MDE", "name": "Ana Pérez", "address": "Carrera 43A # 1-50", "phone": "3001234567"}


class NotificadorFalso:
    def __init__(self):
        self.avisos = []

    def notificar(self, numero, evento):
        self.avisos.append((numero, evento["typeCode"]))


@pytest.fixture
def notificador():
    return NotificadorFalso()


@pytest.fixture
def cliente(notificador):
    with TestClient(crear_app(Config(usuario_api="tienda", dhl_api_password="clave-dhl"), notificador)) as c:
        c.auth = ("tienda", "clave-dhl")
        yield c


def _crear_envio(cliente) -> str:
    r = cliente.post("/mydhlapi/shipments", json={"originCityCode": "BOG", "receiver": RECEPTOR,
                                                  "packages": [PAQUETE], "reference": "PED-1"})
    assert r.status_code == 201
    return r.json()["shipmentTrackingNumber"]


def test_peso_volumetrico_y_facturable_en_libras():
    assert peso_volumetrico_lb(10, 10, 10) == 7.19
    assert peso_facturable_lb(2.0, 10, 10, 10) == 7.5
    assert peso_facturable_lb(8.1, 10, 10, 10) == 8.5


def test_el_precio_sube_entre_ciudades_distintas():
    assert precio_cop(4.5, "BOG", "BOG") == 33750
    assert precio_cop(4.5, "BOG", "MDE") == 47250


def test_las_rutas_de_la_api_exigen_autenticacion(notificador):
    with TestClient(crear_app(Config(dhl_api_password="clave-dhl"), notificador)) as c:
        r = c.post("/mydhlapi/rates", json={"originCityCode": "BOG", "destinationCityCode": "MDE",
                                            "packages": [PAQUETE]})
    assert r.status_code == 401


def test_tarifa_en_cop_con_pesos_imperiales(cliente):
    r = cliente.post("/mydhlapi/rates", json={"originCityCode": "BOG", "destinationCityCode": "MDE",
                                              "packages": [PAQUETE]})
    assert r.status_code == 200
    producto = r.json()["products"][0]
    assert producto["totalPrice"][0] == {"currencyType": "BILLC", "priceCurrency": "COP", "price": 47250.0}
    assert producto["weight"] == {"volumetric": 2.62, "provided": 4.41, "unitOfMeasurement": "imperial"}
    assert producto["totalTransitDays"] == 2


def test_ciudad_sin_cobertura_es_400(cliente):
    r = cliente.post("/mydhlapi/rates", json={"originCityCode": "BOG", "destinationCityCode": "PEI",
                                              "packages": [PAQUETE]})
    assert r.status_code == 400


def test_crear_envio_devuelve_10_digitos_y_notifica_sd(cliente, notificador):
    numero = _crear_envio(cliente)
    assert len(numero) == 10 and numero.isdigit()
    assert notificador.avisos == [(numero, "SD")]


def test_cambio_de_estado_de_demo_queda_en_el_rastreo_y_se_notifica(cliente, notificador):
    numero = _crear_envio(cliente)
    r = cliente.post(f"/demo/envios/{numero}/estado", json={"typeCode": "XX"})
    assert r.status_code == 200
    eventos = cliente.get(f"/mydhlapi/shipments/{numero}/tracking").json()["shipments"][0]["events"]
    assert [e["typeCode"] for e in eventos] == ["SD", "XX"]
    assert set(eventos[0]) == {"date", "time", "typeCode", "description"}
    assert notificador.avisos[-1] == (numero, "XX")


def test_programar_recogida(cliente):
    numero = _crear_envio(cliente)
    r = cliente.post("/mydhlapi/pickups", json={"shipmentTrackingNumber": numero,
                                                "plannedPickupDateAndTime": "2026-10-12T09:00:00-05:00"})
    assert r.status_code == 201
    assert r.json() == {"dispatchConfirmationNumbers": ["CBJ000000001"]}


def test_guia_desconocida_es_404(cliente):
    assert cliente.get("/mydhlapi/shipments/0000000000/tracking").status_code == 404
