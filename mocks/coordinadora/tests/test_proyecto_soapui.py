"""El proyecto de SoapUI se genera desde el WSDL y los scripts Groovy: estas pruebas evitan que se desalineen."""
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
WSDL = "{http://schemas.xmlsoap.org/wsdl/}"
SOAPUI = "{http://eviware.com/soapui/config}"


def _generador():
    especificacion = importlib.util.spec_from_file_location("generar_proyecto", BASE / "generar_proyecto.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def test_el_proyecto_de_soapui_esta_al_dia_con_el_wsdl_y_los_scripts():
    generado = _generador().construir(BASE)
    guardado = (BASE / "coordinadora-soapui-project.xml").read_text(encoding="utf-8")
    assert generado == guardado, "Regenere el proyecto: .venv/bin/python mocks/coordinadora/generar_proyecto.py"


def test_cada_operacion_del_wsdl_tiene_su_script_groovy():
    raiz = ET.parse(BASE / "coordinadora.wsdl").getroot()
    operaciones = {op.get("name") for op in raiz.iter(f"{WSDL}operation")}
    scripts = {p.stem for p in (BASE / "groovy").glob("*.groovy") if not p.stem.startswith("_")}
    esperadas = {"CotizarFlete", "GenerarGuia", "ProgramarRecogida", "ConsultarEstadoGuia", "CambiarEstadoGuia"}
    assert operaciones == scripts == esperadas


def test_el_mock_escucha_en_el_puerto_8088_y_la_ruta_ws_guias():
    raiz = ET.parse(BASE / "coordinadora-soapui-project.xml").getroot()
    mock = raiz.find(f"{SOAPUI}mockService")
    assert mock.get("name") == "CoordinadoraMock"
    assert mock.get("port") == "8088"
    assert mock.get("path") == "/ws/guias"
