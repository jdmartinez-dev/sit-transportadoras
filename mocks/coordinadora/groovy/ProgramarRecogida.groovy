synchronized (System) {
    def datos = leer()
    def numero = solicitud.getNodeValue("//g:codigoRemision")
    def guia = datos.guias[numero]
    if (guia == null) {
        requestContext.cuerpo = fallo("Remisión no encontrada: ${numero}")
        return
    }
    def franja = solicitud.getNodeValue("//g:franja")
    if (!(franja in ["AM", "PM"])) {
        requestContext.cuerpo = fallo("Franja no válida: ${franja} (se espera AM o PM)")
        return
    }
    datos.recogidas = (datos.recogidas ?: 0) + 1
    def recogida = String.format("REC-%06d", datos.recogidas as long)
    guia.recogida = [numero: recogida, fecha: solicitud.getNodeValue("//g:fechaRecogida"), franja: franja]
    guardar(datos)
    requestContext.cuerpo = "<g:ProgramarRecogidaRespuesta><g:numeroRecogida>${recogida}</g:numeroRecogida></g:ProgramarRecogidaRespuesta>".toString()
}
