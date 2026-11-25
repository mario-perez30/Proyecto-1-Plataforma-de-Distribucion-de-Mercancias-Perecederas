"""Convierte el export T-SQL (SQL Server) de BDIADelivery a un script MySQL/MariaDB apto para Workbench.

Uso: python tools/convertir_sqlserver_a_mysql.py database/original/script_sqlserver.sql \n         database/01_crear_base_datos.sql
"""
import re, struct, sys

src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-16").read()

ORDER = ["Provincias", "Clientes", "Productos", "Destinos", "Pedidos", "LineasPedido"]
rows = {t: [] for t in ORDER}
cols = {}
ins_re = re.compile(r"^INSERT \[dbo\]\.\[(\w+)\] \(([^)]*)\) VALUES \((.*)\)\s*$")
mismatch = 0

def conv_values(table, v):
    global mismatch
    # CAST(N'2026-..T..' AS DateTime) -> '2026-.. ..'
    v = re.sub(r"CAST\(N'(\d{4}-\d\d-\d\d)T([\d:.]+)' AS DateTime\)", r"'\1 \2'", v)
    # CAST(12.3 AS Decimal(10, 2)) -> 12.3
    v = re.sub(r"CAST\((-?[\d.]+) AS Decimal\(\d+, \d+\)\)", r"\1", v)
    # N'texto' -> 'texto'
    v = re.sub(r"(?<![\w'])N'", "'", v)
    if table == "Destinos":
        m = re.search(r"0x([0-9A-F]+)$", v)
        b = bytes.fromhex(m.group(1))
        srid = struct.unpack("<i", b[0:4])[0]
        lat, lon = struct.unpack("<dd", b[6:22])  # SQL Server geography point: lat, long
        assert srid == 4326
        parts = v.split(", ")
        if abs(float(parts[-3]) - lat) > 1e-6 or abs(float(parts[-2]) - lon) > 1e-6:
            mismatch += 1
        v = v[: m.start()] + f"POINT({lon!r}, {lat!r})"
    return v

for line in text.splitlines():
    m = ins_re.match(line)
    if not m:
        continue
    t = m.group(1)
    cols[t] = m.group(2).replace("[", "`").replace("]", "`")
    rows[t].append(conv_values(t, m.group(3)))

DDL = """-- =====================================================================
-- BDIADelivery - Proyecto 1 (IA DELIVERY SL)
-- Script convertido de SQL Server (T-SQL) a MySQL / MariaDB para MySQL Workbench
-- Compatible con MySQL 5.7+, MySQL 8 y MariaDB 10.2+
-- Ejecutar completo con el rayo (Execute) en una pestaña de consulta.
-- =====================================================================

SET NAMES utf8mb4;
SET @OLD_FOREIGN_KEY_CHECKS = @@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS = 0;
SET @OLD_UNIQUE_CHECKS = @@UNIQUE_CHECKS, UNIQUE_CHECKS = 0;
SET @OLD_SQL_MODE = @@SQL_MODE, SQL_MODE = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

DROP DATABASE IF EXISTS `BDIADelivery`;
CREATE DATABASE `BDIADelivery` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `BDIADelivery`;

-- ---------------------------------------------------------------------
-- Tablas
-- ---------------------------------------------------------------------
CREATE TABLE `Provincias` (
  `IdProvincia` INT NOT NULL AUTO_INCREMENT,
  `Nombre`      VARCHAR(150) NOT NULL,
  PRIMARY KEY (`IdProvincia`)
) ENGINE = InnoDB;

CREATE TABLE `Clientes` (
  `IdCliente` INT NOT NULL AUTO_INCREMENT,
  `Nombre`    VARCHAR(150) NOT NULL,
  `CIF`       VARCHAR(20)  NULL,
  `Telefono`  VARCHAR(20)  NULL,
  `Email`     VARCHAR(150) NULL,
  PRIMARY KEY (`IdCliente`),
  UNIQUE KEY `UQ_Clientes_CIF` (`CIF`)
) ENGINE = InnoDB;

CREATE TABLE `Productos` (
  `IdProducto`                 INT NOT NULL AUTO_INCREMENT,
  `Nombre`                     VARCHAR(150)  NOT NULL,
  `PrecioVenta`                DECIMAL(10,2) NOT NULL,
  `TiempoFabricacionMedioDias` INT NOT NULL,
  `CaducidadDias`              INT NOT NULL,
  PRIMARY KEY (`IdProducto`),
  CONSTRAINT `CK_Productos_Caducidad`   CHECK (`CaducidadDias` > 0),
  CONSTRAINT `CK_Productos_Fabricacion` CHECK (`TiempoFabricacionMedioDias` >= 0)
) ENGINE = InnoDB;

CREATE TABLE `Destinos` (
  `IdDestino`    INT NOT NULL AUTO_INCREMENT,
  `Direccion`    VARCHAR(200) NOT NULL,
  `Ciudad`       VARCHAR(100) NOT NULL,
  `IdProvincia`  INT NULL,
  `Pais`         VARCHAR(50)  NOT NULL,
  `CodigoPostal` VARCHAR(10)  NULL,
  `Latitud`      DECIMAL(10,7) NULL,
  `Longitud`     DECIMAL(10,7) NULL,
  `Coordenadas`  POINT NOT NULL,   -- equivalente al geography de SQL Server: POINT(x = longitud, y = latitud)
  PRIMARY KEY (`IdDestino`),
  KEY `IX_Destinos_Provincia` (`IdProvincia`),
  CONSTRAINT `FK_Destinos_Provincias` FOREIGN KEY (`IdProvincia`)
    REFERENCES `Provincias` (`IdProvincia`)
) ENGINE = InnoDB;

CREATE TABLE `Pedidos` (
  `IdPedido`    BIGINT NOT NULL AUTO_INCREMENT,
  `FechaPedido` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `IdCliente`   INT NOT NULL,
  `IdDestino`   INT NOT NULL,
  PRIMARY KEY (`IdPedido`),
  KEY `IX_Pedidos_Cliente` (`IdCliente`),
  KEY `IX_Pedidos_Destino` (`IdDestino`),
  CONSTRAINT `FK_Pedidos_Clientes` FOREIGN KEY (`IdCliente`) REFERENCES `Clientes` (`IdCliente`),
  CONSTRAINT `FK_Pedidos_Destinos` FOREIGN KEY (`IdDestino`) REFERENCES `Destinos` (`IdDestino`)
) ENGINE = InnoDB;

CREATE TABLE `LineasPedido` (
  `IdPedido`    BIGINT   NOT NULL,
  `NumeroLinea` SMALLINT NOT NULL,
  `IdProducto`  INT      NOT NULL,
  `Cantidad`    SMALLINT NOT NULL,
  PRIMARY KEY (`IdPedido`, `NumeroLinea`),
  KEY `IX_LineasPedido_Producto` (`IdProducto`),
  CONSTRAINT `FK_LineasPedido_Pedido`   FOREIGN KEY (`IdPedido`)   REFERENCES `Pedidos` (`IdPedido`),
  CONSTRAINT `FK_LineasPedido_Producto` FOREIGN KEY (`IdProducto`) REFERENCES `Productos` (`IdProducto`),
  CONSTRAINT `CK_LineasPedido_Cantidad` CHECK (`Cantidad` BETWEEN 1 AND 500)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Datos
-- ---------------------------------------------------------------------
"""

FOOTER = """
-- ---------------------------------------------------------------------
SET FOREIGN_KEY_CHECKS = @OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS = @OLD_UNIQUE_CHECKS;
SET SQL_MODE = @OLD_SQL_MODE;

-- AVISO: en el script original de SQL Server el punto `Coordenadas` (geography)
-- NO coincide con las columnas Latitud/Longitud (son valores aleatorios distintos).
-- Se han conservado tal cual. Si se quiere que Coordenadas use Latitud/Longitud,
-- descomentar y ejecutar:
-- SET SQL_SAFE_UPDATES = 0;
-- UPDATE Destinos
--    SET Coordenadas = POINT(Longitud, Latitud)
--  WHERE Latitud IS NOT NULL AND Longitud IS NOT NULL;
-- SET SQL_SAFE_UPDATES = 1;

-- Comprobación rápida
SELECT 'Provincias' AS tabla, COUNT(*) AS filas FROM Provincias
UNION ALL SELECT 'Clientes', COUNT(*) FROM Clientes
UNION ALL SELECT 'Productos', COUNT(*) FROM Productos
UNION ALL SELECT 'Destinos', COUNT(*) FROM Destinos
UNION ALL SELECT 'Pedidos', COUNT(*) FROM Pedidos
UNION ALL SELECT 'LineasPedido', COUNT(*) FROM LineasPedido;
"""

BATCH = 1000
with open(dst, "w", encoding="utf-8", newline="\n") as f:
    f.write(DDL)
    for t in ORDER:
        r = rows[t]
        f.write(f"\n-- {t}: {len(r)} filas\n")
        for i in range(0, len(r), BATCH):
            chunk = r[i : i + BATCH]
            f.write(f"INSERT INTO `{t}` ({cols[t]}) VALUES\n")
            f.write(",\n".join(f"({v})" for v in chunk))
            f.write(";\n")
        f.write("COMMIT;\n")
    f.write(FOOTER)

print({t: len(rows[t]) for t in ORDER}, "geo mismatches:", mismatch)
