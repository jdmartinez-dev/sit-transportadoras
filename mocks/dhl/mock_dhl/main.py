"""DHL Express SIMULADO (inspirado en la MyDHL API): REST/JSON, unidades imperiales y códigos propios."""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from mock_dhl.almacen import Almacen
from mock_dhl.config import Config
from mock_dhl.tarifas import (COBERTURA, DESCRIPCIONES, dias_transito, peso_facturable_lb, peso_volumetrico_lb,
                              precio_cop)
from mock_dhl.webhook import NotificadorWebhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

ZONA = timezone(timedelta(hours=-5))


class Dimensiones(BaseModel):
    length: float
    width: float
    height: float


class PaqueteDHL(BaseModel):
    weight: float
    dimensions: Dimensiones


class SolicitudTarifa(BaseModel):
    originCityCode: str
    destinationCityCode: str
    packages: list[PaqueteDHL]


class Receptor(BaseModel):
    cityCode: str
    name: str
    address: str
    phone: str


class SolicitudEnvioDHL(BaseModel):
    originCityCode: str
    receiver: Receptor
    packages: list[PaqueteDHL]
    reference: str


class SolicitudRecogidaDHL(BaseModel):
    shipmentTrackingNumber: str
    plannedPickupDateAndTime: str


class CambioEstado(BaseModel):
    typeCode: str


def nuevo_evento(codigo: str) -> dict:
    momento = datetime.now(ZONA)
    return {"date": momento.strftime("%Y-%m-%d"), "time": momento.strftime("%H:%M:%S"), "typeCode": codigo,
            "description": DESCRIPCIONES.get(codigo, "Unknown event code (test)")}


def crear_app(config: Config | None = None, notificador=None) -> FastAPI:
    config = config or Config()
    notificador = notificador or NotificadorWebhook(config.url_webhook, config.url_token, config.cliente_id,
                                                    config.cliente_mock_dhl_secret)
    almacen = Almacen()
    basica = HTTPBasic()

    def autenticar(credenciales: HTTPBasicCredentials = Depends(basica)) -> None:
        usuario_ok = secrets.compare_digest(credenciales.username, config.usuario_api)
        clave_ok = bool(config.dhl_api_password) and secrets.compare_digest(credenciales.password,
                                                                            config.dhl_api_password)
        if not (usuario_ok and clave_ok):
            raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})

    def validar_ciudad(codigo: str) -> None:
        if codigo not in COBERTURA:
            raise HTTPException(400, f"City not covered: {codigo}")

    def buscar(numero: str):
        envio = almacen.buscar(numero)
        if envio is None:
            raise HTTPException(404, f"Shipment not found: {numero}")
        return envio

    app = FastAPI(title="DHL Express (simulado)", version="2.0.0")

    @app.post("/mydhlapi/rates", dependencies=[Depends(autenticar)])
    def tarifas(solicitud: SolicitudTarifa):
        validar_ciudad(solicitud.originCityCode)
        validar_ciudad(solicitud.destinationCityCode)
        paquetes = solicitud.packages
        provisto = sum(p.weight for p in paquetes)
        volumetrico = sum(peso_volumetrico_lb(p.dimensions.length, p.dimensions.width, p.dimensions.height)
                          for p in paquetes)
        facturable = sum(peso_facturable_lb(p.weight, p.dimensions.length, p.dimensions.width, p.dimensions.height)
                         for p in paquetes)
        origen, destino = solicitud.originCityCode, solicitud.destinationCityCode
        return {"products": [{
            "productName": "EXPRESS DOMESTIC",
            "productCode": "N",
            "totalPrice": [{"currencyType": "BILLC", "priceCurrency": "COP",
                            "price": precio_cop(facturable, origen, destino)}],
            "weight": {"volumetric": round(volumetrico, 2), "provided": round(provisto, 2),
                       "unitOfMeasurement": "imperial"},
            "totalTransitDays": dias_transito(origen, destino),
        }]}

    @app.post("/mydhlapi/shipments", status_code=201, dependencies=[Depends(autenticar)])
    def crear_envio(solicitud: SolicitudEnvioDHL, tareas: BackgroundTasks):
        validar_ciudad(solicitud.originCityCode)
        validar_ciudad(solicitud.receiver.cityCode)
        envio = almacen.crear(solicitud.reference, solicitud.originCityCode, solicitud.receiver.cityCode)
        primero = nuevo_evento("SD")
        envio.eventos.append(primero)
        tareas.add_task(notificador.notificar, envio.numero, primero)
        return {"shipmentTrackingNumber": envio.numero}

    @app.post("/mydhlapi/pickups", status_code=201, dependencies=[Depends(autenticar)])
    def programar_recogida(solicitud: SolicitudRecogidaDHL):
        buscar(solicitud.shipmentTrackingNumber)
        return {"dispatchConfirmationNumbers": [almacen.nueva_recogida()]}

    @app.get("/mydhlapi/shipments/{numero}/tracking", dependencies=[Depends(autenticar)])
    def rastrear(numero: str):
        envio = buscar(numero)
        return {"shipments": [{"shipmentTrackingNumber": numero, "status": "Success", "events": list(envio.eventos)}]}

    @app.post("/demo/envios/{numero}/estado")
    def cambiar_estado(numero: str, cambio: CambioEstado, tareas: BackgroundTasks):
        """Panel de la demo: agrega un evento (puede ser un código desconocido, p. ej. XX) y avisa al SIT."""
        envio = buscar(numero)
        evento = nuevo_evento(cambio.typeCode)
        envio.eventos.append(evento)
        tareas.add_task(notificador.notificar, numero, evento)
        return {"shipmentTrackingNumber": numero, "event": evento}

    @app.get("/salud")
    def salud():
        return {"estado": "ok"}

    return app


app = crear_app()
