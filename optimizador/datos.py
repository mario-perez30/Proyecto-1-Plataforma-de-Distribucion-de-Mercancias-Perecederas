"""Carga de un escenario desde la base de datos BDIADelivery.

La conexión se configura con variables de entorno (valores por defecto para el
MySQL de XAMPP en local):
    BDIA_HOST (127.0.0.1)  BDIA_PORT (3306)  BDIA_USER (root)
    BDIA_PASSWORD (vacía)  BDIA_DB (BDIADelivery)
"""

from __future__ import annotations

import os
from datetime import datetime, time, timedelta

import pymysql

from .modelo import Almacen, Escenario, Parametros, Pedido, TarifaExterna, TipoVehiculo


def conectar():
    """Abre una conexión a la BD con los datos de las variables de entorno."""
    return pymysql.connect(
        host=os.getenv("BDIA_HOST", "127.0.0.1"),
        port=int(os.getenv("BDIA_PORT", "3306")),
        user=os.getenv("BDIA_USER", "root"),
        password=os.getenv("BDIA_PASSWORD", ""),
        database=os.getenv("BDIA_DB", "BDIADelivery"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def _a_hora(valor) -> time:
    """MySQL devuelve las columnas TIME como timedelta."""
    if isinstance(valor, timedelta):
        return (datetime.min + valor).time()
    return valor


def cargar_parametros(cur) -> Parametros:
    cur.execute("SELECT Clave, Valor FROM ParametrosSistema")
    v = {r["Clave"]: float(r["Valor"]) for r in cur.fetchall()}
    return Parametros(
        factor_carretera=v.get("FactorRutaCarretera", 1.25),
        coste_conductor_h=v.get("CosteConductorHora", 22.0),
        dieta_dia=v.get("DietaDiariaConductor", 55.0),
        pernocta=v.get("PernoctaConductor", 45.0),
        conduccion_max_diaria_h=v.get("ConduccionMaxDiariaH", 9.0),
        conduccion_continua_max_h=v.get("ConduccionContinuaMaxH", 4.5),
        pausa_h=v.get("PausaObligatoriaMin", 45.0) / 60,
        descanso_diario_h=v.get("DescansoDiarioMinH", 11.0),
        carga_h=v.get("TiempoCargaAlmacenMin", 60.0) / 60,
    )


def listar_tipos_vehiculo(cur) -> list[dict]:
    cur.execute("SELECT IdTipoVehiculo, TipoVehiculo, CapacidadUnidades, CosteTotalKm "
                "FROM vw_CosteKmTipoVehiculo ORDER BY IdTipoVehiculo")
    return cur.fetchall()


def listar_escenarios(cur) -> list[dict]:
    cur.execute("SELECT e.IdEscenario, e.Nombre, e.Tipo, COUNT(p.IdPedido) AS Pedidos "
                "FROM Escenarios e LEFT JOIN Pedidos p ON p.IdEscenario = e.IdEscenario "
                "GROUP BY e.IdEscenario, e.Nombre, e.Tipo ORDER BY e.IdEscenario")
    return cur.fetchall()


def cargar_escenario(conn, id_escenario: int = 1, id_tipo_vehiculo: int = 1) -> Escenario:
    """Lee pedidos pendientes, almacén principal, tipo de camión, parámetros y tarifa externa."""
    with conn.cursor() as cur:
        params = cargar_parametros(cur)

        cur.execute("SELECT IdAlmacen, Nombre, Latitud, Longitud, HoraApertura FROM Almacenes WHERE EsPrincipal = 1")
        a = cur.fetchone()
        almacen = Almacen(a["IdAlmacen"], a["Nombre"], float(a["Latitud"]), float(a["Longitud"]))
        apertura = _a_hora(a["HoraApertura"])

        cur.execute(
            "SELECT k.*, t.PrecioAdquisicion FROM vw_CosteKmTipoVehiculo k "
            "JOIN TiposVehiculo t ON t.IdTipoVehiculo = k.IdTipoVehiculo "
            "WHERE k.IdAlmacen = %s AND k.IdTipoVehiculo = %s", (almacen.id, id_tipo_vehiculo))
        t = cur.fetchone()
        if t is None:
            raise ValueError(f"No existe el tipo de vehículo {id_tipo_vehiculo}")
        tipo = TipoVehiculo(
            id=t["IdTipoVehiculo"], nombre=t["TipoVehiculo"], capacidad=int(t["CapacidadUnidades"]),
            velocidad_kmh=float(t["VelocidadMediaKmh"]), litros_km=float(t["LitrosKm"]),
            kg_co2_km=float(t["KgCO2Km"]), coste_combustible_km=float(t["CosteCombustibleKm"]),
            coste_peaje_km=float(t["CostePeajeKm"]), coste_mantenimiento_km=float(t["CosteMantenimientoKm"]),
            coste_fijo_km=float(t["CosteFijoKm"]), precio_adquisicion=float(t["PrecioAdquisicion"]),
        )

        cur.execute(
            "SELECT p.IdPedido, p.IdDestino, p.UnidadesTotales, p.FechaListoEnvio, p.FechaCaducidad, "
            "       p.FechaLimiteEntrega, d.Latitud, d.Longitud, d.TiempoDescargaMin, d.IdPais "
            "FROM Pedidos p JOIN Destinos d ON d.IdDestino = p.IdDestino "
            "WHERE p.IdEscenario = %s AND p.Estado = 'Pendiente' ORDER BY p.IdPedido", (id_escenario,))
        filas = cur.fetchall()
        if any(f["FechaLimiteEntrega"] is None for f in filas):
            raise RuntimeError("Faltan las fechas de caducidad: ejecuta database/04_fechas_caducidad.sql")
        pedidos = [
            Pedido(id=f["IdPedido"], id_destino=f["IdDestino"], lat=float(f["Latitud"]), lon=float(f["Longitud"]),
                   unidades=int(f["UnidadesTotales"]),
                   listo=datetime.combine(f["FechaListoEnvio"], apertura),
                   limite=f["FechaLimiteEntrega"], caducidad=f["FechaCaducidad"],
                   descarga_h=int(f["TiempoDescargaMin"]) / 60, pais=f["IdPais"])
            for f in filas
        ]

        cur.execute("SELECT CosteFijoEnvio, CosteKm, CosteUnidad FROM TarifasExternalizacion "
                    "WHERE Activa = 1 ORDER BY FechaDesde DESC LIMIT 1")
        r = cur.fetchone()
        tarifa = TarifaExterna(float(r["CosteFijoEnvio"]), float(r["CosteKm"]), float(r["CosteUnidad"])) if r else None

    return Escenario(id=id_escenario, almacen=almacen, pedidos=pedidos, tipo=tipo, params=params, tarifa=tarifa)
