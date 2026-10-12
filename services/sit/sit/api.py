"""API canónica del SIT (Tabla 2): hacia adentro solo modelo canónico, REST/JSON y JWT."""
from fastapi import APIRouter, Body, Depends, Response

from comun.canonico import (Cotizacion, EventoEstado, Guia, Recogida, SolicitudCotizacion, SolicitudEnvio,
                            SolicitudRecogida, Transportadora)
from comun.seguridad import Rol, ValidadorJWT
from sit.catalogo import repositorio
from sit.servicio import ServicioSIT


def crear_router(servicio: ServicioSIT, Sesiones, validador: ValidadorJWT) -> APIRouter:
    operacion = validador.requiere_roles(Rol.OPERADOR_LOGISTICO, Rol.ADMIN_INTEGRACIONES)
    webhook = validador.requiere_roles(Rol.OPERADOR_LOGISTICO)
    router = APIRouter(prefix="/api/v1")

    @router.post("/cotizaciones", response_model=list[Cotizacion], dependencies=[Depends(operacion)])
    def cotizar(solicitud: SolicitudCotizacion):
        return servicio.cotizar(solicitud)

    @router.post("/envios", response_model=Guia, status_code=201, dependencies=[Depends(operacion)])
    def crear_envio(solicitud: SolicitudEnvio):
        return servicio.crear_guia(solicitud)

    @router.post("/recogidas", response_model=Recogida, status_code=201, dependencies=[Depends(operacion)])
    def programar_recogida(solicitud: SolicitudRecogida):
        return servicio.programar_recogida(solicitud)

    @router.get("/envios/{numero_guia}/estados", response_model=list[EventoEstado],
                dependencies=[Depends(operacion)])
    def consultar_estados(numero_guia: str):
        return servicio.consultar_estados(numero_guia)

    @router.post("/webhooks/{transportadora}", status_code=204, dependencies=[Depends(webhook)])
    def recibir_webhook(transportadora: str, cuerpo: dict = Body(...)):
        servicio.procesar_webhook(transportadora, cuerpo)
        return Response(status_code=204)

    @router.get("/transportadoras", response_model=list[Transportadora], dependencies=[Depends(operacion)])
    def catalogo():
        with Sesiones() as sesion:
            return [Transportadora.model_validate(t, from_attributes=True)
                    for t in repositorio.transportadoras(sesion)]

    return router
