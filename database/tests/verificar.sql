-- =====================================================================
-- Comprobaciones de BDIADelivery tras ejecutar los scripts 01 a 04.
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
    (SELECT CotaInferiorCargas FROM vw_ComparativaTiposVehiculo WHERE IdTipoVehiculo = 1) = 70
-- 04_fechas_caducidad.sql
UNION ALL SELECT 'Pedidos con fechas calculadas: 133',
    (SELECT COUNT(*) FROM Pedidos
      WHERE FechaInicioFabricacion IS NOT NULL AND FechaListoEnvio IS NOT NULL
        AND FechaCaducidad IS NOT NULL AND FechaLimiteEntrega IS NOT NULL) = 133
UNION ALL SELECT 'FechaCaducidad de Pedidos coincide con vw_PedidosResumen',
    (SELECT COUNT(*) FROM Pedidos p JOIN vw_PedidosResumen v ON v.IdPedido = p.IdPedido
      WHERE NOT (p.FechaCaducidad <=> v.FechaCaducidad) OR NOT (p.FechaListoEnvio <=> v.FechaListoParaEnvio)) = 0
UNION ALL SELECT 'Totales de Pedidos coinciden con vw_PedidosResumen',
    (SELECT COUNT(*) FROM Pedidos p JOIN vw_PedidosResumen v ON v.IdPedido = p.IdPedido
      WHERE p.UnidadesTotales <> v.Unidades OR p.NumLineas <> v.NumLineas OR p.ImporteTotal <> v.ImporteVenta) = 0
UNION ALL SELECT 'Unidades totales: 834.265', (SELECT SUM(UnidadesTotales) FROM Pedidos) = 834265
UNION ALL SELECT 'Horas disponibles de reparto > 0 en todos los pedidos',
    (SELECT COUNT(*) FROM Pedidos WHERE HorasDisponiblesReparto IS NULL OR HorasDisponiblesReparto <= 0) = 0
UNION ALL SELECT 'vw_LineasPedidoCaducidad: 17689 filas', (SELECT COUNT(*) FROM vw_LineasPedidoCaducidad) = 17689
UNION ALL SELECT 'Cada pedido tiene al menos una linea limitante',
    (SELECT COUNT(DISTINCT IdPedido) FROM vw_LineasPedidoCaducidad WHERE EsLimitante = 1) = 133
-- 05_flota_conductores.sql
UNION ALL SELECT 'Vehiculos: 70 (40 de 12 t, 20 de 18 t, 10 de 40 t)',
    (SELECT COUNT(*) FROM Vehiculos) = 70
    AND (SELECT COUNT(*) FROM Vehiculos WHERE IdTipoVehiculo = 3) = 10
UNION ALL SELECT 'Conductores: 60 con DNI unico', (SELECT COUNT(DISTINCT DNI) FROM Conductores) = 60
-- 06 y 07: carreteras reales
UNION ALL SELECT 'TramosCarretera: 127 x 127 puntos', (SELECT COUNT(*) FROM TramosCarretera) = 16129
UNION ALL SELECT 'Todos los tramos distintos tienen km y tiempo',
    (SELECT COUNT(*) FROM TramosCarretera WHERE PuntoOrigen <> PuntoDestino AND (Km <= 0 OR MinutosCamion <= 0)) = 0
UNION ALL SELECT 'Velocidad media del camion entre 40 y 90 km/h',
    (SELECT AVG(Km / (MinutosCamion / 60)) FROM TramosCarretera WHERE PuntoOrigen <> PuntoDestino) BETWEEN 40 AND 90;
