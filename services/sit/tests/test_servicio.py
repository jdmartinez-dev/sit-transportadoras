from datetime import date

import pytest
from sqlalchemy import func, select

from comun.canonico import (Direccion, EstadoEnvio, Franja, Paquete, SolicitudCotizacion, SolicitudEnvio,
                            SolicitudRecogida)
from comun.errores import ErrorPlataforma
from comun.eventos import ENVIO_ESTADO_ACTUALIZADO
from sit.catalogo.modelos import EstadoSinEquivalencia, GuiaBD

PAQUETE = Paquete(peso_kg=2.0, largo_cm=30, ancho_cm=20, alto_cm=10)
ORIGEN = Direccion(divipola="11001", direccion="Calle 13 # 68-50", nombre="Bodega", telefono="6015550100")
DESTINO = Direccion(divipola="05001", direccion="Carrera 43A # 1-50", nombre="Ana Pérez", telefono="3001234567")


def _envio(transportadora: str, pedido: str = "PED-1") -> SolicitudEnvio:
    return SolicitudEnvio(pedido_id=pedido, transportadora=transportadora, origen=ORIGEN, destino=DESTINO,
                          paquetes=[PAQUETE])


def _webhook(codigo: str, hora: str = "10:00:00", numero: str = "5300000001") -> dict:
    return {"shipmentTrackingNumber": numero,
            "event": {"date": "2026-10-12", "time": hora, "typeCode": codigo, "description": "-"}}


def _estados_publicados(bus) -> list[str]:
    return [datos.estado.value for tipo, datos in bus.publicados if tipo == ENVIO_ESTADO_ACTUALIZADO]


def test_cotiza_con_todas_las_activas_en_cop_y_kg(entorno):
    cotizaciones = entorno.servicio.cotizar(SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE]))
    por_codigo = {c.transportadora: c for c in cotizaciones}
    assert (por_codigo["dhl"].valor_cop, por_codigo["dhl"].peso_facturable_kg) == (47250, 2.0)
    assert (por_codigo["coordinadora"].valor_cop, por_codigo["coordinadora"].peso_facturable_kg) == (35100, 2.4)


def test_omite_la_transportadora_sin_cobertura(entorno):
    cotizaciones = entorno.servicio.cotizar(SolicitudCotizacion(origen="11001", destino="66001", paquetes=[PAQUETE]))
    assert [c.transportadora for c in cotizaciones] == ["coordinadora"]
    assert entorno.adaptadores["dhl"].enviados == []


def test_transportadora_forzada_devuelve_su_propio_error(entorno):
    with pytest.raises(ErrorPlataforma) as exc:
        entorno.servicio.cotizar(SolicitudCotizacion(origen="11001", destino="66001", paquetes=[PAQUETE],
                                                     transportadora="dhl"))
    assert exc.value.estado_http == 422
    assert exc.value.error.codigo == "DESTINO_NO_CUBIERTO"


def test_sin_ninguna_cotizacion_es_502(entorno):
    caida = ErrorPlataforma(502, "TRANSPORTADORA_SIN_RESPUESTA", "caída")
    for adaptador in entorno.adaptadores.values():
        adaptador.responder = lambda mensaje: caida
    with pytest.raises(ErrorPlataforma) as exc:
        entorno.servicio.cotizar(SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE]))
    assert exc.value.error.codigo == "SIN_COTIZACIONES"


def test_crear_guia_registra_la_guia_sin_estado_aun(entorno):
    guia = entorno.servicio.crear_guia(_envio("coordinadora"))
    assert (guia.numero_guia, guia.transportadora, guia.estado) == ("900000000001", "coordinadora",
                                                                     EstadoEnvio.CREADA)
    with entorno.Sesiones() as sesion:
        fila = sesion.get(GuiaBD, "900000000001")
    assert (fila.pedido_id, fila.ultimo_estado) == ("PED-1", None)


def test_transportadora_desconocida_es_422(entorno):
    with pytest.raises(ErrorPlataforma) as exc:
        entorno.servicio.crear_guia(_envio("fedex"))
    assert exc.value.error.codigo == "TRANSPORTADORA_DESCONOCIDA"


def test_la_recogida_usa_la_transportadora_de_la_guia(entorno):
    entorno.servicio.crear_guia(_envio("dhl"))
    recogida = entorno.servicio.programar_recogida(
        SolicitudRecogida(numero_guia="5300000001", fecha=date(2026, 10, 12), franja=Franja.MANANA))
    assert (recogida.transportadora, recogida.confirmacion) == ("dhl", "CBJ000000001")
    assert entorno.adaptadores["dhl"].operaciones()[-1] == "POST /pickups"


def test_recogida_de_una_guia_desconocida_es_404(entorno):
    with pytest.raises(ErrorPlataforma) as exc:
        entorno.servicio.programar_recogida(
            SolicitudRecogida(numero_guia="0", fecha=date(2026, 10, 12), franja=Franja.MANANA))
    assert exc.value.estado_http == 404
    assert exc.value.error.codigo == "GUIA_NO_ENCONTRADA"


def test_el_webhook_publica_solo_cuando_cambia_el_estado_canonico(entorno):
    entorno.servicio.crear_guia(_envio("dhl"))
    for codigo in ("SD", "PU", "AF", "DF"):
        entorno.servicio.procesar_webhook("dhl", _webhook(codigo))
    assert _estados_publicados(entorno.bus) == ["CREADA", "RECOGIDA", "EN_TRANSITO"]
    _, ultimo = entorno.bus.publicados[-1]
    assert ultimo.numero_guia == "5300000001" and ultimo.transportadora == "dhl"


def test_webhook_antes_de_registrar_la_guia(entorno):
    entorno.servicio.procesar_webhook("dhl", _webhook("SD"))  # llega antes que la respuesta de crear la guía
    entorno.servicio.crear_guia(_envio("dhl", pedido="PED-7"))
    with entorno.Sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(GuiaBD)) == 1
        fila = sesion.get(GuiaBD, "5300000001")
    assert (fila.pedido_id, fila.ultimo_estado) == ("PED-7", "CREADA")
    assert _estados_publicados(entorno.bus) == ["CREADA"]


def test_un_codigo_sin_equivalencia_se_publica_como_novedad_y_se_registra_una_vez(entorno):
    entorno.servicio.crear_guia(_envio("dhl"))
    entorno.servicio.procesar_webhook("dhl", _webhook("XX", "10:00:00"))
    entorno.servicio.procesar_webhook("dhl", _webhook("XX", "10:05:00"))
    assert _estados_publicados(entorno.bus) == ["NOVEDAD"]
    with entorno.Sesiones() as sesion:
        registros = list(sesion.scalars(select(EstadoSinEquivalencia)))
    assert [(r.transportadora, r.codigo_operador, r.numero_guia) for r in registros] == [("dhl", "XX", "5300000001")]


def test_sincronizar_consulta_las_guias_activas_y_publica_el_ultimo_estado(entorno):
    entorno.servicio.crear_guia(_envio("coordinadora"))
    responder = entorno.adaptadores["coordinadora"].responder
    entorno.servicio.sincronizar("coordinadora")
    responder.estados["900000000001"].append({"codigo": "4", "descripcion": "En transporte",
                                              "fecha": "2026-10-12T11:00:00"})
    entorno.servicio.sincronizar("coordinadora")
    entorno.servicio.sincronizar("coordinadora")  # sin cambios: no publica
    responder.estados["900000000001"].append({"codigo": "7", "descripcion": "Entregada",
                                              "fecha": "2026-10-12T16:00:00"})
    entorno.servicio.sincronizar("coordinadora")
    assert _estados_publicados(entorno.bus) == ["CREADA", "EN_TRANSITO", "ENTREGADA"]
    consultas = entorno.adaptadores["coordinadora"].operaciones().count("ConsultarEstadoGuia")
    entorno.servicio.sincronizar("coordinadora")  # ENTREGADA es final: ya no se consulta
    assert entorno.adaptadores["coordinadora"].operaciones().count("ConsultarEstadoGuia") == consultas


def test_varios_cambios_entre_dos_consultas_se_publican_en_orden(entorno):
    entorno.servicio.crear_guia(_envio("coordinadora"))
    responder = entorno.adaptadores["coordinadora"].responder
    responder.estados["900000000001"] += [
        {"codigo": "4", "descripcion": "En transporte", "fecha": "2026-10-12T11:00:00"},
        {"codigo": "6", "descripcion": "En reparto", "fecha": "2026-10-12T15:00:00"}]
    entorno.servicio.sincronizar("coordinadora")  # la primera consulta ya encuentra tres eventos
    assert _estados_publicados(entorno.bus) == ["CREADA", "EN_TRANSITO", "EN_REPARTO"]
    entorno.servicio.sincronizar("coordinadora")  # nada nuevo: no publica de nuevo
    assert len(entorno.bus.publicados) == 3
    with entorno.Sesiones() as sesion:
        assert sesion.get(GuiaBD, "900000000001").eventos_leidos == 3


def test_consultar_estados_traduce_el_historial_del_operador(entorno):
    entorno.servicio.crear_guia(_envio("dhl"))
    estados = entorno.servicio.consultar_estados("5300000001")
    assert [e.estado for e in estados] == [EstadoEnvio.CREADA, EstadoEnvio.RECOGIDA]
    assert entorno.bus.publicados == []


def test_webhook_de_una_transportadora_sin_webhook_es_422(entorno):
    with pytest.raises(ErrorPlataforma) as exc:
        entorno.servicio.procesar_webhook("coordinadora", {})
    assert exc.value.error.codigo == "TRANSPORTADORA_DESCONOCIDA"


def test_respuesta_inesperada_del_operador_es_502(entorno):
    entorno.adaptadores["dhl"].responder = lambda mensaje: {"inesperado": True}
    with pytest.raises(ErrorPlataforma) as exc:
        entorno.servicio.cotizar(SolicitudCotizacion(origen="11001", destino="05001", paquetes=[PAQUETE],
                                                     transportadora="dhl"))
    assert exc.value.estado_http == 502
    assert exc.value.error.codigo == "TRANSPORTADORA_RECHAZO"


def test_si_el_bus_falla_el_estado_se_vuelve_a_intentar(entorno):
    entorno.servicio.crear_guia(_envio("dhl"))
    entorno.bus.falla = ErrorPlataforma(503, "BUS_NO_DISPONIBLE", "Redis caído")
    with pytest.raises(ErrorPlataforma):
        entorno.servicio.procesar_webhook("dhl", _webhook("PU"))
    with entorno.Sesiones() as sesion:
        assert sesion.get(GuiaBD, "5300000001").ultimo_estado is None
    entorno.bus.falla = None
    entorno.servicio.procesar_webhook("dhl", _webhook("PU"))
    assert _estados_publicados(entorno.bus) == ["RECOGIDA"]
