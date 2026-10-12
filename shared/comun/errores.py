"""Error canónico: ningún servicio reenvía el error crudo de una transportadora."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from comun.canonico import ErrorCanonico


class ErrorPlataforma(Exception):
    def __init__(self, estado_http: int, codigo: str, mensaje: str, transportadora: str | None = None):
        super().__init__(mensaje)
        self.estado_http = estado_http
        self.error = ErrorCanonico(codigo=codigo, mensaje=mensaje, transportadora=transportadora)


def registrar_manejador_errores(app: FastAPI) -> None:
    @app.exception_handler(ErrorPlataforma)
    async def _error_plataforma(request: Request, exc: ErrorPlataforma) -> JSONResponse:
        return JSONResponse(status_code=exc.estado_http, content=exc.error.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        detalle = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        error = ErrorCanonico(codigo="SOLICITUD_INVALIDA", mensaje=detalle)
        return JSONResponse(status_code=422, content=error.model_dump())
