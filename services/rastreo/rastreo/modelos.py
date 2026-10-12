from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from comun.bd import FechaHora


class Base(DeclarativeBase):
    pass


class EstadoRegistradoBD(Base):
    __tablename__ = "estado_registrado"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_evento: Mapped[str] = mapped_column(String(36), unique=True)  # descarta entregas repetidas
    numero_guia: Mapped[str] = mapped_column(String(30), index=True)
    transportadora: Mapped[str] = mapped_column(String(30))
    estado: Mapped[str] = mapped_column(String(20))
    ocurrido_en: Mapped[datetime] = mapped_column(FechaHora)
    recibido_en: Mapped[datetime] = mapped_column(FechaHora)
