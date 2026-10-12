import pytest

from comun.pruebas import generar_llaves


@pytest.fixture(scope="session")
def llaves():
    return generar_llaves()
