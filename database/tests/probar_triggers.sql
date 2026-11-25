-- =====================================================================
-- Prueba de los triggers de 04_fechas_caducidad.sql.
-- Modifica datos dentro de una transacción y la deshace al final (ROLLBACK).
-- Cada SELECT devuelve: <comprobación> <TAB> <1 si se cumple>
-- Uso: mysql -N -B BDIADelivery < database/tests/probar_triggers.sql
-- =====================================================================

START TRANSACTION;

SELECT NumLineas, UnidadesTotales, FechaCaducidad, FechaListoEnvio
  INTO @n0, @u0, @cad0, @listo0
  FROM Pedidos WHERE IdPedido = 1;

-- Producto que caduca antes que todos (el de menor CaducidadDias)
SELECT IdProducto INTO @corto FROM Productos ORDER BY CaducidadDias, IdProducto LIMIT 1;

-- 1. Añadir una línea recalcula totales
INSERT INTO LineasPedido (IdPedido, NumeroLinea, IdProducto, Cantidad) VALUES (1, 999, @corto, 10);
SELECT 'Trigger INSERT: NumLineas + 1',        (SELECT NumLineas FROM Pedidos WHERE IdPedido = 1) = @n0 + 1;
SELECT 'Trigger INSERT: UnidadesTotales + 10', (SELECT UnidadesTotales FROM Pedidos WHERE IdPedido = 1) = @u0 + 10;

-- 2. Cambiar la cantidad de la línea recalcula totales
UPDATE LineasPedido SET Cantidad = 25 WHERE IdPedido = 1 AND NumeroLinea = 999;
SELECT 'Trigger UPDATE: UnidadesTotales + 25', (SELECT UnidadesTotales FROM Pedidos WHERE IdPedido = 1) = @u0 + 25;

-- 3. Borrar la línea devuelve los totales originales
DELETE FROM LineasPedido WHERE IdPedido = 1 AND NumeroLinea = 999;
SELECT 'Trigger DELETE: NumLineas original', (SELECT NumLineas FROM Pedidos WHERE IdPedido = 1) = @n0;

-- 4. Retrasar un día la fecha del pedido desplaza sus fechas un día
UPDATE Pedidos SET FechaPedido = DATE_ADD(FechaPedido, INTERVAL 1 DAY) WHERE IdPedido = 1;
SELECT 'Trigger FechaPedido: caducidad + 1 dia',
       (SELECT FechaCaducidad FROM Pedidos WHERE IdPedido = 1) = DATE_ADD(@cad0, INTERVAL 1 DAY);
SELECT 'Trigger FechaPedido: listo + 1 dia',
       (SELECT FechaListoEnvio FROM Pedidos WHERE IdPedido = 1) = DATE_ADD(@listo0, INTERVAL 1 DAY);

ROLLBACK;

SELECT 'ROLLBACK: pedido 1 intacto',
       (SELECT NumLineas = @n0 AND FechaCaducidad = @cad0 FROM Pedidos WHERE IdPedido = 1);
