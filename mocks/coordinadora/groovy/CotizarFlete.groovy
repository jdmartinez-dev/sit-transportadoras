def origen = solicitud.getNodeValue("//g:ciudadOrigen")
def destino = solicitud.getNodeValue("//g:ciudadDestino")
if (!(origen ==~ /\d{8}/) || !(destino ==~ /\d{8}/)) {
    requestContext.cuerpo = fallo("Ciudad no válida: se espera el código DIVIPOLA de 8 dígitos")
    return
}
def pesos = solicitud.getNodeValues("//g:piezas/g:pesoGr")
def largos = solicitud.getNodeValues("//g:piezas/g:largoCm")
def anchos = solicitud.getNodeValues("//g:piezas/g:anchoCm")
def altos = solicitud.getNodeValues("//g:piezas/g:altoCm")
// Peso liquidado: el mayor entre el real y el volumétrico (400 kg/m3 = 0,4 g/cm3), pieza por pieza.
long liquidado = 0
for (int i = 0; i < pesos.length; i++) {
    long real = pesos[i] as long
    long volumen = Math.round((largos[i] as long) * (anchos[i] as long) * (altos[i] as long) * 0.4d)
    liquidado += Math.max(real, volumen)
}
long kilos = (long) Math.ceil(liquidado / 1000.0d)
double factor = origen == destino ? 1.0d : 1.3d
long valor = Math.round((9000 + 6000 * kilos) * factor)
int dias = origen == destino ? 1 : 3
requestContext.cuerpo = "<g:CotizarFleteRespuesta><g:valorFlete>${valor}</g:valorFlete><g:pesoLiquidadoGr>${liquidado}</g:pesoLiquidadoGr><g:diasEntrega>${dias}</g:diasEntrega></g:CotizarFleteRespuesta>".toString()
