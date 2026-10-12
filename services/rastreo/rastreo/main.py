"""Rastreo: consume envio.estado.actualizado y expone el historial canónico (GET /api/v1/rastreo/{guia})."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from comun.bd import crear_motor
from comun.errores import registrar_manejador_errores
from comun.eventos import ENVIO_ESTADO_ACTUALIZADO, Bus
from comun.seguridad import ValidadorJWT
from rastreo.api import crear_router
from rastreo.config import Config
from rastreo.modelos import Base
from rastreo.servicio import ServicioRastreo, crear_manejador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def crear_app(config: Config | None = None, *, bus=None, iniciar_fondo: bool = True) -> FastAPI:
    config = config or Config()
    motor_bd = crear_motor(config.url_bd_efectiva())
    servicio = ServicioRastreo(sessionmaker(motor_bd, expire_on_commit=False))
    bus = bus or Bus.desde_url(config.url_redis)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        Base.metadata.create_all(motor_bd)
        detener = None
        if iniciar_fondo:
            _, detener = bus.iniciar_consumidor(ENVIO_ESTADO_ACTUALIZADO, "rastreo", config.nombre_consumidor,
                                                crear_manejador(servicio))
        yield
        if detener is not None:
            detener.set()

    app = FastAPI(title="Rastreo", version="1.0.0", lifespan=ciclo_de_vida)
    app.state.servicio = servicio
    registrar_manejador_errores(app)
    app.include_router(crear_router(servicio, ValidadorJWT(config.jwt_publica)))

    @app.get("/salud")
    def salud():
        return {"estado": "ok"}

    return app


app = crear_app()
