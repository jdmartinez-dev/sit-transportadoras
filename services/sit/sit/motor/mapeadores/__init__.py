"""Un mapeador por transportadora: sabe en qué campo del mensaje del operador va cada dato canónico."""
from sit.motor.mapeadores.coordinadora import MapeadorCoordinadora
from sit.motor.mapeadores.dhl import MapeadorDHL

MAPEADORES = {mapeador.codigo: mapeador for mapeador in (MapeadorDHL(), MapeadorCoordinadora())}
