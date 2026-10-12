# Transportadora Coordinadora SIMULADA: mock SOAP en SoapUI a partir de un WSDL propio (Tabla 4).
# SoapUI 5.7.2 necesita Java 11: su script usa --illegal-access=permit, que Java 17 eliminó.
FROM eclipse-temurin:11-jre
ARG SOAPUI_VERSION=5.7.2
RUN curl -fsSL "https://dl.eviware.com/soapuios/${SOAPUI_VERSION}/SoapUI-${SOAPUI_VERSION}-linux-bin.tar.gz" \
      | tar -xz -C /opt \
 && mv "/opt/SoapUI-${SOAPUI_VERSION}" /opt/soapui
COPY mocks/coordinadora/coordinadora.wsdl mocks/coordinadora/coordinadora-soapui-project.xml /opt/coordinadora/
ENV ARCHIVO_GUIAS=/tmp/guias-coordinadora.json
WORKDIR /opt/coordinadora
EXPOSE 8088
CMD ["/opt/soapui/bin/mockservicerunner.sh", "-m", "CoordinadoraMock", "-p", "8088", "/opt/coordinadora/coordinadora-soapui-project.xml"]
