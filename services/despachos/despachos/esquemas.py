from pydantic import AwareDatetime, BaseModel

from comun.canonico import Cotizacion, ErrorCanonico
from despachos.modelos import DespachoBD, EstadoDespacho


class Despacho(BaseModel):
    pedido_id: str
    estado: EstadoDespacho
    transportadora: str | None
    numero_guia: str | None
    confirmacion_recogida: str | None
    cotizaciones: list[Cotizacion]
    error: ErrorCanonico | None
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime


def a_esquema(despacho: DespachoBD) -> Despacho:
    return Despacho(
        pedido_id=despacho.pedido_id,
        estado=EstadoDespacho(despacho.estado),
        transportadora=despacho.transportadora,
        numero_guia=despacho.numero_guia,
        confirmacion_recogida=despacho.confirmacion_recogida,
        cotizaciones=[Cotizacion.model_validate(c) for c in despacho.cotizaciones or []],
        error=ErrorCanonico.model_validate(despacho.error) if despacho.error else None,
        creado_en=despacho.creado_en,
        actualizado_en=despacho.actualizado_en,
    )
