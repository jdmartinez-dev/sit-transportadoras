"""Servicio de autenticación: los canales obtienen el token al iniciar sesión (flujo password) y los
servicios internos con el flujo de credenciales de cliente (RFC 6749)."""
import base64
import binascii
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from auth.config import Config
from auth.modelos import Base, Identidad
from auth.semilla import cargar_identidades, verificar_secreto
from auth.tokens import EmisorTokens
from comun.bd import crear_motor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

SIN_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _error_oauth(estado: int, error: str, descripcion: str) -> JSONResponse:
    encabezados = dict(SIN_CACHE)
    if estado == 401:
        encabezados["WWW-Authenticate"] = "Basic"
    return JSONResponse(status_code=estado, content={"error": error, "error_description": descripcion},
                        headers=encabezados)


def _credenciales_basicas(authorization: str | None) -> tuple[str, str] | None:
    if not authorization or not authorization.lower().startswith("basic "):
        return None
    try:
        decodificado = base64.b64decode(authorization[6:]).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None
    cliente, _, secreto = decodificado.partition(":")
    return cliente, secreto


def crear_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    motor = crear_motor(config.url_bd_efectiva())
    Sesiones = sessionmaker(motor, expire_on_commit=False)
    emisor = EmisorTokens(config.jwt_privada, config.duracion_token_seg)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        Base.metadata.create_all(motor)
        with Sesiones() as sesion:
            cargar_identidades(sesion, config)
        yield

    app = FastAPI(title="Servicio de autenticación", version="1.0.0", lifespan=ciclo_de_vida)

    def buscar(nombre: str, tipo: str, secreto: str) -> Identidad | None:
        with Sesiones() as sesion:
            identidad = sesion.get(Identidad, nombre)
        if identidad is None or identidad.tipo != tipo or not verificar_secreto(secreto, identidad.hash_secreto):
            return None
        return identidad

    @app.post("/oauth/token")
    def emitir_token(
        grant_type: str | None = Form(None),
        username: str | None = Form(None),
        password: str | None = Form(None),
        client_id: str | None = Form(None),
        client_secret: str | None = Form(None),
        authorization: str | None = Header(None),
    ):
        if grant_type == "password":
            if not username or not password:
                return _error_oauth(400, "invalid_request", "Faltan username y password")
            identidad = buscar(username, "usuario", password)
            if identidad is None:
                return _error_oauth(400, "invalid_grant", "Usuario o contraseña incorrectos")
        elif grant_type == "client_credentials":
            basicas = _credenciales_basicas(authorization)
            cliente, secreto = basicas if basicas else (client_id, client_secret)
            if not cliente or not secreto:
                return _error_oauth(401, "invalid_client", "Faltan las credenciales del cliente")
            identidad = buscar(cliente, "cliente", secreto)
            if identidad is None:
                return _error_oauth(401, "invalid_client", "Credenciales de cliente incorrectas")
        elif grant_type is None:
            return _error_oauth(400, "invalid_request", "Falta grant_type")
        else:
            return _error_oauth(400, "unsupported_grant_type", f"Flujo no soportado: {grant_type}")

        token = emisor.emitir(identidad.nombre, identidad.lista_roles())
        return JSONResponse(
            content={"access_token": token, "token_type": "Bearer", "expires_in": config.duracion_token_seg},
            headers=SIN_CACHE,
        )

    @app.get("/salud")
    def salud():
        return {"estado": "ok"}

    return app


app = crear_app()
