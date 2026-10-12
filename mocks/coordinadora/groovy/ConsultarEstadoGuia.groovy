def datos
synchronized (System) { datos = leer() }
def numero = solicitud.getNodeValue("//g:codigoRemision")
def guia = datos.guias[numero]
if (guia == null) {
    requestContext.cuerpo = fallo("Remisión no encontrada: ${numero}")
    return
}
def estados = guia.estados.collect { e ->
    "<g:estados><g:codigo>${e.codigo}</g:codigo><g:descripcion>${e.descripcion}</g:descripcion><g:fecha>${e.fecha}</g:fecha></g:estados>"
}.join("")
requestContext.cuerpo = "<g:ConsultarEstadoGuiaRespuesta><g:codigoRemision>${numero}</g:codigoRemision>${estados}</g:ConsultarEstadoGuiaRespuesta>".toString()
