from pathlib import Path

import pytest
import requests
from lxml import etree
from zeep.transports import Transport

from comun.errores import ErrorPlataforma
from sit.adaptadores.soap import AdaptadorSOAP
from sit.motor.tipos import MensajeOperador

WSDL = str(Path(__file__).resolve().parents[3] / "mocks" / "coordinadora" / "coordinadora.wsdl")
ENDPOINT = "http://mock-coordinadora:8088/ws/guias"
SOBRE = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
         'xmlns:g="http://coordinadora.simulada/guias"><soapenv:Body>{}</soapenv:Body></soapenv:Envelope>')
COTIZACION = SOBRE.format("<g:CotizarFleteRespuesta><g:valorFlete>35100</g:valorFlete>"
                          "<g:pesoLiquidadoGr>2400</g:pesoLiquidadoGr><g:diasEntrega>3</g:diasEntrega>"
                          "</g:CotizarFleteRespuesta>")
FALLO = SOBRE.format("<soapenv:Fault><faultcode>soapenv:Client</faultcode>"
                     "<faultstring>Remisión no encontrada: 1</faultstring></soapenv:Fault>")
PIEZA = {"pesoGr": 2000, "largoCm": 30, "anchoCm": 20, "altoCm": 10}
COTIZAR = MensajeOperador("CotizarFlete", {"ciudadOrigen": "11001000", "ciudadDestino": "05001000",
                                           "piezas": [PIEZA]})


class TransporteFalso(Transport):
    """Responde con XML preparado (o lanza una excepción) en lugar de llamar a SoapUI."""

    def __init__(self, respuestas, fallar_carga: bool = False):
        super().__init__()
        self.respuestas = list(respuestas)
        self.enviados = []
        self.fallar_carga = fallar_carga

    def load(self, url):
        if self.fallar_carga:
            self.fallar_carga = False
            raise requests.exceptions.ConnectionError("SoapUI todavía no arranca")
        return super().load(url)

    def post_xml(self, address, envelope, headers):
        self.enviados.append((address, etree.tostring(envelope, encoding="unicode")))
        siguiente = self.respuestas.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        respuesta = requests.Response()
        respuesta.status_code = 200
        respuesta._content = siguiente.encode("utf-8")
        respuesta.headers["Content-Type"] = "text/xml; charset=utf-8"
        return respuesta


def _adaptador(transporte, esperas, reintentos=3) -> AdaptadorSOAP:
    return AdaptadorSOAP("coordinadora", ENDPOINT, reintentos=reintentos, transporte=transporte, wsdl=WSDL,
                         dormir=esperas.append)


def test_invoca_la_operacion_con_la_direccion_del_catalogo():
    transporte = TransporteFalso([COTIZACION])
    respuesta = _adaptador(transporte, []).enviar(COTIZAR)
    assert respuesta == {"valorFlete": 35100, "pesoLiquidadoGr": 2400, "diasEntrega": 3}
    direccion, xml = transporte.enviados[0]
    assert direccion == ENDPOINT
    assert "<ns0:ciudadOrigen>11001000</ns0:ciudadOrigen>" in xml


def test_una_respuesta_de_un_solo_elemento_llega_como_valor():
    transporte = TransporteFalso([SOBRE.format(
        "<g:GenerarGuiaRespuesta><g:codigoRemision>900000000001</g:codigoRemision></g:GenerarGuiaRespuesta>")])
    destinatario = {"nombre": "Ana", "direccion": "Cra 1", "telefono": "3001234567", "ciudad": "05001000"}
    respuesta = _adaptador(transporte, []).enviar(MensajeOperador("GenerarGuia", {
        "referencia": "PED-1", "ciudadOrigen": "11001000", "destinatario": destinatario, "piezas": [PIEZA]}))
    assert respuesta == "900000000001"


def test_un_soap_fault_es_rechazo_sin_reintentos():
    esperas = []
    with pytest.raises(ErrorPlataforma) as exc:
        _adaptador(TransporteFalso([FALLO]), esperas).enviar(
            MensajeOperador("ConsultarEstadoGuia", {"codigoRemision": "1"}))
    assert exc.value.estado_http == 502
    assert exc.value.error.codigo == "TRANSPORTADORA_RECHAZO"
    assert esperas == []


def test_reintenta_si_la_transportadora_no_responde():
    esperas = []
    transporte = TransporteFalso([requests.exceptions.ConnectionError("caído"), COTIZACION])
    assert _adaptador(transporte, esperas).enviar(COTIZAR)["valorFlete"] == 35100
    assert esperas == [0.5]


def test_agota_los_reintentos_con_error_canonico():
    esperas = []
    transporte = TransporteFalso([requests.exceptions.ConnectionError("caído")] * 3)
    with pytest.raises(ErrorPlataforma) as exc:
        _adaptador(transporte, esperas).enviar(COTIZAR)
    assert exc.value.error.codigo == "TRANSPORTADORA_SIN_RESPUESTA"
    assert esperas == [0.5, 1.0]


def test_wsdl_inalcanzable_no_queda_en_cache_y_se_recupera():
    transporte = TransporteFalso([COTIZACION], fallar_carga=True)
    adaptador = _adaptador(transporte, [], reintentos=1)
    with pytest.raises(ErrorPlataforma) as exc:
        adaptador.enviar(COTIZAR)
    assert exc.value.error.codigo == "TRANSPORTADORA_SIN_RESPUESTA"
    assert adaptador.enviar(COTIZAR)["diasEntrega"] == 3


def test_un_xml_inesperado_es_rechazo_canonico_sin_reintentos():
    esperas = []
    raro = SOBRE.format("<g:CotizarFleteRespuesta><g:inesperado>1</g:inesperado></g:CotizarFleteRespuesta>")
    with pytest.raises(ErrorPlataforma) as exc:
        _adaptador(TransporteFalso([raro]), esperas).enviar(COTIZAR)
    assert exc.value.estado_http == 502
    assert exc.value.error.codigo == "TRANSPORTADORA_RECHAZO"
    assert esperas == []
