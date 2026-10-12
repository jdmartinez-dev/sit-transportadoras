"""Dobles de prueba del SIT: transportadoras falsas que responden en el formato de cada operador."""
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import sessionmaker

from comun.bd import crear_motor
from comun.pruebas import BusFalso, generar_llaves
from sit.catalogo import repositorio
from sit.catalogo.modelos import Base
from sit.motor.motor import Motor
from sit.servicio import ServicioSIT


class AdaptadorFalso:
    def __init__(self, responder):
        self.responder = responder
        self.enviados = []

    def enviar(self, mensaje):
        self.enviados.append(mensaje)
        respuesta = self.responder(mensaje)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def operaciones(self) -> list[str]:
        return [m.operacion for m in self.enviados]


def responder_dhl(mensaje):
    if mensaje.operacion == "POST /rates":
        return {"products": [{"totalPrice": [{"price": 47250.0, "priceCurrency": "COP"}],
                              "weight": {"volumetric": 2.62, "provided": 4.41, "unitOfMeasurement": "imperial"},
                              "totalTransitDays": 2}]}
    if mensaje.operacion == "POST /shipments":
        return {"shipmentTrackingNumber": "5300000001"}
    if mensaje.operacion == "POST /pickups":
        return {"dispatchConfirmationNumbers": ["CBJ000000001"]}
    if mensaje.operacion.startswith("GET /shipments/"):
        return {"shipments": [{"events": [
            {"date": "2026-10-12", "time": "09:00:00", "typeCode": "SD", "description": "Shipment information received"},
            {"date": "2026-10-12", "time": "10:00:00", "typeCode": "PU", "description": "Shipment picked up"}]}]}
    raise AssertionError(f"Operación inesperada: {mensaje.operacion}")


class ResponderCoordinadora:
    """Guarda el historial de estados por guía para simular cambios entre consultas programadas."""

    def __init__(self):
        self.estados = {"900000000001": [{"codigo": "1", "descripcion": "Guía generada",
                                          "fecha": "2026-10-12T09:00:00"}]}

    def __call__(self, mensaje):
        if mensaje.operacion == "CotizarFlete":
            return {"valorFlete": 35100, "pesoLiquidadoGr": 2400, "diasEntrega": 3}
        if mensaje.operacion == "GenerarGuia":
            return "900000000001"
        if mensaje.operacion == "ProgramarRecogida":
            return "REC-000001"
        if mensaje.operacion == "ConsultarEstadoGuia":
            numero = mensaje.cuerpo["codigoRemision"]
            return {"codigoRemision": numero, "estados": list(self.estados[numero])}
        raise AssertionError(f"Operación inesperada: {mensaje.operacion}")


@dataclass
class Entorno:
    Sesiones: sessionmaker
    bus: BusFalso
    adaptadores: dict
    servicio: ServicioSIT


@pytest.fixture
def adaptadores_falsos() -> dict:
    return {"dhl": AdaptadorFalso(responder_dhl), "coordinadora": AdaptadorFalso(ResponderCoordinadora())}


@pytest.fixture
def entorno(adaptadores_falsos) -> Entorno:
    motor_bd = crear_motor("sqlite://")
    Base.metadata.create_all(motor_bd)
    Sesiones = sessionmaker(motor_bd, expire_on_commit=False)
    with Sesiones() as sesion:
        repositorio.cargar_semilla_si_vacio(sesion)
    adaptadores = adaptadores_falsos
    bus = BusFalso()
    motor = Motor(Sesiones, lambda transportadora: adaptadores[transportadora.codigo])
    return Entorno(Sesiones, bus, adaptadores, ServicioSIT(Sesiones, motor, bus))


@pytest.fixture(scope="session")
def llaves():
    return generar_llaves()
