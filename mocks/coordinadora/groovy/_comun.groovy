import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import com.eviware.soapui.support.XmlHolder
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

// Estado del simulador: un archivo JSON dentro del contenedor (se pierde al reiniciarlo).
def archivo = new File(System.getenv("ARCHIVO_GUIAS") ?: "/tmp/guias-coordinadora.json")
def leer = { archivo.exists() ? new JsonSlurper().parseText(archivo.getText("UTF-8")) : [consecutivo: 0, recogidas: 0, guias: [:]] }
def guardar = { datos -> archivo.setText(JsonOutput.toJson(datos), "UTF-8") }
def ahora = { LocalDateTime.now(ZoneId.of("America/Bogota")).format(DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")) }
def fallo = { String mensaje -> "<soapenv:Fault><faultcode>soapenv:Client</faultcode><faultstring>${mensaje}</faultstring></soapenv:Fault>".toString() }
def solicitud = new XmlHolder(mockRequest.requestContent)
solicitud.declareNamespace("g", "http://coordinadora.simulada/guias")
