-- Catálogo y tablas de equivalencia iniciales (sección 7.3 de la especificación).
-- El SIT ejecuta este archivo al arrancar, solo si la tabla transportadora está vacía.
-- Agregar una transportadora (Figura 3, parte B) es, sobre todo, agregar filas aquí.

INSERT INTO transportadora (codigo, nombre, protocolo, version_api, adaptador, endpoint, frecuencia_sincronizacion_seg, version_equivalencias, activa) VALUES
  ('dhl', 'DHL Express (simulada)', 'REST', 'MyDHL API 2 (simulada)', 'rest', 'http://mock-dhl:8000/mydhlapi', NULL, '2026.10-1', TRUE),
  ('coordinadora', 'Coordinadora (simulada)', 'SOAP', 'Guías 1.0 (simulada)', 'soap', 'http://mock-coordinadora:8088/ws/guias', 10, '2026.10-1', TRUE);

INSERT INTO equivalencia_estado (transportadora, codigo_operador, estado_canonico) VALUES
  ('dhl', 'SD', 'CREADA'),
  ('dhl', 'PU', 'RECOGIDA'),
  ('dhl', 'AF', 'EN_TRANSITO'),
  ('dhl', 'DF', 'EN_TRANSITO'),
  ('dhl', 'WC', 'EN_REPARTO'),
  ('dhl', 'OK', 'ENTREGADA'),
  ('dhl', 'OH', 'NOVEDAD'),
  ('dhl', 'RT', 'DEVUELTA'),
  ('coordinadora', '1', 'CREADA'),
  ('coordinadora', '2', 'RECOGIDA'),
  ('coordinadora', '3', 'EN_TRANSITO'),
  ('coordinadora', '4', 'EN_TRANSITO'),
  ('coordinadora', '5', 'EN_TRANSITO'),
  ('coordinadora', '6', 'EN_REPARTO'),
  ('coordinadora', '7', 'ENTREGADA'),
  ('coordinadora', '8', 'NOVEDAD'),
  ('coordinadora', '9', 'DEVUELTA');

INSERT INTO equivalencia_ciudad (transportadora, divipola, codigo_operador) VALUES
  ('dhl', '11001', 'BOG'),
  ('dhl', '05001', 'MDE'),
  ('dhl', '76001', 'CLO'),
  ('dhl', '08001', 'BAQ'),
  ('dhl', '13001', 'CTG'),
  ('dhl', '68001', 'BGA'),
  ('coordinadora', '11001', '11001000'),
  ('coordinadora', '05001', '05001000'),
  ('coordinadora', '76001', '76001000'),
  ('coordinadora', '08001', '08001000'),
  ('coordinadora', '13001', '13001000'),
  ('coordinadora', '68001', '68001000'),
  ('coordinadora', '66001', '66001000');

INSERT INTO equivalencia_unidad (transportadora, magnitud, unidad_operador, factor_a_canonico) VALUES
  ('dhl', 'peso', 'lb', 0.45359237),
  ('dhl', 'longitud', 'in', 2.54),
  ('coordinadora', 'peso', 'g', 0.001),
  ('coordinadora', 'longitud', 'cm', 1);
