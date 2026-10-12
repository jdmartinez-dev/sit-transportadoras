"""Utilidades de base de datos comunes (PostgreSQL en Docker, SQLite en las pruebas)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Engine, create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from comun.canonico import ZONA_COLOMBIA


def crear_motor(url: str) -> Engine:
    if url.startswith("sqlite"):
        # Una sola conexión compartida entre hilos: la base en memoria de las pruebas.
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True)


class FechaHora(TypeDecorator):
    """Guarda la fecha en UTC y la devuelve con la zona de Colombia, igual en PostgreSQL y en SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("La fecha debe tener zona horaria")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc).astimezone(ZONA_COLOMBIA)
