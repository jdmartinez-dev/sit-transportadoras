from comun.canonico import PedidoConfirmado
from comun.eventos import PEDIDO_CONFIRMADO, Evento
from despachos.consumidor import crear_manejador

PEDIDO = {"pedido_id": "PED-1002", "transportadora": "coordinadora",
          "destino": {"divipola": "05001", "direccion": "Carrera 43A # 1-50", "nombre": "Ana Pérez",
                      "telefono": "3001234567"},
          "paquetes": [{"peso_kg": 2.0, "largo_cm": 30, "ancho_cm": 20, "alto_cm": 10}]}


def test_el_evento_pedido_confirmado_dispara_la_orquestacion(orquestador, sit):
    datos = PedidoConfirmado.model_validate(PEDIDO).model_dump(mode="json")
    crear_manejador(orquestador)(Evento(tipo=PEDIDO_CONFIRMADO, datos=datos))
    assert sit.nombres() == ["cotizar", "crear_envio", "programar_recogida"]


def test_un_evento_con_datos_invalidos_se_descarta(orquestador, sit):
    crear_manejador(orquestador)(Evento(tipo=PEDIDO_CONFIRMADO, datos={"pedido_id": ""}))
    assert sit.nombres() == []
