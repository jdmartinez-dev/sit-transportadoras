"""Despachos: orquestador del proceso de envío (se activa con pedido.confirmado o con POST /api/v1/despachos)."""
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from comun.bd import crear_motor
from comun.errores import registrar_manejador_errores
from comun.eventos import PEDIDO_CONFIRMADO, Bus
from comun.seguridad import ValidadorJWT
from despachos.api import crear_router
from despachos.cliente_sit import ClienteSIT, ProveedorToken
from despachos.config import Config
from despachos.consumidor import crear_manejador
from despachos.modelos import Base
from despachos.orquestador import Orquestador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def crear_app(config: Config | None = None, *, bus=None, sit=None, iniciar_fondo: bool = True) -> FastAPI:
    config = config or Config()
    motor_bd = crear_motor(config.url_bd_efectiva())
    Sesiones = sessionmaker(motor_bd, expire_on_commit=False)
    bus = bus or Bus.desde_url(config.url_redis)
    if sit is None:
        http = httpx.Client(timeout=config.timeout_sit_seg)
        tokens = ProveedorToken(config.url_token, config.cliente_id, config.cliente_despachos_secret, http)
        sit = ClienteSIT(config.url_sit, tokens, http)
    orquestador = Orquestador(Sesiones, sit, bus, config.origen())

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        Base.metadata.create_all(motor_bd)
        detener = None
        if iniciar_fondo:
            _, detener = bus.iniciar_consumidor(PEDIDO_CONFIRMADO, "despachos", config.nombre_consumidor,
                                                crear_manejador(orquestador))
        yield
        if detener is not None:
            detener.set()

    app = FastAPI(title="Despachos (orquestador)", version="1.0.0", lifespan=ciclo_de_vida)
    registrar_manejador_errores(app)
    app.include_router(crear_router(orquestador, Sesiones, ValidadorJWT(config.jwt_publica)))

    @app.get("/salud")
    def salud():
        return {"estado": "ok"}

    return app


app = crear_app()
