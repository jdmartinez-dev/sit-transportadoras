"""SIT — Servicio de Integración con Transportadoras (patrón Data Model Transformation)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from comun.bd import crear_motor
from comun.errores import registrar_manejador_errores
from comun.eventos import Bus
from comun.seguridad import ValidadorJWT
from sit import adaptadores
from sit.api import crear_router
from sit.catalogo import repositorio
from sit.catalogo.modelos import Base
from sit.config import Config
from sit.motor.motor import Motor
from sit.servicio import ServicioSIT
from sit.sincronizador import Sincronizador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def crear_app(config: Config | None = None, *, bus=None, crear_adaptador=None, iniciar_fondo: bool = True) -> FastAPI:
    config = config or Config()
    motor_bd = crear_motor(config.url_bd_efectiva())
    Sesiones = sessionmaker(motor_bd, expire_on_commit=False)
    bus = bus or Bus.desde_url(config.url_redis)
    motor = Motor(Sesiones, crear_adaptador or (lambda t: adaptadores.crear_adaptador(t, config)))
    servicio = ServicioSIT(Sesiones, motor, bus)
    sincronizador = Sincronizador(servicio, Sesiones)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        Base.metadata.create_all(motor_bd)
        with Sesiones() as sesion:
            if repositorio.cargar_semilla_si_vacio(sesion):
                log.info("Catálogo y tablas de equivalencia cargados desde semilla.sql")
        if iniciar_fondo:
            sincronizador.iniciar()
        yield
        if iniciar_fondo:
            sincronizador.detener()

    app = FastAPI(title="SIT - Servicio de Integración con Transportadoras", version="1.0.0",
                  description="API canónica: los servicios internos nunca ven el modelo de cada transportadora.",
                  lifespan=ciclo_de_vida)
    registrar_manejador_errores(app)
    app.include_router(crear_router(servicio, Sesiones, ValidadorJWT(config.jwt_publica)))

    @app.get("/salud")
    def salud():
        return {"estado": "ok"}

    return app


app = crear_app()
