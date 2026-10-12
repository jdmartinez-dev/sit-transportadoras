"""API de Despachos (Tabla 2): despacho manual o reintento, y consulta."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from comun.canonico import PedidoConfirmado
from comun.errores import ErrorPlataforma
from comun.seguridad import Rol, ValidadorJWT
from despachos.esquemas import Despacho, a_esquema
from despachos.modelos import DespachoBD, EstadoDespacho
from despachos.orquestador import Orquestador


def crear_router(orquestador: Orquestador, Sesiones, validador: ValidadorJWT) -> APIRouter:
    permitidos = validador.requiere_roles(Rol.AGENTE_SERVICIO, Rol.OPERADOR_LOGISTICO)
    router = APIRouter(prefix="/api/v1")

    @router.post("/despachos", response_model=Despacho, status_code=201, dependencies=[Depends(permitidos)],
                 responses={200: {"model": Despacho, "description": "El despacho ya existía o se reanudó"},
                            502: {"model": Despacho, "description": "El despacho quedó FALLIDO"}})
    def despachar(pedido: PedidoConfirmado):
        despacho, creado = orquestador.procesar(pedido)
        if despacho.estado == EstadoDespacho.FALLIDO:
            estado_http = 502
        else:
            estado_http = 201 if creado else 200
        return JSONResponse(status_code=estado_http, content=despacho.model_dump(mode="json"))

    @router.get("/despachos/{pedido_id}", response_model=Despacho, dependencies=[Depends(permitidos)])
    def consultar(pedido_id: str):
        with Sesiones() as sesion:
            despacho = sesion.get(DespachoBD, pedido_id)
            if despacho is None:
                raise ErrorPlataforma(404, "DESPACHO_NO_ENCONTRADO", f"No hay despacho para el pedido {pedido_id}")
            return a_esquema(despacho)

    return router
