import pytest
from sqlalchemy.orm import sessionmaker

from comun.bd import crear_motor
from comun.canonico import EstadoEnvio
from sit.catalogo import repositorio
from sit.catalogo.modelos import Base


@pytest.fixture
def Sesiones():
    motor = crear_motor("sqlite://")
    Base.metadata.create_all(motor)
    return sessionmaker(motor, expire_on_commit=False)


def test_la_semilla_se_carga_una_sola_vez(Sesiones):
    with Sesiones() as sesion:
        assert repositorio.cargar_semilla_si_vacio(sesion) is True
        assert repositorio.cargar_semilla_si_vacio(sesion) is False
        assert [t.codigo for t in repositorio.transportadoras(sesion)] == ["coordinadora", "dhl"]


def test_catalogo_de_la_especificacion(Sesiones):
    with Sesiones() as sesion:
        repositorio.cargar_semilla_si_vacio(sesion)
        dhl = repositorio.transportadora(sesion, "dhl")
        coordinadora = repositorio.transportadora(sesion, "coordinadora")
    assert (dhl.protocolo, dhl.adaptador, dhl.frecuencia_sincronizacion_seg) == ("REST", "rest", None)
    assert dhl.endpoint == "http://mock-dhl:8000/mydhlapi"
    assert (coordinadora.protocolo, coordinadora.adaptador, coordinadora.frecuencia_sincronizacion_seg) == \
        ("SOAP", "soap", 10)
    assert coordinadora.endpoint == "http://mock-coordinadora:8088/ws/guias"
    assert dhl.activa and coordinadora.activa
    assert dhl.version_equivalencias == coordinadora.version_equivalencias == "2026.10-1"


def test_tablas_de_dhl(Sesiones):
    with Sesiones() as sesion:
        repositorio.cargar_semilla_si_vacio(sesion)
        tablas = repositorio.tablas_de(sesion, "dhl")
    assert len(tablas.estados) == 8
    assert tablas.estados["WC"] == EstadoEnvio.EN_REPARTO
    assert tablas.estados["OH"] == EstadoEnvio.NOVEDAD
    assert tablas.ciudades["11001"] == "BOG"
    assert "66001" not in tablas.ciudades  # DHL no cubre Pereira
    assert tablas.unidades == {"peso": ("lb", 0.45359237), "longitud": ("in", 2.54)}


def test_tablas_de_coordinadora(Sesiones):
    with Sesiones() as sesion:
        repositorio.cargar_semilla_si_vacio(sesion)
        tablas = repositorio.tablas_de(sesion, "coordinadora")
    assert len(tablas.estados) == 9
    assert {tablas.estados[c] for c in ("3", "4", "5")} == {EstadoEnvio.EN_TRANSITO}
    assert tablas.ciudades["66001"] == "66001000"
    assert len(tablas.ciudades) == 7
    assert tablas.unidades == {"peso": ("g", 0.001), "longitud": ("cm", 1.0)}
