from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from comun.bd import crear_motor
from comun.canonico import Cotizacion, Direccion, EstadoEnvio, Guia, Recogida, ahora
from comun.pruebas import BusFalso, generar_llaves
from despachos.modelos import Base
from despachos.orquestador import Orquestador

ORIGEN = Direccion(divipola="11001", direccion="Calle 13 # 68-50", nombre="Bodega", telefono="6015550100")


class SitFalso:
    """Doble del ClienteSIT: registra las llamadas y puede fallar una vez por operación."""

    def __init__(self):
        self.llamadas = []
        self.fallas = {}
        self.cotizaciones = [
            Cotizacion(transportadora="dhl", valor_cop=47250, peso_facturable_kg=2.0, dias_estimados=2),
            Cotizacion(transportadora="coordinadora", valor_cop=35100, peso_facturable_kg=2.4, dias_estimados=3),
        ]

    def _registrar(self, nombre, solicitud):
        self.llamadas.append((nombre, solicitud))
        if nombre in self.fallas:
            raise self.fallas.pop(nombre)

    def cotizar(self, solicitud):
        self._registrar("cotizar", solicitud)
        if solicitud.transportadora:
            return [c for c in self.cotizaciones if c.transportadora == solicitud.transportadora]
        return list(self.cotizaciones)

    def crear_envio(self, solicitud):
        self._registrar("crear_envio", solicitud)
        numero = "5300000001" if solicitud.transportadora == "dhl" else "900000000001"
        return Guia(numero_guia=numero, transportadora=solicitud.transportadora, pedido_id=solicitud.pedido_id,
                    estado=EstadoEnvio.CREADA, creada_en=ahora())

    def programar_recogida(self, solicitud):
        self._registrar("programar_recogida", solicitud)
        return Recogida(numero_guia=solicitud.numero_guia, transportadora="coordinadora",
                        confirmacion="REC-000001", fecha=solicitud.fecha, franja=solicitud.franja)

    def nombres(self) -> list[str]:
        return [nombre for nombre, _ in self.llamadas]


@pytest.fixture
def Sesiones():
    motor = crear_motor("sqlite://")
    Base.metadata.create_all(motor)
    return sessionmaker(motor, expire_on_commit=False)


@pytest.fixture
def sit():
    return SitFalso()


@pytest.fixture
def bus():
    return BusFalso()


@pytest.fixture
def orquestador(Sesiones, sit, bus):
    return Orquestador(Sesiones, sit, bus, ORIGEN, hoy=lambda: date(2026, 10, 11))


@pytest.fixture(scope="session")
def llaves():
    return generar_llaves()
