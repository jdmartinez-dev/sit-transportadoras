from fastapi import APIRouter, Depends

from comun.seguridad import Rol, ValidadorJWT
from rastreo.servicio import Rastreo, ServicioRastreo


def crear_router(servicio: ServicioRastreo, validador: ValidadorJWT) -> APIRouter:
    canales = validador.requiere_roles(Rol.CLIENTE, Rol.AGENTE_SERVICIO, Rol.OPERADOR_LOGISTICO)
    router = APIRouter(prefix="/api/v1")

    @router.get("/rastreo/{guia}", response_model=Rastreo, dependencies=[Depends(canales)])
    def consultar(guia: str):
        return servicio.consultar(guia)

    return router
