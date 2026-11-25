-- =====================================================================
-- BDIADelivery - FECHAS DE CADUCIDAD Y TOTALES DE LOS PEDIDOS
-- MySQL Workbench - compatible con MySQL 5.7+, MySQL 8 y MariaDB 10.2+
--
-- ORDEN DE EJECUCIÓN:
--   1) 01_crear_base_datos.sql
--   2) 02_mejoras_costes_flota.sql
--   3) 03_corregir_coordenadas.sql
--   4) 04_fechas_caducidad.sql        (este script)
--
-- Qué añade:
--   * En Pedidos, columnas calculadas a partir de sus líneas y productos:
--       NumLineas, UnidadesTotales, ImporteTotal,
--       FechaInicioFabricacion, FechaListoEnvio, FechaCaducidad,
--       FechaLimiteEntrega y HorasDisponiblesReparto.
--   * Funciones fn_FechaListoPedido y fn_FechaCaducidadPedido.
--   * Procedimiento sp_RecalcularFechasPedidos(IdPedido | NULL = todos).
--   * Triggers que mantienen esas columnas al día cuando cambian las
--     líneas del pedido o su FechaPedido.
--   * Vista vw_LineasPedidoCaducidad: caducidad de cada línea y cuál es
--     la que limita el pedido.
--
-- Reglas (parámetros de ParametrosSistema):
--   FechaInicioFabricacion = FechaPedido + DiasInicioFabricacion
--   FechaListoEnvio        = FechaInicioFabricacion + máx. TiempoFabricacion
--   FechaCaducidad:
--     CaducidadModoEnunciado = 1 -> mín(FechaPedido + Fabricación + Caducidad)
--     CaducidadModoEnunciado = 0 -> FechaListoEnvio + mín(CaducidadDias)
--                                   (producción sincronizada, por defecto)
--   FechaLimiteEntrega     = FechaCaducidad - MargenSeguridadCaducidadH
--
-- Si se cambian esos parámetros: CALL sp_RecalcularFechasPedidos(NULL);
-- =====================================================================

USE `BDIADelivery`;
SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- 1. Columnas nuevas en Pedidos
-- ---------------------------------------------------------------------
ALTER TABLE `Pedidos`
  ADD COLUMN `NumLineas`              SMALLINT      NOT NULL DEFAULT 0,
  ADD COLUMN `UnidadesTotales`        INT           NOT NULL DEFAULT 0,
  ADD COLUMN `ImporteTotal`           DECIMAL(14,2) NOT NULL DEFAULT 0,
  ADD COLUMN `FechaInicioFabricacion` DATE          NULL,
  ADD COLUMN `FechaListoEnvio`        DATE          NULL,
  ADD COLUMN `FechaCaducidad`         DATETIME      NULL,
  ADD COLUMN `FechaLimiteEntrega`     DATETIME      NULL,
  ADD COLUMN `HorasDisponiblesReparto` INT
      GENERATED ALWAYS AS (TIMESTAMPDIFF(HOUR, `FechaListoEnvio`, `FechaLimiteEntrega`)) STORED,
  ADD KEY `IX_Pedidos_Caducidad` (`FechaCaducidad`);

-- ---------------------------------------------------------------------
-- 2. Funciones y procedimiento
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS `trg_LineasPedido_ai`;
DROP TRIGGER IF EXISTS `trg_LineasPedido_au`;
DROP TRIGGER IF EXISTS `trg_LineasPedido_ad`;
DROP TRIGGER IF EXISTS `trg_Pedidos_bi`;
DROP TRIGGER IF EXISTS `trg_Pedidos_bu`;
DROP PROCEDURE IF EXISTS `sp_RecalcularFechasPedidos`;
DROP FUNCTION IF EXISTS `fn_FechaListoPedido`;
DROP FUNCTION IF EXISTS `fn_FechaCaducidadPedido`;

DELIMITER $$

-- Día en que todos los productos del pedido están fabricados
CREATE FUNCTION `fn_FechaListoPedido`(p_IdPedido BIGINT, p_FechaPedido DATETIME)
RETURNS DATE
READS SQL DATA
BEGIN
  DECLARE v_ini INT DEFAULT CAST(fn_Parametro('DiasInicioFabricacion') AS SIGNED);
  RETURN (SELECT DATE_ADD(DATE(p_FechaPedido), INTERVAL v_ini + MAX(pr.`TiempoFabricacionMedioDias`) DAY)
            FROM `LineasPedido` l
            JOIN `Productos` pr ON pr.`IdProducto` = l.`IdProducto`
           WHERE l.`IdPedido` = p_IdPedido);
END$$

-- Fecha de caducidad del pedido (la del producto que caduca antes)
CREATE FUNCTION `fn_FechaCaducidadPedido`(p_IdPedido BIGINT, p_FechaPedido DATETIME)
RETURNS DATETIME
READS SQL DATA
BEGIN
  DECLARE v_ini INT DEFAULT CAST(fn_Parametro('DiasInicioFabricacion') AS SIGNED);
  IF fn_Parametro('CaducidadModoEnunciado') = 1 THEN
    -- Fórmula literal del enunciado
    RETURN (SELECT DATE_ADD(p_FechaPedido,
                            INTERVAL MIN(pr.`TiempoFabricacionMedioDias` + pr.`CaducidadDias`) DAY)
              FROM `LineasPedido` l
              JOIN `Productos` pr ON pr.`IdProducto` = l.`IdProducto`
             WHERE l.`IdPedido` = p_IdPedido);
  END IF;
  -- Producción sincronizada: todo termina el día FechaListoEnvio
  RETURN (SELECT CAST(DATE_ADD(DATE(p_FechaPedido),
                               INTERVAL v_ini + MAX(pr.`TiempoFabricacionMedioDias`) + MIN(pr.`CaducidadDias`) DAY)
                      AS DATETIME)
            FROM `LineasPedido` l
            JOIN `Productos` pr ON pr.`IdProducto` = l.`IdProducto`
           WHERE l.`IdPedido` = p_IdPedido);
END$$

-- Recalcula totales y fechas de un pedido (o de todos si p_IdPedido es NULL)
CREATE PROCEDURE `sp_RecalcularFechasPedidos`(IN p_IdPedido BIGINT)
BEGIN
  DECLARE v_ini    INT DEFAULT CAST(fn_Parametro('DiasInicioFabricacion') AS SIGNED);
  DECLARE v_margen INT DEFAULT CAST(fn_Parametro('MargenSeguridadCaducidadH') AS SIGNED);
  DECLARE v_desde  BIGINT DEFAULT IFNULL(p_IdPedido, 0);
  DECLARE v_hasta  BIGINT DEFAULT IFNULL(p_IdPedido, 9223372036854775807);

  -- Filtro por rango de clave: válido también con SQL_SAFE_UPDATES de Workbench
  UPDATE `Pedidos` p
     SET p.`NumLineas`       = (SELECT COUNT(*) FROM `LineasPedido` l WHERE l.`IdPedido` = p.`IdPedido`),
         p.`UnidadesTotales` = (SELECT COALESCE(SUM(l.`Cantidad`), 0) FROM `LineasPedido` l WHERE l.`IdPedido` = p.`IdPedido`),
         p.`ImporteTotal`    = (SELECT COALESCE(SUM(l.`Cantidad` * pr.`PrecioVenta`), 0)
                                  FROM `LineasPedido` l JOIN `Productos` pr ON pr.`IdProducto` = l.`IdProducto`
                                 WHERE l.`IdPedido` = p.`IdPedido`),
         p.`FechaInicioFabricacion` = DATE_ADD(DATE(p.`FechaPedido`), INTERVAL v_ini DAY),
         p.`FechaListoEnvio`        = fn_FechaListoPedido(p.`IdPedido`, p.`FechaPedido`),
         p.`FechaCaducidad`         = fn_FechaCaducidadPedido(p.`IdPedido`, p.`FechaPedido`),
         p.`FechaLimiteEntrega`     = DATE_SUB(fn_FechaCaducidadPedido(p.`IdPedido`, p.`FechaPedido`), INTERVAL v_margen HOUR)
   WHERE p.`IdPedido` BETWEEN v_desde AND v_hasta;
END$$

-- ---------------------------------------------------------------------
-- 3. Triggers
-- ---------------------------------------------------------------------
-- Cambios en las líneas -> recalcular el pedido afectado
CREATE TRIGGER `trg_LineasPedido_ai` AFTER INSERT ON `LineasPedido`
FOR EACH ROW
BEGIN
  CALL sp_RecalcularFechasPedidos(NEW.`IdPedido`);
END$$

CREATE TRIGGER `trg_LineasPedido_au` AFTER UPDATE ON `LineasPedido`
FOR EACH ROW
BEGIN
  CALL sp_RecalcularFechasPedidos(NEW.`IdPedido`);
  IF NEW.`IdPedido` <> OLD.`IdPedido` THEN
    CALL sp_RecalcularFechasPedidos(OLD.`IdPedido`);
  END IF;
END$$

CREATE TRIGGER `trg_LineasPedido_ad` AFTER DELETE ON `LineasPedido`
FOR EACH ROW
BEGIN
  CALL sp_RecalcularFechasPedidos(OLD.`IdPedido`);
END$$

-- Pedido nuevo: todavía sin líneas, solo se conoce el inicio de fabricación
CREATE TRIGGER `trg_Pedidos_bi` BEFORE INSERT ON `Pedidos`
FOR EACH ROW
BEGIN
  SET NEW.`FechaInicioFabricacion` =
      DATE_ADD(DATE(NEW.`FechaPedido`), INTERVAL CAST(fn_Parametro('DiasInicioFabricacion') AS SIGNED) DAY);
END$$

-- Cambio de FechaPedido -> recalcular sus fechas
CREATE TRIGGER `trg_Pedidos_bu` BEFORE UPDATE ON `Pedidos`
FOR EACH ROW
BEGIN
  IF NOT (NEW.`FechaPedido` <=> OLD.`FechaPedido`) THEN
    SET NEW.`FechaInicioFabricacion` =
        DATE_ADD(DATE(NEW.`FechaPedido`), INTERVAL CAST(fn_Parametro('DiasInicioFabricacion') AS SIGNED) DAY);
    SET NEW.`FechaListoEnvio`    = fn_FechaListoPedido(NEW.`IdPedido`, NEW.`FechaPedido`);
    SET NEW.`FechaCaducidad`     = fn_FechaCaducidadPedido(NEW.`IdPedido`, NEW.`FechaPedido`);
    SET NEW.`FechaLimiteEntrega` = DATE_SUB(NEW.`FechaCaducidad`,
                                   INTERVAL CAST(fn_Parametro('MargenSeguridadCaducidadH') AS SIGNED) HOUR);
  END IF;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- 4. Caducidad por línea de pedido
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `vw_LineasPedidoCaducidad` AS
SELECT x.*,
       (x.FechaCaducidadProducto = x.FechaCaducidadPedido) AS EsLimitante
FROM (
  SELECT l.`IdPedido`, l.`NumeroLinea`, l.`IdProducto`, pr.`Nombre` AS Producto,
         c.`Nombre` AS Categoria, r.`Nombre` AS RegimenTemperatura, l.`Cantidad`,
         pr.`TiempoFabricacionMedioDias`, pr.`CaducidadDias`,
         p.`FechaPedido`, p.`FechaListoEnvio`,
         DATE_ADD(p.`FechaPedido`, INTERVAL pr.`TiempoFabricacionMedioDias` + pr.`CaducidadDias` DAY) AS FechaCaducidadEnunciado,
         CAST(DATE_ADD(p.`FechaListoEnvio`, INTERVAL pr.`CaducidadDias` DAY) AS DATETIME)               AS FechaCaducidadSincronizada,
         IF(fn_Parametro('CaducidadModoEnunciado') = 1,
            DATE_ADD(p.`FechaPedido`, INTERVAL pr.`TiempoFabricacionMedioDias` + pr.`CaducidadDias` DAY),
            CAST(DATE_ADD(p.`FechaListoEnvio`, INTERVAL pr.`CaducidadDias` DAY) AS DATETIME))           AS FechaCaducidadProducto,
         p.`FechaCaducidad` AS FechaCaducidadPedido
  FROM `LineasPedido` l
  JOIN `Pedidos` p              ON p.`IdPedido`    = l.`IdPedido`
  JOIN `Productos` pr           ON pr.`IdProducto` = l.`IdProducto`
  JOIN `Categorias` c           ON c.`IdCategoria` = pr.`IdCategoria`
  JOIN `RegimenesTemperatura` r ON r.`IdRegimen`   = c.`IdRegimen`
) x;

-- ---------------------------------------------------------------------
-- 5. Cálculo inicial
-- ---------------------------------------------------------------------
CALL sp_RecalcularFechasPedidos(NULL);

-- Comprobación rápida
SELECT COUNT(*) AS Pedidos,
       MIN(FechaListoEnvio) AS ListoMin, MAX(FechaListoEnvio) AS ListoMax,
       MIN(FechaCaducidad) AS CaducidadMin, MAX(FechaCaducidad) AS CaducidadMax,
       MIN(HorasDisponiblesReparto) AS HorasRepartoMin, MAX(HorasDisponiblesReparto) AS HorasRepartoMax,
       SUM(UnidadesTotales) AS Unidades, SUM(ImporteTotal) AS Importe
FROM `Pedidos`;
