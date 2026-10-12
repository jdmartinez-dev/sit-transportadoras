"""Genera coordinadora-soapui-project.xml a partir del WSDL y de los scripts Groovy de groovy/.

Los scripts quedan en archivos .groovy legibles; el proyecto de SoapUI (XML) se regenera con:
    .venv/bin/python mocks/coordinadora/generar_proyecto.py
"""
import uuid
from pathlib import Path

NS = "http://coordinadora.simulada/guias"
OPERACIONES = ["CotizarFlete", "GenerarGuia", "ProgramarRecogida", "ConsultarEstadoGuia", "CambiarEstadoGuia"]
RUTA_WSDL = "file:/opt/coordinadora/coordinadora.wsdl"
RESPUESTA = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:g="{NS}">
   <soapenv:Header/>
   <soapenv:Body>${{cuerpo}}</soapenv:Body>
</soapenv:Envelope>"""


def _id(nombre: str) -> str:
    """Identificadores estables, para que el XML generado no cambie entre ejecuciones."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"coordinadora-simulada/{nombre}"))


def construir(base: Path) -> str:
    wsdl = (base / "coordinadora.wsdl").read_text(encoding="utf-8")
    comun = (base / "groovy" / "_comun.groovy").read_text(encoding="utf-8")

    operaciones_interfaz = "\n".join(
        f'''    <con:operation id="{_id('op-' + op)}" isOneWay="false" action="{NS}/{op}" name="{op}" bindingOperationName="{op}" type="Request-Response" inputName="" receivesAttachments="false" sendsAttachments="false" anonymous="optional">
      <con:settings/>
    </con:operation>'''
        for op in OPERACIONES
    )

    operaciones_mock = []
    for op in OPERACIONES:
        script = comun + "\n" + (base / "groovy" / f"{op}.groovy").read_text(encoding="utf-8")
        operaciones_mock.append(f'''    <con:mockOperation name="{op}" id="{_id('mock-' + op)}" interface="GuiasBinding" operation="{op}">
      <con:settings/>
      <con:defaultResponse>Respuesta</con:defaultResponse>
      <con:dispatchStyle>SEQUENCE</con:dispatchStyle>
      <con:response name="Respuesta" id="{_id('resp-' + op)}" httpResponseStatus="200" encoding="UTF-8">
        <con:settings/>
        <con:script><![CDATA[{script}]]></con:script>
        <con:responseContent><![CDATA[{RESPUESTA}]]></con:responseContent>
        <con:wsaConfig mustUnderstand="NONE" version="200508" action="{NS}/{op}"/>
      </con:response>
      <con:dispatchConfig/>
    </con:mockOperation>''')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<con:soapui-project id="{_id('proyecto')}" activeEnvironment="Default" name="Coordinadora simulada" resourceRoot="" soapui-version="5.7.2" abortOnError="false" runType="SEQUENTIAL" xmlns:con="http://eviware.com/soapui/config">
  <con:settings/>
  <con:interface xsi:type="con:WsdlInterface" id="{_id('interfaz')}" wsaVersion="NONE" name="GuiasBinding" type="wsdl" bindingName="{{{NS}}}GuiasBinding" soapVersion="1_1" anonymous="optional" definition="{RUTA_WSDL}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <con:settings/>
    <con:definitionCache type="TEXT" rootPart="{RUTA_WSDL}">
      <con:part>
        <con:url>{RUTA_WSDL}</con:url>
        <con:content><![CDATA[{wsdl}]]></con:content>
        <con:type>http://schemas.xmlsoap.org/wsdl/</con:type>
      </con:part>
    </con:definitionCache>
    <con:endpoints>
      <con:endpoint>http://localhost:8088/ws/guias</con:endpoint>
    </con:endpoints>
{operaciones_interfaz}
  </con:interface>
  <con:mockService id="{_id('mockservice')}" port="8088" path="/ws/guias" host="localhost" name="CoordinadoraMock" bindToHostOnly="false" docroot="">
    <con:settings>
      <con:setting id="com.eviware.soapui.impl.wsdl.mock.WsdlMockService@require-soap-action">false</con:setting>
    </con:settings>
    <con:properties/>
{chr(10).join(operaciones_mock)}
  </con:mockService>
  <con:properties/>
  <con:wssContainer/>
  <con:oAuth2ProfileContainer/>
  <con:oAuth1ProfileContainer/>
  <con:sensitiveInformation/>
</con:soapui-project>
'''


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    (base / "coordinadora-soapui-project.xml").write_text(construir(base), encoding="utf-8")
    print("Proyecto de SoapUI regenerado: mocks/coordinadora/coordinadora-soapui-project.xml")
