synchronized (System) {
    def datos = leer()
    // Si el contenedor se reinició, el consecutivo arranca según la hora: no repite números ya entregados.
    datos.consecutivo = (datos.consecutivo ?: (System.currentTimeMillis().intdiv(1000L) % 100000000L) * 1000L) + 1
    def numero = String.format("9%011d", datos.consecutivo as long)
    datos.guias[numero] = [
        referencia   : solicitud.getNodeValue("//g:referencia"),
        ciudadOrigen : solicitud.getNodeValue("//g:ciudadOrigen"),
        ciudadDestino: solicitud.getNodeValue("//g:destinatario/g:ciudad"),
        estados      : [[codigo: "1", descripcion: "Guía generada", fecha: ahora()]]
    ]
    guardar(datos)
    requestContext.cuerpo = "<g:GenerarGuiaRespuesta><g:codigoRemision>${numero}</g:codigoRemision></g:GenerarGuiaRespuesta>".toString()
}
