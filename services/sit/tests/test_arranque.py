import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from sit.adaptadores import crear_adaptador
from sit.adaptadores.rest import AdaptadorREST
from sit.adaptadores.soap import AdaptadorSOAP
from sit.catalogo.modelos import TransportadoraBD
from sit.config import Config
from sit.sincronizador import Sincronizador


def _transportadora(codigo: str, adaptador: str) -> TransportadoraBD:
    return TransportadoraBD(codigo=codigo, nombre=codigo, protocolo=adaptador.upper(), version_api="1",
                            adaptador=adaptador, endpoint=f"http://{codigo}", frecuencia_sincronizacion_seg=None,
                            version_equivalencias="1", activa=True)


def test_la_fabrica_elige_el_adaptador_del_catalogo_con_credenciales_por_convencion():
    config = Config(usuario_dhl="tienda", dhl_api_password="clave")
    assert config.credenciales("dhl") == ("tienda", "clave")
    assert config.credenciales("coordinadora") is None
    assert isinstance(crear_adaptador(_transportadora("dhl", "rest"), config), AdaptadorREST)
    assert isinstance(crear_adaptador(_transportadora("coordinadora", "soap"), config), AdaptadorSOAP)
    with pytest.raises(ValueError):
        crear_adaptador(_transportadora("regional", "sftp"), config)


def test_el_sincronizador_programa_solo_las_transportadoras_con_frecuencia(entorno):
    programador = BackgroundScheduler()
    Sincronizador(entorno.servicio, entorno.Sesiones, programador).programar()
    trabajos = {t.id: t for t in programador.get_jobs()}
    assert set(trabajos) == {"sincronizar-coordinadora"}
    assert trabajos["sincronizar-coordinadora"].trigger.interval.total_seconds() == 10
