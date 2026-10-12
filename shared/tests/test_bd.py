from datetime import datetime, timezone

import pytest
from sqlalchemy import String
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from comun.bd import FechaHora, crear_motor
from comun.canonico import ZONA_COLOMBIA
from comun.config import ConfigBase


class Base(DeclarativeBase):
    pass


class Registro(Base):
    __tablename__ = "registro"
    id: Mapped[str] = mapped_column(String(5), primary_key=True)
    momento: Mapped[datetime] = mapped_column(FechaHora)


@pytest.fixture
def Sesiones():
    motor = crear_motor("sqlite://")
    Base.metadata.create_all(motor)
    return sessionmaker(motor)


def test_fechahora_guarda_en_utc_y_devuelve_la_hora_de_colombia(Sesiones):
    with Sesiones() as sesion:
        sesion.add(Registro(id="a", momento=datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc)))
        sesion.commit()
    with Sesiones() as sesion:
        momento = sesion.get(Registro, "a").momento
    assert momento == datetime(2026, 10, 12, 9, 0, tzinfo=ZONA_COLOMBIA)
    assert momento.utcoffset() == ZONA_COLOMBIA.utcoffset(None)


def test_fechahora_rechaza_fechas_sin_zona(Sesiones):
    with Sesiones() as sesion:
        sesion.add(Registro(id="b", momento=datetime(2026, 10, 12, 14, 0)))
        with pytest.raises(StatementError):
            sesion.commit()


def test_config_arma_la_url_de_postgresql_o_usa_la_indicada():
    assert ConfigBase(bd_nombre="sit", postgres_password="x").url_bd_efectiva() == \
        "postgresql+psycopg://plataforma:x@postgres:5432/sit"
    assert ConfigBase(url_bd="sqlite://").url_bd_efectiva() == "sqlite://"
