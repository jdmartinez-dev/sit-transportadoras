import pytest

from comun.canonico import EstadoEnvio
from comun.errores import ErrorPlataforma
from sit.motor.equivalencias import TablasEquivalencia


@pytest.fixture
def tablas():
    return TablasEquivalencia(
        transportadora="dhl",
        estados={"PU": EstadoEnvio.RECOGIDA, "AF": EstadoEnvio.EN_TRANSITO, "DF": EstadoEnvio.EN_TRANSITO},
        ciudades={"11001": "BOG", "05001": "MDE"},
        unidades={"peso": ("lb", 0.45359237), "longitud": ("in", 2.54)},
    )


def test_varios_codigos_del_operador_apuntan_al_mismo_estado(tablas):
    assert tablas.traducir_estado("AF").estado == EstadoEnvio.EN_TRANSITO
    assert tablas.traducir_estado("DF").estado == EstadoEnvio.EN_TRANSITO
    assert not tablas.traducir_estado("AF").sin_equivalencia


def test_codigo_sin_equivalencia_se_traduce_como_novedad(tablas):
    traduccion = tablas.traducir_estado("XX")
    assert traduccion.estado == EstadoEnvio.NOVEDAD
    assert traduccion.sin_equivalencia


def test_ciudad_canonica_a_codigo_del_operador(tablas):
    assert tablas.ciudad_a_operador("05001") == "MDE"


def test_ciudad_sin_cobertura_es_error_canonico(tablas):
    with pytest.raises(ErrorPlataforma) as exc:
        tablas.ciudad_a_operador("66001")
    assert exc.value.estado_http == 422
    assert exc.value.error.codigo == "DESTINO_NO_CUBIERTO"
    assert exc.value.error.transportadora == "dhl"


def test_conversion_de_unidades_en_ambos_sentidos(tablas):
    assert tablas.a_unidad_operador("peso", 2.0) == pytest.approx(4.40925, rel=1e-4)
    assert tablas.a_unidad_canonica("longitud", 10) == pytest.approx(25.4)
