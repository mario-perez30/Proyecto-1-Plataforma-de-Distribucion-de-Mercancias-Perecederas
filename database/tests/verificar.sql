-- =====================================================================
-- Comprobaciones de BDIADelivery tras ejecutar los scripts 01, 02 y 03.
-- Cada fila devuelve: <comprobación> <TAB> <1 si se cumple, 0 o NULL si falla>
-- El pipeline de CI falla si alguna fila no termina en 1.
-- Uso: mysql -N -B BDIADelivery < database/tests/verificar.sql
-- =====================================================================

SELECT 'Provincias: 72 (47 ES + 18 PT + 7 AD)', (SELECT COUNT(*) FROM Provincias) = 72
UNION ALL SELECT 'Clientes: 500',               (SELECT COUNT(*) FROM Clientes) = 500
UNION ALL SELECT 'Productos: 10000',            (SELECT COUNT(*) FROM Productos) = 10000
UNION ALL SELECT 'Destinos: 1500',              (SELECT COUNT(*) FROM Destinos) = 1500
UNION ALL SELECT 'Pedidos: 133',                (SELECT COUNT(*) FROM Pedidos) = 133
UNION ALL SELECT 'LineasPedido: 17689',         (SELECT COUNT(*) FROM LineasPedido) = 17689
UNION ALL SELECT 'Tipos de vehiculo: 3',        (SELECT COUNT(*) FROM TiposVehiculo) = 3
UNION ALL SELECT 'Destinos con provincia de otro pais: 0',
    (SELECT COUNT(*) FROM Destinos d JOIN Provincias p ON p.IdProvincia = d.IdProvincia WHERE p.IdPais <> d.IdPais) = 0
UNION ALL SELECT 'Provincias sin destino: 0',
    (SELECT COUNT(*) FROM Provincias p WHERE NOT EXISTS (SELECT 1 FROM Destinos d WHERE d.IdProvincia = p.IdProvincia)) = 0
UNION ALL SELECT 'Coordenadas coinciden con Latitud/Longitud',
    (SELECT COUNT(*) FROM Destinos
      WHERE ABS(ST_X(Coordenadas) - Longitud) > 0.000001 OR ABS(ST_Y(Coordenadas) - Latitud) > 0.000001) = 0
UNION ALL SELECT 'Destinos dentro de la peninsula (lat 36-44, lon -10..3.5)',
    (SELECT COUNT(*) FROM Destinos WHERE Latitud NOT BETWEEN 36 AND 44 OR Longitud NOT BETWEEN -10 AND 3.5) = 0
UNION ALL SELECT 'Distancia desde Mataro calculada en todos los destinos',
    (SELECT COUNT(*) FROM Destinos WHERE DistanciaKmOrigen IS NULL OR DistanciaKmOrigen <= 0) = 0
UNION ALL SELECT 'vw_PedidosResumen: 133 pedidos',        (SELECT COUNT(*) FROM vw_PedidosResumen) = 133
UNION ALL SELECT 'Ningun pedido caduca antes de estar listo',
    (SELECT COUNT(*) FROM vw_PedidosResumen WHERE FechaCaducidad < FechaListoParaEnvio) = 0
UNION ALL SELECT 'vw_CosteKmTipoVehiculo: precio de gasoleo vigente',
    (SELECT COUNT(*) FROM vw_CosteKmTipoVehiculo WHERE PrecioNetoLitro IS NULL) = 0
UNION ALL SELECT 'vw_EstimacionEnvioDirecto: 399 filas (133 x 3)', (SELECT COUNT(*) FROM vw_EstimacionEnvioDirecto) = 399
UNION ALL SELECT 'Envio directo viable en los 133 pedidos con los 3 tipos',
    (SELECT COUNT(*) FROM vw_ComparativaTiposVehiculo WHERE PedidosViablesEnvioDirecto = 133) = 3
UNION ALL SELECT 'Coste envio directo 12 t = 228.750 EUR (+-1 %)',
    (SELECT ABS(CosteEnvioDirectoPropio - 228750) / 228750 FROM vw_ComparativaTiposVehiculo WHERE IdTipoVehiculo = 1) < 0.01
UNION ALL SELECT 'Coste externalizado = 189.758 EUR (+-1 %)',
    (SELECT ABS(CosteExternalizado - 189758) / 189758 FROM vw_ComparativaTiposVehiculo WHERE IdTipoVehiculo = 1) < 0.01
UNION ALL SELECT 'Cota inferior de cargas 12 t: 70',
    (SELECT CotaInferiorCargas FROM vw_ComparativaTiposVehiculo WHERE IdTipoVehiculo = 1) = 70;
