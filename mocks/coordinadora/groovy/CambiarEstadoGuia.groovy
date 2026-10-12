def DESCRIPCIONES = ["1": "Guía generada", "2": "Recogida", "3": "En terminal de origen", "4": "En transporte",
                     "5": "En terminal de destino", "6": "En reparto", "7": "Entregada", "8": "Novedad",
                     "9": "Devuelta al remitente"]
synchronized (System) {
    def datos = leer()
    def numero = solicitud.getNodeValue("//g:codigoRemision")
    def guia = datos.guias[numero]
    if (guia == null) {
        requestContext.cuerpo = fallo("Remisión no encontrada: ${numero}")
        return
    }
    def codigo = solicitud.getNodeValue("//g:codigoEstado")
    guia.estados << [codigo: codigo, descripcion: DESCRIPCIONES[codigo] ?: "Estado de prueba sin descripción", fecha: ahora()]
    guardar(datos)
    requestContext.cuerpo = "<g:CambiarEstadoGuiaRespuesta><g:resultado>OK</g:resultado></g:CambiarEstadoGuiaRespuesta>"
}
