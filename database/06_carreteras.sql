-- =====================================================================
-- BDIADelivery - RUTAS POR CARRETERA REAL
-- Ejecutar después de 01 a 05. El 07 (generado) carga la matriz.
--
-- Puntos: 0 = almacén principal (Mataró); > 0 = IdDestino.
--
-- TramosCarretera: km y tiempo por carretera entre cada par de puntos,
--   calculados con OSRM (Open Source Routing Machine) sobre OpenStreetMap.
--   MinutosCamion aplica la velocidad de camión:
--     v_camion = min(VelocidadMaxCamionKmh, FactorVelocidadCamion x v_coche)
-- GeometriaTramos: trazado de cada tramo usado en una ruta, con la velocidad
--   del camión en cada segmento (JSON). Se rellena bajo demanda al abrir la
--   simulación y queda en caché.
-- Datos de rutas (c) colaboradores de OpenStreetMap (ODbL).
-- =====================================================================

USE `BDIADelivery`;
SET NAMES utf8mb4;

CREATE TABLE `TramosCarretera` (
  `PuntoOrigen`   INT NOT NULL,
  `PuntoDestino`  INT NOT NULL,
  `Km`            DECIMAL(9,3) NOT NULL,
  `MinutosCoche`  DECIMAL(9,2) NOT NULL,
  `MinutosCamion` DECIMAL(9,2) NOT NULL,
  `Fuente`        VARCHAR(60) NOT NULL DEFAULT 'OSRM sobre OpenStreetMap',
  `FechaCalculo`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`PuntoOrigen`, `PuntoDestino`),
  CONSTRAINT `CK_Tramos_Km` CHECK (`Km` >= 0),
  CONSTRAINT `CK_Tramos_Min` CHECK (`MinutosCamion` >= 0)
) ENGINE = InnoDB;

CREATE TABLE `GeometriaTramos` (
  `PuntoOrigen`   INT NOT NULL,
  `PuntoDestino`  INT NOT NULL,
  `Km`            DECIMAL(9,3) NOT NULL,
  `MinutosCamion` DECIMAL(9,2) NOT NULL,
  `Puntos`        MEDIUMTEXT NOT NULL,   -- JSON [[lat, lon, km acumulado, km/h del camión en el segmento], ...]
  `FechaCalculo`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`PuntoOrigen`, `PuntoDestino`)
) ENGINE = InnoDB;

INSERT INTO `ParametrosSistema` (`Clave`, `Valor`, `Unidad`, `Descripcion`) VALUES
('UsarCarreteras',         1.0000, '0/1',  '1 = km y tiempos por carretera real (TramosCarretera); 0 = línea recta x factor'),
('VelocidadMaxCamionKmh', 90.0000, 'km/h', 'Velocidad máxima del camión (autopista/autovía, España)'),
('FactorVelocidadCamion',  0.8800, 'factor', 'Velocidad del camión respecto a la de un turismo en el mismo tramo');
