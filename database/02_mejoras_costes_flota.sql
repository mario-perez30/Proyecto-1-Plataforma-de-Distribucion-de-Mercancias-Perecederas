-- =====================================================================
-- BDIADelivery - MEJORAS (costes, flota, combustible, temperatura,
--                escenarios y resultados de planificación)
-- MySQL Workbench - compatible con MySQL 5.7+, MySQL 8 y MariaDB 10.2+
--
-- ORDEN DE EJECUCIÓN:
--   1) 01_crear_base_datos.sql        (crea la BD base con los datos)
--   2) 02_mejoras_costes_flota.sql    (este script)
--   3) 03_corregir_coordenadas.sql    (corrige las coordenadas de los destinos)
-- Para repetirlo, vuelve a ejecutar los tres (el 1 borra y recrea la BD).
--
-- Los valores económicos (precios de gasóleo, peajes, salarios, precios
-- de camiones...) son REFERENCIAS ORIENTATIVAS para el prototipo:
-- revisarlos y actualizarlos en las tablas de parámetros.
-- =====================================================================

USE `BDIADelivery`;
SET NAMES utf8mb4;
SET @OLD_SQL_SAFE_UPDATES = @@SQL_SAFE_UPDATES, SQL_SAFE_UPDATES = 0;

-- =====================================================================
-- 1. PAÍSES (España, Portugal, Andorra) con IVA y peaje medio
-- =====================================================================
CREATE TABLE `Paises` (
  `IdPais`       CHAR(2)      NOT NULL,              -- ISO 3166-1 alfa-2
  `Nombre`       VARCHAR(50)  NOT NULL,
  `IVA`          DECIMAL(5,2) NOT NULL,              -- % (Andorra: IGI)
  `PeajeMedioKm` DECIMAL(6,4) NOT NULL DEFAULT 0,    -- €/km medio camión pesado
  PRIMARY KEY (`IdPais`),
  UNIQUE KEY `UQ_Paises_Nombre` (`Nombre`)
) ENGINE = InnoDB;

INSERT INTO `Paises` (`IdPais`, `Nombre`, `IVA`, `PeajeMedioKm`) VALUES
('ES', 'España',   21.00, 0.0400),
('PT', 'Portugal', 23.00, 0.1000),
('AD', 'Andorra',   4.50, 0.0000);

ALTER TABLE `Provincias`
  ADD COLUMN `IdPais` CHAR(2) NOT NULL DEFAULT 'ES' AFTER `Nombre`,
  ADD KEY `IX_Provincias_Pais` (`IdPais`),
  ADD CONSTRAINT `FK_Provincias_Paises` FOREIGN KEY (`IdPais`) REFERENCES `Paises` (`IdPais`);

-- =====================================================================
-- 2. ALMACENES (origen de las rutas: planta de Mataró)
-- =====================================================================
CREATE TABLE `Almacenes` (
  `IdAlmacen`    INT NOT NULL AUTO_INCREMENT,
  `Nombre`       VARCHAR(150) NOT NULL,
  `Direccion`    VARCHAR(200) NOT NULL,
  `Ciudad`       VARCHAR(100) NOT NULL,
  `IdPais`       CHAR(2)      NOT NULL,
  `Latitud`      DECIMAL(10,7) NOT NULL,
  `Longitud`     DECIMAL(10,7) NOT NULL,
  `Coordenadas`  POINT NOT NULL,                     -- POINT(x = longitud, y = latitud)
  `HoraApertura` TIME NOT NULL DEFAULT '06:00:00',   -- hora de inicio de carga
  `HoraCierre`   TIME NOT NULL DEFAULT '22:00:00',
  `EsPrincipal`  TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`IdAlmacen`),
  CONSTRAINT `FK_Almacenes_Paises` FOREIGN KEY (`IdPais`) REFERENCES `Paises` (`IdPais`)
) ENGINE = InnoDB;

INSERT INTO `Almacenes` (`Nombre`, `Direccion`, `Ciudad`, `IdPais`, `Latitud`, `Longitud`, `Coordenadas`, `EsPrincipal`) VALUES
('IA DELIVERY SL - Planta central', 'Instalaciones centrales', 'Mataró', 'ES', 41.5381000, 2.4445000,
 POINT(2.4445, 41.5381), 1);

-- =====================================================================
-- 3. DESTINOS: país normalizado, nombre completo, ventana horaria,
--    tiempo de descarga y distancia desde el almacén principal
-- =====================================================================
ALTER TABLE `Destinos`
  ADD COLUMN `IdPais` CHAR(2) NULL AFTER `Pais`,
  ADD COLUMN `NombreCompleto` VARCHAR(400)
      GENERATED ALWAYS AS (CONCAT_WS(', ', `Direccion`, CONCAT_WS(' ', `CodigoPostal`, `Ciudad`), `Pais`)) STORED AFTER `IdDestino`,
  ADD COLUMN `HoraApertura`      TIME     NOT NULL DEFAULT '07:00:00',
  ADD COLUMN `HoraCierre`        TIME     NOT NULL DEFAULT '20:00:00',
  ADD COLUMN `TiempoDescargaMin` SMALLINT NOT NULL DEFAULT 30,
  ADD COLUMN `DistanciaKmOrigen` DECIMAL(8,2) NULL;   -- se calcula con sp_RecalcularDistancias

UPDATE `Destinos` d JOIN `Paises` p ON p.`Nombre` = d.`Pais` SET d.`IdPais` = p.`IdPais`;

ALTER TABLE `Destinos`
  MODIFY `IdPais` CHAR(2) NOT NULL,
  ADD KEY `IX_Destinos_Pais` (`IdPais`),
  ADD CONSTRAINT `FK_Destinos_Paises` FOREIGN KEY (`IdPais`) REFERENCES `Paises` (`IdPais`),
  ADD CONSTRAINT `CK_Destinos_Horario` CHECK (`HoraCierre` > `HoraApertura`),
  ADD CONSTRAINT `CK_Destinos_Descarga` CHECK (`TiempoDescargaMin` >= 0);

-- =====================================================================
-- 4. CADENA DE FRÍO: régimen de temperatura y categorías de producto
-- =====================================================================
CREATE TABLE `RegimenesTemperatura` (
  `IdRegimen` TINYINT NOT NULL,          -- mayor id = más exigente
  `Nombre`    VARCHAR(30) NOT NULL,
  `TempMinC`  DECIMAL(5,1) NOT NULL,
  `TempMaxC`  DECIMAL(5,1) NOT NULL,
  PRIMARY KEY (`IdRegimen`),
  CONSTRAINT `CK_Regimen_Rango` CHECK (`TempMaxC` >= `TempMinC`)
) ENGINE = InnoDB;

INSERT INTO `RegimenesTemperatura` VALUES
(1, 'Ambiente',     15.0,  25.0),
(2, 'Refrigerado',   0.0,   4.0),
(3, 'Congelado',   -25.0, -18.0);

CREATE TABLE `Categorias` (
  `IdCategoria` INT NOT NULL AUTO_INCREMENT,
  `Nombre`      VARCHAR(100) NOT NULL,
  `IdRegimen`   TINYINT NOT NULL,
  PRIMARY KEY (`IdCategoria`),
  UNIQUE KEY `UQ_Categorias_Nombre` (`Nombre`),
  CONSTRAINT `FK_Categorias_Regimen` FOREIGN KEY (`IdRegimen`) REFERENCES `RegimenesTemperatura` (`IdRegimen`)
) ENGINE = InnoDB;

-- Las 10 familias de producto que existen en la tabla Productos
INSERT INTO `Categorias` (`Nombre`, `IdRegimen`) VALUES
('Leche Entera',         2),
('Queso Semicurado',     2),
('Fuet Extra',           1),
('Jamón Cocido',         2),
('Croquetas Congeladas', 3),
('Tomate Triturado',     1),
('Pizza Refrigerada',    2),
('Gazpacho Fresco',      2),
('Ensalada Preparada',   2),
('Yogur Natural',        2);

ALTER TABLE `Productos` ADD COLUMN `IdCategoria` INT NULL AFTER `Nombre`;

UPDATE `Productos` p
  JOIN `Categorias` c ON p.`Nombre` LIKE CONCAT(c.`Nombre`, ' %')
   SET p.`IdCategoria` = c.`IdCategoria`;

-- Si algún producto quedara sin categoría, esta sentencia falla (comprobación).
ALTER TABLE `Productos`
  MODIFY `IdCategoria` INT NOT NULL,
  ADD KEY `IX_Productos_Categoria` (`IdCategoria`),
  ADD CONSTRAINT `FK_Productos_Categorias` FOREIGN KEY (`IdCategoria`) REFERENCES `Categorias` (`IdCategoria`);

-- =====================================================================
-- 5. COMBUSTIBLE: tipos (con factor de emisiones) y precios por país
-- =====================================================================
CREATE TABLE `TiposCombustible` (
  `IdCombustible` INT NOT NULL AUTO_INCREMENT,
  `Nombre`        VARCHAR(50) NOT NULL,
  `KgCO2PorLitro` DECIMAL(5,3) NOT NULL,     -- emisiones directas (tank-to-wheel)
  PRIMARY KEY (`IdCombustible`),
  UNIQUE KEY `UQ_TiposCombustible_Nombre` (`Nombre`)
) ENGINE = InnoDB;

INSERT INTO `TiposCombustible` (`Nombre`, `KgCO2PorLitro`) VALUES
('Gasóleo A',   2.680),
('Gasolina 95', 2.310);

-- Histórico de precios: se usa el último con FechaDesde <= fecha consultada
CREATE TABLE `PreciosCombustible` (
  `IdPrecio`      INT NOT NULL AUTO_INCREMENT,
  `IdCombustible` INT NOT NULL,
  `IdPais`        CHAR(2) NOT NULL,
  `FechaDesde`    DATE NOT NULL,
  `PrecioLitro`   DECIMAL(6,3) NOT NULL,     -- € / litro, IVA incluido
  `Fuente`        VARCHAR(200) NULL,
  PRIMARY KEY (`IdPrecio`),
  UNIQUE KEY `UQ_Precio_Comb_Pais_Fecha` (`IdCombustible`, `IdPais`, `FechaDesde`),
  CONSTRAINT `FK_Precios_Combustible` FOREIGN KEY (`IdCombustible`) REFERENCES `TiposCombustible` (`IdCombustible`),
  CONSTRAINT `FK_Precios_Paises`      FOREIGN KEY (`IdPais`)        REFERENCES `Paises` (`IdPais`),
  CONSTRAINT `CK_Precios_Positivo`    CHECK (`PrecioLitro` > 0)
) ENGINE = InnoDB;

INSERT INTO `PreciosCombustible` (`IdCombustible`, `IdPais`, `FechaDesde`, `PrecioLitro`, `Fuente`) VALUES
(1, 'ES', '2026-01-01', 1.420, 'Referencia orientativa - actualizar (Geoportal gasolineras MITECO)'),
(2, 'ES', '2026-01-01', 1.520, 'Referencia orientativa - actualizar (Geoportal gasolineras MITECO)'),
(1, 'PT', '2026-01-01', 1.600, 'Referencia orientativa - actualizar (DGEG)'),
(2, 'PT', '2026-01-01', 1.720, 'Referencia orientativa - actualizar (DGEG)'),
(1, 'AD', '2026-01-01', 1.220, 'Referencia orientativa - actualizar (Govern d''Andorra)'),
(2, 'AD', '2026-01-01', 1.330, 'Referencia orientativa - actualizar (Govern d''Andorra)');

-- =====================================================================
-- 6. FLOTA: tipos de vehículo (costes) y vehículos concretos
-- =====================================================================
CREATE TABLE `TiposVehiculo` (
  `IdTipoVehiculo`      INT NOT NULL AUTO_INCREMENT,
  `Nombre`              VARCHAR(100) NOT NULL,
  `CapacidadUnidades`   INT NOT NULL,              -- nº de productos que caben
  `MMA_Toneladas`       DECIMAL(5,2) NOT NULL,
  `IdCombustible`       INT NOT NULL,
  `ConsumoL100km`       DECIMAL(5,2) NOT NULL,     -- consumo en marcha
  `ConsumoFrioLHora`    DECIMAL(4,2) NOT NULL DEFAULT 0, -- equipo frigorífico
  `IdRegimenMax`        TINYINT NOT NULL,          -- régimen más frío que admite
  `Multitemperatura`    TINYINT(1) NOT NULL DEFAULT 0,   -- compartimentos a distinta temperatura
  `VelocidadMediaKmh`   DECIMAL(5,1) NOT NULL,
  `CosteMantenimientoKm` DECIMAL(6,4) NOT NULL,    -- €/km taller, revisiones, frigo
  `CosteNeumaticosKm`   DECIMAL(6,4) NOT NULL,     -- €/km
  `PrecioAdquisicion`   DECIMAL(12,2) NOT NULL,    -- € (inversión)
  `ValorResidual`       DECIMAL(12,2) NOT NULL DEFAULT 0,
  `VidaUtilAnios`       TINYINT NOT NULL,
  `SeguroAnual`         DECIMAL(10,2) NOT NULL,
  `ImpuestosAnuales`    DECIMAL(10,2) NOT NULL,    -- IVTM, ITV, tarjeta transporte...
  `KmAnualesEstimados`  INT NOT NULL,
  PRIMARY KEY (`IdTipoVehiculo`),
  UNIQUE KEY `UQ_TiposVehiculo_Nombre` (`Nombre`),
  CONSTRAINT `FK_TiposVehiculo_Combustible` FOREIGN KEY (`IdCombustible`) REFERENCES `TiposCombustible` (`IdCombustible`),
  CONSTRAINT `FK_TiposVehiculo_Regimen`     FOREIGN KEY (`IdRegimenMax`)  REFERENCES `RegimenesTemperatura` (`IdRegimen`),
  CONSTRAINT `CK_TiposVehiculo_Capacidad`   CHECK (`CapacidadUnidades` > 0),
  CONSTRAINT `CK_TiposVehiculo_Velocidad`   CHECK (`VelocidadMediaKmh` > 0),
  CONSTRAINT `CK_TiposVehiculo_Vida`        CHECK (`VidaUtilAnios` > 0 AND `KmAnualesEstimados` > 0),
  CONSTRAINT `CK_TiposVehiculo_Residual`    CHECK (`ValorResidual` <= `PrecioAdquisicion`)
) ENGINE = InnoDB;

-- La flota es homogénea (enunciado): cada planificación elige UN tipo.
-- Se dejan 3 tipos para poder comparar escenarios.
INSERT INTO `TiposVehiculo`
(`Nombre`, `CapacidadUnidades`, `MMA_Toneladas`, `IdCombustible`, `ConsumoL100km`, `ConsumoFrioLHora`,
 `IdRegimenMax`, `Multitemperatura`, `VelocidadMediaKmh`, `CosteMantenimientoKm`, `CosteNeumaticosKm`,
 `PrecioAdquisicion`, `ValorResidual`, `VidaUtilAnios`, `SeguroAnual`, `ImpuestosAnuales`, `KmAnualesEstimados`) VALUES
('Camión rígido frigorífico bitemperatura 12 t', 12000, 12.00, 1, 24.00, 2.00, 3, 1, 70.0, 0.0900, 0.0300,  95000.00, 20000.00, 8, 4500.00,  900.00, 100000),
('Camión rígido frigorífico bitemperatura 18 t', 18000, 18.00, 1, 28.00, 2.50, 3, 1, 70.0, 0.1000, 0.0350, 120000.00, 25000.00, 8, 5000.00, 1100.00, 110000),
('Tráiler frigorífico bitemperatura 40 t',       33000, 40.00, 1, 33.00, 3.00, 3, 1, 70.0, 0.1200, 0.0450, 190000.00, 40000.00, 8, 7000.00, 1800.00, 130000);

CREATE TABLE `Vehiculos` (
  `IdVehiculo`     INT NOT NULL AUTO_INCREMENT,
  `Matricula`      VARCHAR(15) NOT NULL,
  `IdTipoVehiculo` INT NOT NULL,
  `IdAlmacen`      INT NOT NULL,
  `FechaAlta`      DATE NOT NULL,
  `KmActuales`     INT NOT NULL DEFAULT 0,
  `Estado`         ENUM('Disponible','EnRuta','Taller','Baja') NOT NULL DEFAULT 'Disponible',
  PRIMARY KEY (`IdVehiculo`),
  UNIQUE KEY `UQ_Vehiculos_Matricula` (`Matricula`),
  KEY `IX_Vehiculos_Tipo` (`IdTipoVehiculo`),
  KEY `IX_Vehiculos_Almacen` (`IdAlmacen`),
  CONSTRAINT `FK_Vehiculos_Tipo`    FOREIGN KEY (`IdTipoVehiculo`) REFERENCES `TiposVehiculo` (`IdTipoVehiculo`),
  CONSTRAINT `FK_Vehiculos_Almacen` FOREIGN KEY (`IdAlmacen`)      REFERENCES `Almacenes` (`IdAlmacen`),
  CONSTRAINT `CK_Vehiculos_Km`      CHECK (`KmActuales` >= 0)
) ENGINE = InnoDB;

-- =====================================================================
-- 7. CONDUCTORES (un conductor por viaje, ida y vuelta)
-- =====================================================================
CREATE TABLE `Conductores` (
  `IdConductor`      INT NOT NULL AUTO_INCREMENT,
  `Nombre`           VARCHAR(150) NOT NULL,
  `DNI`              VARCHAR(15)  NOT NULL,
  `IdAlmacen`        INT NOT NULL,
  `CosteHoraEmpresa` DECIMAL(6,2) NULL,   -- NULL = usar parámetro CosteConductorHora
  `FechaAlta`        DATE NOT NULL,
  `Activo`           TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`IdConductor`),
  UNIQUE KEY `UQ_Conductores_DNI` (`DNI`),
  KEY `IX_Conductores_Almacen` (`IdAlmacen`),
  CONSTRAINT `FK_Conductores_Almacen` FOREIGN KEY (`IdAlmacen`) REFERENCES `Almacenes` (`IdAlmacen`)
) ENGINE = InnoDB;

-- =====================================================================
-- 8. PARÁMETROS GLOBALES (costes de personal, normativa, tiempos)
-- =====================================================================
CREATE TABLE `ParametrosSistema` (
  `Clave`       VARCHAR(60)    NOT NULL,
  `Valor`       DECIMAL(12,4)  NOT NULL,
  `Unidad`      VARCHAR(20)    NOT NULL,
  `Descripcion` VARCHAR(255)   NOT NULL,
  PRIMARY KEY (`Clave`)
) ENGINE = InnoDB;

INSERT INTO `ParametrosSistema` (`Clave`, `Valor`, `Unidad`, `Descripcion`) VALUES
('FactorRutaCarretera',          1.2500, 'factor', 'Multiplica la distancia en línea recta (haversine) para estimar km por carretera'),
('CosteConductorHora',          22.0000, '€/h',    'Coste empresa por hora de trabajo del conductor (salario + SS)'),
('DietaDiariaConductor',        55.0000, '€/día',  'Dieta por día de servicio fuera de base'),
('PernoctaConductor',           45.0000, '€/noche','Coste de pernocta cuando el viaje requiere descanso diario fuera'),
('ConduccionMaxDiariaH',         9.0000, 'h',      'Reglamento (CE) 561/2006: conducción diaria máxima'),
('ConduccionContinuaMaxH',       4.5000, 'h',      'Reglamento (CE) 561/2006: conducción continua antes de pausa'),
('PausaObligatoriaMin',         45.0000, 'min',    'Reglamento (CE) 561/2006: pausa tras 4,5 h de conducción'),
('DescansoDiarioMinH',          11.0000, 'h',      'Reglamento (CE) 561/2006: descanso diario normal'),
('TiempoCargaAlmacenMin',       60.0000, 'min',    'Tiempo de carga del camión en Mataró'),
('DiasInicioFabricacion',        1.0000, 'días',   'La fabricación empieza al día siguiente de recibir el pedido'),
('MargenSeguridadCaducidadH',   24.0000, 'h',      'El pedido debe llegar al menos estas horas antes de caducar'),
('CaducidadModoEnunciado',       0.0000, '0/1',    '1 = fórmula literal del enunciado, 0 = producción sincronizada (FechaListo + caducidad mínima)'),
('DevolucionGasoleoProfesional', 0.0490, '€/l',    'Devolución parcial del impuesto (España, vehículos >= 7,5 t)'),
('MMAMinGasoleoProfesional',     7.5000, 't',      'MMA mínima para la devolución del gasóleo profesional');

-- =====================================================================
-- 9. TARIFA DE EXTERNALIZACIÓN (coste actual para calcular el ahorro)
-- =====================================================================
CREATE TABLE `TarifasExternalizacion` (
  `IdTarifa`       INT NOT NULL AUTO_INCREMENT,
  `Proveedor`      VARCHAR(150) NOT NULL,
  `FechaDesde`     DATE NOT NULL,
  `CosteFijoEnvio` DECIMAL(10,2) NOT NULL DEFAULT 0,   -- € por envío
  `CosteKm`        DECIMAL(8,4)  NOT NULL DEFAULT 0,   -- € por km (ida)
  `CosteUnidad`    DECIMAL(8,4)  NOT NULL DEFAULT 0,   -- € por unidad transportada
  `Activa`         TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`IdTarifa`)
) ENGINE = InnoDB;

INSERT INTO `TarifasExternalizacion` (`Proveedor`, `FechaDesde`, `CosteFijoEnvio`, `CosteKm`, `CosteUnidad`) VALUES
('Operador logístico frigorífico actual (referencia)', '2026-01-01', 120.00, 1.8500, 0.0000);

-- =====================================================================
-- 10. ESCENARIOS (entrenamiento / real) y estado de los pedidos
-- =====================================================================
CREATE TABLE `Escenarios` (
  `IdEscenario`   INT NOT NULL AUTO_INCREMENT,
  `Nombre`        VARCHAR(150) NOT NULL,
  `Tipo`          ENUM('Entrenamiento','Real','Simulacion') NOT NULL,
  `Descripcion`   VARCHAR(500) NULL,
  `FechaCreacion` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`IdEscenario`)
) ENGINE = InnoDB;

INSERT INTO `Escenarios` (`Nombre`, `Tipo`, `Descripcion`) VALUES
('Dataset inicial', 'Entrenamiento', 'Pedidos importados del script original de SQL Server');

ALTER TABLE `Pedidos`
  ADD COLUMN `IdEscenario` INT NULL AFTER `IdPedido`,
  ADD COLUMN `Estado` ENUM('Pendiente','EnFabricacion','Listo','EnRuta','Entregado','Cancelado') NOT NULL DEFAULT 'Pendiente',
  ADD COLUMN `Prioridad` TINYINT NOT NULL DEFAULT 3,               -- 1 = máxima
  ADD COLUMN `FechaEntregaSolicitada` DATETIME NULL;

UPDATE `Pedidos` SET `IdEscenario` = 1;

ALTER TABLE `Pedidos`
  MODIFY `IdEscenario` INT NOT NULL,
  ADD KEY `IX_Pedidos_Escenario` (`IdEscenario`),
  ADD KEY `IX_Pedidos_Fecha` (`FechaPedido`),
  ADD CONSTRAINT `FK_Pedidos_Escenarios` FOREIGN KEY (`IdEscenario`) REFERENCES `Escenarios` (`IdEscenario`),
  ADD CONSTRAINT `CK_Pedidos_Prioridad` CHECK (`Prioridad` BETWEEN 1 AND 5);

-- =====================================================================
-- 11. RESULTADOS DEL OPTIMIZADOR: planificaciones, rutas y paradas
--     (las rellena el prototipo de IA; permite comparar algoritmos)
-- =====================================================================
CREATE TABLE `Planificaciones` (
  `IdPlanificacion`     INT NOT NULL AUTO_INCREMENT,
  `IdEscenario`         INT NOT NULL,
  `IdAlmacen`           INT NOT NULL,
  `IdTipoVehiculo`      INT NOT NULL,                 -- flota homogénea
  `Algoritmo`           VARCHAR(60) NOT NULL,          -- p. ej. 'OR-Tools VRPTW', 'Genético'
  `ParametrosAlgoritmo` JSON NULL,
  `FechaEjecucion`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `TiempoCalculoSeg`    DECIMAL(10,3) NULL,
  `Notas`               VARCHAR(500) NULL,
  PRIMARY KEY (`IdPlanificacion`),
  KEY `IX_Planif_Escenario` (`IdEscenario`),
  CONSTRAINT `FK_Planif_Escenario` FOREIGN KEY (`IdEscenario`)    REFERENCES `Escenarios` (`IdEscenario`),
  CONSTRAINT `FK_Planif_Almacen`   FOREIGN KEY (`IdAlmacen`)      REFERENCES `Almacenes` (`IdAlmacen`),
  CONSTRAINT `FK_Planif_Tipo`      FOREIGN KEY (`IdTipoVehiculo`) REFERENCES `TiposVehiculo` (`IdTipoVehiculo`)
) ENGINE = InnoDB;

CREATE TABLE `Rutas` (
  `IdRuta`             BIGINT NOT NULL AUTO_INCREMENT,
  `IdPlanificacion`    INT NOT NULL,
  `NumCamion`          SMALLINT NOT NULL,              -- camión dentro de la planificación
  `NumViaje`           SMALLINT NOT NULL DEFAULT 1,    -- nº de viaje de ese camión
  `IdVehiculo`         INT NULL,                       -- vehículo real asignado (opcional)
  `IdConductor`        INT NULL,
  `FechaSalida`        DATETIME NOT NULL,
  `FechaRegreso`       DATETIME NULL,
  `UnidadesCargadas`   INT NOT NULL DEFAULT 0,
  `KmTotales`          DECIMAL(10,2) NOT NULL DEFAULT 0,
  `HorasConduccion`    DECIMAL(8,2)  NOT NULL DEFAULT 0,
  `LitrosCombustible`  DECIMAL(10,2) NOT NULL DEFAULT 0,
  `CosteCombustible`   DECIMAL(12,2) NOT NULL DEFAULT 0,
  `CostePeajes`        DECIMAL(12,2) NOT NULL DEFAULT 0,
  `CosteConductor`     DECIMAL(12,2) NOT NULL DEFAULT 0,
  `CosteDietas`        DECIMAL(12,2) NOT NULL DEFAULT 0,   -- dietas + pernoctas
  `CosteMantenimiento` DECIMAL(12,2) NOT NULL DEFAULT 0,   -- mantenimiento + neumáticos
  `CosteFijoImputado`  DECIMAL(12,2) NOT NULL DEFAULT 0,   -- amortización + seguro + impuestos
  `CosteTotal`         DECIMAL(12,2) GENERATED ALWAYS AS
                       (`CosteCombustible` + `CostePeajes` + `CosteConductor` + `CosteDietas`
                        + `CosteMantenimiento` + `CosteFijoImputado`) STORED,
  `KgCO2`              DECIMAL(12,2) NOT NULL DEFAULT 0,
  `Estado`             ENUM('Planificada','EnCurso','Completada','Cancelada') NOT NULL DEFAULT 'Planificada',
  PRIMARY KEY (`IdRuta`),
  UNIQUE KEY `UQ_Rutas_Camion_Viaje` (`IdPlanificacion`, `NumCamion`, `NumViaje`),
  KEY `IX_Rutas_Vehiculo` (`IdVehiculo`),
  KEY `IX_Rutas_Conductor` (`IdConductor`),
  CONSTRAINT `FK_Rutas_Planif`    FOREIGN KEY (`IdPlanificacion`) REFERENCES `Planificaciones` (`IdPlanificacion`) ON DELETE CASCADE,
  CONSTRAINT `FK_Rutas_Vehiculo`  FOREIGN KEY (`IdVehiculo`)      REFERENCES `Vehiculos` (`IdVehiculo`),
  CONSTRAINT `FK_Rutas_Conductor` FOREIGN KEY (`IdConductor`)     REFERENCES `Conductores` (`IdConductor`),
  CONSTRAINT `CK_Rutas_Km`        CHECK (`KmTotales` >= 0),
  CONSTRAINT `CK_Rutas_Fechas`    CHECK (`FechaRegreso` IS NULL OR `FechaRegreso` >= `FechaSalida`)
) ENGINE = InnoDB;

CREATE TABLE `ParadasRuta` (
  `IdRuta`               BIGINT   NOT NULL,
  `Orden`                SMALLINT NOT NULL,
  `IdPedido`             BIGINT   NOT NULL,
  `IdDestino`            INT      NOT NULL,
  `KmDesdeAnterior`      DECIMAL(10,2) NOT NULL DEFAULT 0,
  `LlegadaPrevista`      DATETIME NOT NULL,
  `SalidaPrevista`       DATETIME NULL,
  `LlegadaReal`          DATETIME NULL,
  `FechaCaducidadPedido` DATETIME NOT NULL,
  `MargenHoras`          INT GENERATED ALWAYS AS (TIMESTAMPDIFF(HOUR, `LlegadaPrevista`, `FechaCaducidadPedido`)) STORED,
  `CumpleCaducidad`      TINYINT(1) GENERATED ALWAYS AS (`LlegadaPrevista` <= `FechaCaducidadPedido`) STORED,
  PRIMARY KEY (`IdRuta`, `Orden`),
  UNIQUE KEY `UQ_Paradas_Ruta_Pedido` (`IdRuta`, `IdPedido`),
  KEY `IX_Paradas_Pedido` (`IdPedido`),
  KEY `IX_Paradas_Destino` (`IdDestino`),
  CONSTRAINT `FK_Paradas_Ruta`    FOREIGN KEY (`IdRuta`)    REFERENCES `Rutas` (`IdRuta`) ON DELETE CASCADE,
  CONSTRAINT `FK_Paradas_Pedido`  FOREIGN KEY (`IdPedido`)  REFERENCES `Pedidos` (`IdPedido`),
  CONSTRAINT `FK_Paradas_Destino` FOREIGN KEY (`IdDestino`) REFERENCES `Destinos` (`IdDestino`)
) ENGINE = InnoDB;

-- =====================================================================
-- 12. FUNCIONES Y PROCEDIMIENTOS
-- =====================================================================
DROP FUNCTION IF EXISTS `fn_DistanciaKm`;
DROP FUNCTION IF EXISTS `fn_Parametro`;
DROP FUNCTION IF EXISTS `fn_PrecioCombustible`;
DROP PROCEDURE IF EXISTS `sp_RecalcularDistancias`;

DELIMITER $$

-- Distancia en línea recta (fórmula de haversine) en km
CREATE FUNCTION `fn_DistanciaKm`(lat1 DOUBLE, lon1 DOUBLE, lat2 DOUBLE, lon2 DOUBLE)
RETURNS DOUBLE
DETERMINISTIC NO SQL
BEGIN
  DECLARE a DOUBLE;
  IF lat1 IS NULL OR lon1 IS NULL OR lat2 IS NULL OR lon2 IS NULL THEN
    RETURN NULL;
  END IF;
  SET a = POW(SIN(RADIANS(lat2 - lat1) / 2), 2)
        + COS(RADIANS(lat1)) * COS(RADIANS(lat2)) * POW(SIN(RADIANS(lon2 - lon1) / 2), 2);
  RETURN 6371.0088 * 2 * ATAN2(SQRT(a), SQRT(1 - a));
END$$

-- Valor de un parámetro de ParametrosSistema
CREATE FUNCTION `fn_Parametro`(p_clave VARCHAR(60))
RETURNS DECIMAL(12,4)
READS SQL DATA
BEGIN
  RETURN (SELECT `Valor` FROM `ParametrosSistema` WHERE `Clave` = p_clave);
END$$

-- Precio vigente de un combustible en un país en una fecha
CREATE FUNCTION `fn_PrecioCombustible`(p_combustible INT, p_pais CHAR(2), p_fecha DATE)
RETURNS DECIMAL(6,3)
READS SQL DATA
BEGIN
  RETURN (SELECT `PrecioLitro` FROM `PreciosCombustible`
           WHERE `IdCombustible` = p_combustible AND `IdPais` = p_pais AND `FechaDesde` <= p_fecha
           ORDER BY `FechaDesde` DESC LIMIT 1);
END$$

-- Rellena Destinos.DistanciaKmOrigen (km por carretera estimados desde el almacén principal)
CREATE PROCEDURE `sp_RecalcularDistancias`()
BEGIN
  DECLARE v_safe INT DEFAULT @@SQL_SAFE_UPDATES;
  SET SQL_SAFE_UPDATES = 0;
  UPDATE `Destinos` d
    JOIN `Almacenes` a ON a.`EsPrincipal` = 1
     SET d.`DistanciaKmOrigen` = ROUND(fn_DistanciaKm(a.`Latitud`, a.`Longitud`, d.`Latitud`, d.`Longitud`)
                                       * fn_Parametro('FactorRutaCarretera'), 2);
  SET SQL_SAFE_UPDATES = v_safe;
END$$

DELIMITER ;

CALL sp_RecalcularDistancias();

-- =====================================================================
-- 13. VISTAS DE ANÁLISIS
-- =====================================================================

-- 13.1 Resumen de cada pedido: unidades, importe, fechas de fabricación
--      y caducidad (fórmula del enunciado) y necesidades de temperatura
CREATE OR REPLACE VIEW `vw_PedidosResumen` AS
SELECT p.`IdPedido`, p.`IdEscenario`, p.`FechaPedido`, p.`IdCliente`, p.`IdDestino`, p.`Estado`, p.`Prioridad`,
       COUNT(*)                                        AS NumLineas,
       SUM(l.`Cantidad`)                               AS Unidades,
       ROUND(SUM(l.`Cantidad` * pr.`PrecioVenta`), 2)  AS ImporteVenta,
       DATE_ADD(DATE(p.`FechaPedido`), INTERVAL fn_Parametro('DiasInicioFabricacion') DAY) AS FechaInicioFabricacion,
       DATE_ADD(DATE(p.`FechaPedido`),
                INTERVAL fn_Parametro('DiasInicioFabricacion') + MAX(pr.`TiempoFabricacionMedioDias`) DAY) AS FechaListoParaEnvio,
       -- (a) Fórmula literal del enunciado: Fecha Pedido + Tiempo Fabricación + Días Caducidad (mínimo del pedido)
       MIN(DATE_ADD(p.`FechaPedido`, INTERVAL pr.`TiempoFabricacionMedioDias` + pr.`CaducidadDias` DAY)) AS FechaCaducidadEnunciado,
       -- (b) Producción sincronizada: todos los productos terminan a la vez (FechaListo) y caducan
       --     FechaListo + Días Caducidad. Con los datos actuales (a) deja TODOS los pedidos caducados
       --     antes de estar fabricados, por eso por defecto se usa (b).
       CAST(DATE_ADD(DATE(p.`FechaPedido`), INTERVAL fn_Parametro('DiasInicioFabricacion')
            + MAX(pr.`TiempoFabricacionMedioDias`) + MIN(pr.`CaducidadDias`) DAY) AS DATETIME) AS FechaCaducidadSincronizada,
       IF(fn_Parametro('CaducidadModoEnunciado') = 1,
          MIN(DATE_ADD(p.`FechaPedido`, INTERVAL pr.`TiempoFabricacionMedioDias` + pr.`CaducidadDias` DAY)),
          CAST(DATE_ADD(DATE(p.`FechaPedido`), INTERVAL fn_Parametro('DiasInicioFabricacion')
               + MAX(pr.`TiempoFabricacionMedioDias`) + MIN(pr.`CaducidadDias`) DAY) AS DATETIME)) AS FechaCaducidad,
       MAX(c.`IdRegimen`)                              AS IdRegimenMasExigente,
       (MAX(c.`IdRegimen`) = 3 AND MIN(c.`IdRegimen`) < 3) AS RequiereMultitemperatura
FROM `Pedidos` p
JOIN `LineasPedido` l ON l.`IdPedido`   = p.`IdPedido`
JOIN `Productos`   pr ON pr.`IdProducto` = l.`IdProducto`
JOIN `Categorias`   c ON c.`IdCategoria` = pr.`IdCategoria`
GROUP BY p.`IdPedido`, p.`IdEscenario`, p.`FechaPedido`, p.`IdCliente`, p.`IdDestino`, p.`Estado`, p.`Prioridad`;

-- 13.2 Coste por km de cada tipo de vehículo (con precios vigentes hoy
--      en el país del almacén) y emisiones por km
CREATE OR REPLACE VIEW `vw_CosteKmTipoVehiculo` AS
SELECT km.*,
       ROUND(km.CosteCombustibleKm + km.CostePeajeKm + km.CosteMantenimientoKm + km.CosteFijoKm + km.CosteConductorKm, 4) AS CosteTotalKm
FROM (
  SELECT precio.`IdAlmacen`, precio.`IdTipoVehiculo`, precio.`Nombre` AS TipoVehiculo, precio.`CapacidadUnidades`,
         precio.`VelocidadMediaKmh`, precio.`IdRegimenMax`, precio.`Multitemperatura`,
         ROUND(precio.PrecioNetoLitro, 3)                                   AS PrecioNetoLitro,
         ROUND(precio.LitrosKm, 4)                                          AS LitrosKm,
         ROUND(precio.LitrosKm * precio.PrecioNetoLitro, 4)                 AS CosteCombustibleKm,
         precio.`PeajeMedioKm`                                              AS CostePeajeKm,
         ROUND(precio.`CosteMantenimientoKm` + precio.`CosteNeumaticosKm`, 4) AS CosteMantenimientoKm,
         ROUND(((precio.`PrecioAdquisicion` - precio.`ValorResidual`) / precio.`VidaUtilAnios`
                + precio.`SeguroAnual` + precio.`ImpuestosAnuales`) / precio.`KmAnualesEstimados`, 4) AS CosteFijoKm,
         ROUND(fn_Parametro('CosteConductorHora') / precio.`VelocidadMediaKmh`, 4) AS CosteConductorKm,
         ROUND(precio.LitrosKm * precio.`KgCO2PorLitro`, 4)                 AS KgCO2Km
  FROM (
    SELECT a.`IdAlmacen`, pa.`PeajeMedioKm`, t.*, c.`KgCO2PorLitro`,
           fn_PrecioCombustible(t.`IdCombustible`, a.`IdPais`, CURDATE())
             - IF(a.`IdPais` = 'ES' AND t.`IdCombustible` = 1
                  AND t.`MMA_Toneladas` >= fn_Parametro('MMAMinGasoleoProfesional'),
                  fn_Parametro('DevolucionGasoleoProfesional'), 0) AS PrecioNetoLitro,
           t.`ConsumoL100km` / 100 + t.`ConsumoFrioLHora` / t.`VelocidadMediaKmh` AS LitrosKm
    FROM `TiposVehiculo` t
    JOIN `TiposCombustible` c ON c.`IdCombustible` = t.`IdCombustible`
    CROSS JOIN `Almacenes` a
    JOIN `Paises` pa ON pa.`IdPais` = a.`IdPais`
  ) precio
) km;

-- 13.3 Estimación de ENVÍO DIRECTO (un camión por pedido, ida y vuelta)
--      para cada pedido y tipo de vehículo. Sirve como línea base para
--      comparar con las rutas optimizadas y con la externalización.
CREATE OR REPLACE VIEW `vw_EstimacionEnvioDirecto` AS
SELECT `IdPedido`, `IdEscenario`, `IdDestino`, `IdTipoVehiculo`, TipoVehiculo, Unidades, `CapacidadUnidades`,
       ROUND(DistanciaKm, 1)                         AS DistanciaKmIda,
       ROUND(2 * DistanciaKm, 1)                     AS KmIdaVuelta,
       ROUND(HorasConduccionIda, 2)                  AS HorasConduccionIda,
       ROUND(HorasTrabajo, 2)                        AS HorasTrabajo,
       DescansosTotal                                AS Pernoctas,
       FechaListoParaEnvio, LlegadaEstimada, FechaCaducidad,
       TIMESTAMPDIFF(HOUR, LlegadaEstimada, FechaCaducidad) AS MargenHoras,
       (Unidades <= `CapacidadUnidades`)             AS CumpleCapacidad,
       (`IdRegimenMax` >= IdRegimenMasExigente
        AND (RequiereMultitemperatura = 0 OR `Multitemperatura` = 1)) AS CumpleTemperatura,
       (LlegadaEstimada <= DATE_SUB(FechaCaducidad, INTERVAL fn_Parametro('MargenSeguridadCaducidadH') HOUR)) AS CumpleCaducidad,
       ROUND(2 * DistanciaKm * LitrosKm, 1)                         AS Litros,
       ROUND(2 * DistanciaKm * CosteCombustibleKm, 2)               AS CosteCombustible,
       ROUND(2 * DistanciaKm * CostePeajeKm, 2)                     AS CostePeajes,
       ROUND(2 * DistanciaKm * CosteMantenimientoKm, 2)             AS CosteMantenimiento,
       ROUND(2 * DistanciaKm * CosteFijoKm, 2)                      AS CosteFijoImputado,
       ROUND(HorasTrabajo * fn_Parametro('CosteConductorHora'), 2)  AS CosteConductor,
       ROUND((DescansosTotal + 1) * fn_Parametro('DietaDiariaConductor')
             + DescansosTotal * fn_Parametro('PernoctaConductor'), 2) AS CosteDietas,
       ROUND(2 * DistanciaKm * (CosteCombustibleKm + CostePeajeKm + CosteMantenimientoKm + CosteFijoKm)
             + HorasTrabajo * fn_Parametro('CosteConductorHora')
             + (DescansosTotal + 1) * fn_Parametro('DietaDiariaConductor')
             + DescansosTotal * fn_Parametro('PernoctaConductor'), 2) AS CosteTotalPropio,
       ROUND(2 * DistanciaKm * KgCO2Km, 1)                          AS KgCO2
FROM (
  -- t3: horas trabajadas (conducción ida+vuelta, pausas, carga, descarga) y llegada estimada
  SELECT t2.*,
         2 * (t2.HorasConduccionIda + t2.HorasPausasIda) + t2.HorasCarga + t2.`TiempoDescargaMin` / 60 AS HorasTrabajo,
         DATE_ADD(TIMESTAMP(t2.FechaListoParaEnvio, t2.`HoraApertura`),
                  INTERVAL ROUND((t2.HorasCarga + t2.HorasConduccionIda + t2.HorasPausasIda
                                  + t2.DescansosIda * t2.HorasDescanso) * 60) MINUTE)  AS LlegadaEstimada
  FROM (
    -- t2: pausas y descansos obligatorios (Reglamento CE 561/2006)
    SELECT t1.*,
           FLOOR(t1.HorasConduccionIda / t1.MaxContinua) * t1.HorasPausa            AS HorasPausasIda,
           GREATEST(CEIL(t1.HorasConduccionIda / t1.MaxDiaria) - 1, 0)              AS DescansosIda,
           GREATEST(CEIL(2 * t1.HorasConduccionIda / t1.MaxDiaria) - 1, 0)          AS DescansosTotal
    FROM (
      -- t1: horas de conducción y parámetros
      SELECT b.*,
             b.DistanciaKm / b.`VelocidadMediaKmh`              AS HorasConduccionIda,
             fn_Parametro('TiempoCargaAlmacenMin') / 60         AS HorasCarga,
             fn_Parametro('ConduccionContinuaMaxH')             AS MaxContinua,
             fn_Parametro('PausaObligatoriaMin') / 60           AS HorasPausa,
             fn_Parametro('ConduccionMaxDiariaH')               AS MaxDiaria,
             fn_Parametro('DescansoDiarioMinH')                 AS HorasDescanso
      FROM (
        -- base: pedido x tipo de vehículo con distancia desde el almacén principal
        SELECT r.`IdPedido`, r.`IdEscenario`, r.`IdDestino`, r.Unidades, r.FechaListoParaEnvio, r.FechaCaducidad,
               r.IdRegimenMasExigente, r.RequiereMultitemperatura,
               k.`IdTipoVehiculo`, k.TipoVehiculo, k.`CapacidadUnidades`, k.`VelocidadMediaKmh`,
               k.`IdRegimenMax`, k.`Multitemperatura`, k.LitrosKm,
               k.CosteCombustibleKm, k.CostePeajeKm, k.CosteMantenimientoKm, k.CosteFijoKm, k.KgCO2Km,
               d.`TiempoDescargaMin`, a.`HoraApertura`,
               fn_DistanciaKm(a.`Latitud`, a.`Longitud`, d.`Latitud`, d.`Longitud`)
                 * fn_Parametro('FactorRutaCarretera')          AS DistanciaKm
        FROM `vw_PedidosResumen` r
        JOIN `Destinos` d  ON d.`IdDestino` = r.`IdDestino`
        JOIN `Almacenes` a ON a.`EsPrincipal` = 1
        JOIN `vw_CosteKmTipoVehiculo` k ON k.`IdAlmacen` = a.`IdAlmacen`
      ) b
    ) t1
  ) t2
) t3;

-- 13.4 Comparativa por escenario y tipo de vehículo:
--      viabilidad, cota inferior de cargas, coste propio vs externalizado
CREATE OR REPLACE VIEW `vw_ComparativaTiposVehiculo` AS
SELECT e.`IdEscenario`, e.`IdTipoVehiculo`, e.TipoVehiculo, e.`CapacidadUnidades`,
       COUNT(*)                                                    AS Pedidos,
       SUM(e.CumpleCapacidad AND e.CumpleTemperatura AND e.CumpleCaducidad) AS PedidosViablesEnvioDirecto,
       SUM(e.Unidades)                                             AS UnidadesTotales,
       CEIL(SUM(e.Unidades) / e.`CapacidadUnidades`)               AS CotaInferiorCargas,
       ROUND(SUM(e.KmIdaVuelta), 0)                                AS KmEnvioDirecto,
       ROUND(SUM(e.CosteTotalPropio), 2)                           AS CosteEnvioDirectoPropio,
       ROUND(SUM(tx.`CosteFijoEnvio` + e.DistanciaKmIda * tx.`CosteKm` + e.Unidades * tx.`CosteUnidad`), 2) AS CosteExternalizado,
       ROUND(SUM(e.KgCO2) / 1000, 2)                               AS ToneladasCO2
FROM `vw_EstimacionEnvioDirecto` e
CROSS JOIN (SELECT `CosteFijoEnvio`, `CosteKm`, `CosteUnidad`
              FROM `TarifasExternalizacion`
             WHERE `Activa` = 1
             ORDER BY `FechaDesde` DESC
             LIMIT 1) tx
GROUP BY e.`IdEscenario`, e.`IdTipoVehiculo`, e.TipoVehiculo, e.`CapacidadUnidades`;

-- 13.5 Resumen de cada planificación generada por el optimizador
CREATE OR REPLACE VIEW `vw_ResumenPlanificacion` AS
SELECT p.`IdPlanificacion`, p.`IdEscenario`, p.`Algoritmo`, tv.`Nombre` AS TipoVehiculo,
       p.`FechaEjecucion`, p.`TiempoCalculoSeg`,
       r.NumCamiones, r.NumRutas, r.KmTotales, r.CosteTotal, r.KgCO2,
       ROUND(100 * r.UnidadesMediasRuta / tv.`CapacidadUnidades`, 1) AS OcupacionMediaPct,
       pr.PedidosPlanificados, pr.PedidosFueraDePlazo
FROM `Planificaciones` p
JOIN `TiposVehiculo` tv ON tv.`IdTipoVehiculo` = p.`IdTipoVehiculo`
LEFT JOIN (
  SELECT `IdPlanificacion`,
         COUNT(DISTINCT `NumCamion`) AS NumCamiones,
         COUNT(*)                    AS NumRutas,
         SUM(`KmTotales`)            AS KmTotales,
         SUM(`CosteTotal`)           AS CosteTotal,
         SUM(`KgCO2`)                AS KgCO2,
         AVG(`UnidadesCargadas`)     AS UnidadesMediasRuta
  FROM `Rutas` GROUP BY `IdPlanificacion`
) r ON r.`IdPlanificacion` = p.`IdPlanificacion`
LEFT JOIN (
  SELECT ru.`IdPlanificacion`,
         COUNT(*)                         AS PedidosPlanificados,
         SUM(pa.`CumpleCaducidad` = 0)    AS PedidosFueraDePlazo
  FROM `ParadasRuta` pa JOIN `Rutas` ru ON ru.`IdRuta` = pa.`IdRuta`
  GROUP BY ru.`IdPlanificacion`
) pr ON pr.`IdPlanificacion` = p.`IdPlanificacion`;

SET SQL_SAFE_UPDATES = @OLD_SQL_SAFE_UPDATES;

-- =====================================================================
-- Comprobaciones rápidas
-- =====================================================================
SELECT * FROM `vw_CosteKmTipoVehiculo`;
SELECT * FROM `vw_ComparativaTiposVehiculo`;
SELECT * FROM `vw_EstimacionEnvioDirecto` ORDER BY `IdPedido`, `IdTipoVehiculo` LIMIT 30;
