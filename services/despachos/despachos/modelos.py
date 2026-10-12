from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from comun.bd import FechaHora


class EstadoDespacho(str, Enum):
    PENDIENTE = "PENDIENTE"
    GUIA_CREADA = "GUIA_CREADA"
    RECOGIDA_PROGRAMADA = "RECOGIDA_PROGRAMADA"
    FALLIDO = "FALLIDO"


class Base(DeclarativeBase):
    pass


class DespachoBD(Base):
    """Un despacho por pedido: el id del despacho es el pedido_id. Cada paso guarda su resultado para poder reanudar."""

    __tablename__ = "despacho"

    pedido_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    estado: Mapped[str] = mapped_column(String(30))
    solicitud: Mapped[dict] = mapped_column(JSON)
    transportadora_solicitada: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transportadora: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cotizaciones: Mapped[list] = mapped_column(JSON, default=list)
    numero_guia: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confirmacion_recogida: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evento_publicado: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(FechaHora)
    actualizado_en: Mapped[datetime] = mapped_column(FechaHora)
